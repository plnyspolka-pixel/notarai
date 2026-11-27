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


def handler(event, context):
    import ekw

    if not isinstance(event, dict) or event.get("rejestr") != "kw" or not isinstance(event.get("numer"), str):
        return {"ok": False, "kod": "zle_zadanie", "komunikat": "Nieprawidłowe zapytanie."}
    try:
        _configure()
        ksiega = ekw.pobierz(event["numer"][:40])
    except ValueError as error:
        return {"ok": False, "kod": "zly_numer", "komunikat": str(error)}
    except ekw.BladEKW as error:
        return {"ok": False, "kod": error.kod, "komunikat": str(error)}
    except Exception as error:                     # no details: they could carry data
        logging.warning("rejestry: nieoczekiwany blad %s", type(error).__name__)
        return {"ok": False, "kod": "niedostepny", "komunikat": "Rejestr chwilowo nie odpowiada. Spróbuj później."}
    return {"ok": True, "ksiega": ksiega, "tekst": ekw.do_tekstu(ksiega), "zrodlo": ksiega.get("zrodlo", "")}
