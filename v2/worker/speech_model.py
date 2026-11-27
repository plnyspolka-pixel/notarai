"""The local speech model, downloaded in the background with visible progress.

Only used when the office chooses "mowa na tym komputerze". The model (faster-whisper) is fetched
once into the office's home directory; the panel shows how much is done. After the download the
model is loaded into memory once, so the first note does not wait for it.
"""
import threading
from pathlib import Path

from . import transcribe as local_speech

SIZES_MB = {"tiny": 75, "base": 145, "small": 484, "medium": 1530, "large-v3": 3090, "turbo": 1620}


class ModelDownload:
    def __init__(self, root: Path, *, downloader=None, warm=None):
        self._root = Path(root)
        self._downloader = downloader or _download
        self._warm = warm or (lambda model: local_speech.load(model, self._root))
        self._lock = threading.Lock()
        self._state: dict = {"state": "brak", "model": None}

    def _folder(self, model: str) -> Path:
        return self._root / f"models--Systran--faster-whisper-{model}"

    def _done_mb(self, model: str) -> int:
        folder = self._folder(model)
        if not folder.exists():
            return 0
        return sum(f.stat().st_size for f in folder.rglob("*") if f.is_file() and not f.is_symlink()) // 2**20

    def start(self, model: str) -> dict:
        if model not in SIZES_MB:
            raise ValueError("unknown speech model")
        with self._lock:
            if self._state["state"] == "pobieranie" and self._state["model"] == model:
                return self.progress()
            self._state = {"state": "pobieranie", "model": model}
        threading.Thread(target=self._run, args=(model,), daemon=True, name="notarai-model-mowy").start()
        return self.progress()

    def _run(self, model: str) -> None:
        try:
            self._downloader(model, self._root)
            with self._lock:
                self._state = {"state": "ladowanie", "model": model}
            self._warm(model)
            with self._lock:
                self._state = {"state": "gotowy", "model": model}
        except Exception:
            with self._lock:
                self._state = {"state": "blad", "model": model}

    def progress(self) -> dict:
        with self._lock:
            current = dict(self._state)
        model = current["model"]
        if model is None:
            return {"state": "brak", "percent": 0, "text": "Model mowy nie jest pobrany."}
        total = SIZES_MB[model]
        done = min(self._done_mb(model), total)
        percent = 100 if current["state"] in {"ladowanie", "gotowy"} else min(99, done * 100 // total)
        text = {
            "pobieranie": f"Pobieram model mowy na ten komputer: {done} z ok. {total} MB.",
            "ladowanie": "Model pobrany. Przygotowuję go do pracy…",
            "gotowy": "Model mowy jest gotowy. Nagrania przepisuje ten komputer, bez wysyłania dźwięku.",
            "blad": "Nie udało się pobrać modelu mowy. Sprawdź internet i napisz „mowa na tym komputerze” jeszcze raz.",
        }[current["state"]]
        return {"state": current["state"], "percent": percent, "text": text}


def _download(model: str, root: Path) -> None:
    from faster_whisper.utils import download_model

    root.mkdir(parents=True, exist_ok=True)
    download_model(model, cache_dir=str(root))
