"""Amazon Polly — pomocniczy polski lektor projektu aktu (AWS Frankfurt).

To jest TTS, a nie formalne odczytanie aktu z art. 94 Prawa o notariacie.
API nie zapisuje tekstu ani dzwieku, nie tworzy zadan S3 i nie loguje tresci.
"""
import logging
import os
from functools import lru_cache

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field

import autoryzacja
import kalkulator

log = logging.getLogger("notarai.polly")
router = APIRouter(prefix="/api/polly", tags=["lektor"])
REGION = os.getenv("AWS_REGION", "eu-central-1")
WLACZONE = os.getenv("PIECZAPP_POLLY", "false").strip().lower() in ("1", "true", "yes")
MAKS_ZNAKOW = 2400  # Polly: maks. 3000 znakow rozliczanych na SynthesizeSpeech.

# Nie kazdy glos obsluguje kazdy silnik; walidujemy po stronie serwera.
GLOSY = {
    "Ola": ("generative", "neural"),
    "Ewa": ("generative", "standard"),
    "Maja": ("standard",),
    "Jacek": ("standard",),
    "Jan": ("standard",),
}
# Ograniczamy mozliwosc niekontrolowanego generowania kosztow. Limity sa
# lokalne dla repliki ECS; nie sa globalnym budzetem rozliczeniowym AWS.
limit = kalkulator.Limit(
    int(os.getenv("PIECZAPP_POLLY_NA_GODZINE", "120")),
    int(os.getenv("PIECZAPP_POLLY_NA_DOBE", "3000")),
)


class Synteza(BaseModel):
    tekst: str = Field(min_length=1, max_length=MAKS_ZNAKOW)
    glos: str = "Ola"
    silnik: str = "generative"


@lru_cache(maxsize=1)
def _klient():
    # Nigdy nie korzystamy z regionu ustawionego przez przegladarke.
    return boto3.client("polly", region_name=REGION)


def _dostep(request: Request):
    if not WLACZONE:
        raise HTTPException(503, "Lektor Amazon Polly jest wylaczony.")
    if REGION != "eu-central-1":
        raise HTTPException(503, "Lektor wymaga regionu AWS eu-central-1.")
    if autoryzacja.MULTI:
        # Middleware uwierzytelnia osoby; dostep serwisowy do tresci
        # klienta oraz token pomocnika nie daja prawa do syntezy.
        if not getattr(request.state, "email", "") or getattr(request.state, "serwis", False):
            raise HTTPException(403, "Lektor wymaga zalogowania do kancelarii.")


@router.get("/konfiguracja")
def konfiguracja(request: Request):
    _dostep(request)
    return {
        "wlaczony": True,
        "region": REGION,
        "jezyk": "pl-PL",
        "glosy": {k: list(v) for k, v in GLOSY.items()},
        "maks_znakow": MAKS_ZNAKOW,
        "formalny_odczyt": False,
    }


@router.post("/synteza")
def synteza(dane: Synteza, request: Request):
    """Zwraca MP3 tylko do odtworzenia w RAM przegladarki; bez S3/cache."""
    _dostep(request)
    tekst = dane.tekst.strip()
    if not tekst or any(ord(c) < 32 and c not in "\n\r\t" for c in tekst):
        raise HTTPException(422, "Niepoprawny tekst do odczytu.")
    if dane.glos not in GLOSY or dane.silnik not in GLOSY[dane.glos]:
        raise HTTPException(422, "Niedostepna kombinacja glosu i silnika.")

    klucz = (getattr(request.state, "kancelaria", "") or "lokalnie") + ":" + (
        getattr(request.state, "email", "") or "stanowisko"
    )
    limit.sprawdz(klucz, "Limit odczytow zostal wykorzystany. Sprobuj pozniej.")
    try:
        odpowiedz = _klient().synthesize_speech(
            Text=tekst,
            TextType="text",  # zakaz przesylania SSML od uzytkownika
            VoiceId=dane.glos,
            Engine=dane.silnik,
            LanguageCode="pl-PL",
            OutputFormat="mp3",
        )
        strumien = odpowiedz["AudioStream"]
        try:
            audio = strumien.read()
        finally:
            strumien.close()
        if not audio:
            raise ValueError("empty Polly AudioStream")
    except (BotoCoreError, ClientError, KeyError, OSError, ValueError) as blad:
        # Nie logujemy odpowiedzi dostawcy ani tekstu z aktu.
        log.warning("Polly: synteza niedostepna (%s)", type(blad).__name__)
        raise HTTPException(503, "Nie udalo sie wygenerowac odczytu w AWS Frankfurt.") from None

    return Response(
        content=audio,
        media_type="audio/mpeg",
        headers={
            "Cache-Control": "private, no-store, max-age=0",
            "Pragma": "no-cache",
            "X-Content-Type-Options": "nosniff",
        },
    )
