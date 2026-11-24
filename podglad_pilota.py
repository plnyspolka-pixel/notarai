"""Krotkotrwaly przekaz zaszyfrowanych kadrów z rozszerzenia do telefonu.

Backend nie ma prywatnego klucza ECDH ani klucza AES: dostaje tylko pakiet
ECDH-P256/AES-GCM z nonce i zaszyfrowana zawartoscia. Przechowuje w S3
wylacznie ostatnia klatke, a nie nagranie. Rozdzielenie kancelarii zapewnia
ContextVar magazynu i uwierzytelnione endpointy app.py.
"""
import json
from datetime import datetime, timedelta, timezone

import magazyn

MAKS_CIPHERTEXT_ZNAKOW = 450_000
SWIEZOSC_S = 15


def _teraz():
    return datetime.now(timezone.utc)


def _klucz(zlecenie: str) -> str:
    return f"{magazyn.PREFIKS}/{magazyn.kancelaria()}/podglad-pilota/{zlecenie}.json"


def zapisz(zlecenie: str, numer: int, pubkey: dict, iv: str, ciphertext: str) -> None:
    if numer < 1 or numer > 10000 or len(ciphertext) > MAKS_CIPHERTEXT_ZNAKOW:
        raise ValueError("Niepoprawne parametry kadru.")
    if not isinstance(pubkey, dict) or pubkey.get("kty") != "EC" or pubkey.get("crv") != "P-256":
        raise ValueError("Niepoprawny klucz kadru.")
    if not isinstance(iv, str) or len(iv) > 48 or not iv:
        raise ValueError("Niepoprawny nonce kadru.")
    if not isinstance(ciphertext, str) or not ciphertext:
        raise ValueError("Brak zaszyfrowanego kadru.")
    wpis = {
        "numer": numer, "klucz": {k: pubkey[k] for k in ("kty", "crv", "x", "y") if k in pubkey},
        "iv": iv, "dane": ciphertext, "czas": _teraz().isoformat(timespec="seconds"),
    }
    magazyn._klient_s3().put_object(
        Bucket=magazyn.BUCKET, Key=_klucz(zlecenie),
        Body=json.dumps(wpis, separators=(",", ":")).encode("utf-8"),
        **magazyn._szyfrowanie(),
    )


def ostatni(zlecenie: str) -> dict | None:
    try:
        odp = magazyn._klient_s3().get_object(Bucket=magazyn.BUCKET, Key=_klucz(zlecenie))
    except Exception as blad:
        if type(blad).__name__ in ("NoSuchKey", "ClientError"):
            return None
        raise
    wpis = json.loads(odp["Body"].read().decode("utf-8"))
    try:
        if _teraz() - datetime.fromisoformat(wpis["czas"]) > timedelta(seconds=SWIEZOSC_S):
            return None
    except (KeyError, ValueError, TypeError):
        return None
    return {k: wpis[k] for k in ("numer", "klucz", "iv", "dane", "czas")}


def usun(zlecenie: str) -> None:
    magazyn._klient_s3().delete_objects(
        Bucket=magazyn.BUCKET,
        Delete={"Objects": [{"Key": _klucz(zlecenie)}], "Quiet": True},
    )
