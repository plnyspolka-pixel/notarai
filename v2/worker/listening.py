"""Always-on microphones: transcripts of deeds read aloud and notes of conversations, by themselves.

A microphone is any paired device in "listen" mode (a tablet in reception, a computer in the
notary's room). It sends short audio segments that contain sound; silence is dropped on the
device. Here every segment is transcribed locally, segments from one microphone are joined into a
conversation, and a conversation ends after a quiet gap. Then:

  * if it follows the text of a deed in one of the cases, it is the reading of that deed: the
    transcript is added to that case as a stenogram (matching is by shared word sequences, in code);
  * otherwise it is a conversation (a visit or a phone call heard in the room): a note with who,
    what about, any agreed date and contact is written to the case "sekretariat", together with
    the transcript. The summary needs the assistant; without it the transcript alone is kept.

Audio is held only in memory until transcribed and is never stored unless the office asks for it.
"""
import json
import re
import threading
import time
import unicodedata
from collections import deque

NOTES_CASE = "sekretariat"
SYSTEM_CASES = {"procedury", "styl-kancelarii", "zasady-kancelarii", NOTES_CASE}
MIN_WORDS = 12
MATCH = 0.3
MAX_QUEUE = 400

SYSTEM_NOTE = (
    "Jesteś asystentem polskiej kancelarii notarialnej. Dostajesz zapis rozmowy usłyszanej w kancelarii przez "
    "mikrofon (rozpoznawanie mowy może mylić słowa). Odpowiedz wyłącznie JSON-em:\n"
    '{"rodzaj": "wizyta, telefon albo inne", "podsumowanie": "2-4 zdania: kto, w jakiej sprawie, co ustalono", '
    '"osoby": ["imiona i nazwiska, jeśli padły"], "termin": "uzgodniony termin wizyty lub czynności albo pusty tekst", '
    '"kontakt": "telefon lub e-mail, jeśli padł, albo pusty tekst", "do_zrobienia": ["co kancelaria ma zrobić"]}\n'
    "Telefon: słychać jedną stronę rozmowy telefonicznej. Nie zmyślaj niczego, czego nie ma w zapisie. "
    "Znaczniki w nawiasach kwadratowych przepisuj bez zmian."
)


def words(text: str) -> list[str]:
    text = text.lower().replace("ł", "l")
    text = "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")
    return re.findall(r"[a-z]{2,}", text)          # numbers are read as words: leave them out on both sides


def shingles(text: str) -> set:
    w = words(text)
    return {" ".join(w[i:i + 3]) for i in range(len(w) - 2)}


def containment(spoken: set, written: set) -> float:
    return len(spoken & written) / len(spoken) if spoken else 0.0


class Listening:
    def __init__(self, vault, transcribe, inference, settings, *, clock=time.time, extract=None):
        """`transcribe(audio, suffix)` -> text or None; `inference()` -> Inference; `settings()` -> ListenSettings."""
        self._vault, self._transcribe, self._inference, self._settings = vault, transcribe, inference, settings
        self._clock, self._extract = clock, extract
        self._queue: deque = deque()
        self._conversations: dict[str, dict] = {}
        self.sources: dict[str, dict] = {}
        self._lock = threading.Lock()
        self._shingle_cache: dict[tuple, set] = {}
        self._finished: list = []

    # ---------------------------------------------------------------- intake
    def accept(self, source: str, audio: bytes, suffix: str, started: float, duration: float) -> bool:
        current = self._settings()
        if not current.enabled or current.paused:
            return False
        with self._lock:
            if len(self._queue) >= MAX_QUEUE:
                self._queue.popleft()          # never grow without bound if transcription falls behind
            self._queue.append((source, audio, suffix, started, duration))
            seen = self.sources.setdefault(source, {"segments": 0})
            seen.update(last=self._clock(), segments=seen["segments"] + 1)
        return True

    def pending(self) -> int:
        return len(self._queue)

    # ---------------------------------------------------------------- work, on a background thread
    def tick(self) -> list[dict]:
        self._transcribe_pending()
        return self._close_idle()

    def _hear(self, item):
        source, audio, suffix, started, duration = item
        try:
            return (self._transcribe(audio, suffix) or "").strip()
        except Exception:
            return ""

    def _transcribe_pending(self) -> None:
        """Pieces are transcribed several at a time (a cloud job takes seconds), then filed in order."""
        from concurrent.futures import ThreadPoolExecutor

        while True:
            with self._lock:
                batch = [self._queue.popleft() for _ in range(min(len(self._queue), 8))]
            if not batch:
                return
            with ThreadPoolExecutor(max_workers=4) as pool:
                texts = list(pool.map(self._hear, batch))
            for (source, _, _, started, duration), text in sorted(zip(batch, texts), key=lambda pair: pair[0][3]):
                if text:
                    self._file_piece(source, text, started, duration)

    def _file_piece(self, source, text, started, duration) -> None:
        with self._lock:
            conversation = self._conversations.get(source)
            gap = self._settings().gap_seconds
            if conversation is not None and started - conversation["end"] > gap:
                self._finished.append(self._conversations.pop(source))
                conversation = None
            if conversation is None:
                conversation = self._conversations[source] = {"source": source, "start": started, "end": started, "texts": []}
            conversation["texts"].append(text)
            conversation["end"] = max(conversation["end"], started + duration)

    def _close_idle(self) -> list[dict]:
        now, gap = self._clock(), self._settings().gap_seconds
        with self._lock:
            done, self._finished = self._finished, []
            for source in [s for s, c in self._conversations.items() if now - c["end"] > gap]:
                done.append(self._conversations.pop(source))
        return [result for result in (self._file(c) for c in done) if result is not None]

    def flush(self) -> list[dict]:
        """Close every open conversation now (used when listening is switched off)."""
        self._transcribe_pending()
        with self._lock:
            done = self._finished + list(self._conversations.values())
            self._finished, self._conversations = [], {}
        return [result for result in (self._file(c) for c in done) if result is not None]

    # ---------------------------------------------------------------- what a conversation becomes
    def _deed_texts(self):
        for item in self._vault.summaries():
            if item["case"] in SYSTEM_CASES or item["case"] is None:
                continue
            # Deeds are Word documents; notes, transcripts and voice notes are text files and never a deed.
            if not item["name"].lower().endswith(".docx"):
                continue
            key = (item["id"], item["version"])
            if key not in self._shingle_cache:
                _, _, data = self._vault.get(item["id"], item["version"], actor="nasluch")
                try:
                    text = "\n".join(self._extract(data))
                except Exception:
                    text = ""
                self._shingle_cache[key] = shingles(text)
            yield item, self._shingle_cache[key]

    def _file(self, conversation: dict) -> dict | None:
        transcript = " ".join(conversation["texts"])
        if len(words(transcript)) < MIN_WORDS:
            return None
        start = time.localtime(conversation["start"])
        stamp = time.strftime("%Y%m%d-%H%M", start)
        span = f"{time.strftime('%d.%m.%Y %H:%M', start)}–{time.strftime('%H:%M', time.localtime(conversation['end']))}"
        source = conversation["source"]
        safe_source = re.sub(r"[^\w-]+", "-", source).strip("-")[:30] or "mikrofon"
        spoken = shingles(transcript)
        best, score = None, 0.0
        for item, written in self._deed_texts():
            current = containment(spoken, written)
            if current > score:
                best, score = item, current
        if best is not None and score >= MATCH:
            name = f"stenopis-{stamp}-{safe_source}.txt"
            body = (f"Stenopis odczytania aktu „{best['name']}” (wersja {best['version']}), {span}, mikrofon: {source}.\n"
                    f"Zapis automatyczny z rozpoznawania mowy; zgodność z aktem {round(score * 100)}%. Sprawdź przed użyciem.\n\n"
                    f"{transcript}\n")
            doc_id, version = self._vault.put(None, 0, name, body.encode(), actor="nasluch", case=best["case"])
            return {"kind": "stenopis", "case": best["case"], "id": doc_id, "name": name, "deed": best["name"],
                    "score": round(score, 2)}
        note, summary = None, ""
        inference = self._inference()
        if inference is not None and inference.enabled:
            try:
                answer = inference.ask(purpose="listen", system=SYSTEM_NOTE, text=transcript, max_tokens=1500)
                start_json, end_json = answer.text.find("{"), answer.text.rfind("}")
                note = json.loads(answer.text[start_json:end_json + 1])
            except Exception:
                note = None
        kind = (note or {}).get("rodzaj", "")
        title = {"telefon": "Rozmowa telefoniczna", "wizyta": "Rozmowa z klientem"}.get(kind, "Rozmowa")
        if note:
            parts = [str(note.get("podsumowanie", "")).strip()]
            if note.get("osoby"):
                parts.append("Osoby: " + ", ".join(map(str, note["osoby"])))
            if note.get("termin"):
                parts.append("Termin: " + str(note["termin"]))
            if note.get("kontakt"):
                parts.append("Kontakt: " + str(note["kontakt"]))
            if note.get("do_zrobienia"):
                parts.append("Do zrobienia: " + "; ".join(map(str, note["do_zrobienia"])))
            summary = "\n".join(p for p in parts if p)
        name = f"rozmowa-{stamp}-{safe_source}.txt"
        body = (f"{title}, {span}, mikrofon: {source}.\n"
                + (f"\n{summary}\n" if summary else "\n(Bez podsumowania: asystent jest wyłączony.)\n")
                + f"\nZapis rozmowy (automatyczny, sprawdź):\n{transcript}\n")
        doc_id, version = self._vault.put(None, 0, name, body.encode(), actor="nasluch", case=NOTES_CASE)
        return {"kind": kind or "rozmowa", "case": NOTES_CASE, "id": doc_id, "name": name, "summary": summary}
