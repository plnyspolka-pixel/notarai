"""B2B appointment booking: partner REST API and stateless MCP 2026-07-28.

External partners NEVER use the office Cognito token. They see only offices that
opted in, free slots and bookings created with their own partner ID. All changes
share the office's existing atomic calendar file (S3 conditional ETag writes).
"""
import hashlib
import json
import os
import re
import secrets
import threading
import uuid
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

import autoryzacja
import kalendarz
import magazyn

STREFA = ZoneInfo("Europe/Warsaw")
PLIK_USTAWIEN = "rezerwacje_hurtowe"
PROTOKOL_MCP = "2026-07-28"
_BLOKADA_PARTNEROW = threading.Lock()

router_biuro = APIRouter(prefix="/api/rezerwacje-hurtowe", tags=["rezerwacje kancelarii"])
router_partner = APIRouter(prefix="/api/hurtowe", tags=["rezerwacje B2B"])
router_admin = APIRouter(prefix="/api/admin/hurtowi", tags=["partnerzy B2B"])
router_mcp = APIRouter(tags=["MCP"])


class Polityka(BaseModel):
    wlaczone: bool = False
    # Te same godziny dla klientow ze strony notarai.pl (rezerwacje_klientow.py).
    klienci: bool = False
    miasto: str = Field(default="", max_length=100)
    adres: str = Field(default="", max_length=250)
    # 0 = poniedzialek, 6 = niedziela. Kazdy dzien: [poczatek, koniec].
    godziny: dict[str, list[str]] = Field(default_factory=dict)
    czas_minut: int = 60
    wyprzedzenie_godzin: int = 24
    max_dni: int = 60


class PartnerNowy(BaseModel):
    nazwa: str = Field(min_length=2, max_length=140)
    kancelarie: list[str] = Field(min_length=1, max_length=200)


class Wizyta(BaseModel):
    kancelaria: str = Field(min_length=1, max_length=100)
    data: str
    godzina: str
    rodzaj: str
    uczestnicy: str = Field(min_length=2, max_length=500)
    telefon: str = Field(default="", max_length=40)
    rodzaj_inny: str = Field(default="", max_length=200)
    zewnetrzne_id: str = Field(default="", max_length=100)
    idempotency_key: str = Field(min_length=12, max_length=120)
    potwierdzam: bool = False


class Przesuniecie(BaseModel):
    data: str
    godzina: str
    potwierdzam: bool = False


class Anulowanie(BaseModel):
    potwierdzam: bool = False


def _teraz() -> datetime:
    return datetime.now(STREFA)


def _minuty(tekst: str) -> int:
    if not re.fullmatch(r"(?:[01]\d|2[0-3]):(?:00|30)", tekst):
        raise HTTPException(400, "Godzina musi miec format HH:00 lub HH:30.")
    return int(tekst[:2]) * 60 + int(tekst[3:])


def _hhmm(minuty: int) -> str:
    return f"{minuty // 60:02d}:{minuty % 60:02d}"


def _data(tekst: str) -> date:
    try:
        return date.fromisoformat(tekst)
    except ValueError:
        raise HTTPException(400, "Data w formacie RRRR-MM-DD.")


def _polityka() -> dict:
    return magazyn.wczytaj_plik_kancelarii(PLIK_USTAWIEN, Polityka().model_dump())


def _popraw_polityke(dane: Polityka) -> dict:
    if dane.czas_minut not in (30, 60, 90, 120):
        raise HTTPException(400, "Czas spotkania: 30, 60, 90 lub 120 minut.")
    if not 1 <= dane.wyprzedzenie_godzin <= 168 or not 1 <= dane.max_dni <= 90:
        raise HTTPException(400, "Wyprzedzenie: 1-168 godzin; horyzont: 1-90 dni.")
    if (dane.wlaczone or dane.klienci) and (not dane.miasto.strip() or not dane.adres.strip() or not dane.godziny):
        raise HTTPException(400, "Aby wlaczyc rezerwacje, podaj miasto, adres i godziny.")
    for dzien, przedzial in dane.godziny.items():
        if dzien not in tuple(str(i) for i in range(7)) or len(przedzial) != 2:
            raise HTTPException(400, "Godziny: klucz dnia 0-6 oraz [od, do].")
        start, koniec = map(_minuty, przedzial)
        if start >= koniec or koniec - start < dane.czas_minut:
            raise HTTPException(400, "Nieprawidlowy przedzial dostepnosci.")
    return {**dane.model_dump(), "miasto": dane.miasto.strip(), "adres": dane.adres.strip()}


def _biuro_wlasciciel(request: Request):
    # Only a named owner of this office, never a service administrator or helper.
    if not autoryzacja.MULTI or getattr(request.state, "serwis", False):
        raise HTTPException(403, "Ustawienia wymagaja logowania wlasciciela kancelarii w SaaS.")
    _, _, wpis, email = autoryzacja._moja_kancelaria(request)
    autoryzacja._wymagaj_wlasciciela(wpis, email)
    if wpis.get("przechowywanie") == "u-klienta":
        raise HTTPException(409, "Kancelaria przechowuje dane lokalnie.")
    return wpis


@router_biuro.get("/ustawienia")
def ustawienia(request: Request):
    _biuro_wlasciciel(request)
    return _polityka()


@router_biuro.put("/ustawienia")
def ustaw_ustawienia(request: Request, dane: Polityka):
    _biuro_wlasciciel(request)
    p = _popraw_polityke(dane)

    def zmiana(aktualne):
        aktualne.clear()
        aktualne.update(p)
        return dict(aktualne)

    return magazyn.zmien_plik_kancelarii(PLIK_USTAWIEN, zmiana, {})


def _partnerzy() -> list[dict]:
    """No cache: revoked keys stop working on the next request."""
    if magazyn.TRYB != "s3":
        import config
        sciezka = config.DANE / "hurtowi.json"
        return json.loads(sciezka.read_text("utf-8")) if sciezka.exists() else []
    key = f"{magazyn.PREFIKS}/admin/hurtowi.json"
    try:
        obj = magazyn._klient_s3().get_object(Bucket=magazyn.BUCKET, Key=key)
    except Exception as exc:
        if magazyn._kod_bledu(exc) in ("NoSuchKey", "404"):
            return []
        raise
    return json.loads(obj["Body"].read().decode("utf-8"))


def _mutuj_partnerow(funkcja):
    """Atomic read/modify/write, also across several App Runner instances."""
    if magazyn.TRYB != "s3":
        import config
        sciezka = config.DANE / "hurtowi.json"
        with _BLOKADA_PARTNEROW:
            sciezka.parent.mkdir(parents=True, exist_ok=True)
            dane = _partnerzy()
            wynik = funkcja(dane)
            tmp = sciezka.with_suffix(".tmp")
            tmp.write_text(json.dumps(dane, ensure_ascii=False), "utf-8")
            tmp.replace(sciezka)
            return wynik
    key = f"{magazyn.PREFIKS}/admin/hurtowi.json"
    for _ in range(5):
        try:
            obj = magazyn._klient_s3().get_object(Bucket=magazyn.BUCKET, Key=key)
            dane = json.loads(obj["Body"].read().decode("utf-8"))
            warunek = {"IfMatch": obj["ETag"]}
        except Exception as exc:
            if magazyn._kod_bledu(exc) not in ("NoSuchKey", "404"):
                raise
            dane, warunek = [], {"IfNoneMatch": "*"}
        wynik = funkcja(dane)
        try:
            magazyn._klient_s3().put_object(
                Bucket=magazyn.BUCKET, Key=key,
                Body=json.dumps(dane, ensure_ascii=False).encode("utf-8"),
                **warunek, **magazyn._szyfrowanie(),
            )
            return wynik
        except Exception as exc:
            if magazyn._kod_bledu(exc) not in ("PreconditionFailed", "ConditionalRequestConflict", "412", "409"):
                raise
    raise HTTPException(409, "Rownoczesna zmiana partnerow, ponow probe.")


@router_admin.get("")
def lista_partnerow(request: Request):
    autoryzacja._wymagaj_admina(request)
    return [{k: v for k, v in p.items() if k != "hash"} for p in _partnerzy()]


@router_admin.post("", status_code=201)
def dodaj_partnera(request: Request, dane: PartnerNowy):
    autoryzacja._wymagaj_admina(request)
    biura = {x["id"] for x in autoryzacja._wczytaj_rejestr().values()}
    ids = sorted(set(dane.kancelarie))
    if any(x not in biura for x in ids):
        raise HTTPException(400, "Nieznany identyfikator kancelarii.")
    token = "nth_" + secrets.token_urlsafe(40)
    w = {"id": uuid.uuid4().hex[:16], "nazwa": dane.nazwa.strip(), "kancelarie": ids,
         "aktywny": True, "hash": hashlib.sha256(token.encode()).hexdigest(),
         "utworzono": datetime.now(timezone.utc).isoformat()}
    _mutuj_partnerow(lambda lista: lista.append(w))
    return {"id": w["id"], "nazwa": w["nazwa"], "kancelarie": ids,
            "api_key": token, "uwaga": "Klucz jest pokazywany tylko raz."}


@router_admin.delete("/{partner_id}")
def zablokuj_partnera(request: Request, partner_id: str):
    autoryzacja._wymagaj_admina(request)

    def zmiana(lista):
        for p in lista:
            if p["id"] == partner_id:
                p["aktywny"] = False
                return {"zablokowano": partner_id}
        raise HTTPException(404, "Nie ma takiego partnera.")
    return _mutuj_partnerow(zmiana)


def _wymagaj_partnera(request: Request) -> dict:
    naglowek = request.headers.get("authorization", "")
    token = naglowek[7:] if naglowek.startswith("Bearer ") else ""
    if not token.startswith("nth_") or len(token) < 32:
        raise HTTPException(401, "Wymagany klucz API partnera.")
    digest = hashlib.sha256(token.encode()).hexdigest()
    for p in _partnerzy():
        if p.get("aktywny") and secrets.compare_digest(digest, p["hash"]):
            return p
    raise HTTPException(401, "Klucz API jest nieprawidlowy lub zablokowany.")


def _kancelaria(partner: dict, id_k: str) -> dict:
    if id_k not in partner["kancelarie"]:
        raise HTTPException(404, "Kancelaria niedostepna dla tego partnera.")
    _, biuro = autoryzacja._znajdz(autoryzacja._wczytaj_rejestr(), id_k)
    if (not biuro or not biuro.get("aktywna", True) or
            biuro.get("przechowywanie", "chmura") == "u-klienta" or
            not autoryzacja._oplacona(id_k) or not autoryzacja.umowa_zawarta(id_k)):
        raise HTTPException(404, "Kancelaria niedostepna.")
    return biuro


class _WBiurze:
    """Temporary tenant scope, never lets one partner read another office's case."""
    def __init__(self, id_k: str):
        self.id_k = id_k

    def __enter__(self):
        self.k = magazyn.kancelaria_var.set(self.id_k)
        self.p = magazyn.przechowywanie_var.set("chmura")
        return self

    def __exit__(self, *_):
        magazyn.przechowywanie_var.reset(self.p)
        magazyn.kancelaria_var.reset(self.k)


def _dostepne(wpisy: list[dict], p: dict, dzien: str) -> list[dict]:
    d = _data(dzien)
    teraz = _teraz()
    if d < teraz.date() or d > teraz.date() + timedelta(days=p["max_dni"]):
        return []
    godziny = p["godziny"].get(str(d.weekday()))
    if not godziny:
        return []
    od, do = map(_minuty, godziny)
    wynik = []
    for m in range(od, do - p["czas_minut"] + 1, 30):
        poczatek = datetime.combine(d, time(m // 60, m % 60), tzinfo=STREFA)
        if poczatek < teraz + timedelta(hours=p["wyprzedzenie_godzin"]):
            continue
        start, koniec = _hhmm(m), _hhmm(m + p["czas_minut"])
        if any(w["data"] == dzien and w.get("godzina") and
               w.get("status") != "anulowana" and
               w["godzina"] < koniec and start < kalendarz._koniec(w) for w in wpisy):
            continue
        wynik.append({"data": dzien, "godzina": start, "koniec": koniec})
    return wynik


def _kontekst(partner: dict, id_k: str):
    biuro = _kancelaria(partner, id_k)
    return biuro


def _wolne(partner: dict, id_k: str, dzien: str) -> dict:
    _kontekst(partner, id_k)
    with _WBiurze(id_k):
        p = _polityka()
        if not p.get("wlaczone"):
            raise HTTPException(404, "Kancelaria nie udostepnia terminow.")
        if kalendarz.dni().get(dzien, {}).get("nieczynne"):
            sloty = []
        else:
            sloty = _dostepne(kalendarz.lista(), p, dzien)
        return {"kancelaria": id_k, "data": dzien, "czas_minut": p["czas_minut"], "terminy": sloty}


@router_partner.get("/kancelarie")
def kancelarie(request: Request, miasto: str = ""):
    partner = _wymagaj_partnera(request)
    wynik = []
    for id_k in partner["kancelarie"]:
        try:
            biuro = _kancelaria(partner, id_k)
            with _WBiurze(id_k):
                p = _polityka()
            if p.get("wlaczone") and (not miasto or miasto.casefold() in p["miasto"].casefold()):
                wynik.append({"id": id_k, "nazwa": biuro["nazwa"], "miasto": p["miasto"],
                              "adres": p["adres"], "czas_minut": p["czas_minut"]})
        except HTTPException:
            continue
    return wynik


@router_partner.get("/dostepnosc")
def dostepnosc(request: Request, kancelaria: str, data: str):
    partner = _wymagaj_partnera(request)
    return _wolne(partner, kancelaria, data)


def _publiczny(w: dict, id_k: str) -> dict:
    return {k: w.get(k) for k in ("id", "data", "godzina", "koniec", "rodzaj",
                                  "uczestnicy", "telefony", "zewnetrzne_id", "status", "utworzono")} | {
        "kancelaria": id_k}


def _wymagaj_potwierdzenia(tak: bool):
    if not tak:
        raise HTTPException(400, "Do zmiany kalendarza wymagane potwierdzam=true.")


def _zapisz_kalendarz(zmiana):
    try:
        return magazyn.zmien_plik_kancelarii("kalendarz", zmiana, [])
    except magazyn.KonfliktZapisu as exc:
        raise HTTPException(409, str(exc))
    except ValueError as exc:
        raise HTTPException(400, str(exc))


def _rezerwuj(partner: dict, dane: Wizyta) -> dict:
    _wymagaj_potwierdzenia(dane.potwierdzam)
    _kontekst(partner, dane.kancelaria)
    if dane.rodzaj not in kalendarz.RODZAJE:
        raise HTTPException(400, "Nieznany rodzaj czynnosci.")
    with _WBiurze(dane.kancelaria):
        p = _polityka()
        if not p.get("wlaczone"):
            raise HTTPException(404, "Kancelaria nie przyjmuje rezerwacji B2B.")
        if kalendarz.dni().get(dane.data, {}).get("nieczynne"):
            raise HTTPException(409, "Kancelaria jest tego dnia nieczynna.")
        # Compare idempotency for identical payloads only; never leak another partner's booking.
        fingerprint = hashlib.sha256(json.dumps(
            dane.model_dump(exclude={"potwierdzam", "idempotency_key"}), sort_keys=True,
            ensure_ascii=False).encode("utf-8")).hexdigest()

        def zmiana(wpisy):
            for w in wpisy:
                if (w.get("zrodlo") == "hurtowe" and w.get("partner_id") == partner["id"] and
                        w.get("idempotency_key") == dane.idempotency_key):
                    if w.get("fingerprint") != fingerprint:
                        raise HTTPException(409, "Klucz idempotencji zostal juz uzyty dla innej rezerwacji.")
                    return _publiczny(w, dane.kancelaria)
            if dane.godzina not in {s["godzina"] for s in _dostepne(wpisy, p, dane.data)}:
                raise HTTPException(409, "Wybrany termin nie jest juz dostepny.")
            m = _minuty(dane.godzina)
            nowy = kalendarz._sprawdz({
                "data": dane.data, "godzina": dane.godzina, "koniec": _hhmm(m + p["czas_minut"]),
                "rodzaj": dane.rodzaj, "rodzaj_inny": dane.rodzaj_inny,
                "uczestnicy": dane.uczestnicy,
                "telefony": [{"imie": "", "numer": dane.telefon}] if dane.telefon else [],
            })
            wpis = {"id": uuid.uuid4().hex[:12], **nowy, "zrodlo": "hurtowe",
                    "partner_id": partner["id"], "zewnetrzne_id": dane.zewnetrzne_id,
                    "idempotency_key": dane.idempotency_key, "fingerprint": fingerprint,
                    "status": "potwierdzona",
                    "utworzono": datetime.now(timezone.utc).isoformat()}
            kalendarz._sprawdz_kolizje(wpisy, wpis)
            wpisy.append(wpis)
            return _publiczny(wpis, dane.kancelaria)
        return _zapisz_kalendarz(zmiana)


@router_partner.post("/rezerwacje", status_code=201)
def rezerwuj(request: Request, dane: Wizyta):
    return _rezerwuj(_wymagaj_partnera(request), dane)


def _zmien(partner: dict, id_k: str, id_w: str, aktualizacja: Przesuniecie | None) -> dict:
    _kontekst(partner, id_k)
    with _WBiurze(id_k):
        p = _polityka()
        if aktualizacja and (not p.get("wlaczone") or
                             kalendarz.dni().get(aktualizacja.data, {}).get("nieczynne")):
            raise HTTPException(409, "Kancelaria nie przyjmuje rezerwacji w tym terminie.")

        def zmiana(wpisy):
            w = next((x for x in wpisy if x["id"] == id_w and x.get("zrodlo") == "hurtowe" and
                      x.get("partner_id") == partner["id"]), None)
            if not w:
                raise HTTPException(404, "Nie znaleziono rezerwacji partnera.")
            if w.get("status") == "anulowana":
                if aktualizacja:
                    raise HTTPException(409, "Nie mozna przeniesc anulowanej rezerwacji.")
                return _publiczny(w, id_k)
            if aktualizacja:
                if aktualizacja.godzina not in {s["godzina"] for s in _dostepne(
                        [x for x in wpisy if x["id"] != id_w], p, aktualizacja.data)}:
                    raise HTTPException(409, "Nowy termin jest niedostepny.")
                m = _minuty(aktualizacja.godzina)
                w.update(data=aktualizacja.data, godzina=aktualizacja.godzina,
                         koniec=_hhmm(m + p["czas_minut"]))
                kalendarz._sprawdz_kolizje(wpisy, w, pomin=id_w)
            else:
                w["status"] = "anulowana"
                w["anulowano"] = datetime.now(timezone.utc).isoformat()
            return _publiczny(w, id_k)
        return _zapisz_kalendarz(zmiana)


@router_partner.put("/rezerwacje/{id_w}")
def przesun(request: Request, id_w: str, kancelaria: str, dane: Przesuniecie):
    _wymagaj_potwierdzenia(dane.potwierdzam)
    return _zmien(_wymagaj_partnera(request), kancelaria, id_w, dane)


@router_partner.post("/rezerwacje/{id_w}/anuluj")
def anuluj(request: Request, id_w: str, kancelaria: str, dane: Anulowanie):
    _wymagaj_potwierdzenia(dane.potwierdzam)
    return _zmien(_wymagaj_partnera(request), kancelaria, id_w, None)


@router_partner.get("/rezerwacje")
def moje_rezerwacje(request: Request, kancelaria: str):
    partner = _wymagaj_partnera(request)
    _kontekst(partner, kancelaria)
    with _WBiurze(kancelaria):
        wpisy = magazyn.wczytaj_plik_kancelarii("kalendarz", [])
    return [_publiczny(w, kancelaria) for w in wpisy
            if w.get("zrodlo") == "hurtowe" and w.get("partner_id") == partner["id"]]


# Office staff may inspect partner-origin bookings through the regular calendar;
# canceled entries are retained for audit but hidden by kalendarz.lista().


# MCP (current stateless Streamable HTTP, 2026-07-28).
# Explicit JSON-RPC implementation avoids a second session manager/lifespan.
_NARZEDZIA = [
    ("kancelarie", "Lista kancelarii, ktore zgodzily sie na rezerwacje hurtowe.",
     {"miasto": {"type": "string"}}, []),
    ("wolne_terminy", "Wolne godziny w kancelarii na wskazany dzien.",
     {"kancelaria": {"type": "string"}, "data": {"type": "string"}}, ["kancelaria", "data"]),
    ("zarezerwuj_spotkanie", "Tworzy potwierdzona rezerwacje. Wymaga potwierdzenia klienta.",
     Wizyta.model_json_schema().get("properties", {}),
     ["kancelaria", "data", "godzina", "rodzaj", "uczestnicy", "idempotency_key", "potwierdzam"]),
    ("przeloz_spotkanie", "Przenosi wlasna rezerwacje na inny termin.",
     {"kancelaria": {"type": "string"}, "id": {"type": "string"}, "data": {"type": "string"},
      "godzina": {"type": "string"}, "potwierdzam": {"type": "boolean"}}, ["kancelaria", "id", "data", "godzina", "potwierdzam"]),
    ("anuluj_spotkanie", "Anuluje wlasna rezerwacje i zwalnia godzine.",
     {"kancelaria": {"type": "string"}, "id": {"type": "string"}, "potwierdzam": {"type": "boolean"}},
     ["kancelaria", "id", "potwierdzam"]),
    ("moje_rezerwacje", "Wlasne rezerwacje partnera w wybranej kancelarii.",
     {"kancelaria": {"type": "string"}}, ["kancelaria"]),
]
TOOLS = [{"name": name, "description": opis,
          "inputSchema": {"type": "object", "properties": pola,
                          "required": wymagane, "additionalProperties": False}}
         for name, opis, pola, wymagane in _NARZEDZIA]
_INFO = {"io.modelcontextprotocol/serverInfo": {"name": "notarai-rezerwacje", "version": "1.0.0"}}


def _wywolaj(nazwa: str, args: dict, partner: dict):
    if nazwa == "kancelarie":
        # Same logic as REST, no artificial fake Request.
        wynik = []
        for id_k in partner["kancelarie"]:
            try:
                biuro = _kancelaria(partner, id_k)
                with _WBiurze(id_k):
                    p = _polityka()
                if p.get("wlaczone") and args.get("miasto", "").casefold() in p["miasto"].casefold():
                    wynik.append({"id": id_k, "nazwa": biuro["nazwa"], "miasto": p["miasto"],
                                  "adres": p["adres"], "czas_minut": p["czas_minut"]})
            except HTTPException:
                pass
        return wynik
    if nazwa == "wolne_terminy":
        return _wolne(partner, args["kancelaria"], args["data"])
    if nazwa == "zarezerwuj_spotkanie":
        return _rezerwuj(partner, Wizyta(**args))
    if nazwa == "przeloz_spotkanie":
        _wymagaj_potwierdzenia(args["potwierdzam"])
        return _zmien(partner, args["kancelaria"], args["id"],
                      Przesuniecie(**{k: args[k] for k in ("data", "godzina", "potwierdzam")}))
    if nazwa == "anuluj_spotkanie":
        _wymagaj_potwierdzenia(args["potwierdzam"])
        return _zmien(partner, args["kancelaria"], args["id"], None)
    if nazwa == "moje_rezerwacje":
        id_k = args["kancelaria"]
        _kontekst(partner, id_k)
        with _WBiurze(id_k):
            wpisy = magazyn.wczytaj_plik_kancelarii("kalendarz", [])
        return [_publiczny(w, id_k) for w in wpisy
                if w.get("zrodlo") == "hurtowe" and w.get("partner_id") == partner["id"]]
    raise HTTPException(404, "Nieznane narzedzie MCP.")


def _rpc_error(identyfikator, kod: int, opis: str, status: int = 400):
    return Response(content=json.dumps({"jsonrpc": "2.0", "id": identyfikator,
                                        "error": {"code": kod, "message": opis}},
                                       ensure_ascii=False),
                    status_code=status, media_type="application/json")


@router_mcp.post("/mcp")
async def mcp(request: Request):
    # Reject browser-origin requests unless explicitly allowlisted.
    origin = request.headers.get("origin")
    allowed = {x.strip() for x in os.getenv("PIECZAPP_MCP_ORIGINS", "").split(",") if x.strip()}
    if origin and origin not in allowed:
        raise HTTPException(403, "Origin nie jest dozwolony.")
    partner = _wymagaj_partnera(request)
    if request.headers.get("content-type", "").split(";")[0].strip() != "application/json":
        return _rpc_error(None, -32600, "Wymagany application/json.", 415)
    try:
        body = await request.json()
    except ValueError:
        return _rpc_error(None, -32700, "Niepoprawny JSON.")
    if not isinstance(body, dict) or body.get("jsonrpc") != "2.0" or not isinstance(body.get("method"), str):
        return _rpc_error(None, -32600, "Niepoprawne zapytanie JSON-RPC.")
    ident = body.get("id")
    method = body["method"]
    params = body.get("params", {})
    if not isinstance(params, dict):
        return _rpc_error(ident, -32602, "Niepoprawne parametry.")
    meta = params.get("_meta", {})
    if not isinstance(meta, dict):
        return _rpc_error(ident, -32602, "Niepoprawne metadane.")
    wersja = request.headers.get("mcp-protocol-version", "")
    if (wersja != PROTOKOL_MCP or meta.get("io.modelcontextprotocol/protocolVersion") != wersja):
        return _rpc_error(ident, -32600, "UnsupportedProtocolVersionError: 2026-07-28.", 400)
    if not isinstance(meta.get("io.modelcontextprotocol/clientCapabilities"), dict):
        return _rpc_error(ident, -32602, "Brak clientCapabilities.")
    if request.headers.get("mcp-method") != method:
        return _rpc_error(ident, -32600, "HeaderMismatch: Mcp-Method.", 400)
    if method == "tools/call" and request.headers.get("mcp-name") != params.get("name"):
        return _rpc_error(ident, -32600, "HeaderMismatch: Mcp-Name.", 400)
    if "id" not in body:
        return Response(status_code=202)
    if method == "server/discover":
        wynik = {"resultType": "complete", "supportedVersions": [PROTOKOL_MCP],
                 "capabilities": {"tools": {}}, "_meta": _INFO}
    elif method == "tools/list":
        wynik = {"resultType": "complete", "tools": TOOLS, "_meta": _INFO}
    elif method == "tools/call":
        nazwa = params.get("name")
        if nazwa not in {x[0] for x in _NARZEDZIA}:
            return _rpc_error(ident, -32601, "Nieznane narzedzie.", 404)
        args = params.get("arguments", {})
        if not isinstance(args, dict):
            return _rpc_error(ident, -32602, "arguments musi byc obiektem.")
        required = next(x[3] for x in _NARZEDZIA if x[0] == nazwa)
        if any(k not in args for k in required):
            return _rpc_error(ident, -32602, "Brak wymaganych argumentow.")
        try:
            rezultat = _wywolaj(nazwa, args, partner)
            wynik = {"resultType": "complete", "content": [
                {"type": "text", "text": json.dumps(rezultat, ensure_ascii=False)}],
                "isError": False, "_meta": _INFO}
        except (HTTPException, ValueError, KeyError, TypeError) as exc:
            opis = exc.detail if isinstance(exc, HTTPException) else "Niepoprawne argumenty."
            wynik = {"resultType": "complete", "content": [{"type": "text", "text": str(opis)}],
                     "isError": True, "_meta": _INFO}
    else:
        return _rpc_error(ident, -32601, "Nieobslugiwana metoda MCP.", 404)
    return {"jsonrpc": "2.0", "id": ident, "result": wynik}
