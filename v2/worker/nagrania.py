"""Encrypted local chunks for a single, explicitly armed recording."""
import json
import os
from contextlib import closing
from datetime import datetime, timedelta, timezone
from io import BytesIO
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from .ustalenia import propozycje
from .vault import valid_case

LIMIT = 8 * 1024 * 1024
FORMATS = {"video/webm": "webm", "video/mp4": "mp4", "audio/webm": "webm", "audio/mp4": "m4a", "audio/ogg": "ogg"}


class Start(BaseModel):
    sprawa: str = Field(min_length=1, max_length=120, pattern=r"\S")
    format: str
    sprawa_id: str | None = None
    stanowisko: str | None = None


class Koniec(BaseModel):
    czesci: int = Field(ge=1, le=10000, strict=True)


def router_nagran(vault, admin, auth, writable, see_case, transkrybuj):
    router = APIRouter(prefix="/v2/nagrania")
    with vault._tx() as db:
        db.execute("CREATE TABLE IF NOT EXISTS nagrania (id TEXT PRIMARY KEY, opis BLOB NOT NULL, gotowe INTEGER NOT NULL DEFAULT 0)")
        db.execute("CREATE TABLE IF NOT EXISTS nagrania_czesci (id TEXT, nr INTEGER, dane BLOB NOT NULL, PRIMARY KEY(id, nr))")

        db.execute("CREATE TABLE IF NOT EXISTS ustalenia_nagran (id TEXT PRIMARY KEY, dane BLOB NOT NULL)")

    def aad(id, nr):
        return f"notarai-v2:nagranie:{id}:{nr}".encode()

    def szyfruj(db, id, nr, dane):
        nonce = os.urandom(12)
        return nonce + vault._dek(db, id).encrypt(nonce, dane, aad(id, nr))

    def odszyfruj(db, id, nr, dane):
        return vault._dek(db, id).decrypt(dane[:12], dane[12:], aad(id, nr))

    def nagranie(db, id):
        wynik = db.execute("SELECT opis, gotowe FROM nagrania WHERE id=?", (id,)).fetchone()
        if wynik is None:
            raise HTTPException(404, "Nie znaleziono nagrania")
        return wynik

    @router.put("/{id}", dependencies=[Depends(admin)])
    def rozpocznij(id: UUID, dane: Start):
        if not valid_case(dane.sprawa_id) or dane.stanowisko not in {None, "gabinet", "sekretariat"}:
            raise HTTPException(422, "Nieprawidłowa sprawa lub stanowisko")
        if dane.format not in FORMATS:
            raise HTTPException(422, "Nieobsługiwany format")
        id = str(id)
        with vault._tx() as db:
            vault._dek(db, id, create=True)
            db.execute("INSERT OR IGNORE INTO nagrania (id, opis) VALUES (?, ?)", (id, szyfruj(db, id, "opis", json.dumps({
                **dane.model_dump(), "start": datetime.now(timezone.utc).isoformat(timespec="seconds")
            }).encode())))
            zapis, _ = nagranie(db, id)
            poprzedni = json.loads(odszyfruj(db, id, "opis", zapis))
            poprzedni.pop("start", None)
            if Start.model_validate(poprzedni) != dane:
                raise HTTPException(409, "Metadane nagrania zostały już zapisane")
        return {"id": id}

    @router.put("/{id}/czesci/{nr}", dependencies=[Depends(admin)])
    async def zapisz_czesc(id: UUID, nr: int, request: Request):
        if not 0 <= nr < 10000:
            raise HTTPException(422, "Nieprawidłowy numer fragmentu")
        dane = bytearray()
        async for blok in request.stream():
            if len(dane) + len(blok) > LIMIT:
                raise HTTPException(413, "Fragment przekracza limit")
            dane.extend(blok)
        if not dane:
            raise HTTPException(422, "Pusty fragment")
        id = str(id)
        with vault._tx() as db:
            _, gotowe = nagranie(db, id)
            poprzedni = db.execute("SELECT dane FROM nagrania_czesci WHERE id=? AND nr=?", (id, nr)).fetchone()
            if poprzedni is not None:
                if odszyfruj(db, id, nr, poprzedni[0]) != dane:
                    raise HTTPException(409, "Fragment ma inną zawartość")
            elif gotowe:
                raise HTTPException(409, "Nagranie zakończone")
            else:
                db.execute("INSERT INTO nagrania_czesci VALUES (?, ?, ?)", (id, nr, szyfruj(db, id, nr, bytes(dane))))
        return {"nr": nr}

    @router.put("/{id}/koniec", dependencies=[Depends(admin)])
    def zakoncz(id: UUID, dane: Koniec):
        id = str(id)
        with vault._tx() as db:
            nagranie(db, id)
            liczba, ostatni = db.execute("SELECT count(*), max(nr) FROM nagrania_czesci WHERE id=?", (id,)).fetchone()
            if liczba != dane.czesci or ostatni != liczba - 1:
                raise HTTPException(409, "Brakuje fragmentów nagrania")
            db.execute("UPDATE nagrania SET gotowe=1 WHERE id=?", (id,))
        return {"id": id}

    @router.get("", dependencies=[Depends(admin)])
    def lista():
        with closing(vault.connect()) as db:
            return [{"id": id, "gotowe": bool(gotowe), **json.loads(odszyfruj(db, id, "opis", opis))}
                    for id, opis, gotowe in db.execute("SELECT id, opis, gotowe FROM nagrania ORDER BY rowid DESC")]

    @router.get("/{id}")
    def pobierz(id: UUID, identity=Depends(auth)):
        id = str(id)
        with closing(vault.connect()) as db:
            opis, gotowe = nagranie(db, id)
            liczba = db.execute("SELECT count(*) FROM nagrania_czesci WHERE id=?", (id,)).fetchone()[0]
            meta = json.loads(odszyfruj(db, id, "opis", opis))
            see_case(identity, meta.get("sprawa_id"))
            if not meta.get("sprawa_id") and identity.scope != "admin":
                raise HTTPException(404, "Nie znaleziono nagrania")
            if not gotowe:
                raise HTTPException(409, "Nagranie nie zostało zakończone")
            format = meta["format"]

        def fragmenty():
            for nr in range(liczba):
                with closing(vault.connect()) as db:
                    dane, = db.execute(
                        "SELECT dane FROM nagrania_czesci WHERE id=? AND nr=?", (id, nr)
                    ).fetchone()
                    fragment = odszyfruj(db, id, nr, dane)
                yield fragment

        return StreamingResponse(fragmenty(), media_type=format, headers={
            "Content-Disposition": f'attachment; filename="nagranie-{id}.{FORMATS[format]}"'
        })

    @router.post("/{id}/stenogram", dependencies=[Depends(admin)])
    def stenogram(id: UUID):
        id = str(id)
        with vault._ro() as db:
            zapis = db.execute("SELECT dane FROM ustalenia_nagran WHERE id=?", (id,)).fetchone()
            if zapis is not None:
                return json.loads(odszyfruj(db, id, "ustalenia", zapis[0]))
            opis, gotowe = nagranie(db, id)
            meta = json.loads(odszyfruj(db, id, "opis", opis))
            if not gotowe:
                raise HTTPException(409, "Nagranie nie zostało zakończone")
            rozmiar = db.execute("SELECT sum(length(dane)) FROM nagrania_czesci WHERE id=?", (id,)).fetchone()[0]
            if rozmiar > 256 * 1024 * 1024:
                raise HTTPException(413, "Nagranie przekracza limit lokalnej transkrypcji")
            audio = BytesIO()
            for nr, dane in db.execute("SELECT nr, dane FROM nagrania_czesci WHERE id=? ORDER BY nr", (id,)):
                audio.write(odszyfruj(db, id, nr, dane))
        with audio:
            audio.seek(0)
            try:
                segmenty = transkrybuj(audio)
                if isinstance(segmenty, str):
                    segmenty = [{"tekst": segmenty, "sekunda": 0}]
                tekst = " ".join(segment["tekst"] for segment in segmenty).strip()
            except Exception:
                raise HTTPException(409, "Lokalna transkrypcja się nie powiodła") from None
        if not tekst:
            raise HTTPException(409, "Nie rozpoznano mowy w nagraniu")
        with vault._tx() as db:
            zapis = db.execute("SELECT dane FROM ustalenia_nagran WHERE id=?", (id,)).fetchone()
            if zapis is None:
                plik = str(uuid4())
                vault._insert(db, plik, 1, f"stenogram-{id}.txt", tekst.encode("utf-8"), "local-admin", meta.get("sprawa_id"))
                vault._log(db, "local-admin", "write", plik, 1)
                dane = {"plik": plik, "tekst": tekst, "ustalenia": propozycje(segmenty)}
                db.execute("INSERT INTO ustalenia_nagran VALUES (?, ?)",
                           (id, szyfruj(db, id, "ustalenia", json.dumps(dane).encode())))
            else:
                dane = json.loads(odszyfruj(db, id, "ustalenia", zapis[0]))
        return dane

    def wpisy(db):
        for id, opis, dane in db.execute(
            "SELECT n.id, n.opis, u.dane FROM nagrania n JOIN ustalenia_nagran u ON n.id=u.id"
        ):
            yield id, json.loads(odszyfruj(db, id, "opis", opis)), json.loads(odszyfruj(db, id, "ustalenia", dane))

    @router.get("/kalendarz/wpisy")
    def kalendarz(identity=Depends(auth)):
        wynik = []
        with vault._ro() as db:
            for id, meta, dane in wpisy(db):
                sprawa = meta.get("sprawa_id")
                if identity.scope != "admin" and not sprawa:
                    continue
                if identity.cases is not None and sprawa not in identity.cases:
                    continue
                for nr, pozycja in enumerate(dane["ustalenia"]):
                    wynik.append({**pozycja, "id": id, "nr": nr, "sprawa": sprawa or meta["sprawa"],
                                  "start": meta.get("start"), "stanowisko": meta.get("stanowisko")})
        return sorted(wynik, key=lambda w: (w["termin"] is None, w["termin"] or w["start"] or ""))

    @router.post("/{id}/ustalenia/{nr}/zatwierdz")
    def zatwierdz(id: UUID, nr: int, identity=Depends(writable)):
        id = str(id)
        with vault._tx() as db:
            for klucz, meta, dane in wpisy(db):
                if klucz != id:
                    continue
                sprawa = meta.get("sprawa_id")
                see_case(identity, sprawa)
                if not sprawa and identity.scope != "admin":
                    break
                if not 0 <= nr < len(dane["ustalenia"]):
                    break
                pozycja = dane["ustalenia"][nr]
                if not pozycja["termin"]:
                    raise HTTPException(422, "Ustalenie nie ma terminu do zatwierdzenia")
                if pozycja.get("zatwierdzony"):
                    return pozycja
                poczatek = datetime.fromisoformat(pozycja["termin"])
                koniec = poczatek + timedelta(minutes=60)
                for _, _, inne in wpisy(db):
                    for wpis in inne["ustalenia"]:
                        if wpis.get("zatwierdzony"):
                            od = datetime.fromisoformat(wpis["termin"])
                            if od < koniec and poczatek < od + timedelta(minutes=60):
                                raise HTTPException(409, "Ten termin koliduje z zatwierdzonym spotkaniem.")
                pozycja["zatwierdzony"] = True
                db.execute("UPDATE ustalenia_nagran SET dane=? WHERE id=?",
                           (szyfruj(db, id, "ustalenia", json.dumps(dane).encode()), id))
                return pozycja
        raise HTTPException(404, "Nie znaleziono ustalenia")

    return router
