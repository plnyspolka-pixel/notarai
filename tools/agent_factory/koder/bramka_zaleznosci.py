"""Bramka nowych zależności (W3, miara K5 „zmyślone paczki”).

Odrzuca diff, który dopisuje `import x` / `from x import ...` modułu najwyższego poziomu,
którego nie ma w bibliotece standardowej, w repozytorium (plik/katalog w korzeniu, także
nowy plik z tego samego diffu) ani w requirements.txt. Powód odrzucenia: `nowa_zaleznosc`.

API:
    sprawdz_diff(diff_text, repo_root) -> list[Naruszenie]
        diff_text - unified diff zmian agenta (np. `git diff --cached`),
        repo_root - katalog z kodem BAZY (sprzed zmian agenta) i jej requirements.txt.

CLI (kod 1, gdy są naruszenia; na wyjściu JSON bez treści plików):
    git diff --cached | python bramka_zaleznosci.py REPO_ROOT

Ograniczenia: nie widzi `__import__`, `importlib.import_module("x")` ani importów w
plikach innych niż .py; import przeniesiony w obrębie pliku nie jest „nowy”, jeżeli
plik bazy już go miał.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
import re
import sys

POWOD = "nowa_zaleznosc"

# Nazwa dystrybucji z requirements.txt -> moduł importu, tylko tam, gdzie się różnią.
# Reszta: małe litery, "-" i "." -> "_". Lista celowo krótka i jawna.
DYSTRYBUCJA_MODUL = {
    "pyjwt": "jwt", "pillow": "PIL", "beautifulsoup4": "bs4", "pymupdf": "fitz",
    "python-docx": "docx", "pyyaml": "yaml", "dnspython": "dns",
    "websocket-client": "websocket", "python-multipart": "multipart",
    "python-dateutil": "dateutil", "scikit-learn": "sklearn", "opencv-python": "cv2",
}

_PLIK_RE = re.compile(r"^\+\+\+ (?:b/)?(?P<p>\S+)")
_IMPORT_RE = re.compile(r"^\s*import\s+(?P<m>[A-Za-z_][\w.]*(?:\s+as\s+\w+)?(?:\s*,\s*[A-Za-z_][\w.]*(?:\s+as\s+\w+)?)*)")
_FROM_RE = re.compile(r"^\s*from\s+(?P<m>[A-Za-z_][\w.]*)\s+import\b")


@dataclass(frozen=True)
class Naruszenie:
    plik: str
    modul: str
    powod: str = POWOD


def moduly_z_wiersza(wiersz: str) -> set[str]:
    """Moduły najwyższego poziomu z jednego wiersza importu (bez importów względnych)."""
    wiersz = wiersz.split("#", 1)[0]
    m = _FROM_RE.match(wiersz)
    if m:
        return {m.group("m").split(".")[0]}
    m = _IMPORT_RE.match(wiersz)
    if m:
        return {c.strip().split()[0].split(".")[0] for c in m.group("m").split(",") if c.strip()}
    return set()


def moduly_wymagan(requirements: Path) -> set[str]:
    out: set[str] = set()
    if not requirements.is_file():
        return out
    for wiersz in requirements.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)", wiersz.split("#", 1)[0])
        if m:
            nazwa = m.group(1).lower()
            out.add(DYSTRYBUCJA_MODUL.get(nazwa, re.sub(r"[-.]", "_", nazwa)))
    return out


def moduly_lokalne(repo_root: Path) -> set[str]:
    return {p.stem if p.suffix == ".py" else p.name for p in repo_root.iterdir()
            if p.suffix == ".py" or (p.is_dir() and not p.name.startswith("."))}


def dodane_wiersze(diff_text: str) -> dict[str, list[str]]:
    """Plik .py -> wiersze dopisane w diffie."""
    out: dict[str, list[str]] = {}
    plik = None
    for w in diff_text.splitlines():
        if w.startswith("+++ "):
            m = _PLIK_RE.match(w)
            plik = m.group("p") if m and m.group("p") != "/dev/null" else None
            if plik and plik.endswith(".py"):
                out.setdefault(plik, [])
        elif w.startswith("+") and plik and plik.endswith(".py"):
            out[plik].append(w[1:])
    return out


def sprawdz_diff(diff_text: str, repo_root: Path | str) -> list[Naruszenie]:
    repo_root = Path(repo_root)
    dodane = dodane_wiersze(diff_text)
    nowe_lokalne = {Path(p).stem for p in dodane if "/" not in p}
    znane = (set(sys.stdlib_module_names) | moduly_wymagan(repo_root / "requirements.txt")
             | moduly_lokalne(repo_root) | nowe_lokalne)
    out: list[Naruszenie] = []
    for plik, wiersze in sorted(dodane.items()):
        baza = repo_root / plik
        bylo: set[str] = set()
        if baza.is_file():
            for w in baza.read_text(encoding="utf-8", errors="replace").splitlines():
                bylo |= moduly_z_wiersza(w)
        nowe: set[str] = set()
        for w in wiersze:
            nowe |= moduly_z_wiersza(w)
        out += [Naruszenie(plik, m) for m in sorted(nowe - bylo - znane)]
    return out


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print(__doc__)
        return 2
    naruszenia = sprawdz_diff(sys.stdin.read(), Path(argv[0]))
    print(json.dumps({"powod": POWOD if naruszenia else None,
                      "naruszenia": [asdict(n) for n in naruszenia]}, ensure_ascii=False))
    return 1 if naruszenia else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
