"""Leady z formularzy Meta (Facebook / Instagram Lead Ads) -> gielda (leady.py).

Meta wysyla webhook "leadgen" (sam identyfikator leada), my pobieramy tresc
z Graph API tokenem strony i tworzymy lead. Konfiguracja (w chmurze z Secrets
Manager, sekret notarai/meta, nigdy w repozytorium):
  PIECZAPP_META_VERIFY      - token weryfikacji subskrypcji (dowolny, ten sam w panelu Meta)
  PIECZAPP_META_APP_SECRET  - App Secret aplikacji Meta (podpis X-Hub-Signature-256)
  PIECZAPP_META_TOKEN       - token dostepu strony z uprawnieniem leads_retrieval
  PIECZAPP_META_GRAPH       - wersja Graph API (domyslnie v21.0 - sprawdz aktualna w panelu Meta)

Pola formularza: standardowe (full_name, first_name, last_name, phone_number,
email, city) i pytania wlasne. Pytanie o sprawe rozpoznajemy po kluczu albo
tresci (sprawa, czynnosc), opis po "opis", miejscowosc po city / miasto /
miejscowosc. Wszystkie pozostale odpowiedzi trafiaja do leada jako
"dodatkowe" (np. wartosc, termin, kredyt) - kancelaria widzi je w opisie.
"""
import hashlib
import hmac
import logging
import os

import httpx
from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from fastapi.responses import PlainTextResponse

import dziennik
import leady

log = logging.getLogger("pieczapp.meta")

GRAPH = "https://graph.facebook.com/" + os.getenv("PIECZAPP_META_GRAPH", "v21.0")
POLA_LEADA = "created_time,field_data,form_id,ad_id,ad_name,adset_name,campaign_name,platform,is_organic"
_transport: httpx.BaseTransport | None = None   # testy podstawiaja httpx.MockTransport

router = APIRouter(prefix="/api/meta", tags=["meta"])


def _env(nazwa: str) -> str:
    return os.getenv(nazwa, "").strip()


@router.get("/leadgen")
def weryfikacja(request: Request):
    p = request.query_params
    if p.get("hub.mode") == "subscribe" and _env("PIECZAPP_META_VERIFY") and \
            hmac.compare_digest(p.get("hub.verify_token", ""), _env("PIECZAPP_META_VERIFY")):
        return PlainTextResponse(p.get("hub.challenge", ""))
    raise HTTPException(403, "Zly token weryfikacji.")


def podpis_poprawny(cialo: bytes, naglowek: str) -> bool:
    sekret = _env("PIECZAPP_META_APP_SECRET")
    if not sekret or not naglowek.startswith("sha256="):
        return False
    oczekiwany = hmac.new(sekret.encode(), cialo, hashlib.sha256).hexdigest()
    return hmac.compare_digest(oczekiwany, naglowek[7:])


def pobierz_lead(leadgen_id: str) -> dict:
    # Token w naglowku, nie w adresie: adres trafia do komunikatow bledow httpx.
    with httpx.Client(timeout=20, transport=_transport) as klient:
        odp = klient.get(f"{GRAPH}/{leadgen_id}", params={"fields": POLA_LEADA},
                         headers={"Authorization": f"Bearer {_env('PIECZAPP_META_TOKEN')}"})
    odp.raise_for_status()
    return odp.json()


def z_formularza(dane: dict) -> dict:
    """field_data Meta -> pola leada."""
    pola = {}
    for f in dane.get("field_data") or []:
        wartosci = f.get("values") or []
        pola[str(f.get("name") or "")] = ", ".join(str(v) for v in wartosci)
    wynik = {"imie": "", "nazwisko": "", "telefon": "", "email": "", "sprawa": "", "opis": "", "miejscowosc": ""}
    dodatkowe = []
    for klucz, wartosc in pola.items():
        k = klucz.lower()
        if k == "full_name":
            czesci = wartosc.split()
            wynik["imie"], wynik["nazwisko"] = (czesci[0] if czesci else ""), " ".join(czesci[1:])
        elif k == "first_name":
            wynik["imie"] = wartosc
        elif k == "last_name":
            wynik["nazwisko"] = wartosc
        elif k in ("phone_number", "phone", "telefon"):
            wynik["telefon"] = wartosc
        elif k == "email":
            wynik["email"] = wartosc
        elif k in ("city", "miasto", "miejscowosc", "miejscowość") or "miejscow" in k or "miasto" in k:
            wynik["miejscowosc"] = wartosc
        elif "sprawa" in k or "czynno" in k or "rodzaj" in k:
            wynik["sprawa"] = wartosc.replace("_", " ")
        elif "opis" in k:
            wynik["opis"] = wartosc
        elif wartosc:
            dodatkowe.append(f"{klucz.replace('_', ' ')}: {wartosc}")
    if dodatkowe:
        wynik["opis"] = (wynik["opis"] + "\n" if wynik["opis"] else "") + "Dodatkowo: " + "; ".join(dodatkowe)
    return wynik


def przetworz(zmiana: dict) -> dict | None:
    leadgen_id = str(zmiana.get("leadgen_id") or "")
    if not leadgen_id.isdigit():
        return None
    if any((l.get("meta") or {}).get("leadgen_id") == leadgen_id for l in leady._wczytaj()["leady"]):
        log.info("meta: lead %s juz jest (ponowiony webhook)", leadgen_id)
        return None
    dane = pobierz_lead(leadgen_id)
    f = z_formularza(dane)
    meta = {"leadgen_id": leadgen_id, **{k: dane.get(k) for k in
            ("form_id", "ad_id", "ad_name", "adset_name", "campaign_name", "platform", "is_organic", "created_time")}}
    return leady.nowy(klient=f, sprawa=f["sprawa"] or f["opis"], opis=f["opis"],
                      miejscowosc=f["miejscowosc"], zrodlo="meta", meta=meta)


def _przetworz_wszystkie(zmiany: list[dict]) -> None:
    for z in zmiany:
        try:
            przetworz(z)
        except Exception as blad:  # noqa: BLE001 - jeden zly lead nie blokuje reszty
            log.error("meta: lead %s nie przetworzony (%s)", z.get("leadgen_id"), dziennik.opis_bledu(blad))


@router.post("/leadgen")
async def webhook(request: Request, zadania: BackgroundTasks):
    cialo = await request.body()
    if not podpis_poprawny(cialo, request.headers.get("x-hub-signature-256", "")):
        raise HTTPException(403, "Zly podpis.")
    import json
    dane = json.loads(cialo or b"{}")
    zmiany = [c.get("value") or {} for e in dane.get("entry") or [] for c in e.get("changes") or []
              if c.get("field") == "leadgen"]
    # Meta czeka kilka sekund na 200; pobranie i rozsylka ida w tle.
    zadania.add_task(_przetworz_wszystkie, zmiany)
    return {"ok": True, "leady": len(zmiany)}


# ---------------------------------------------------------------- leady przekazywane przez Finance You
#
# Finance You odbiera webhook Meta dla swoich stron i formularz z ustawionym
# client_forward_url wysyla prosto do zewnetrznego panelu (src/lib/
# meta-leads-client-forward.server.ts w repo finyou): JSON LeadKlienta
# + naglowek x-lead-secret. U siebie nie zostawia danych osobowych.
#
# Sekret jest wspolny z Finance You (meta_lead_forms.client_forward_secret).
# Tutaj trzymamy tylko jego skrot SHA-256 - skrot losowego 256-bitowego
# sekretu nie jest tajny, wiec nie potrzeba Secrets Manager. Zmiana sekretu:
# nowy skrot w PIECZAPP_LEADY_FINYOU_SHA256 (albo tu) i nowy sekret w Finance You.
SKROT_SEKRETU_FINYOU = os.getenv(
    "PIECZAPP_LEADY_FINYOU_SHA256", "55ce75e25719b1124a1093f3a6acdafc4d1b2c69f1293ad6a3c2ca0cf7b42246")


def sekret_finyou_poprawny(sekret: str) -> bool:
    if not sekret or not SKROT_SEKRETU_FINYOU:
        return False
    return hmac.compare_digest(hashlib.sha256(sekret.encode("utf-8")).hexdigest(), SKROT_SEKRETU_FINYOU)


@router.post("/finyou")
async def z_finyou(request: Request):
    """Lead z formularza Meta przekazany przez Finance You."""
    if not sekret_finyou_poprawny(request.headers.get("x-lead-secret", "")):
        raise HTTPException(403, "Zly sekret.")
    try:
        dane = await request.json()
    except ValueError:
        raise HTTPException(400, "To nie jest JSON.")
    meta_id = str(dane.get("meta_lead_id") or "")
    if not meta_id:
        raise HTTPException(400, "Brak meta_lead_id.")
    if any((l.get("meta") or {}).get("leadgen_id") == meta_id for l in leady._wczytaj()["leady"]):
        return {"ok": True, "duplikat": True}
    pola = [{"name": p.get("nazwa"), "values": [p.get("wartosc")]} for p in dane.get("pola") or [] if isinstance(p, dict)]
    f = z_formularza({"field_data": pola})
    # Finance You czysci imie z wklejonych numerow i wyluskuje telefon odporniej - bierzemy jego wersje.
    if dane.get("imie") and not f["nazwisko"]:
        czesci = str(dane["imie"]).split()
        f["imie"], f["nazwisko"] = (czesci[0] if czesci else ""), " ".join(czesci[1:])
    f["telefon"] = str(dane.get("telefon") or f["telefon"] or "")
    f["email"] = str(dane.get("email") or f["email"] or "")
    meta = {"leadgen_id": meta_id, "form_id": dane.get("formularz_id"), "ad_id": dane.get("reklama_id"),
            "campaign_id": dane.get("kampania_id"), "created_time": dane.get("utworzono"), "przez": "finyou"}
    lead = leady.nowy(klient=f, sprawa=f["sprawa"] or f["opis"], opis=f["opis"],
                      miejscowosc=f["miejscowosc"], zrodlo="meta", meta=meta)
    return {"ok": True, "id": lead["id"], "wyslano": lead["wyslano"]}
