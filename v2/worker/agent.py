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
- the model sees text only (file text, window fields, page text), pseudonymised like every other
  call through `inference.py`; no screenshots leave the computer.

Every step is narrated in the chat; nothing of the content is logged.
"""
import json
import os
import re
import shutil
import string
import time
import unicodedata
from pathlib import Path

MAX_STEPS = 24
MAX_SEEN = 9000            # characters of one observation shown to the model
MAX_HISTORY = 60000

ACTS = {                   # kinds of irreversible act -> words that name them (normalised, no accents)
    "wyslanie": ("wyslij", "wyslac", "przeslij", "nadaj", "send", "submit", "zloz", "zlozyc", "zatwierdz",
                 "potwierdz", "dalej i wyslij"),
    "podpis": ("podpisz", "podpisac", "sign"),
    "platnosc": ("zaplac", "oplac", "zaplacic", "kup teraz", "zamow", "pay"),
    "usuniecie": ("usun", "usunac", "skasuj", "wyczysc", "delete", "remove"),
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
    "- {\"krok\":\"koniec\",\"odpowiedz\":co zrobiłeś i co z tego wynika, po polsku, krótko}\n"
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


def act_kind(label: str) -> str | None:
    """The irreversible act a button or key names, if any."""
    words = plain(label)
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


# ------------------------------------------------------------------ the computer
class Computer:
    """What the agent can touch. Every method returns text for the model (and raises AgentError)."""

    READABLE = (".docx", ".pdf", ".txt", ".eml", ".csv", ".md", ".xml", ".html", ".htm")

    def __init__(self, home: Path, *, desktop=None, browser=None, roots=None, starter=None, rules=None):
        self._home = Path(home)
        self._desktop, self._browser = desktop, browser          # callables returning the targets
        self._roots, self._starter, self._rules = roots, starter, rules

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
        fields = [f"[{c.kind}] {c.label}" + (f" = „{c.value}”" if c.value else "") for c in self._browser().controls()]
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
        """`ask(system, text)` -> the model's reply (through inference.py)."""
        self._computer, self._ask, self._narrate = computer, ask, narrate
        self._rules, self._max = rules, max_steps

    def run(self, task: str, *, allowed=frozenset(), history=None) -> dict:
        """Returns {"answer", "steps", "stopped": None | {"kind", "label", "step", "history"}}.

        `allowed`: kinds of irreversible act approved for this run (from the sentence or a „Tak”)."""
        allowed = set(allowed) | asked_for(task)
        history, steps = list(history or []), []
        for _ in range(self._max):
            transcript = "\n\n".join(history)[-MAX_HISTORY:]
            reply = self._ask(SYSTEM_AGENT, f"Polecenie notariusza: {task}\n\nDotychczasowe kroki:\n{transcript or '(brak)'}"
                                            "\n\nPodaj następny krok (jeden obiekt JSON).")
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
                label = step.get("przycisk") or step.get("co") or step.get("klawisze") or kind
                return {"answer": "", "steps": steps,
                        "stopped": {"kind": act, "label": str(label), "step": step, "history": history}}
            if act == "wyslanie" and self._rules is not None:
                from .rules import RuleViolation
                try:
                    self._rules.check_send("komputer", [])
                except RuleViolation as error:
                    return {"answer": f"Zasada kancelarii nie pozwala teraz wysłać: {error}", "steps": steps, "stopped": None}
            self._narrate(f"Krok {len(steps) + 1}: {why or self._describe(step)}")
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
        return {"answer": "Przerwałem po wielu krokach. Napisz, co dalej, albo podziel polecenie na mniejsze.",
                "steps": steps, "stopped": None}

    @staticmethod
    def _irreversible(step) -> str | None:
        kind = step["krok"]
        if kind in {"kliknij", "web_kliknij"}:
            return act_kind(step.get("przycisk") or step.get("co") or "")
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
                 "widok": "czytam stronę", "web_wpisz": "wpisuję na stronie", "web_kliknij": "klikam na stronie"}
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
        }
        if k not in actions:
            raise AgentError(f"Nie znam kroku „{k}”.")
        return actions[k]()
