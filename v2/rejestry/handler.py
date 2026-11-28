"""notarai-v2-rejestry: treść księgi wieczystej dla stanowiska NotarAI V2.

Używa bez zmian `ekw.py` z V1 (Finance You, a zapasowo Apify; sprzątanie u dostawcy,
walidacja numeru). Token dostawcy czytany z Secrets Manager przez rolę tej funkcji;
stanowisko nigdy go nie widzi. Wywołuje ją tylko rola stanowiska V2 (IAM).

Nic nie jest zapisywane, a do logów nie trafia ani numer księgi, ani jej treść.
"""
import json
import logging
import os

import boto3

logging.getLogger().setLevel(logging.WARNING)
_ready = False


def _configure() -> None:
    """Tokens from Secrets Manager into the environment ekw.py reads, once per container."""
    global _ready
    if _ready:
        return
    client = boto3.client("secretsmanager")
    for variable, arn in (("PIECZAPP_APIFY_TOKEN", os.environ.get("APIFY_SECRET_ARN", "")),
                          ("PIECZAPP_FINYOU_TOKEN", os.environ.get("FINYOU_SECRET_ARN", ""))):
        if arn:
            value = json.loads(client.get_secret_value(SecretId=arn)["SecretString"])
            os.environ[variable] = str(value.get("token", "")).strip()
    _ready = True


KRZ_ACTOR = "regdata~krz-debtor-scraper"     # Apify: KRZ by PESEL (modes person and soleTrader), 28.11.2026
KRZ_MODES = ("person", "soleTrader")        # osoba fizyczna nieprowadząca / prowadząca działalność


def _krz(pesel: str) -> dict:
    """KRZ through Apify (owner's decision 28.11.2026: Apify first, the station's browser only as the fallback).
    Both modes at once; nothing is stored here and the PESEL never reaches a log."""
    import concurrent.futures

    import httpx

    token = os.environ.get("PIECZAPP_APIFY_TOKEN", "")
    if not token:
        return {"ok": False, "kod": "brak_tokenu", "komunikat": "Apify nie jest skonfigurowane."}

    def one(mode):
        response = httpx.post(f"https://api.apify.com/v2/acts/{KRZ_ACTOR}/run-sync-get-dataset-items",
                              params={"timeout": 240, "format": "json"},
                              headers={"Authorization": f"Bearer {token}"},
                              json={"searchMode": mode, "identifier": pesel, "maxResults": 50}, timeout=270)
        if response.status_code not in (200, 201):
            raise RuntimeError(f"apify {response.status_code}")
        items = response.json()
        if not isinstance(items, list):
            raise RuntimeError("apify format")
        return mode, items

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        found = dict(pool.map(one, KRZ_MODES))
    keep = ("entityName", "firstName", "lastName", "proceedingId", "caseSignature", "proceedingKind",
            "proceedingType", "proceedingStatus", "proceedingStartDate", "court", "courtDivision", "role",
            "searchType", "sourceUrl")
    wpisy = [{"tryb": mode, **{k: str(v)[:300] for k, v in item.items() if k in keep and v not in (None, "")}}
             for mode, items in found.items() for item in items if isinstance(item, dict)
             and (item.get("caseSignature") or item.get("proceedingId"))]
    return {"ok": True, "wpisy": wpisy, "zrodlo": "Apify (krz.ms.gov.pl)", "tryby": list(KRZ_MODES)}


def handler(event, context):
    import ekw

    if isinstance(event, dict) and event.get("rejestr") == "krz":
        pesel = str(event.get("pesel", ""))
        if not (len(pesel) == 11 and pesel.isdigit()):
            return {"ok": False, "kod": "zle_zadanie", "komunikat": "Nieprawidłowy numer PESEL."}
        try:
            _configure()
            return _krz(pesel)
        except Exception as error:                 # no details: they could carry data
            logging.warning("rejestry: krz przez apify nie powiodl sie %s", type(error).__name__)
            return {"ok": False, "kod": "niedostepny", "komunikat": "Apify nie odpowiedziało."}
    if not isinstance(event, dict) or event.get("rejestr") != "kw" or not isinstance(event.get("numer"), str):
        return {"ok": False, "kod": "zle_zadanie", "komunikat": "Nieprawidłowe zapytanie."}
    try:
        _configure()
        numer = event["numer"][:40]
        # Owner's decision 28.11.2026: Apify first, then the Finance You engine (EKW) when it is configured.
        try:
            ksiega = ekw.pobierz_apify(numer) if ekw.token() else ekw.pobierz_finyou(numer)
        except ekw.BladEKW as first:
            if first.kod == "zly_numer" or not (ekw.token() and ekw.finyou_adres() and ekw.finyou_token()):
                raise
            logging.warning("rejestry: apify %s, probuje Finance You", first.kod)
            ksiega = ekw.pobierz_finyou(numer)
    except ValueError as error:
        return {"ok": False, "kod": "zly_numer", "komunikat": str(error)}
    except ekw.BladEKW as error:
        return {"ok": False, "kod": error.kod, "komunikat": str(error)}
    except Exception as error:                     # no details: they could carry data
        logging.warning("rejestry: nieoczekiwany blad %s", type(error).__name__)
        return {"ok": False, "kod": "niedostepny", "komunikat": "Rejestr chwilowo nie odpowiada. Spróbuj później."}
    return {"ok": True, "ksiega": ksiega, "tekst": ekw.do_tekstu(ksiega), "zrodlo": ksiega.get("zrodlo", "")}
