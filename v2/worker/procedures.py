"""Teach by showing: a narrated screen recording becomes a reusable procedure.

The notary records the screen while filling a form in any program or on any website and says
what goes where and why. From a few frames and the narration the model writes down the
procedure: an ordered list of fields, where each value comes from, and the reason. The notary
corrects and approves it. Later, for a concrete case, the same procedure yields the values to
enter, each with a copy button. On the workstation the values are also typed into the form by
autofill.py (web pages and Windows programs); sending always waits for the notary's approval.

Procedures are documents in the vault (case "procedury"), so they are encrypted, versioned
and backed up like everything else.
"""
import json
import re
import secrets
import threading
import time
import unicodedata

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .inference import Inference

CASE = "procedury"
SUFFIX = ".procedura.json"
PENDING_TTL = 30 * 60

SYSTEM_LEARN = (
    "Jesteś asystentem polskiej kancelarii notarialnej. Dostajesz zrzuty ekranu (w kolejności) oraz słowny "
    "komentarz notariusza, który pokazuje, jak wypełnia formularz w programie albo na stronie urzędowej. "
    "Zapisz procedurę jako JSON i nic poza nim:\n"
    '{"program": "nazwa programu lub strony", "cel": "do czego służy ta czynność", '
    '"rodzaj": "strona albo program", "adres": "adres strony z paska przeglądarki (https://...) albo tytuł okna programu", '
    '"kroki": [{"pole": "etykieta pola albo napis na przycisku, dokładnie tak jak na ekranie", "zrodlo": "skąd wziąć '
    'wartość, np. PESEL sprzedającego z aktu; albo stała wartość", "dlaczego": "powód podany przez notariusza", '
    '"akcja": "wpisz, kliknij albo wyslij"}]}\n'
    "Akcja: wpisz dla pól; kliknij dla przycisków przechodzących dalej w tym samym formularzu (np. Dalej); "
    "wyslij wyłącznie dla przycisku, który wysyła albo składa wniosek, podpisuje go lub zapisuje na stałe.\n"
    "Zasady: kolejność kroków jak na nagraniu; opisuj skąd bierze się wartość, a nie konkretną wartość z nagrania "
    "(dane na nagraniu dotyczą jednej sprawy); gdy notariusz nie podał powodu, wpisz pusty tekst; nie zmyślaj pól, "
    "których nie widać ani nie słychać. Znaczniki w nawiasach kwadratowych przepisuj bez zmian."
)
SYSTEM_FILL = (
    "Jesteś asystentem polskiej kancelarii notarialnej. Dostajesz procedurę wypełniania formularza i dokumenty "
    "sprawy. Dla każdego kroku podaj wartość do wpisania, wyłącznie na podstawie dokumentów. Odpowiedz JSON-em "
    'i niczym więcej: {"wartosci": [{"pole": "...", "wartosc": "...", "skad": "z którego dokumentu"}]}\n'
    "Zachowaj kolejność i nazwy pól z procedury. Gdy wartości nie ma w dokumentach, wpisz pusty tekst w "
    "\"wartosc\"; nigdy nie zgaduj. Dla kroków typu 'kliknij' wpisz w \"wartosc\" słowo kliknij. "
    "Znaczniki w nawiasach kwadratowych przepisuj bez zmian."
)


class ProcedureError(Exception):
    """Fixed message, safe to show."""


class Step(BaseModel):
    model_config = ConfigDict(extra="ignore")
    pole: str = Field(min_length=1, max_length=200)
    zrodlo: str = Field(default="", max_length=400)
    dlaczego: str = Field(default="", max_length=600)
    # wpisz (default), kliknij (moves within the form), wyslij (sends: only after approval)
    akcja: str = Field(default="", pattern=r"^(|wpisz|kliknij|wyslij)$")


class Procedure(BaseModel):
    model_config = ConfigDict(extra="ignore")
    nazwa: str = Field(min_length=1, max_length=80)
    program: str = Field(default="", max_length=120)
    cel: str = Field(default="", max_length=400)
    rodzaj: str = Field(default="", pattern=r"^(|strona|program)$")     # web page or Windows program
    adres: str = Field(default="", max_length=400)                        # https address or window title
    kroki: list[Step] = Field(min_length=1, max_length=80)


def slug(name: str) -> str:
    plain = "".join(c for c in unicodedata.normalize("NFD", name.lower().replace("ł", "l"))
                    if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", "-", plain).strip("-")[:60] or "procedura"


def _json(text: str) -> dict:
    """Models sometimes wrap JSON in a code fence or a sentence; take the outermost object."""
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("no JSON")
    value = json.loads(text[start:end + 1])
    if not isinstance(value, dict):
        raise ValueError("not an object")
    return value


class Procedures:
    def __init__(self, vault, inference, drafts):
        """`inference` may be a callable, as in Drafts; `drafts` supplies case context and parties."""
        self._vault, self._source, self._drafts = vault, inference, drafts
        self._pending: dict[str, dict] = {}
        self._lock = threading.Lock()

    @property
    def _inference(self) -> Inference:
        return self._source() if callable(self._source) else self._source

    # ------------------------------------------------------------ teaching
    def learn(self, name: str, narration: str, frames: list[bytes], actor: str, recording: bytes | None = None) -> dict:
        name = " ".join(name.split())
        narration = narration.strip()
        if not name or len(name) > 80:
            raise ProcedureError("Podaj krótką nazwę procedury, np. „Wniosek o wpis w KW”.")
        if len(narration) < 20:
            raise ProcedureError("Opisz słowami, co wypełniasz i dlaczego. Bez tego nie nauczę się procedury.")
        if not frames:
            raise ProcedureError("Nagranie nie zawiera obrazu ekranu.")
        answer = self._inference.ask(
            purpose="learn", system=SYSTEM_LEARN, max_tokens=8000, images=tuple(frames[:Inference.MAX_IMAGES]),
            text=f"Nazwa procedury: {name}\n\n=== KOMENTARZ NOTARIUSZA ===\n{narration}",
        )
        try:
            procedure = Procedure.model_validate({"nazwa": name, **_json(answer.text)})
        except (ValueError, ValidationError):
            raise ProcedureError("Nie udało się odczytać procedury z nagrania. Nagraj krócej i powiedz po kolei, "
                                 "co wpisujesz w każde pole.") from None
        token = secrets.token_urlsafe(16)
        with self._lock:
            now = time.monotonic()
            self._pending = {k: v for k, v in self._pending.items() if v["expires"] > now}
            while len(self._pending) >= 5:
                self._pending.pop(next(iter(self._pending)))
            self._pending[token] = {"actor": actor, "expires": now + PENDING_TTL, "recording": recording}
        return {"id": token, "procedure": procedure.model_dump()}

    def approve(self, token: str, procedure: dict, actor: str) -> dict:
        """Store what the notary approved (possibly corrected), and the recording next to it."""
        with self._lock:
            pending = self._pending.get(token)
        if pending is None or pending["actor"] != actor or pending["expires"] <= time.monotonic():
            raise ProcedureError("Ta propozycja wygasła. Nagraj procedurę jeszcze raz.")
        try:
            approved = Procedure.model_validate(procedure)
        except ValidationError:
            raise ProcedureError("Procedura musi mieć nazwę i przynajmniej jeden krok z nazwą pola.") from None
        stem = slug(approved.nazwa)
        saved = self._store(stem + SUFFIX, json.dumps(approved.model_dump(), ensure_ascii=False, indent=1).encode(), actor)
        if pending["recording"]:
            self._store(stem + ".nagranie.webm", pending["recording"], actor)
        with self._lock:
            self._pending.pop(token, None)
        return {"name": approved.nazwa, "version": saved, "steps": len(approved.kroki)}

    def _store(self, name: str, data: bytes, actor: str) -> int:
        existing = next((d for d in self._vault.summaries({CASE}) if d["name"] == name), None)
        if existing:
            return self._vault.put(existing["id"], existing["version"], name, data, actor=actor)[1]
        return self._vault.put(None, 0, name, data, actor=actor, case=CASE)[1]

    # ------------------------------------------------------------ using
    def list(self) -> list[dict]:
        result = []
        for item in self._vault.summaries({CASE}):
            if item["name"].endswith(SUFFIX):
                result.append({"id": item["id"], "slug": item["name"][:-len(SUFFIX)], "version": item["version"]})
        return result

    def get(self, wanted: str, actor: str) -> Procedure:
        key = slug(wanted)
        found = [p for p in self.list() if p["slug"] == key] or [p for p in self.list() if key in p["slug"]]
        if len(found) != 1:
            raise ProcedureError("Nie ma takiej procedury." if not found else "Kilka procedur pasuje do tej nazwy.")
        _, _, data = self._vault.get(found[0]["id"], actor=actor)
        return Procedure.model_validate(json.loads(data))

    def names(self, actor: str):
        return [self.get(p["slug"], actor).nazwa for p in self.list()]

    def fill(self, wanted: str, case: str, actor: str, names=()) -> dict:
        """Values for one case, in the procedure's order. Nothing is typed anywhere: the notary copies."""
        from .autofill import action_of

        procedure = self.get(wanted, actor)
        context, sources, skipped = self._drafts._context(case, actor)
        steps = "\n".join(f"{n}. pole: {s.pole}; źródło: {s.zrodlo}" for n, s in enumerate(procedure.kroki, 1)
                          if action_of(s) == "wpisz")
        answer = self._inference.ask(
            purpose="fill", system=SYSTEM_FILL, names=self._drafts._names(case, names), max_tokens=8000,
            text=f"=== PROCEDURA: {procedure.nazwa} ({procedure.program}) ===\n{steps}\n\n{context}",
        )
        try:
            values = _json(answer.text).get("wartosci")
            by_field = {str(v.get("pole", "")).strip().lower(): v for v in values if isinstance(v, dict)}
        except (ValueError, AttributeError, TypeError):
            raise ProcedureError("Nie udało się przygotować wartości. Spróbuj ponownie.") from None
        items = []
        for step in procedure.kroki:
            action = action_of(step)
            if action != "wpisz":       # buttons need no value from the documents
                items.append({"field": step.pole, "value": "kliknij", "from": "", "why": step.dlaczego, "action": action})
                continue
            value = by_field.get(step.pole.strip().lower(), {})
            items.append({"field": step.pole, "value": str(value.get("wartosc", "") or "")[:2000],
                          "from": str(value.get("skad", "") or "")[:200], "why": step.dlaczego, "action": action})
        return {"name": procedure.nazwa, "program": procedure.program, "items": items,
                "rodzaj": procedure.rodzaj, "adres": procedure.adres,
                "missing": sum(1 for i in items if not i["value"]), "skipped": skipped,
                "unknown_placeholders": list(answer.unknown_placeholders)}
