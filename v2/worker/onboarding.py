"""First-run guide of the workstation: the office is set up by talking, one step at a time.

Each step is checked against the real state (recovery code enrolled, mail connected, style learned,
a phone paired...), so a step is done only when it is really done. A step can be skipped and come
back later; "przewodnik" shows the whole list at any time. Only the workstation panel sees it.

Activities ("czynności": a KW application, a tax notice, a registry entry...) are learned once by
showing: the first time the notary records doing it, the program keeps the procedure, and from then
on offers to do it automatically (values filled by the program, sending only after approval).
"""
import json
import re
import unicodedata
from pathlib import Path

ACTIVITIES = [
    "Wniosek o wpis w księdze wieczystej (EKW)",
    "Deklaracja PCC-3 i zawiadomienie do urzędu skarbowego",
    "Zawiadomienie gminy o prawie pierwokupu",
    "Rejestr aktów poświadczenia dziedziczenia",
    "Wypisy aktu dla stron i urzędów",
    "Repertorium A",
]
ACT_KINDS = ["Sprzedaż lokalu", "Darowizna", "Umowa deweloperska", "Poświadczenie dziedziczenia",
             "Pełnomocnictwo", "Umowa o podział majątku"]


def slug(text: str) -> str:
    plain = "".join(c for c in unicodedata.normalize("NFD", text.lower().replace("ł", "l"))
                    if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", "-", plain).strip("-")


STEPS = [
    {"key": "kod", "title": "Kod odzyskiwania sejfu",
     "why": "Jedyny klucz do kopii sejfu. Wydrukuj go i schowaj w sejfie kancelarii; bez niego kopii nie da się otworzyć.",
     "actions": [("Utwórz kod odzyskiwania", "kod odzyskiwania")]},
    {"key": "konto", "title": "Zalogowanie stanowiska",
     "why": "Logowanie włącza asystenta AI i przepisywanie mowy we Frankfurcie. Raz na tym komputerze.",
     "actions": [("Zaloguj", "zaloguj")]},
    {"key": "dane", "title": "Gdzie mają być dane",
     "why": "Wybierz, czy mowę przepisuje ten komputer, czy Frankfurt, i czy wysyłać zaszyfrowaną kopię do Frankfurtu.",
     "actions": [("Wybierz", "gdzie są dane")]},
    {"key": "kopia", "title": "Kopia zapasowa",
     "why": "Codzienna kopia na innym dysku (np. pendrive albo dysk sieciowy) albo zaszyfrowana kopia we Frankfurcie.",
     "actions": [("Wskaż dysk na kopie", "wybierz folder kopii"), ("Kopia we Frankfurcie", "gdzie są dane")]},
    {"key": "akty", "title": "Folder z aktami kancelarii",
     "why": "Tam program będzie szukał dotychczasowych aktów i tam podsunie zapis nowych.",
     "actions": [("Wybierz folder aktów", "wybierz folder aktów")]},
    {"key": "styl", "title": "Nauka z dotychczasowych aktów",
     "why": "Program czyta akty na miejscu i zapamiętuje stałe sformułowania kancelarii (nie dane klientów).",
     "actions": [("Ucz się z folderu aktów", "naucz się stylu z folderu aktów")]},
    {"key": "poczta", "title": "Poczta",
     "why": "Outlook albo Thunderbird na tym komputerze: maile od klientów trafią do spraw jednym zdaniem.",
     "actions": [("Połącz pocztę", "połącz pocztę")]},
    {"key": "czynnosci", "title": "Czynności kancelarii: pokaż raz, potem automat",
     "why": "Wybierz czynności, które robicie (wnioski EKW, PCC-3, rejestry). Pierwszy raz robisz ją sam przy "
            "nagrywaniu ekranu i komentarzu; potem program wypełnia ją sam, a wysyła dopiero po Twoim zatwierdzeniu.",
     "actions": [("Wybierz czynności", "czynności")]},
    {"key": "akt", "title": "Pierwszy akt od początku do końca",
     "why": "Próbna sprawa na fikcyjnych danych: pliki do sprawy, projekt aktu, poprawki, zatwierdzenie. "
            "Tak program uczy się Waszego toku pracy.",
     "actions": [("Zacznij próbny akt", "nowa sprawa proba-1"), ("Rodzaje aktów", "rodzaje aktów")]},
    {"key": "telefon", "title": "NotarAI Pocket na telefonie",
     "why": "Zeskanuj kod QR aparatem telefonu; Pocket podpowie, jak dodać go jako aplikację na ekran główny.",
     "actions": [("Dodaj telefon", "dodaj telefon")]},
    {"key": "mikrofony", "title": "Mikrofony w pokojach (nieobowiązkowe)",
     "why": "Tablet albo telefon na ładowarce w sekretariacie lub gabinecie: notatki z rozmów i stenopisy aktów.",
     "actions": [("Dodaj mikrofon", "dodaj mikrofon Sekretariat")]},
]


class Onboarding:
    def __init__(self, home: Path, checks: dict):
        """`checks[key]()` -> bool for steps whose state the program can see itself."""
        self._path = Path(home) / "przewodnik.json"
        self._checks = checks

    # ------------------------------------------------------------ state (no personal data)
    def _load(self) -> dict:
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = {}
        data.setdefault("skipped", [])
        data.setdefault("marked", [])
        data.setdefault("activities", [])
        data.setdefault("finished", False)
        return data

    def _save(self, data: dict) -> None:
        self._path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")

    def mark(self, key: str) -> None:
        data = self._load()
        if key not in data["marked"]:
            data["marked"].append(key)
            self._save(data)

    def skip(self, key: str) -> None:
        data = self._load()
        if key not in data["skipped"]:
            data["skipped"].append(key)
            self._save(data)

    def restart(self) -> None:
        data = self._load()
        data["skipped"], data["finished"] = [], False
        self._save(data)

    # ------------------------------------------------------------ steps
    def done(self, key: str) -> bool:
        data = self._load()
        if key in data["marked"]:
            return True
        if key == "czynnosci":
            return bool(data["activities"]) and self._checks["learned"]() > 0
        check = self._checks.get(key)
        return bool(check and check())

    def status(self) -> list[dict]:
        data = self._load()
        return [{"key": s["key"], "title": s["title"], "done": self.done(s["key"]), "skipped": s["key"] in data["skipped"]}
                for s in STEPS]

    def current(self) -> dict | None:
        """The first step neither done nor skipped; None once the guide is complete."""
        data = self._load()
        if data["finished"]:
            return None
        for index, step in enumerate(STEPS, 1):
            if step["key"] not in data["skipped"] and not self.done(step["key"]):
                return {**step, "number": index, "of": len(STEPS)}
        data["finished"] = True
        self._save(data)
        return None

    # ------------------------------------------------------------ activities
    def activities(self) -> list[str]:
        return self._load()["activities"]

    def choose(self, name: str) -> list[str]:
        name = " ".join(name.split())[:120]
        data = self._load()
        if name and slug(name) not in {slug(a) for a in data["activities"]}:
            data["activities"].append(name)
            self._save(data)
        return data["activities"]

    def drop(self, name: str) -> list[str]:
        data = self._load()
        data["activities"] = [a for a in data["activities"] if slug(a) != slug(name)]
        self._save(data)
        return data["activities"]
