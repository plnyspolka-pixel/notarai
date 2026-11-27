"""Speech to text for narrated recordings, on this computer only.

Uses faster-whisper when it is installed (`pip install faster-whisper`; the model is downloaded
once, then runs offline). No cloud speech service is used: audio never leaves the computer.
Without it the notary types or corrects the narration by hand.
"""
import tempfile
from pathlib import Path

_model = None


def available() -> bool:
    try:
        import faster_whisper  # noqa: F401
        return True
    except Exception:
        return False


def transcribe(recording: bytes, model_size: str = "small") -> str:
    """Polish transcript of a WebM/Opus recording. Raises RuntimeError when unavailable."""
    global _model
    if not available():
        raise RuntimeError("no local transcriber")
    from faster_whisper import WhisperModel

    if _model is None:
        _model = WhisperModel(model_size, device="cpu", compute_type="int8")
    with tempfile.TemporaryDirectory() as scratch:
        path = Path(scratch) / "nagranie.webm"
        path.write_bytes(recording)
        segments, _ = _model.transcribe(str(path), language="pl", vad_filter=True)
        return " ".join(segment.text.strip() for segment in segments).strip()
