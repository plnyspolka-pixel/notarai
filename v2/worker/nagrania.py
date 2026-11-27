"""Encrypted local chunks for a single, explicitly armed recording."""
import json
import os
from contextlib import closing
from io import BytesIO
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

LIMIT = 8 * 1024 * 1024
FORMATS = {"video/webm": "webm", "video/mp4": "mp4", "audio/webm": "webm", "audio/mp4": "m4a", "audio/ogg": "ogg"}


class Start(BaseModel):
    sprawa: str = Field(min_length=1, max_length=120, pattern=r"\S")
    format: str


class Koniec(BaseModel):
    czesci: int = Field(ge=1, le=10000, strict=True)


def router_nagran(vault, admin, transkrybuj):
    router = APIRouter(prefix="/v2/nagrania", dependencies=[Depends(admin)])
    with vault._tx() as db:
        db.execute("CREATE TABLE IF NOT EXISTS nagrania (id TEXT PRIMARY KEY, opis BLOB NOT NULL, gotowe INTEGER NOT NULL DEFAULT 0)")
        db.execute("CREATE TABLE IF NOT EXISTS nagrania_czesci (id TEXT, nr INTEGER, dane BLOB NOT NULL, PRIMARY KEY(id, nr))")

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

    @router.put("/{id}")
    def rozpocznij(id: UUID, dane: Start):
        if dane.format not in FORMATS:
            raise HTTPException(422, "Nieobsługiwany format")
        id = str(id)
        opis = dane.model_dump_json().encode()
        with vault._tx() as db:
            vault._dek(db, id, create=True)
            db.execute("INSERT OR IGNORE INTO nagrania (id, opis) VALUES (?, ?)", (id, szyfruj(db, id, "opis", opis)))
            zapis, _ = nagranie(db, id)
            if odszyfruj(db, id, "opis", zapis) != opis:
                raise HTTPException(409, "Metadane nagrania zostały już zapisane")
        return {"id": id}

    @router.put("/{id}/czesci/{nr}")
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

    @router.put("/{id}/koniec")
    def zakoncz(id: UUID, dane: Koniec):
        id = str(id)
        with vault._tx() as db:
            nagranie(db, id)
            liczba, ostatni = db.execute("SELECT count(*), max(nr) FROM nagrania_czesci WHERE id=?", (id,)).fetchone()
            if liczba != dane.czesci or ostatni != liczba - 1:
                raise HTTPException(409, "Brakuje fragmentów nagrania")
            db.execute("UPDATE nagrania SET gotowe=1 WHERE id=?", (id,))
        return {"id": id}

    @router.get("")
    def lista():
        with closing(vault.connect()) as db:
            return [{"id": id, "gotowe": bool(gotowe), **json.loads(odszyfruj(db, id, "opis", opis))}
                    for id, opis, gotowe in db.execute("SELECT id, opis, gotowe FROM nagrania ORDER BY rowid DESC")]

    @router.get("/{id}")
    def pobierz(id: UUID):
        id = str(id)
        with closing(vault.connect()) as db:
            opis, gotowe = nagranie(db, id)
            liczba = db.execute("SELECT count(*) FROM nagrania_czesci WHERE id=?", (id,)).fetchone()[0]
            if not gotowe:
                raise HTTPException(409, "Nagranie nie zostało zakończone")
            format = json.loads(odszyfruj(db, id, "opis", opis))["format"]

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

    @router.post("/{id}/stenogram")
    def stenogram(id: UUID):
        id = str(id)
        with vault._ro() as db:
            _, gotowe = nagranie(db, id)
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
                tekst = transkrybuj(audio)
            except Exception:
                raise HTTPException(409, "Lokalna transkrypcja się nie powiodła") from None
        if not tekst:
            raise HTTPException(409, "Nie rozpoznano mowy w nagraniu")
        plik, _ = vault.put(None, 0, f"stenogram-{id}.txt", tekst.encode("utf-8"))
        return {"plik": plik, "tekst": tekst}

    return router
