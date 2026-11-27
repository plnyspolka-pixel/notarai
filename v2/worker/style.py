"""Learn how this office writes, from the acts already on its computers.

The scan runs on the workstation and reads documents in place; nothing is copied into the vault
and nothing is sent anywhere. From the acts it finds it keeps only what repeats: sentences that
appear in many acts of the same kind (after numbers are blanked out) are the office's own
formulas, and their average position gives the usual order of an act. A sentence that names a
particular client differs from act to act, so it never repeats and is never kept; what is learned
is the office's wording, not its clients.

When a draft is prepared, the formulas for that kind of act go to the model as wording to use
verbatim, in that order.
"""
import json
import os
import re
import threading
import time
import unicodedata
import zipfile
from collections import defaultdict
from io import BytesIO
from pathlib import Path

CASE = "styl-kancelarii"
NAME = "styl.json"
EXTENSIONS = (".docx", ".odt", ".rtf", ".txt")
MAX_FILES = 200_000
MAX_BYTES = 15 * 1024 * 1024
SKIP_DIRS = {"windows", "program files", "program files (x86)", "programdata", "appdata", "$recycle.bin",
             "system volume information", "node_modules", ".git", "__pycache__", "venv", ".venv", "temp", "tmp",
             "workcopies", "przegladarka", "modele-mowy", "cache", ".cache", "library", "proc", "sys", "dev"}

# Kind of act by what its title says. Order matters: the first match wins.
KINDS = (
    ("sprzedaż", ("umowa sprzedazy", "umowy sprzedazy", "sprzedaje", "sprzedaz")),
    ("darowizna", ("umowa darowizny", "darowizny", "daruje")),
    ("pełnomocnictwo", ("pelnomocnictwo", "pelnomocnikiem")),
    ("testament", ("testament",)),
    ("dziedziczenie", ("poswiadczenia dziedziczenia", "protokol dziedziczenia", "akt poswiadczenia dziedziczenia")),
    ("hipoteka", ("hipoteki", "hipoteke", "hipoteka")),
    ("spółka", ("umowa spolki", "akt zalozycielski", "spolki z ograniczona")),
    ("dożywocie", ("dozywocia",)),
    ("służebność", ("sluzebnosci", "sluzebnosc")),
    ("dział spadku", ("dzialu spadku", "dzial spadku")),
    ("ustanowienie odrębnej własności", ("ustanowienia odrebnej wlasnosci", "odrebnej wlasnosci lokalu")),
)


def plain(text: str) -> str:
    text = text.lower().replace("ł", "l")
    return "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")


def kind_of(text: str) -> str:
    head = plain(text[:1500])
    for kind, words in KINDS:
        if any(word in head for word in words):
            return kind
    return "inne"


def is_act(text: str) -> bool:
    """A notarial deed, not any document: its fixed vocabulary is hard to miss."""
    sample = plain(text[:20000])
    score = sum(marker in sample for marker in (
        "akt notarialny", "repertorium a", "rep. a", "notariusz", "stawil", "kancelarii notarialnej",
        "akt ten zostal odczytany", "przyjety i podpisany", "taksa notarialna", "wypis", "§ 1"))
    return score >= 3


# ------------------------------------------------------------ reading files in place
def read_text(path: Path) -> str | None:
    try:
        if path.stat().st_size > MAX_BYTES:
            return None
        data = path.read_bytes()
    except OSError:
        return None
    name = path.name.lower()
    try:
        if name.endswith(".docx"):
            from .docx_writer import extract

            return "\n".join(extract(data))
        if name.endswith(".odt"):
            with zipfile.ZipFile(BytesIO(data)) as archive:
                xml = archive.read("content.xml").decode("utf-8", errors="replace")
            xml = re.sub(r"</text:(p|h)>", "\n", xml)
            xml = re.sub(r"<text:(s|tab)[^>]*/>", " ", xml)
            return re.sub(r"<[^>]+>", "", xml).replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
        if name.endswith(".rtf"):
            text = data.decode("cp1250", errors="replace")
            text = re.sub(r"\\'([0-9a-f]{2})", lambda m: bytes([int(m.group(1), 16)]).decode("cp1250", "replace"), text)
            text = re.sub(r"\\par[d]?\b", "\n", text)
            text = re.sub(r"\\[a-z]+-?\d* ?|[{}]", "", text)
            return text
        for encoding in ("utf-8", "cp1250"):
            try:
                return data.decode(encoding)
            except UnicodeDecodeError:
                continue
    except Exception:
        return None
    return None


def default_roots() -> list[Path]:
    """Every local disk on Windows; the home directory elsewhere."""
    if os.name == "nt":
        import string

        return [Path(f"{letter}:\\") for letter in string.ascii_uppercase if Path(f"{letter}:\\").exists()]
    return [Path.home()]


def walk(roots, deadline: float, progress: dict):
    for root in roots:
        stack = [Path(root)]
        while stack:
            if time.monotonic() > deadline or progress["files"] >= MAX_FILES or progress.get("cancel"):
                return
            folder = stack.pop()
            try:
                entries = list(os.scandir(folder))
            except OSError:
                continue
            for entry in entries:
                try:
                    if entry.is_dir(follow_symlinks=False):
                        if entry.name.lower() not in SKIP_DIRS and not entry.name.startswith("."):
                            stack.append(Path(entry.path))
                    elif entry.name.lower().endswith(EXTENSIONS) and not entry.name.startswith(("~$", ".~lock")):
                        progress["files"] += 1
                        yield Path(entry.path)
                except OSError:
                    continue


# ------------------------------------------------------------ what repeats is the office's style
BREAK = re.compile(r"[.!?;:](?=\s+[A-ZĄĆĘŁŃÓŚŹŻ§])")
ABBREVIATIONS = {"art", "ust", "pkt", "nr", "ul", "al", "tj", "tzn", "np", "dz", "poz", "zm", "im", "os", "św", "sp",
                 "o.o", "r", "rep", "lit", "par", "str", "tel", "kod", "godz", "ok", "prof", "dr", "mgr", "inż"}


def sentences(text: str) -> list[str]:
    """Sentences of a deed. Abbreviations ("art.", "ust.") and numbering ("§ 4.") do not end a sentence."""
    out = []
    for paragraph in text.split("\n"):
        paragraph = " ".join(paragraph.split())
        start = 0
        for found in BREAK.finditer(paragraph):
            before = paragraph[start:found.start()].rsplit(" ", 1)[-1].lower()
            if found.group(0) == "." and (before in ABBREVIATIONS or before.isdigit() or len(before) == 1):
                continue
            out.append(paragraph[start:found.end()].strip())
            start = found.end()
        out.append(paragraph[start:].strip())
    return [s for s in out if 25 <= len(s) <= 600]


def key(sentence: str) -> str:
    return re.sub(r"\d+", "#", " ".join(plain(sentence).split()))


def blank_numbers(sentence: str) -> str:
    return re.sub(r"\d+(?:[.,/]\d+)*", "…", sentence)


def learn(acts: dict) -> dict:
    """`acts`: kind -> list of texts. Returns formulas per kind with their share and usual position."""
    formulas = {}
    for kind, texts in acts.items():
        if len(texts) < 2:
            continue
        seen, first, positions = defaultdict(set), {}, defaultdict(list)
        for index, text in enumerate(texts):
            found = sentences(text)
            for place, sentence in enumerate(found):
                k = key(sentence)
                if index not in seen[k]:
                    seen[k].add(index)
                    positions[k].append(place / max(1, len(found) - 1))
                    first.setdefault(k, blank_numbers(sentence))
        need = max(2, round(0.4 * len(texts)))
        kept = [{"text": first[k], "share": round(len(acts_with) / len(texts), 2),
                 "position": round(sum(positions[k]) / len(positions[k]), 3)}
                for k, acts_with in seen.items() if len(acts_with) >= need]
        formulas[kind] = sorted(kept, key=lambda f: f["position"])[:120]
    return formulas


class Style:
    def __init__(self, vault):
        self._vault = vault
        self.progress: dict = {"running": False}
        self._lock = threading.Lock()

    # ---- stored profile
    def profile(self) -> dict | None:
        found = next((d for d in self._vault.summaries({CASE}) if d["name"] == NAME), None)
        if found is None:
            return None
        return json.loads(self._vault.get(found["id"], actor="styl")[2])

    def _store(self, profile: dict, actor: str) -> None:
        data = json.dumps(profile, ensure_ascii=False).encode()
        found = next((d for d in self._vault.summaries({CASE}) if d["name"] == NAME), None)
        if found is None:
            self._vault.put(None, 0, NAME, data, actor=actor, case=CASE)
        else:
            self._vault.put(found["id"], found["version"], NAME, data, actor=actor)

    # ---- scanning
    def scan(self, roots, actor: str, *, seconds: int = 1200) -> dict:
        """Read acts in place under `roots` and store what repeats. Runs for at most `seconds`."""
        with self._lock:
            if self.progress.get("running"):
                raise RuntimeError("a scan is already running")
            self.progress = {"running": True, "files": 0, "acts": 0, "started": time.time(), "roots": [str(r) for r in roots]}
        try:
            acts = defaultdict(list)
            deadline = time.monotonic() + seconds
            for path in walk(roots, deadline, self.progress):
                text = read_text(path)
                if text and is_act(text):
                    acts[kind_of(text)].append(text)
                    self.progress["acts"] += 1
            profile = {
                "updated": int(time.time()), "files_scanned": self.progress["files"],
                "acts": {kind: len(texts) for kind, texts in acts.items()},
                "formulas": learn(acts), "complete": time.monotonic() <= deadline and self.progress["files"] < MAX_FILES,
            }
            self._store(profile, actor)
            return profile
        finally:
            self.progress["running"] = False

    def start(self, roots, actor: str) -> bool:
        if self.progress.get("running"):
            return False
        threading.Thread(target=self._background, args=(roots, actor), daemon=True, name="notarai-styl").start()
        return True

    def _background(self, roots, actor):
        try:
            self.scan(roots, actor)
        except Exception:
            self.progress = {**self.progress, "running": False, "failed": True}

    # ---- using
    def guidance(self, instruction: str) -> str:
        """Formulas for the kind of act asked for, as wording to use verbatim, in order."""
        profile = self.profile()
        if not profile:
            return ""
        kind = kind_of(instruction)
        formulas = profile["formulas"].get(kind) or []
        if not formulas:
            return ""
        lines = "\n".join(f"- {f['text']}" for f in formulas[:60])
        return (f"\n\n=== STYL KANCELARII: STAŁE SFORMUŁOWANIA AKTÓW ({kind}) ===\n"
                "Kancelaria używa tych zdań w swoich aktach. Użyj ich dosłownie, w tej kolejności, w odpowiednich "
                "miejscach projektu; w miejsca oznaczone „…” wstaw dane z dokumentów sprawy.\n" + lines)
