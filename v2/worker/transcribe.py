"""Speech to text on this computer only: narrated recordings and voice notes.

faster-whisper runs locally; the model is downloaded once into the vault's directory and then
works offline. No cloud speech service is used, so audio never leaves the computer. Without it
the recording is still stored and the notary can type the text.
"""
import tempfile
import threading
from pathlib import Path

MODELS = ("tiny", "base", "small", "medium", "large-v3", "turbo")
AUDIO = (".webm", ".ogg", ".opus", ".oga", ".m4a", ".mp3", ".wav", ".aac", ".amr", ".3gp", ".flac", ".mp4")
_models: dict = {}
_lock = threading.Lock()


def is_audio(name: str) -> bool:
    return name.lower().endswith(AUDIO)


def available() -> bool:
    try:
        import faster_whisper  # noqa: F401
        return True
    except Exception:
        return False


def transcribe(recording: bytes, model_size: str = "small", root: Path | None = None, suffix: str = ".webm") -> str:
    """Polish transcript of an audio file in any common format. Raises RuntimeError when unavailable."""
    if not available():
        raise RuntimeError("no local transcriber")
    if model_size not in MODELS:
        raise ValueError("unknown speech model")
    from faster_whisper import WhisperModel

    with _lock:                      # one model in memory, loaded once
        if model_size not in _models:
            _models[model_size] = WhisperModel(model_size, device="cpu", compute_type="int8",
                                               download_root=str(root) if root else None)
        model = _models[model_size]
    with tempfile.TemporaryDirectory() as scratch:
        path = Path(scratch) / ("nagranie" + (suffix if suffix.startswith(".") and len(suffix) <= 6 else ".webm"))
        path.write_bytes(recording)
        segments, _ = model.transcribe(str(path), language="pl", vad_filter=True, beam_size=5)
        return " ".join(segment.text.strip() for segment in segments).strip()
