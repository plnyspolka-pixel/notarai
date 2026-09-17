"""Transkrypcja wiadomosci glosowych - lokalnie, faster-whisper.

Nagranie nie opuszcza komputera. Plik audio jest usuwany zaraz po transkrypcji.
Model pobierany raz (PIECZAPP_WHISPER, domyslnie "small", ~500 MB) do
katalogu cache faster-whisper. W logach tylko dlugosc nagrania i czas.
"""
import logging
import os
import tempfile
import time
from pathlib import Path

log = logging.getLogger("pieczapp.transkrypcja")

MODEL = os.getenv("PIECZAPP_WHISPER", "small")
_model = None


def dostepna() -> bool:
    try:
        import faster_whisper  # noqa: F401
        return True
    except ImportError:
        return False


def _zaladuj():
    global _model
    if _model is None:
        from faster_whisper import WhisperModel
        log.info("laduje model whisper %s", MODEL)
        _model = WhisperModel(MODEL, device="cpu", compute_type="int8")
    return _model


def transkrybuj(dane_audio: bytes, rozszerzenie: str = ".webm") -> str:
    if not dostepna():
        raise RuntimeError(
            "Brak biblioteki faster-whisper. Zainstaluj: pip install faster-whisper"
        )
    start = time.time()
    with tempfile.NamedTemporaryFile(suffix=rozszerzenie, delete=False) as plik:
        plik.write(dane_audio)
        sciezka = Path(plik.name)
    try:
        model = _zaladuj()
        segmenty, info = model.transcribe(
            str(sciezka), language="pl", beam_size=5, vad_filter=True,
        )
        tekst = " ".join(s.text.strip() for s in segmenty).strip()
    finally:
        sciezka.unlink(missing_ok=True)
    log.info("transkrypcja: %.0f s nagrania w %.1f s", getattr(info, "duration", 0), time.time() - start)
    return tekst
