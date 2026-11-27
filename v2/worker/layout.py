"""The notary's own workspace: which tiles are shown, in what order. Simple by default (none).

A tile is a label and the sentence it sends to the chat, so anything that can be said can be a
tile. Layouts are per device; the workstation panel has one of its own.
"""
import json
import os
import threading
from pathlib import Path

MAX_TILES = 40

# Ready-made tools the notary can add. (label, sentence, workstation only)
TOOLS = (
    ("Dokumenty", "dokumenty", False),
    ("Sprawy", "sprawy", False),
    ("Taksa", "taksa", False),
    ("Umowa sprzedaży", "przygotuj umowę sprzedaży", False),
    ("Umowa darowizny", "przygotuj umowę darowizny", False),
    ("Pełnomocnictwo", "przygotuj pełnomocnictwo", False),
    ("Testament", "przygotuj testament", False),
    ("Poświadczenie dziedziczenia", "przygotuj protokół dziedziczenia", False),
    ("Podsumuj sprawę", "podsumuj sprawę w pięciu zdaniach", False),
    ("Czego brakuje?", "jakich dokumentów albo danych brakuje w tej sprawie?", False),
    ("Procedury", "procedury", False),
    ("Poczta", "poczta", True),
    ("Nagraj procedurę", "nagraj procedurę", True),
    ("Programy", "programy", True),
    ("Otwarte do edycji", "otwarte", True),
    ("Zrób kopię", "zrób kopię", True),
    ("Stan stanowiska", "stan", True),
    ("Urządzenia", "urządzenia", True),
    ("Dodaj telefon", "dodaj telefon", True),
    ("Dziennik", "dziennik", True),
    ("Zużycie AI", "zużycie", True),
)


def tools_for(admin: bool) -> list[dict]:
    return [{"label": label, "say": say} for label, say, workstation in TOOLS if admin or not workstation]


def clean(layout) -> dict:
    """Validate what a page or a chat command wants to store."""
    if not isinstance(layout, dict):
        raise ValueError("invalid layout")
    tiles, seen = [], set()
    for tile in layout.get("tiles") or []:
        label = " ".join(str(tile.get("label", "")).split())[:40]
        say = " ".join(str(tile.get("say", "")).split())[:200]
        if not label or not say or label.lower() in seen:
            continue
        seen.add(label.lower())
        tiles.append({"label": label, "say": say})
    if len(tiles) > MAX_TILES:
        raise ValueError("too many tiles")
    return {"show": bool(layout.get("show")) and bool(tiles), "tiles": tiles}


class Layouts:
    def __init__(self, home: Path):
        self._path, self._lock = Path(home) / "layouts.json", threading.Lock()

    def _all(self) -> dict:
        try:
            return json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def get(self, key: str) -> dict:
        return clean(self._all().get(key) or {})

    def put(self, key: str, layout) -> dict:
        layout = clean(layout)
        with self._lock:
            everything = self._all()
            everything[key] = layout
            temporary = self._path.with_name("layouts.json.new")
            temporary.write_text(json.dumps(everything, ensure_ascii=False), encoding="utf-8")
            os.replace(temporary, self._path)
        return layout
