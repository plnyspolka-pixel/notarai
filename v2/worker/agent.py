"""The computer agent: NotarAI does what the notary asks on this computer, step by step.

Owner's decision 27.11.2026: on the workstation the notary's sentence ("otwórz akt Kowalskiego w Wordzie
i popraw datę", "wejdź na stronę sądu i pobierz…") is carried out by the program itself: it reads files
anywhere on the disk, starts programs, types and clicks in Windows programs (UI Automation) and in the
NotarAI browser. The command is the approval. What the code still holds back, whatever the model says:

- nothing is deleted: there is no tool for it, and an existing file is changed only by replacing words
  in it (a copy of the previous version is kept in the program's folder first);
- a click or key that sends, submits, signs, pays or deletes runs only when the notary's own sentence
  asked for that kind of act; otherwise the agent stops and the chat asks „Tak / Nie”;
- every document saved goes through the office's rules (`check_document`), every send through
  `check_send`; each act runs once, never repeated after an uncertain result;
- text (file text, window fields, page text) is pseudonymised like every other call through `inference.py`;
- owner's decision 27.11.2026 (2.7.0): the agent may also look at the screen. A screenshot goes to the model in
  the EU as it is (names in a picture cannot be replaced), every look is said in the chat, and the station can
  switch it off („wyłącz zrzuty ekranu agenta”). With a picture the agent can click a point and type, which
  reaches programs that expose no fields;
- owner's decision 27.11.2026 (2.7.0): the agent may run a program with arguments (command line). Never through
  a shell: no cmd, PowerShell, script hosts or interpreters, no script files, no system tools that delete,
  format or change accounts; AWS credentials are not passed on; a command whose words name an irreversible act
  runs only when the notary asked for that act. The station can switch it off („wyłącz wiersz poleceń agenta”).

Every step is narrated in the chat; nothing of the content is logged.
"""
import json
import os
import re
import secrets
import shutil
import string
import subprocess
import time
import unicodedata
from pathlib import Path

MAX_STEPS = 80             # one run; the chat offers „Kontynuuj” after that (2.8.0: 24 ended ordinary work half way)
KEEP_FULL = 8              # the newest steps stay whole in the transcript; older ones shrink to their first lines
MAX_SEEN = 9000            # characters of one observation shown to the model
MAX_HISTORY = 60000

ACTS = {                   # kinds of irreversible act -> words that name them (normalised, no accents)
    "wyslanie": ("wyslij", "wyslac", "przeslij", "nadaj", "send", "submit", "zloz", "zlozyc", "zatwierdz",
                 "potwierdz", "dalej i wyslij"),
    "podpis": ("podpisz", "podpisac", "sign"),
    "platnosc": ("zaplac", "oplac", "zaplacic", "kup teraz", "zamow", "pay"),
    "usuniecie": ("usun", "usunac", "skasuj", "wyczysc", "delete", "remove"),
}

# Never started by the agent, whatever the sentence: shells and interpreters (they would run anything, deleting
# included), script hosts, and system tools that delete, format, or change accounts, services and the registry.
BLOCKED_PROGRAMS = frozenset({
    "cmd", "command", "powershell", "pwsh", "powershell_ise", "wt", "bash", "sh", "wsl", "ssh", "conhost",
    "wscript", "cscript", "mshta", "rundll32", "regsvr32", "msiexec", "installutil", "msbuild",
    "python", "pythonw", "py", "pyw", "node", "deno", "bun", "ruby", "perl", "php", "java", "javaw", "lua",
    "reg", "regedit", "regedt32", "format", "diskpart", "chkdsk", "sdelete", "cipher", "bcdedit", "vssadmin", "wbadmin",
    "shutdown", "logoff", "net", "net1", "sc", "schtasks", "at", "taskkill", "tskill", "takeown", "icacls", "cacls",
    "attrib", "robocopy", "xcopy", "wmic", "fsutil", "mountvol", "subst", "runas", "psexec", "forfiles", "where",
    "certutil", "bitsadmin", "curl", "wget", "ftp", "tftp", "telnet", "netsh", "dism", "sfc", "wevtutil", "rd", "del",
})
# Remote help and remote desktop: never started by the agent, whatever the sentence (owner's decision 27.11.2026,
# after the agent opened a remote support window on its own). Someone else at the keyboard is the notary's call.
REMOTE_HELP = ("quickassist", "msra", "mstsc", "teamviewer", "anydesk", "rustdesk", "ammyy", "supremo", "splashtop",
               "remotepc", "logmein", "screenconnect", "connectwise", "ultraviewer", "aeroadmin", "zohoassist",
               "zoho assist", "remote desktop", "remoteassistance", "remote assistance", "pomoc zdalna", "szybka pomoc",
               "pulpit zdalny", "zdalnej pomocy", "zdalna pomoc", "pomoc techniczna", "remotehelp", "bomgar", "beyondtrust",
               "dwservice", "nomachine", "parsec", "tightvnc", "ultravnc", "realvnc", "vncviewer", "radmin", "netsupport")
RUNNABLE = (".exe", ".com")


def remote_help(text) -> bool:
    words = plain(text).replace("-", " ").replace("_", " ")
    return any(name in words or name.replace(" ", "") in words.replace(" ", "") for name in REMOTE_HELP)
COMMAND_ACTS = {            # words of a command line that name an irreversible act
    "usuniecie": ("delete", "del", "remove", "rm", "erase", "purge", "drop", "uninstall", "clear", "clean", "wipe", "usun"),
    "wyslanie": ("send", "submit", "upload", "publish", "post", "mail", "wyslij"),
    "podpis": ("sign", "podpisz"),
    "platnosc": ("pay", "zaplac"),
}

SYSTEM_AGENT = (
    "Jesteś NotarAI, programem na komputerze polskiej kancelarii notarialnej (Windows). Wykonujesz polecenie "
    "notariusza na tym komputerze krok po kroku. W każdej odpowiedzi podaj DOKŁADNIE JEDEN obiekt JSON (bez innego "
    "tekstu) w postaci {\"po_co\": \"jedno krótkie zdanie po polsku\", \"krok\": nazwa, ...argumenty}. Dostępne kroki:\n"
    "- {\"krok\":\"pliki\",\"folder\":ścieżka} – zawartość folderu (\"\" = foldery startowe: Pulpit, Dokumenty, Pobrane, akty)\n"
    "- {\"krok\":\"szukaj\",\"nazwa\":słowa,\"folder\":ścieżka lub \"\"} – pliki, których nazwa zawiera te słowa\n"
    "- {\"krok\":\"czytaj\",\"plik\":ścieżka} – tekst pliku DOCX, PDF, TXT, EML\n"
    "- {\"krok\":\"zamien\",\"plik\":ścieżka,\"stare\":tekst,\"nowe\":tekst} – zamiana tekstu w pliku DOCX lub TXT "
    "(zapisuje plik; poprzednia wersja zostaje w kopii programu)\n"
    "- {\"krok\":\"nowy_plik\",\"plik\":ścieżka,\"tekst\":treść} – nowy plik DOCX lub TXT (nie nadpisuje istniejącego)\n"
    "- {\"krok\":\"uruchom\",\"co\":ścieżka pliku, folderu albo nazwa programu} – otwiera w domyślnym programie\n"
    "- {\"krok\":\"okna\"} – tytuły otwartych okien\n"
    "- {\"krok\":\"okno\",\"okno\":fragment tytułu} – pola, przyciski i teksty tego okna\n"
    "- {\"krok\":\"wpisz\",\"okno\":…,\"pole\":etykieta,\"wartosc\":tekst} – wpisuje w pole okna\n"
    "- {\"krok\":\"kliknij\",\"okno\":…,\"przycisk\":etykieta}\n"
    "- {\"krok\":\"klawisze\",\"okno\":…,\"klawisze\":np. \"^s\" (Ctrl+S), \"{ENTER}\"}\n"
    "- {\"krok\":\"strona\",\"adres\":https://…} – otwiera stronę w przeglądarce NotarAI\n"
    "- {\"krok\":\"widok\"} – tekst, pola i odnośniki otwartej strony\n"
    "- {\"krok\":\"web_wpisz\",\"pole\":etykieta,\"wartosc\":tekst}\n"
    "- {\"krok\":\"web_kliknij\",\"co\":etykieta przycisku albo tekst odnośnika}\n"
    "- {\"krok\":\"ekran\",\"okno\":fragment tytułu albo \"\"} – zrzut całego ekranu (z tym oknem na wierzchu); zobaczysz go "
    "w następnym kroku. Używaj, gdy okno nie pokazuje pól albo nie wiesz, co jest na ekranie\n"
    "- {\"krok\":\"kliknij_punkt\",\"x\":liczba,\"y\":liczba,\"co\":napis na tym elemencie,\"dwuklik\":false} – klika w punkt "
    "ostatniego zrzutu (piksele obrazu, lewy górny róg = 0,0)\n"
    "- {\"krok\":\"pisz\",\"tekst\":tekst} – wpisuje tekst z klawiatury tam, gdzie jest kursor (po kliknięciu w pole)\n"
    "- {\"krok\":\"narzedzia\"} – programy sterowane z wiersza poleceń znalezione na tym komputerze (cli-anything-*, winapp)\n"
    "- {\"krok\":\"polecenie\",\"program\":nazwa albo ścieżka .exe,\"argumenty\":[lista napisów]} – uruchamia program z argumentami "
    "i zwraca to, co wypisał (bez powłoki: żadnych |, >, &&; cmd, PowerShell i skrypty są niedostępne). Opcje programu poznasz "
    "argumentem --help\n"
    "- {\"krok\":\"notatka\",\"program\":nazwa programu albo adres strony,\"tekst\":jedno zdanie o drodze przez program} – "
    "zapamiętuje na przyszłość, jak dojść do ekranu albo funkcji (menu, zakładki, przyciski); bez danych osób i numerów\n"
    "- {\"krok\":\"pytanie\",\"problem\":co Cię blokuje, jednym zdaniem,\"opcje\":[2-4 krótkie możliwości, co dalej]} – "
    "gdy utkniesz (kilka prób bez skutku, niejasne okno, kilka możliwych dróg) NIE zgaduj: zapytaj notariusza; po "
    "odpowiedzi pracujesz dalej, a program zapamięta wniosek\n"
    "- {\"krok\":\"koniec\",\"odpowiedz\":co zrobiłeś i co z tego wynika, po polsku, krótko}\n"
    "Najpierw plan: jeśli niżej jest MAPA PROGRAMU dla tego programu, idź prosto po znanej drodze, a gdy jest tam "
    "SPRAWDZONA DROGA dla tej czynności, wykonaj dokładnie jej kroki po kolei, bez rozglądania się i bez zrzutów. Jeśli mapy nie ma, "
    "najpierw poznaj program (okno albo widok głównego ekranu, potem menu i zakładki, bez zapisywania czegokolwiek), zapisz "
    "drogę krokiem notatka i dopiero wtedy wykonuj polecenie. Gdy polecenie dotyczy kilku pozycji (np. kilku aktów), "
    "rób je po kolei i nie kończ, póki wszystkie nie są przygotowane. Logowania, certyfikatu, PIN-u, hasła, podpisu i "
    "płatności nie wykonujesz nigdy: przygotuj wszystko i zakończ, mówiąc, co czeka na notariusza. "
    "W starszych programach część pól przychodzi jako „pole bez nazwy N” (program rysuje podpisy sam): zrób wtedy JEDEN "
    "zrzut ekranu, ustal, które pole jest którym, zapisz to krokiem notatka (np. „ekran Nowy wpis: pole bez nazwy 1 = "
    "data aktu”) i dalej wpisuj krokiem wpisz po tych nazwach, nie klikaniem w punkt. "
    "Pracujesz W TLE: okno programu zostaje pod oknami notariusza, nie wychodzi na wierzch, mysz i klawiatura są jego. "
    "Dlatego używaj kroków okno, wpisz i kliknij (działają bez wyciągania okna), a krok ekran zawsze z nazwą okna "
    "(program sfotografuje je w tle). Kroków klawisze oraz ekran bez nazwy okna unikaj: wymagają okna na wierzchu i "
    "zgody notariusza. "
    "Listy rozwijane ([select]) ustawiasz krokiem wpisz z wartością równą jednej z pozycji; nie rozwijaj ich klikaniem "
    "ani zrzutem. Krok kliknij na liście tylko podaje jej pozycje. Po każdym kliknięciu wynik mówi, co się w oknie "
    "pojawiło, zmieniło i zniknęło: czytaj to, zanim uznasz, że coś nie zadziałało. "
    "- {\"krok\":\"punkt\",\"okno\":fragment tytułu,\"nazwa\":nazwa z listy NAUCZONE PUNKTY} – naciska miejsce w oknie, które "
    "notariusz pokazał wcześniej jednym kliknięciem (panel, ikona, kafelek rysowany przez program)\n"
    "MENU PRZED PANELEM: w starszych programach panele boczne, kafelki i ikony są rysowane i nie mają nazw, ale menu "
    "główne je ma. Do modułu albo funkcji idź najpierw pozycją z dopiskiem (menu) albo (zakładka), potem nauczonym "
    "punktem (krok punkt). Gdy element jest tylko narysowany i nie ma go ani w menu, ani wśród nauczonych punktów, nie "
    "próbuj trafiać w niego na ślepo: zadaj pytanie krokiem pytanie z dodatkowymi polami \"punkt\": nazwa tego elementu i "
    "\"okno\": fragment tytułu okna; notariusz kliknie go raz i odtąd masz go jako nauczony punkt. "
    "Kolejność prób w programie Windows: najpierw okno/wpisz/kliknij (pola po nazwach); gdy okno nie ma pól, ekran i "
    "kliknij_punkt/pisz; gdy program ma własny wiersz poleceń albo narzędzie cli-anything, polecenie. "
    "Zasady: działaj samodzielnie, nie pytaj o rzeczy, które możesz sprawdzić. Zanim zmienisz plik, przeczytaj go. "
    "Nie zgaduj ścieżek: najpierw szukaj. Plików nie usuwasz. Wysłanie, złożenie, podpis, zapłata albo usunięcie "
    "tylko wtedy, gdy notariusz o to poprosił. Gdy czegoś nie da się zrobić, zakończ krokiem koniec i powiedz "
    "dlaczego oraz co notariusz może zrobić. Znaczniki w nawiasach kwadratowych zastępują dane osobowe: przepisuj je "
    "bez zmian, program podstawi prawdziwe wartości."
)


class AgentError(Exception):
    """Fixed Polish message, safe to show."""


class NeedFront(AgentError):
    """This step cannot be done with the window left under the notary's work: it needs the window in front, the
    mouse or the keyboard for a moment. The run stops and the notary decides (owner's decision 28.11.2026)."""


def plain(text) -> str:
    text = unicodedata.normalize("NFD", str(text).lower().replace("ł", "l"))
    return " ".join("".join(c for c in text if unicodedata.category(c) != "Mn").split())


# Acts the agent never performs, whatever the sentence says (owner's decision 27.11.2026, 2.8.0): it prepares
# everything, shows the window and hands over. Signing and paying are the notary's own; logging in needs the
# notary's certificate, PIN or password.
HANDOVER = {
    "logowanie": ("zaloguj", "zalogowac", "logowanie", "logowania", "certyfikat", "certyfikatem", "pin", "haslo",
                  "log in", "login", "sign in"),
}
NEVER = frozenset({"logowanie", "podpis", "platnosc"})


def act_kind(label: str) -> str | None:
    """The irreversible act a button or key names, if any."""
    words = plain(label)
    for kind, names in HANDOVER.items():          # „sign in” is a login, not a signature
        if any(re.search(r"(^|[^a-z])" + re.escape(name) + r"($|[^a-z])", words) for name in names):
            return kind
    for kind, names in ACTS.items():
        if any(re.search(r"(^|[^a-z])" + re.escape(name) + r"($|[^a-z])", words) for name in names):
            return kind
    return None


def asked_for(task: str) -> set[str]:
    """Kinds of irreversible act the notary's own sentence asks for (decided by code, not by the model)."""
    words = plain(task)
    endings = "(|c|ac|ic|my|cie|e)"               # wyślij / wysłać / usuń / usunąć / złóż / złóżcie…
    return {kind for kind, names in ACTS.items()
            if any(re.search(r"(^|[^a-z])" + re.escape(name) + endings + r"($|[^a-z])", words) for name in names)}


def parse_step(answer: str) -> dict:
    found = re.search(r"\{.*\}", answer, re.S)
    if not found:
        raise ValueError("no json")
    step = json.loads(found.group(0))
    if not isinstance(step, dict) or not isinstance(step.get("krok"), str):
        raise ValueError("no step")
    return step


# ------------------------------------------------------------------ what the agent remembers about programs
class ProgramMap:
    """Screens, fields and buttons of the programs and sites the agent has seen, kept between tasks.

    Built by code from what the agent reads (`okno`, `widok`): names of fields and buttons only, never their
    values, and nothing that looks like a number of a person or a case. The agent adds short notes about the
    way through a program (`notatka`). Next time the map is in front of the model from the first step, so it
    does not wander. Stored on this computer, next to the program's own data."""

    MAX_PROGRAMS, MAX_SCREENS, MAX_LABELS, MAX_NOTES = 30, 40, 60, 30

    def __init__(self, home: Path):
        self._path = Path(home) / "mapa-programow.json"

    def _load(self) -> dict:
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

    def _save(self, data: dict) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self._path.with_suffix(".tmp")
            temporary.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            os.replace(temporary, self._path)
        except OSError:
            pass                                   # the map is a convenience; a full disk must not stop the work

    @staticmethod
    def _safe(label) -> str | None:
        label = " ".join(str(label or "").split())[:60]
        if len(label) < 2 or re.search(r"\d{5,}|@|\[[A-Z_]+\d*\]", label):
            return None                            # numbers of people and cases, e-mails, placeholders: not a name of a field
        return label

    @staticmethod
    def key(name: str) -> str:
        """A program by the last part of its window title („Dokument1 - Word” -> „word”), a site by its host."""
        host = re.match(r"https?://([^/:]+)", name or "")
        if host:
            return host.group(1).lower().removeprefix("www.")
        parts = [part.strip() for part in re.split(r"\s[-–—|]\s", name or "") if part.strip()]
        return plain(parts[-1] if parts else name)[:60]

    def record(self, program: str, screen: str, controls) -> None:
        program, screen = self.key(program), (self._safe(screen) or "ekran")
        if not program:
            return
        fields = [l for l in (self._safe(c.label) for c in controls if c.kind in {"text", "select", "check"}) if l]
        buttons = [l for l in (self._safe(c.label) for c in controls if c.kind == "button") if l]
        if not fields and not buttons:
            return
        data = self._load()
        if program not in data and len(data) >= self.MAX_PROGRAMS:
            return
        entry = data.setdefault(program, {"ekrany": {}, "notatki": []})
        if screen not in entry["ekrany"] and len(entry["ekrany"]) >= self.MAX_SCREENS:
            return
        known = entry["ekrany"].setdefault(screen, {"pola": [], "przyciski": []})
        before = json.dumps(known, sort_keys=True)
        known["pola"] = list(dict.fromkeys(known["pola"] + fields))[:self.MAX_LABELS]
        known["przyciski"] = list(dict.fromkeys(known["przyciski"] + buttons))[:self.MAX_LABELS]
        if json.dumps(known, sort_keys=True) != before:
            self._save(data)

    def note(self, program: str, text_: str) -> str:
        program = self.key(program)
        note = " ".join(str(text_ or "").split())[:300]
        if not program or len(note) < 8:
            raise AgentError("Podaj program i notatkę.")
        if re.search(r"\d{5,}|@|\[[A-Z_]+\d*\]", note):
            raise AgentError("Notatka ma opisywać drogę przez program (menu, ekrany, przyciski), bez danych osób i numerów.")
        data = self._load()
        entry = data.setdefault(program, {"ekrany": {}, "notatki": []})
        if note not in entry["notatki"]:
            entry["notatki"] = (entry["notatki"] + [note])[-self.MAX_NOTES:]
            self._save(data)
        return f"Zapamiętałem o programie „{program}”."

    MAX_ROUTES, MAX_POINTS = 6, 60

    def point(self, program: str, name: str, fx: float, fy: float) -> bool:
        """A place in the program's window the notary showed with one click: its name and where it lies as a share of
        the window's width and height (so it survives another window size). Nothing of what is written there."""
        program, name = self.key(program), self._safe(name)
        if not program or not name or not (0 <= fx <= 1 and 0 <= fy <= 1):
            return False
        data = self._load()
        entry = data.setdefault(program, {"ekrany": {}, "notatki": []})
        points = entry.setdefault("punkty", {})
        if name not in points and len(points) >= self.MAX_POINTS:
            return False
        points[name] = {"x": round(fx, 4), "y": round(fy, 4)}
        self._save(data)
        return True

    def points(self, program: str) -> dict:
        return dict(self._load().get(self.key(program), {}).get("punkty", {}))

    def route(self, program: str, purpose: str, steps: list[str]) -> None:
        """A way through the program that ended well, as names of what was pressed and filled (never values).
        For one purpose only the shortest known way is kept: each good repetition can only make it shorter."""
        program, purpose = self.key(program), plain(purpose)[:30]
        steps = [step for step in (self._safe(s) for s in steps) if step][:40]
        if not program or not purpose or len(steps) < 2:
            return
        data = self._load()
        entry = data.setdefault(program, {"ekrany": {}, "notatki": []})
        routes = entry.setdefault("drogi", {})
        known = routes.get(purpose)
        if known is not None and len(known["kroki"]) <= len(steps):
            known["razy"] = known.get("razy", 1) + 1
        else:
            if purpose not in routes and len(routes) >= self.MAX_ROUTES:
                return
            routes[purpose] = {"kroki": steps, "razy": (known or {}).get("razy", 0) + 1}
        self._save(data)

    def programs(self) -> list[str]:
        return sorted(self._load())

    def forget(self, program: str) -> bool:
        data = self._load()
        hit = next((k for k in data if plain(program) in k), None)
        if hit is None:
            return False
        del data[hit]
        self._save(data)
        return True

    def describe(self, program: str | None = None, limit: int = 7000) -> str:
        data = self._load()
        if program is not None:
            data = {k: v for k, v in data.items() if plain(program) in k}
        lines = []
        for name, entry in sorted(data.items()):
            lines.append(f"PROGRAM {name}")
            lines += [f"  droga: {note}" for note in entry.get("notatki", [])]
            if entry.get("punkty"):
                lines.append("  NAUCZONE PUNKTY (pokazane przez notariusza, krok punkt): " + ", ".join(entry["punkty"]))
            for purpose, way in entry.get("drogi", {}).items():
                lines.append(f"  SPRAWDZONA DROGA „{purpose}” ({len(way['kroki'])} kroków, udana {way.get('razy', 1)} razy): "
                             + " -> ".join(way["kroki"]))
            for screen, parts in entry.get("ekrany", {}).items():
                lines.append(f"  ekran „{screen}”: pola: {', '.join(parts['pola']) or '-'}; przyciski: {', '.join(parts['przyciski']) or '-'}")
        return "\n".join(lines)[:limit]


# ------------------------------------------------------------------ the log of each run, kept for learning
class RunLog:
    """One file per run in `dziennik-agenta`: every step as kind, place and the NAME of the field or button, whether
    it worked and how long it took. Never a value typed, a file's text, a path or a screenshot; the notary's sentence
    is kept without names and numbers. From these files the office and the program see where time is lost
    (owner's decision 28.11.2026). The exact live log with values stays in memory only."""

    KEEP = 60

    def __init__(self, home: Path, task: str):
        self._folder = Path(home) / "dziennik-agenta"
        self._lines, self._started = [], time.time()
        self._path = self._folder / (time.strftime("%Y%m%d-%H%M%S") + f"-{secrets.token_hex(2)}.jsonl")
        self._lines.append({"zadanie": self.shape(task), "start": time.strftime("%Y-%m-%d %H:%M:%S")})

    @staticmethod
    def shape(task: str) -> str:
        """The sentence without what could name a person or a case: capitalised words after the first, and digits."""
        words = str(task).split()
        kept = [w if i == 0 or not w[:1].isupper() else "…" for i, w in enumerate(words)]
        return re.sub(r"\d", "#", " ".join(kept))[:200]

    @staticmethod
    def place(step) -> tuple[str, str]:
        kind = step.get("krok", "")
        where = ProgramMap.key(str(step.get("okno") or step.get("adres") or "")) if step.get("okno") or step.get("adres") else ""
        what = ProgramMap._safe(step.get("pole") or step.get("przycisk") or step.get("co") or (
            step.get("program") if kind == "polecenie" else "") or (step.get("nazwa") if kind == "punkt" else "")) or ""
        return where, what

    def step(self, step, outcome: str, seconds: float, *, state: str = "ok") -> None:
        where, what = self.place(step)
        line = {"t": round(time.time() - self._started, 1), "krok": step.get("krok", ""), "gdzie": where, "co": what,
                "stan": state, "s": round(seconds, 1)}
        if outcome.startswith("BŁĄD"):
            line["stan"] = "blad" if state == "ok" else state
            line["blad"] = re.sub(r"\d", "#", re.sub(r"„[^”]*”", "„…”", outcome))[:120]
        self._lines.append(line)

    def end(self, how: str) -> None:
        steps = [l for l in self._lines if "krok" in l]
        self._lines.append({"koniec": how, "krokow": len(steps), "bledow": sum(1 for l in steps if l["stan"] == "blad"),
                            "cofnietych": sum(1 for l in steps if l["stan"] == "cofniety"),
                            "sekund": round(time.time() - self._started)})
        try:
            self._folder.mkdir(parents=True, exist_ok=True)
            self._path.write_text("\n".join(json.dumps(l, ensure_ascii=False) for l in self._lines) + "\n", encoding="utf-8")
            for old in sorted(self._folder.glob("*.jsonl"))[:-self.KEEP]:
                old.unlink(missing_ok=True)
        except OSError:
            pass                                   # the log is for learning; it must never stop the work

    @staticmethod
    def recent(home: Path, count: int = 5) -> list[tuple[str, list]]:
        folder = Path(home) / "dziennik-agenta"
        runs = []
        for path in sorted(folder.glob("*.jsonl"), reverse=True)[:count]:
            try:
                runs.append((str(path), [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]))
            except (OSError, ValueError):
                continue
        return runs


# ------------------------------------------------------------------ the computer
class Computer:
    """What the agent can touch. Every method returns text for the model (and raises AgentError)."""

    READABLE = (".docx", ".pdf", ".txt", ".eml", ".csv", ".md", ".xml", ".html", ".htm")

    def __init__(self, home: Path, *, desktop=None, browser=None, roots=None, starter=None, rules=None,
                 grabber=None, pointer=None, typist=None, runner=None, label_at=None, allowed=None, which=None,
                 clicks=None):
        """`allowed()` -> {"screen": bool, "commands": bool}: what the station lets the agent do (settings)."""
        self._home = Path(home)
        self._desktop, self._browser = desktop, browser          # callables returning the targets
        self._roots, self._starter, self._rules = roots, starter, rules
        self._grabber, self._pointer, self._typist, self._runner = grabber, pointer, typist, runner
        self._clicks = clicks                                    # the notary's own click, for learning a point
        self._label_at, self._allowed, self._which = label_at, allowed, which or shutil.which
        self._scale = None                                       # screen pixels per pixel of the last screenshot
        self.map = ProgramMap(self._home)
        self.used_browser = False                                # this run touched the NotarAI browser
        self.seen = None             # seen(jpeg): the chat shows what the browser shows now (set for each run)
        self.login_needed = None                                 # a login screen was just read: where
        self.read_windows = {}                                   # window -> names of its buttons, as last read (this run)
        self.front_allowed = False                               # the notary allowed the front for this run
        self._current, self._shot_of, self._origin = None, None, (0, 0)
        self.fields_seen = 0
        self.picture = None                                      # JPEG for the model's next turn, taken once

    def _may(self, what: str) -> bool:
        return True if self._allowed is None else bool(self._allowed().get(what, True))

    def _quiet(self) -> bool:
        """Work out of the notary's way: no window brought to the front, mouse and keyboard left alone."""
        return self._allowed is not None and bool(self._allowed().get("background", False))

    def _borrow(self, what: str, action, desktop=None):
        """The one step that needs the front: only with the notary's word, and the screen is given back at once."""
        if not self._quiet():
            return action()
        if not self.front_allowed:
            raise NeedFront(what)
        before = desktop.to_front() if desktop is not None and hasattr(desktop, "to_front") else None
        try:
            time.sleep(0 if self._grabber or self._pointer or self._typist else 0.3)
            return action()
        finally:
            if desktop is not None and hasattr(desktop, "give_back"):
                desktop.give_back(before)

    # ---- the screen (owner's decision 27.11.2026)
    @staticmethod
    def _grab():
        if os.name != "nt":
            raise AgentError("Ekran widzę tylko na Windows.")
        import io

        from PIL import ImageGrab

        shot = ImageGrab.grab()                                   # the primary screen: one coordinate system
        width = shot.width
        shot.thumbnail((1568, 1568))
        out = io.BytesIO()
        shot.convert("RGB").save(out, "JPEG", quality=70)
        return out.getvalue(), width / shot.width, (shot.width, shot.height)

    def screen(self, title: str = "") -> str:
        if not self._may("screen"):
            raise AgentError("Zrzuty ekranu dla agenta są wyłączone na tym stanowisku („włącz zrzuty ekranu agenta”).")
        desktop = self._window(title) if title else self._current
        if self._quiet() and desktop is not None and hasattr(desktop, "capture"):
            shot = desktop.capture()                 # the window itself, wherever it lies: nothing comes to the front
            if shot is not None:
                self.picture, self._scale, size, self._origin = shot
                self._shot_of = desktop
                return (f"Zrzut okna {size[0]}x{size[1]} pikseli (zrobiony w tle, okno nie wyszło na wierzch) jest dołączony "
                        "do tej wiadomości (tylko teraz).")

        def whole():
            if title and not self._quiet():
                time.sleep(0 if self._grabber else 0.4)
            try:
                return (self._grabber or self._grab)()
            except AgentError:
                raise
            except Exception:
                raise AgentError("Nie udało się zrobić zrzutu ekranu.") from None
        picture, scale, size = self._borrow("zrzut ekranu (tego okna nie da się sfotografować w tle)", whole, desktop)
        self.picture, self._scale, self._origin, self._shot_of = picture, scale, (0, 0), None
        return f"Zrzut ekranu {size[0]}x{size[1]} pikseli jest dołączony do tej wiadomości (tylko teraz)."

    def _point(self, x, y) -> tuple[int, int]:
        if self._scale is None:
            raise AgentError("Najpierw zrób zrzut krokiem „ekran”: punkt podaje się na ostatnim zrzucie.")
        try:
            return round(float(x) * self._scale), round(float(y) * self._scale)
        except (TypeError, ValueError):
            raise AgentError("Podaj x i y jako liczby.") from None

    def label_at(self, x, y) -> str:
        """What Windows itself calls the element under the point ("" when it does not say)."""
        try:
            px, py = self._point(x, y)
            px, py = px + self._origin[0], py + self._origin[1]        # a window's picture: its place on the screen
            if self._label_at is not None:
                return str(self._label_at(px, py) or "")
            if os.name != "nt":
                return ""
            from pywinauto import Desktop as UiaDesktop

            return str(UiaDesktop(backend="uia").from_point(px, py).element_info.name or "")
        except Exception:
            return ""

    def click_point(self, x, y, double: bool = False) -> str:
        px, py = self._point(x, y)
        target = self._shot_of
        if target is not None and target.click_at(px, py, double):       # a message to the window: the mouse does not move
            self._scale = None
            return "Kliknąłem w punkt okna (w tle, bez ruchu myszy). Zrób nowy zrzut, żeby zobaczyć wynik."
        sx, sy = px + self._origin[0], py + self._origin[1]

        def with_mouse():
            if self._pointer is not None:
                self._pointer(sx, sy, double)
                return
            try:
                from pywinauto import mouse
            except Exception:
                raise AgentError("W punkt klikam tylko na Windows.") from None
            (mouse.double_click if double else mouse.click)(coords=(sx, sy))
            time.sleep(0.8)
        self._borrow("kliknięcie myszą w punkt ekranu", with_mouse, target or self._current)
        self._scale = None            # the screen has changed: the next point needs a new screenshot
        return "Kliknąłem w punkt. Zrób nowy zrzut, żeby zobaczyć wynik."

    def write(self, value: str) -> str:
        if not value:
            raise AgentError("Brak tekstu do wpisania.")
        target = self._shot_of or self._current
        if self._quiet() and target is not None and hasattr(target, "send_text") and target.send_text(value):
            return f"Wpisałem {len(value)} znaków w kliknięte pole (w tle, bez klawiatury)."

        def with_keyboard():
            if self._typist is not None:
                self._typist(value)
                return
            try:
                from pywinauto.keyboard import send_keys
            except Exception:
                raise AgentError("Z klawiatury piszę tylko na Windows.") from None
            escaped = re.sub(r"([+^%~(){}\[\]])", r"{\1}", value).replace("\n", "{ENTER}")
            send_keys(escaped, with_spaces=True, with_tabs=True, pause=0.01)
        self._borrow("pisanie z klawiatury w oknie programu", with_keyboard, target)
        return f"Wpisałem z klawiatury {len(value)} znaków."

    # ---- command line (owner's decision 27.11.2026): one program with arguments, never a shell
    def _program(self, program: str) -> Path:
        name = program.strip().strip('"') if isinstance(program, str) else ""
        if not name:
            raise AgentError("Jaki program uruchomić?")
        found = Path(name) if Path(name).is_absolute() and Path(name).is_file() else None
        if found is None:
            located = self._which(name)
            if not located:
                raise AgentError(f"Nie ma na tym komputerze programu „{name}” (krok „narzedzia” pokaże dostępne).")
            found = Path(located)
        # Judged by the file's own name, read the Windows way whatever system this runs on.
        name = re.split(r"[\\/]", str(found))[-1].strip(" .").lower()
        stem, _, suffix = name.rpartition(".") if "." in name else (name, "", "")
        if suffix in {"bat", "cmd", "ps1", "psm1", "vbs", "vbe", "js", "jse", "wsf", "wsh", "msi", "msp", "scr", "lnk", "hta", "py"}:
            raise AgentError("Uruchamiam tylko programy .exe; skryptów (.bat, .cmd, .ps1, .vbs) nie.")
        if os.name == "nt" and "." + suffix not in RUNNABLE:
            raise AgentError("Uruchamiam tylko programy .exe.")
        if remote_help(stem) or remote_help(program):
            raise AgentError("Programów pomocy zdalnej i pulpitu zdalnego nie uruchamiam. Jeśli ich potrzebujesz, "
                             "uruchom je sam.")
        if stem in BLOCKED_PROGRAMS or stem.split(".")[0] in BLOCKED_PROGRAMS:
            raise AgentError(f"Programu „{stem}” nie uruchamiam: powłoki, interpretery i narzędzia systemowe, "
                             "które mogą kasować dane albo zmieniać system, są zablokowane.")
        return found

    def command(self, program: str, arguments) -> str:
        if not self._may("commands"):
            raise AgentError("Wiersz poleceń dla agenta jest wyłączony na tym stanowisku („włącz wiersz poleceń agenta”).")
        if isinstance(arguments, str):
            arguments = [arguments] if arguments else []
        if not isinstance(arguments, list) or len(arguments) > 40 or any(not isinstance(a, (str, int, float)) for a in arguments):
            raise AgentError("Argumenty podaj jako listę napisów.")
        executable = self._program(program)
        argv = [str(executable), *[str(a) for a in arguments]]
        env = {k: v for k, v in os.environ.items() if not k.upper().startswith(("AWS_", "NOTARAI"))}
        run = self._runner or subprocess.run
        try:
            done = run(argv, shell=False, capture_output=True, timeout=90, env=env, stdin=subprocess.DEVNULL,
                       cwd=str(Path(os.environ.get("USERPROFILE") or Path.home())))
        except subprocess.TimeoutExpired:
            raise AgentError("Program nie skończył w 90 sekund; przerwałem czekanie.") from None
        except OSError:
            raise AgentError(f"Nie udało się uruchomić „{executable.name}”.") from None

        def shown(raw):
            if isinstance(raw, bytes):
                for encoding in ("utf-8", "cp852", "cp1250"):
                    try:
                        return raw.decode(encoding)
                    except UnicodeDecodeError:
                        continue
                return raw.decode("utf-8", errors="replace")
            return str(raw or "")
        output = (shown(done.stdout) + ("\n" + shown(done.stderr) if done.stderr else "")).strip()
        return f"{executable.name} zakończył się kodem {done.returncode}.\n{output[:6000] or '(nic nie wypisał)'}"

    def tools(self) -> str:
        found = set()
        for folder in os.environ.get("PATH", "").split(os.pathsep):
            try:
                for entry in os.scandir(folder):
                    stem = Path(entry.name).stem.lower()
                    if stem.startswith("cli-anything-") or stem in {"winapp", "soffice", "winword", "excel"}:
                        found.add(stem)
            except OSError:
                continue
        if not found:
            return ("Nie znalazłem narzędzi cli-anything ani winapp w ścieżce systemowej. Krok „polecenie” uruchomi każdy "
                    "inny program .exe po nazwie albo pełnej ścieżce (opcje: argument --help).")
        return "Narzędzia wiersza poleceń:\n" + "\n".join(sorted(found)) + "\nOpcje każdego: argument --help."

    # ---- files
    def roots(self) -> list[Path]:
        if self._roots is not None:
            return [Path(p) for p in self._roots()]
        profile = Path(os.environ.get("USERPROFILE") or Path.home())
        found = [profile / name for name in ("Desktop", "Pulpit", "Documents", "Dokumenty", "Downloads", "Pobrane")]
        if os.name == "nt":
            found += [Path(f"{letter}:\\") for letter in string.ascii_uppercase if Path(f"{letter}:\\").exists()]
        return [p for p in found if p.exists()]

    @staticmethod
    def _path(path: str) -> Path:
        if not isinstance(path, str) or not path.strip():
            raise AgentError("Brak ścieżki.")
        return Path(os.path.expandvars(os.path.expanduser(path.strip().strip('"'))))

    def files(self, folder: str) -> str:
        if not folder:
            return "Foldery startowe:\n" + "\n".join(str(p) for p in self.roots())
        where = self._path(folder)
        if not where.is_dir():
            raise AgentError(f"Nie ma folderu {where}.")
        lines = []
        try:
            for entry in sorted(where.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))[:300]:
                try:
                    if entry.is_dir():
                        lines.append(f"[folder] {entry.name}")
                    else:
                        stat = entry.stat()
                        lines.append(f"{entry.name}  ({stat.st_size // 1024} KB, "
                                     f"{time.strftime('%Y-%m-%d %H:%M', time.localtime(stat.st_mtime))})")
                except OSError:
                    continue
        except OSError:
            raise AgentError(f"Brak dostępu do folderu {where}.") from None
        return f"{where}:\n" + ("\n".join(lines) or "(pusty)")

    def find(self, name: str, folder: str = "", *, limit=40, seconds=25.0) -> str:
        words = [w for w in plain(name).split() if w]
        if not words:
            raise AgentError("Podaj, czego szukać.")
        starts = [self._path(folder)] if folder else self.roots()
        deadline, hits, seen = time.monotonic() + seconds, [], set()
        skip = {"windows", "program files", "program files (x86)", "programdata", "$recycle.bin", "appdata",
                "node_modules", ".git", "system volume information"}
        for start in starts:
            for current, dirs, files in os.walk(start, onerror=lambda e: None):
                dirs[:] = [d for d in dirs if plain(d) not in skip and not d.startswith(".")]
                for item in files + dirs:
                    if all(w in plain(item) for w in words):
                        path = str(Path(current) / item)
                        if path not in seen:
                            seen.add(path)
                            hits.append(path)
                if len(hits) >= limit or time.monotonic() > deadline:
                    break
            if len(hits) >= limit or time.monotonic() > deadline:
                break
        if not hits:
            return f"Nie znalazłem plików z „{name}” w nazwie."
        return "Znalazłem:\n" + "\n".join(hits)

    def read(self, path: str) -> str:
        where = self._path(path)
        if not where.is_file():
            raise AgentError(f"Nie ma pliku {where}.")
        if where.suffix.lower() not in self.READABLE:
            raise AgentError(f"Pliku {where.suffix} nie odczytam jako tekst; mogę go otworzyć krokiem „uruchom”.")
        if where.stat().st_size > 40_000_000:
            raise AgentError("Plik jest za duży.")
        data = where.read_bytes()
        try:
            if where.suffix.lower() == ".docx":
                from .docx_writer import extract
                text = "\n".join(extract(data))
            elif where.suffix.lower() == ".pdf":
                from .drafting import pdf_text
                text = pdf_text(data)
            else:
                text = data.decode("utf-8", errors="replace")
        except Exception:
            raise AgentError("Tego pliku nie da się odczytać (np. skan bez tekstu albo plik uszkodzony).") from None
        return f"{where}:\n{text}"

    def _keep_copy(self, where: Path) -> None:
        copies = self._home / "kopie-przed-zmiana"
        copies.mkdir(parents=True, exist_ok=True)
        shutil.copy2(where, copies / f"{time.strftime('%Y%m%d-%H%M%S')}-{where.name}")

    def _check(self, name: str, text: str) -> None:
        if self._rules is not None:
            from .rules import RuleViolation
            try:
                self._rules.check_document(name, text)
            except RuleViolation as error:
                raise AgentError(f"Zasada kancelarii nie pozwala zapisać: {error}") from None

    def replace(self, path: str, old: str, new: str) -> str:
        where = self._path(path)
        if not where.is_file() or where.suffix.lower() not in {".docx", ".txt"}:
            raise AgentError("Zamieniam tekst tylko w istniejących plikach DOCX i TXT.")
        if not old:
            raise AgentError("Podaj tekst do zamiany.")
        if where.suffix.lower() == ".txt":
            content = where.read_text(encoding="utf-8", errors="replace")
            count = content.count(old)
            if not count:
                raise AgentError("Nie ma tego tekstu w pliku.")
            changed = content.replace(old, new)
            self._check(where.name, changed)
            self._keep_copy(where)
            where.write_text(changed, encoding="utf-8")
            return f"Zamieniłem {count} raz(y) w {where.name}."
        from docx import Document

        document = Document(str(where))
        count = 0
        paragraphs = list(document.paragraphs)
        for table in document.tables:
            for row in table.rows:
                for cell in row.cells:
                    paragraphs.extend(cell.paragraphs)
        for paragraph in paragraphs:
            if old not in paragraph.text:
                continue
            count += paragraph.text.count(old)
            runs = paragraph.runs
            joined = "".join(r.text for r in runs)
            if any(old in r.text for r in runs):
                for r in runs:
                    r.text = r.text.replace(old, new)
            elif runs:                                    # the text spans runs: keep the first run's format
                runs[0].text = joined.replace(old, new)
                for r in runs[1:]:
                    r.text = ""
        if not count:
            raise AgentError("Nie ma tego tekstu w dokumencie (sprawdź pisownię, np. spacje i myślniki).")
        text = "\n".join(p.text for p in paragraphs)
        self._check(where.name, text)
        self._keep_copy(where)
        try:
            document.save(str(where))
        except PermissionError:
            raise AgentError("Plik jest otwarty w innym programie. Zamknij go w Wordzie i powiedz „spróbuj jeszcze raz”.") from None
        return f"Zamieniłem {count} raz(y) w {where.name} i zapisałem plik."

    def new_file(self, path: str, text: str) -> str:
        where = self._path(path)
        if where.exists():
            raise AgentError("Taki plik już istnieje; nie nadpisuję go. Wybierz inną nazwę albo zamień tekst w nim.")
        if where.suffix.lower() not in {".docx", ".txt"}:
            raise AgentError("Nowe pliki zapisuję jako DOCX albo TXT.")
        self._check(where.name, text)
        where.parent.mkdir(parents=True, exist_ok=True)
        if where.suffix.lower() == ".txt":
            where.write_text(text, encoding="utf-8")
        else:
            from .docx_writer import build
            where.write_bytes(build([line for line in text.splitlines()]))
        return f"Zapisałem {where}."

    def start(self, what: str) -> str:
        target = what.strip().strip('"') if isinstance(what, str) else ""
        if not target:
            raise AgentError("Co uruchomić?")
        if remote_help(target):
            raise AgentError("Programów pomocy zdalnej i pulpitu zdalnego nie uruchamiam. Jeśli ich potrzebujesz, "
                             "uruchom je sam.")
        name = plain(Path(target).stem if ("\\" in target or "/" in target or "." in target) else target)
        if name and self._desktop is not None:
            try:
                running = [w for w in self._desktop().windows() if name in plain(w)]
            except Exception:
                running = []
            if running:                      # never a second copy: the program is already open
                raise AgentError(f"„{target}” już działa (okno „{running[0]}”). Nie uruchamiam drugiej kopii: "
                                 "przejdź do tego okna krokiem okno.")
        if self._starter is not None:
            self._starter(target)
        elif os.name == "nt":
            try:
                if self._quiet():
                    import win32api
                    win32api.ShellExecute(0, "open", target, None, "", 4)      # SW_SHOWNOACTIVATE: the notary keeps the keyboard
                else:
                    os.startfile(target)                   # files open in their own program, folders in Explorer
            except Exception:
                raise AgentError(f"Nie udało się uruchomić „{target}”.") from None
        else:
            raise AgentError("Programy uruchamiam tylko na Windows.")
        time.sleep(0 if self._starter else 2.5)
        return f"Uruchomiłem {target}."

    # ---- Windows programs
    def _window(self, title):
        from .autofill import FillError

        desktop = self._desktop()
        if self._quiet():
            try:
                desktop.quiet = True               # the window stays where it lies; fields and buttons by messages
            except Exception:
                pass
        try:
            desktop.focus(title)
        except FillError as error:
            raise AgentError(str(error)) from None
        self._current = desktop
        return desktop

    @staticmethod
    def _all(desktop):
        """Everything a person can use in the window: fields and buttons, and menus, tabs, trees, lists."""
        try:
            return desktop.controls(deep=True)
        except TypeError:
            return desktop.controls()

    LOGIN_FIELD = re.compile(r"(^|[^a-z])(haslo|pin|password|kod pin|haslo dostepu)($|[^a-z])")

    def _login(self, where: str, controls, password_field: bool = False) -> None:
        """A screen that asks for a password or a PIN: the notary's part. The loop stops and the chat asks."""
        if password_field or any(c.kind == "text" and self.LOGIN_FIELD.search(plain(c.label)) for c in controls):
            self.login_needed = where or "program"

    def windows(self) -> str:
        return "Otwarte okna:\n" + "\n".join(self._desktop().windows())

    def window(self, title: str) -> str:
        desktop = self._window(title)
        lines = []
        found = self._all(desktop)
        self._login(desktop.where() or title, found, bool(getattr(desktop, "password_field", False)))
        for control in found:
            value = f" = „{control.value}”" if control.value else ""
            options = f" (do wyboru: {', '.join(control.options[:15])})" if control.options else ""
            lines.append(f"[{control.kind}] {control.label}{value}{options}")
        self.map.record(desktop.where() or title, desktop.where() or title, found)
        way = getattr(desktop, "read_by", "") or "UI Automation"
        self.read_windows[plain(desktop.where() or title)] = [plain(re.sub(r"\s*\([^)]*\)\s*$", "", c.label)) for c in found
                                                              if c.kind in {"button", "check"} and c.label.strip()]
        self.fields_seen = len(found)
        return (f"Okno {desktop.where()} (odczyt: {way}, elementów: {len(found)}):\n"
                + ("\n".join(lines[:500]) or "(brak pól dostępnych dla programu: użyj kroku ekran)"))

    def _control(self, desktop, label, kinds):
        from .autofill import norm

        wanted = norm(re.sub(r"\s*\((menu|zakładka|gałąź|pozycja|wiersz|odnośnik)\)\s*$", "", str(label)))
        controls = [c for c in self._all(desktop) if c.kind in kinds]
        exact = [c for c in controls if norm(c.label) == wanted]
        partial = [c for c in controls if wanted and wanted in norm(c.label)]
        found = exact or partial
        if not found:
            raise AgentError(f"Nie ma pola ani przycisku „{label}” w tym oknie.")
        return found[0]

    def type(self, title: str, label: str, value: str) -> str:
        from .autofill import FillError

        desktop = self._window(title)
        control = self._control(desktop, label, {"text", "select", "check"})
        try:
            if control.kind == "select":
                desktop.choose(control, value)
            elif control.kind == "check":
                desktop.check(control, plain(value) in {"tak", "1", "true", "zaznacz"})
            else:
                desktop.type(control, value)
        except FillError as error:             # with the reason, e.g. the positions a list really has
            raise AgentError(str(error)) from None
        return f"Wpisałem w „{control.label}”: {desktop.read(control)}"

    @staticmethod
    def _watch_click(rect, seconds: float):
        """Wait for the notary's own left click inside `rect`; (x, y) on the screen, or None when time ran out."""
        import ctypes

        user32, deadline, was_down = ctypes.windll.user32, time.monotonic() + seconds, True
        while time.monotonic() < deadline:
            down = bool(user32.GetAsyncKeyState(0x01) & 0x8000)
            if down and not was_down:
                spot = (ctypes.c_long * 2)()
                user32.GetCursorPos(spot)
                if rect[0] <= spot[0] < rect[2] and rect[1] <= spot[1] < rect[3]:
                    return spot[0], spot[1]
            was_down = down
            time.sleep(0.015)
        return None

    def learn_point(self, title: str, name: str, seconds: float = 60.0) -> str:
        """„Pokażę, kliknij za mną”: the notary clicks the thing once in the program; its place is remembered by name."""
        desktop = self._window(title)
        rect = desktop.rect() if hasattr(desktop, "rect") else None
        if not rect or rect[2] <= rect[0] or rect[3] <= rect[1]:
            raise AgentError("Nie widzę położenia okna tego programu. Przywróć je (nie może być zminimalizowane).")
        spot = (self._clicks or self._watch_click)(rect, seconds)
        if spot is None:
            raise AgentError(f"Nie zobaczyłem kliknięcia w oknie „{desktop.where()}” w ciągu {int(seconds)} sekund.")
        fx, fy = (spot[0] - rect[0]) / (rect[2] - rect[0]), (spot[1] - rect[1]) / (rect[3] - rect[1])
        if not self.map.point(desktop.where() or title, name, fx, fy):
            raise AgentError("Nie udało się zapamiętać tego punktu (nazwa bez numerów, najwyżej 60 punktów na program).")
        return f"Zapamiętałem „{name}” w programie „{desktop.where()}”. Następnym razem nacisnę to sam."

    def press_point(self, title: str, name: str) -> str:
        """Press a place the notary showed before; say what changed, and take the front only if nothing did."""
        desktop = self._window(title)
        known = self.map.points(desktop.where() or title)
        wanted = plain(name)
        hit = next((k for k in known if plain(k) == wanted), None) or next((k for k in known if wanted and wanted in plain(k)), None)
        if hit is None:
            raise AgentError(f"Nie znam punktu „{name}” w tym programie. Znane: {', '.join(known) or 'żaden'}. "
                             "Zadaj pytanie z polem punkt, a notariusz pokaże go jednym kliknięciem.")
        rect = desktop.rect() if hasattr(desktop, "rect") else None
        if not rect:
            raise AgentError("Nie widzę położenia okna tego programu.")
        dx, dy = round(known[hit]["x"] * (rect[2] - rect[0])), round(known[hit]["y"] * (rect[3] - rect[1]))
        try:
            before = self._state(self._all(desktop))
        except Exception:
            before = {}
        title_before = desktop.where()
        sent = hasattr(desktop, "click_at") and desktop.click_at(dx, dy)
        time.sleep(0 if getattr(self, "instant", False) else 0.8)
        changes = self._changes(desktop, before)
        if sent and ("nic się nie zmieniło" not in changes or desktop.where() != title_before):
            return f"Nacisnąłem nauczony punkt „{hit}” (w tle)." + changes

        def with_mouse():                      # the program did not take the message: the real mouse, for a moment
            if self._pointer is not None:
                self._pointer(rect[0] + dx, rect[1] + dy, False)
                return
            from pywinauto import mouse
            mouse.click(coords=(rect[0] + dx, rect[1] + dy))
            time.sleep(0.8)
        self._borrow(f"kliknięcie myszą w nauczony punkt „{hit}” (program nie przyjął go w tle)", with_mouse, desktop)
        return f"Nacisnąłem nauczony punkt „{hit}” myszą." + self._changes(desktop, before)

    @staticmethod
    def _state(found) -> dict:
        return {f"[{c.kind}] {c.label}": c.value for c in found if c.label.strip()}

    def _changes(self, desktop, before: dict) -> str:
        """What the window shows now that it did not show before the step: the agent's eyes after every click."""
        try:
            found = self._all(desktop)
        except Exception:
            return ""
        after = self._state(found)
        self._login(desktop.where(), found, bool(getattr(desktop, "password_field", False)))
        self.map.record(desktop.where(), desktop.where(), found)
        self.read_windows[plain(desktop.where())] = [plain(re.sub(r"\s*\([^)]*\)\s*$", "", c.label)) for c in found
                                                     if c.kind in {"button", "check"} and c.label.strip()]
        appeared = [name for name in after if name not in before]
        gone = [name for name in before if name not in after]
        changed = [f"{name} = „{after[name]}”" for name in after if name in before and after[name] != before[name]]
        if not (appeared or gone or changed):
            return ("\nW polach, przyciskach i menu okna nic się nie zmieniło. To nie musi znaczyć, że klik nie zadziałał: "
                    "jeśli to była lista, ustaw ją krokiem wpisz z wartością; jeśli program coś narysował sam, zrób ekran okna.")
        return ("\nPo tym kroku" + ("; pojawiło się: " + " | ".join(appeared[:40]) if appeared else "")
                + ("; zmieniło się: " + " | ".join(changed[:20]) if changed else "")
                + ("; zniknęło: " + " | ".join(gone[:20]) if gone else "") + ".")

    def click(self, title: str, label: str) -> str:
        desktop = self._window(title)
        from .autofill import FillError

        control = self._control(desktop, label, {"button", "check", "select"})
        if control.kind == "select":           # a drop-down list is not opened by clicking: its positions are read and one is set
            known = desktop.options(control) if hasattr(desktop, "options") else list(control.options)
            now = f" Teraz: „{control.value}”." if control.value else ""
            if known:
                return (f"„{control.label}” to lista rozwijana.{now} Pozycje: " + " | ".join(known[:40])
                        + ". Ustaw ją krokiem wpisz z jedną z tych wartości; nie trzeba jej rozwijać.")
            return (f"„{control.label}” to lista rozwijana, ale program nie podaje jej pozycji.{now} Zrób ekran tego okna, "
                    "żeby je zobaczyć, a wartość ustaw krokiem wpisz.")
        try:
            before = self._state(self._all(desktop))
        except Exception:
            before = {}
        try:
            desktop.click(control)
        except FillError:                      # no way to press it by a message: the mouse, with the notary's word
            self._borrow(f"naciśnięcie myszą „{control.label}”", lambda: control.ref.click_input(), desktop)
        time.sleep(0 if self._starter or self._pointer or self._grabber or getattr(self, "instant", False) else 1.0)
        return f"Kliknąłem „{control.label}”." + self._changes(desktop, before)

    def keys(self, title: str, keys: str) -> str:
        desktop = self._window(title)

        def press():
            try:
                from pywinauto.keyboard import send_keys
            except Exception:
                raise AgentError("Klawisze wysyłam tylko na Windows.") from None
            send_keys(keys, pause=0.05)
        self._borrow(f"naciśnięcie klawiszy {keys} w oknie programu", press, desktop)
        return f"Nacisnąłem {keys}."

    # ---- the NotarAI browser
    def web(self, url: str) -> str:
        from .autofill import FillError

        if remote_help(url) or "remotedesktop.google" in str(url).lower():
            raise AgentError("Stron pomocy zdalnej i pulpitu zdalnego nie otwieram. Jeśli ich potrzebujesz, otwórz je sam.")

        try:
            where = self._browser().open(url if re.match(r"https?://", url or "") else "https://" + str(url))
        except FillError as error:
            raise AgentError(str(error)) from None
        return f"Otworzyłem {where}.\n" + self.view()

    def view(self) -> str:
        def look(page):
            title = page.title()
            body = page.evaluate("() => document.body ? document.body.innerText : ''")
            links = page.evaluate("""() => [...document.querySelectorAll('a,button,[role=button]')]
                .filter(e => e.offsetParent !== null).map(e => (e.innerText || e.value || e.getAttribute('aria-label') || '').trim())
                .filter(t => t).slice(0, 120)""")
            password = page.evaluate("""() => [...document.querySelectorAll('input[type=password]')]
                .some(e => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0; })""")
            return page.url, title, body, links, password
        url, title, body, links, *rest = self._browser().on_page(look, timeout=60)
        self.used_browser = True
        self.last_page = url
        controls = self._browser().controls()
        self._login(url, controls, bool(rest and rest[0]))
        self.map.record(url, re.sub(r"^https?://[^/]+", "", url.split("?")[0].split("#")[0])[:60] or "/", controls)
        fields = [f"[{c.kind}] {c.label}" + (f" = „{c.value}”" if c.value else "") for c in controls]
        self._glance()
        return (f"Strona {url} — {title}\nTekst:\n{' '.join(body.split())[:5000]}\n"
                f"Pola:\n" + "\n".join(fields[:80]) + "\nPrzyciski i odnośniki:\n" + " | ".join(links))

    def web_type(self, label: str, value: str) -> str:
        browser = self._browser()
        control = self._control(browser, label, {"text", "select", "check"})
        if control.kind == "select":
            browser.choose(control, value)
        elif control.kind == "check":
            browser.check(control, plain(value) in {"tak", "1", "true", "zaznacz"})
        else:
            browser.type(control, value)
        self._glance()
        return f"Wpisałem w „{control.label}”."

    def _glance(self) -> None:
        """What the page looks like now, into the NotarAI window (never to the model, never to a file)."""
        if self.seen is None:
            return
        try:
            self.seen(self._browser().on_page(lambda page: page.screenshot(type="jpeg", quality=45), timeout=20))
        except Exception:
            pass

    def web_click(self, label: str) -> str:
        browser = self._browser()
        try:
            control = self._control(browser, label, {"button", "check"})
            browser.click(control)
        except AgentError:
            def press(page):
                target = page.get_by_text(label, exact=False).first
                target.click(timeout=8000)
                try:
                    page.wait_for_load_state("networkidle", timeout=8000)
                except Exception:
                    pass
            try:
                browser.on_page(press, timeout=40)
            except Exception:
                raise AgentError(f"Nie ma na stronie „{label}”.") from None
        return f"Kliknąłem „{label}”.\n" + self.view()


# ------------------------------------------------------------------ the loop
class Agent:
    def __init__(self, computer: Computer, ask, *, narrate=lambda line: None, rules=None, max_steps=MAX_STEPS):
        """`ask(system, text, images)` -> the model's reply (through inference.py); `images` is a tuple of JPEGs."""
        self._computer, self._ask, self._narrate = computer, ask, narrate
        self._rules, self._max = rules, max_steps

    STUCK_AFTER = 3            # failed steps in a row: the agent asks the notary instead of trying on

    READS = frozenset({"okno", "okna", "widok", "pliki", "szukaj", "czytaj", "narzedzia"})
    ACTIONS = frozenset({"wpisz", "kliknij", "web_wpisz", "web_kliknij", "punkt"})

    def run(self, task: str, *, allowed=frozenset(), history=None, lessons: str = "", cancelled=lambda: False) -> dict:
        """Returns {"answer", "steps", "stopped": None | {"kind", "label", "step", "history"}}.

        `allowed`: kinds of irreversible act approved for this run (from the sentence or a „Tak”)."""
        home = getattr(self._computer, "_home", None)
        self._log = RunLog(home, task) if home is not None and getattr(self._computer, "keep_log", True) else None
        self._trail, self._way = [], []          # (step, result) pairs of this run; what was pressed and filled, in order
        result = self._run(task, allowed=allowed, history=history, lessons=lessons, cancelled=cancelled)
        stopped = result.get("stopped")
        how = "zatrzymane" if result.get("cancelled") else ("gotowe" if stopped is None else "czeka: " + stopped["kind"])
        if self._log is not None:
            self._log.end(how)
        known = getattr(self._computer, "map", None)
        if how == "gotowe" and known is not None and self._way and not any(
                str(step.get("wynik", "")).startswith("BŁĄD") for step in result["steps"][-3:]):
            places = {}
            for where, what in self._way:
                places.setdefault(where, []).append(what)
            purpose = (plain(task).split() or [""])[0]
            for where, steps in places.items():      # the way that worked, kept for the next time (never values)
                known.route(where, purpose, steps)
        return result

    def _looping(self) -> str | None:
        """The same steps with the same results, three times over: going in circles (decided by code)."""
        trail = self._trail
        for period in range(1, 7):
            if len(trail) >= 3 * period and trail[-period:] == trail[-2 * period:-period] == trail[-3 * period:-2 * period]:
                return f"powtarzam w kółko te same {period} kroki z tym samym wynikiem" if period > 1 else \
                    "trzy razy z rzędu robię to samo z tym samym wynikiem"
        return None

    def _run(self, task: str, *, allowed=frozenset(), history=None, lessons: str = "", cancelled=lambda: False) -> dict:
        allowed = (set(allowed) | asked_for(task)) - NEVER
        self._computer.front_allowed = "wierzch" in allowed      # the front of the screen: only after the notary's „tak”
        history, steps = list(history or []), []
        known = getattr(self._computer, "map", None)
        stop = {"answer": "Zatrzymałem pracę na komputerze. Niczego więcej nie robię.", "steps": steps,
                "stopped": None, "cancelled": True}
        for _ in range(self._max):
            if cancelled():                   # „stop” in the chat, or the window was closed: checked before every step
                self._narrate(f"{time.strftime('%H:%M:%S')} · zatrzymane")
                return stop
            older = [entry if len(entry) < 500 else entry[:400] + " […]" for entry in history[:-KEEP_FULL]]
            transcript = "\n\n".join(older + history[-KEEP_FULL:])[-MAX_HISTORY:]
            picture, self._computer.picture = getattr(self._computer, "picture", None), None
            learned = known.describe() if known is not None else ""
            reply = self._ask(SYSTEM_AGENT, f"Polecenie notariusza: {task}\n\n"
                                            + (f"LEKCJE KANCELARII (wyciągnięte z wcześniejszych prac i odpowiedzi notariusza; "
                                               f"stosuj je):\n{lessons}\n\n" if lessons else "")
                                            + (f"MAPA PROGRAMU (z poprzednich prac na tym komputerze):\n{learned}\n\n" if learned else "")
                                            + f"Dotychczasowe kroki:\n{transcript or '(brak)'}"
                                            "\n\nPodaj następny krok (jeden obiekt JSON).", (picture,) if picture else ())
            try:
                step = parse_step(reply)
            except ValueError:
                history.append("(Odpowiedź nie była obiektem JSON z kluczem krok. Podaj jeden obiekt JSON.)")
                continue
            kind = step["krok"]
            why = str(step.get("po_co", ""))[:200]
            if kind == "koniec":
                return {"answer": str(step.get("odpowiedz", "")).strip() or "Gotowe.", "steps": steps, "stopped": None}
            if kind == "pytanie":
                options = [str(o)[:120] for o in (step.get("opcje") or []) if str(o).strip()][:4]
                problem = str(step.get("problem", "")).strip()[:300] or "Nie wiem, jak dalej."
                self._narrate(f"{time.strftime('%H:%M:%S')} · utknąłem: {problem} · pytam notariusza")
                show = None
                if str(step.get("punkt", "")).strip() and str(step.get("okno", "")).strip():
                    show = {"nazwa": str(step["punkt"]).strip()[:60], "okno": str(step["okno"]).strip()[:80]}
                return {"answer": "", "steps": steps, "stopped": {"kind": "pytanie", "label": problem, "options": options,
                                                                  "step": step, "history": history, "show": show}}
            failed = 0
            for earlier in reversed(steps):
                if not str(earlier.get("wynik", "")).startswith("BŁĄD"):
                    break
                failed += 1
            if failed >= self.STUCK_AFTER:     # decided by code: three failures in a row is being stuck
                problem = "kilka kolejnych kroków się nie udało: " + "; ".join(
                    str(e["wynik"])[6:80] for e in steps[-self.STUCK_AFTER:])
                self._narrate(f"{time.strftime('%H:%M:%S')} · {failed} błędy z rzędu: zatrzymuję się i pytam notariusza")
                return {"answer": "", "steps": steps, "stopped": {
                    "kind": "pytanie", "label": problem, "step": None, "history": history,
                    "options": ["Spróbuj innym sposobem", "Pokażę Ci, jak to zrobić", "Przerwij"]}}
            act = self._irreversible(step)
            if act and act not in allowed:
                label = (step.get("przycisk") or step.get("co") or step.get("klawisze")
                         or (kind == "polecenie" and f"{step.get('program', '')} {' '.join(map(str, step.get('argumenty') or []))}"[:160])
                         or kind)
                return {"answer": "", "steps": steps,
                        "stopped": {"kind": act, "label": str(label), "step": step, "history": history}}
            if act == "wyslanie" and self._rules is not None:
                from .rules import RuleViolation
                try:
                    self._rules.check_send("komputer", [])
                except RuleViolation as error:
                    return {"answer": f"Zasada kancelarii nie pozwala teraz wysłać: {error}", "steps": steps, "stopped": None}
            refused = self._order(step)
            signature = json.dumps({k: v for k, v in step.items() if k != "po_co"}, ensure_ascii=False, sort_keys=True)
            if not refused and kind in self.READS and self._trail and self._trail[-1][0] == signature:
                refused = ("Ten sam odczyt przed chwilą dał ten wynik (jest wyżej) i nic się od tego czasu nie zmieniło. "
                           "Nie powtarzaj go: wykonaj czynność albo zadaj pytanie krokiem pytanie.")
            if refused:
                history.append(f"KROK {json.dumps(step, ensure_ascii=False)}\nWYNIK: BŁĄD: {refused}")
                steps.append({"krok": kind, "po_co": why, "wynik": "BŁĄD: " + refused})
                self._narrate(f"{time.strftime('%H:%M:%S')} · cofnięte: {self._exact(step)} · {refused}")
                if self._log is not None:
                    self._log.step(step, "BŁĄD: cofnięte przez program", 0, state="cofniety")
                continue
            number, started = len(steps) + 1, time.monotonic()
            self._narrate(f"{time.strftime('%H:%M:%S')} krok {number} · {self._exact(step)}"
                          + (f" · po co: {why}" if why else "")
                          + (" · zrzut ekranu idzie do asystenta we Frankfurcie tak, jak go widać" if kind == "ekran" else ""))
            self._computer.login_needed = None
            if cancelled():
                self._narrate(f"{time.strftime('%H:%M:%S')} · zatrzymane przed krokiem {number}")
                return stop
            try:
                seen = self._do(step)
            except NeedFront as needed:        # not without the notary's word: the run waits, the step is not counted
                self._narrate(f"{time.strftime('%H:%M:%S')} krok {number} · wstrzymany: wymaga okna na wierzchu ({needed})")
                return {"answer": "", "steps": steps,
                        "stopped": {"kind": "wierzch", "label": str(needed), "step": step, "history": history}}
            except AgentError as error:
                seen = "BŁĄD: " + str(error)
            except Exception:
                seen = "BŁĄD: ten krok się nie udał."
            self._narrate(f"{time.strftime('%H:%M:%S')} krok {number} · wynik ({time.monotonic() - started:.1f} s): "
                          + self._outcome(kind, seen))
            steps.append({"krok": kind, "po_co": why, "wynik": seen.split("\n", 1)[0][:200]})
            history.append(f"KROK {json.dumps(step, ensure_ascii=False)}\nWYNIK: {seen[:MAX_SEEN]}")
            if self._log is not None:
                self._log.step(step, seen, time.monotonic() - started)
            self._trail.append((signature, hash(seen)))
            if kind in self.ACTIONS and not seen.startswith("BŁĄD"):
                where, what = RunLog.place(step)
                where = where or ProgramMap.key(str(getattr(self._computer, "last_page", "") or ""))
                if what:
                    self._way.append((where or "program", ("wpisz " if "wpisz" in kind else "punkt " if kind == "punkt"
                                                           else "kliknij ") + what))
            circling = self._looping()
            if circling:       # no more turns of the same circle: the notary decides how to go on
                self._narrate(f"{time.strftime('%H:%M:%S')} · kręcę się w kółko ({circling}): zatrzymuję się i pytam notariusza")
                return {"answer": "", "steps": steps, "stopped": {
                    "kind": "pytanie", "label": f"kręcę się w kółko: {circling} (ostatnio: {self._plain_step(step)})",
                    "step": None, "history": history,
                    "options": ["Spróbuj innym sposobem", "Pokażę Ci, jak to zrobić", "Przerwij"]}}
            if act:            # an irreversible act happened: once, never repeated by the loop
                allowed.discard(act)
            needed = getattr(self._computer, "login_needed", None)
            if needed:         # the screen just read asks for a password or a PIN: the notary's part
                self._computer.login_needed = None
                self._narrate(f"{time.strftime('%H:%M:%S')} · ekran logowania w „{needed}”: czekam na notariusza")
                return {"answer": "", "steps": steps,
                        "stopped": {"kind": "logowanie", "label": f"logowanie w „{needed}”", "step": step,
                                    "history": history, "where": needed}}
        return {"answer": "", "steps": steps,
                "stopped": {"kind": "limit", "label": f"{len(steps)} kroków", "step": None, "history": history}}

    def _irreversible(self, step) -> str | None:
        kind = step["krok"]
        if kind in {"kliknij", "web_kliknij"}:
            return act_kind(step.get("przycisk") or step.get("co") or "")
        if kind in {"wpisz", "web_wpisz"} and re.search(r"(^|[^a-z])(haslo|pin|password|kod pin)($|[^a-z])", plain(step.get("pole", ""))):
            return "logowanie"                     # a password or a PIN is typed by the notary, never by the program
        if kind == "kliknij_punkt":       # what Windows calls the element counts first, then what the model says it is
            return act_kind(self._computer.label_at(step.get("x"), step.get("y"))) or act_kind(str(step.get("co", "")))
        if kind == "polecenie":
            arguments = step.get("argumenty")
            words = set(re.findall(r"[a-z]+", plain(" ".join(str(a) for a in arguments) if isinstance(arguments, list) else str(arguments))))
            return next((act for act, names in COMMAND_ACTS.items() if words & set(names)), None)
        if kind == "klawisze":
            keys = str(step.get("klawisze", "")).lower()
            return "usuniecie" if "{del" in keys or "{delete" in keys else None
        return None

    def _order(self, step) -> str | None:
        """Fields before pictures, kept by code (2.8.1): a program is driven by the names of its fields and menus.
        A screenshot comes only after the window was read, and a point is not clicked where a named button exists."""
        computer, kind = self._computer, step["krok"]
        if getattr(computer, "_desktop", None) is None or kind not in {"ekran", "kliknij_punkt"}:
            return None
        read = getattr(computer, "read_windows", {})
        if not read and not getattr(computer, "used_browser", False):
            return ("Najpierw odczytaj okno programu krokiem okno (pola, przyciski i menu po nazwach). Zrzut ekranu "
                    "dopiero wtedy, gdy okno nie pokaże tego, czego potrzebujesz.")
        if kind == "kliknij_punkt":
            wanted = plain(str(step.get("co", "")))
            for title, names in read.items():
                if wanted and wanted in names:
                    return (f"„{step.get('co')}” jest w oknie po nazwie: użyj kroku kliknij z przyciskiem „{step.get('co')}” "
                            "zamiast klikać w punkt.")
        return None

    WAYS = {"okno": "pola okna", "wpisz": "pola okna", "kliknij": "pola okna", "klawisze": "klawiatura", "punkt": "nauczony punkt",
            "ekran": "ZRZUT EKRANU", "kliknij_punkt": "ZRZUT EKRANU", "pisz": "klawiatura",
            "widok": "strona", "web_wpisz": "strona", "web_kliknij": "strona", "strona": "strona",
            "polecenie": "wiersz poleceń", "narzedzia": "wiersz poleceń"}

    @classmethod
    def _exact(cls, step) -> str:
        """The step as it is carried out, for the live log: by which way, what, where, with what."""
        way = cls.WAYS.get(step["krok"])
        return (f"[{way}] " if way else "") + cls._plain_step(step)

    @staticmethod
    def _plain_step(step) -> str:
        get = lambda key, limit=70: str(step.get(key, "") or "")[:limit]
        kind = step["krok"]
        forms = {
            "pliki": lambda: f"lista folderu „{get('folder') or 'foldery startowe'}”",
            "szukaj": lambda: f"szukam plików „{get('nazwa')}”" + (f" w „{get('folder')}”" if get("folder") else ""),
            "czytaj": lambda: f"czytam plik „{get('plik', 120)}”",
            "zamien": lambda: f"w pliku „{get('plik', 120)}” zamieniam „{get('stare')}” na „{get('nowe')}”",
            "nowy_plik": lambda: f"zapisuję nowy plik „{get('plik', 120)}”",
            "uruchom": lambda: f"uruchamiam „{get('co', 120)}”",
            "okna": lambda: "odczytuję listę otwartych okien",
            "okno": lambda: f"odczytuję pola, przyciski i menu okna „{get('okno')}”",
            "wpisz": lambda: f"okno „{get('okno')}”, pole „{get('pole')}”: wpisuję „{get('wartosc')}”",
            "kliknij": lambda: f"okno „{get('okno')}”: klikam „{get('przycisk')}”",
            "klawisze": lambda: f"okno „{get('okno')}”: naciskam {get('klawisze')}",
            "strona": lambda: f"przeglądarka: otwieram {get('adres', 160)}",
            "widok": lambda: "przeglądarka: odczytuję stronę",
            "web_wpisz": lambda: f"przeglądarka, pole „{get('pole')}”: wpisuję „{get('wartosc')}”",
            "web_kliknij": lambda: f"przeglądarka: klikam „{get('co')}”",
            "ekran": lambda: "robię zrzut ekranu" + (f" z oknem „{get('okno')}”" if get("okno") else ""),
            "kliknij_punkt": lambda: f"klikam w punkt ({step.get('x')}, {step.get('y')}) „{get('co')}”",
            "pisz": lambda: f"piszę z klawiatury „{get('tekst')}”",
            "narzedzia": lambda: "sprawdzam narzędzia wiersza poleceń",
            "polecenie": lambda: "wiersz poleceń: " + f"{get('program')} {' '.join(map(str, step.get('argumenty') or [])) if isinstance(step.get('argumenty', []), list) else ''}"[:200],
            "notatka": lambda: f"zapamiętuję o programie „{get('program')}”: {get('tekst', 200)}",
            "punkt": lambda: f"okno „{get('okno')}”: naciskam nauczony punkt „{get('nazwa')}”",
        }
        return forms.get(kind, lambda: kind)()

    @staticmethod
    def _outcome(kind: str, seen: str) -> str:
        """What came back, in one line: an error whole, a reading as its size and first line."""
        first = seen.split("\n", 1)[0][:220]
        if seen.startswith("BŁĄD") or kind not in {"okno", "widok", "strona", "czytaj", "pliki", "okna", "szukaj", "polecenie"}:
            return first
        return f"{first} ({seen.count(chr(10))} wierszy)"

    @staticmethod
    def _describe(step) -> str:
        names = {"pliki": "przeglądam folder", "szukaj": "szukam plików", "czytaj": "czytam plik",
                 "zamien": "poprawiam plik", "nowy_plik": "zapisuję nowy plik", "uruchom": "uruchamiam",
                 "okna": "sprawdzam otwarte okna", "okno": "czytam okno programu", "wpisz": "wpisuję w pole",
                 "kliknij": "klikam", "klawisze": "naciskam klawisze", "strona": "otwieram stronę",
                 "widok": "czytam stronę", "web_wpisz": "wpisuję na stronie", "web_kliknij": "klikam na stronie",
                 "ekran": "patrzę na ekran", "kliknij_punkt": "klikam w punkt na ekranie", "pisz": "piszę z klawiatury",
                 "narzedzia": "sprawdzam narzędzia wiersza poleceń", "polecenie": "uruchamiam program z wiersza poleceń",
                 "notatka": "zapamiętuję drogę przez program", "punkt": "naciskam nauczony punkt"}
        return names.get(step["krok"], step["krok"])

    def _do(self, step) -> str:
        c, k = self._computer, step["krok"]
        get = lambda key: str(step.get(key, "") or "")
        actions = {
            "pliki": lambda: c.files(get("folder")),
            "szukaj": lambda: c.find(get("nazwa"), get("folder")),
            "czytaj": lambda: c.read(get("plik")),
            "zamien": lambda: c.replace(get("plik"), get("stare"), get("nowe")),
            "nowy_plik": lambda: c.new_file(get("plik"), get("tekst")),
            "uruchom": lambda: c.start(get("co")),
            "okna": c.windows,
            "okno": lambda: c.window(get("okno")),
            "wpisz": lambda: c.type(get("okno"), get("pole"), get("wartosc")),
            "kliknij": lambda: c.click(get("okno"), get("przycisk")),
            "klawisze": lambda: c.keys(get("okno"), get("klawisze")),
            "strona": lambda: c.web(get("adres")),
            "widok": c.view,
            "web_wpisz": lambda: c.web_type(get("pole"), get("wartosc")),
            "web_kliknij": lambda: c.web_click(get("co")),
            "ekran": lambda: c.screen(get("okno")),
            "kliknij_punkt": lambda: c.click_point(step.get("x"), step.get("y"), bool(step.get("dwuklik"))),
            "pisz": lambda: c.write(get("tekst")),
            "narzedzia": c.tools,
            "polecenie": lambda: c.command(get("program"), step.get("argumenty", [])),
            "notatka": lambda: c.map.note(get("program"), get("tekst")),
            "punkt": lambda: c.press_point(get("okno"), get("nazwa")),
        }
        if k not in actions:
            raise AgentError(f"Nie znam kroku „{k}”.")
        return actions[k]()
