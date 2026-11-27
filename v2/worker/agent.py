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
RUNNABLE = (".exe", ".com")
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
    "- {\"krok\":\"koniec\",\"odpowiedz\":co zrobiłeś i co z tego wynika, po polsku, krótko}\n"
    "Najpierw plan: jeśli niżej jest MAPA PROGRAMU dla tego programu, idź prosto po znanej drodze. Jeśli mapy nie ma, "
    "najpierw poznaj program (okno albo widok głównego ekranu, potem menu i zakładki, bez zapisywania czegokolwiek), zapisz "
    "drogę krokiem notatka i dopiero wtedy wykonuj polecenie. Gdy polecenie dotyczy kilku pozycji (np. kilku aktów), "
    "rób je po kolei i nie kończ, póki wszystkie nie są przygotowane. Logowania, certyfikatu, PIN-u, hasła, podpisu i "
    "płatności nie wykonujesz nigdy: przygotuj wszystko i zakończ, mówiąc, co czeka na notariusza. "
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
            for screen, parts in entry.get("ekrany", {}).items():
                lines.append(f"  ekran „{screen}”: pola: {', '.join(parts['pola']) or '-'}; przyciski: {', '.join(parts['przyciski']) or '-'}")
        return "\n".join(lines)[:limit]


# ------------------------------------------------------------------ the computer
class Computer:
    """What the agent can touch. Every method returns text for the model (and raises AgentError)."""

    READABLE = (".docx", ".pdf", ".txt", ".eml", ".csv", ".md", ".xml", ".html", ".htm")

    def __init__(self, home: Path, *, desktop=None, browser=None, roots=None, starter=None, rules=None,
                 grabber=None, pointer=None, typist=None, runner=None, label_at=None, allowed=None, which=None):
        """`allowed()` -> {"screen": bool, "commands": bool}: what the station lets the agent do (settings)."""
        self._home = Path(home)
        self._desktop, self._browser = desktop, browser          # callables returning the targets
        self._roots, self._starter, self._rules = roots, starter, rules
        self._grabber, self._pointer, self._typist, self._runner = grabber, pointer, typist, runner
        self._label_at, self._allowed, self._which = label_at, allowed, which or shutil.which
        self._scale = None                                       # screen pixels per pixel of the last screenshot
        self.map = ProgramMap(self._home)
        self.used_browser = False                                # this run touched the NotarAI browser
        self.picture = None                                      # JPEG for the model's next turn, taken once

    def _may(self, what: str) -> bool:
        return True if self._allowed is None else bool(self._allowed().get(what, True))

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
        if title:
            self._window(title)
            time.sleep(0 if self._grabber else 0.4)
        try:
            picture, scale, size = (self._grabber or self._grab)()
        except AgentError:
            raise
        except Exception:
            raise AgentError("Nie udało się zrobić zrzutu ekranu.") from None
        self.picture, self._scale = picture, scale
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
        if self._pointer is not None:
            self._pointer(px, py, double)
        else:
            try:
                from pywinauto import mouse
            except Exception:
                raise AgentError("W punkt klikam tylko na Windows.") from None
            (mouse.double_click if double else mouse.click)(coords=(px, py))
            time.sleep(0.8)
        self._scale = None            # the screen has changed: the next point needs a new screenshot
        return "Kliknąłem w punkt. Zrób nowy zrzut, żeby zobaczyć wynik."

    def write(self, value: str) -> str:
        if not value:
            raise AgentError("Brak tekstu do wpisania.")
        if self._typist is not None:
            self._typist(value)
        else:
            try:
                from pywinauto.keyboard import send_keys
            except Exception:
                raise AgentError("Z klawiatury piszę tylko na Windows.") from None
            escaped = re.sub(r"([+^%~(){}\[\]])", r"{\1}", value).replace("\n", "{ENTER}")
            send_keys(escaped, with_spaces=True, with_tabs=True, pause=0.01)
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
        if self._starter is not None:
            self._starter(target)
        elif os.name == "nt":
            try:
                os.startfile(target)                       # files open in their own program, folders in Explorer
            except OSError:
                raise AgentError(f"Nie udało się uruchomić „{target}”.") from None
        else:
            raise AgentError("Programy uruchamiam tylko na Windows.")
        time.sleep(0 if self._starter else 2.5)
        return f"Uruchomiłem {target}."

    # ---- Windows programs
    def _window(self, title):
        from .autofill import FillError

        desktop = self._desktop()
        try:
            desktop.focus(title)
        except FillError as error:
            raise AgentError(str(error)) from None
        return desktop

    def windows(self) -> str:
        return "Otwarte okna:\n" + "\n".join(self._desktop().windows())

    def window(self, title: str) -> str:
        desktop = self._window(title)
        lines = []
        for control in desktop.controls():
            value = f" = „{control.value}”" if control.value else ""
            options = f" (do wyboru: {', '.join(control.options[:15])})" if control.options else ""
            lines.append(f"[{control.kind}] {control.label}{value}{options}")
        self.map.record(desktop.where() or title, desktop.where() or title, desktop.controls())
        return f"Okno {desktop.where()}:\n" + ("\n".join(lines) or "(brak pól dostępnych dla programu)")

    def _control(self, desktop, label, kinds):
        from .autofill import norm

        wanted = norm(label)
        controls = [c for c in desktop.controls() if c.kind in kinds]
        exact = [c for c in controls if norm(c.label) == wanted]
        partial = [c for c in controls if wanted and wanted in norm(c.label)]
        found = exact or partial
        if not found:
            raise AgentError(f"Nie ma pola ani przycisku „{label}” w tym oknie.")
        return found[0]

    def type(self, title: str, label: str, value: str) -> str:
        desktop = self._window(title)
        control = self._control(desktop, label, {"text", "select", "check"})
        if control.kind == "select":
            desktop.choose(control, value)
        elif control.kind == "check":
            desktop.check(control, plain(value) in {"tak", "1", "true", "zaznacz"})
        else:
            desktop.type(control, value)
        return f"Wpisałem w „{control.label}”: {desktop.read(control)}"

    def click(self, title: str, label: str) -> str:
        desktop = self._window(title)
        control = self._control(desktop, label, {"button", "check"})
        desktop.click(control)
        time.sleep(0 if self._starter else 1.0)
        return f"Kliknąłem „{control.label}”."

    def keys(self, title: str, keys: str) -> str:
        self._window(title)
        try:
            from pywinauto.keyboard import send_keys
        except Exception:
            raise AgentError("Klawisze wysyłam tylko na Windows.") from None
        send_keys(keys, pause=0.05)
        return f"Nacisnąłem {keys}."

    # ---- the NotarAI browser
    def web(self, url: str) -> str:
        from .autofill import FillError

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
            return page.url, title, body, links
        url, title, body, links = self._browser().on_page(look, timeout=60)
        self.used_browser = True
        controls = self._browser().controls()
        self.map.record(url, re.sub(r"^https?://[^/]+", "", url.split("?")[0].split("#")[0])[:60] or "/", controls)
        fields = [f"[{c.kind}] {c.label}" + (f" = „{c.value}”" if c.value else "") for c in controls]
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
        return f"Wpisałem w „{control.label}”."

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

    def run(self, task: str, *, allowed=frozenset(), history=None) -> dict:
        """Returns {"answer", "steps", "stopped": None | {"kind", "label", "step", "history"}}.

        `allowed`: kinds of irreversible act approved for this run (from the sentence or a „Tak”)."""
        allowed = (set(allowed) | asked_for(task)) - NEVER
        history, steps = list(history or []), []
        known = getattr(self._computer, "map", None)
        for _ in range(self._max):
            older = [entry if len(entry) < 500 else entry[:400] + " […]" for entry in history[:-KEEP_FULL]]
            transcript = "\n\n".join(older + history[-KEEP_FULL:])[-MAX_HISTORY:]
            picture, self._computer.picture = getattr(self._computer, "picture", None), None
            learned = known.describe() if known is not None else ""
            reply = self._ask(SYSTEM_AGENT, f"Polecenie notariusza: {task}\n\n"
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
            self._narrate(f"Krok {len(steps) + 1}: {why or self._describe(step)}" + (
                " (zrzut ekranu idzie do asystenta we Frankfurcie tak, jak go widać)" if kind == "ekran" else "") + (
                f" [{step.get('program', '')} {' '.join(str(a) for a in step.get('argumenty') or [])[:120]}]"
                if kind == "polecenie" and isinstance(step.get("argumenty", []), list) else ""))
            try:
                seen = self._do(step)
            except AgentError as error:
                seen = "BŁĄD: " + str(error)
            except Exception:
                seen = "BŁĄD: ten krok się nie udał."
            steps.append({"krok": kind, "po_co": why, "wynik": seen.split("\n", 1)[0][:200]})
            history.append(f"KROK {json.dumps(step, ensure_ascii=False)}\nWYNIK: {seen[:MAX_SEEN]}")
            if act:            # an irreversible act happened: once, never repeated by the loop
                allowed.discard(act)
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

    @staticmethod
    def _describe(step) -> str:
        names = {"pliki": "przeglądam folder", "szukaj": "szukam plików", "czytaj": "czytam plik",
                 "zamien": "poprawiam plik", "nowy_plik": "zapisuję nowy plik", "uruchom": "uruchamiam",
                 "okna": "sprawdzam otwarte okna", "okno": "czytam okno programu", "wpisz": "wpisuję w pole",
                 "kliknij": "klikam", "klawisze": "naciskam klawisze", "strona": "otwieram stronę",
                 "widok": "czytam stronę", "web_wpisz": "wpisuję na stronie", "web_kliknij": "klikam na stronie",
                 "ekran": "patrzę na ekran", "kliknij_punkt": "klikam w punkt na ekranie", "pisz": "piszę z klawiatury",
                 "narzedzia": "sprawdzam narzędzia wiersza poleceń", "polecenie": "uruchamiam program z wiersza poleceń",
                 "notatka": "zapamiętuję drogę przez program"}
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
        }
        if k not in actions:
            raise AgentError(f"Nie znam kroku „{k}”.")
        return actions[k]()
