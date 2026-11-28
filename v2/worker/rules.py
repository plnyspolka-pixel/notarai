"""The office's hard rules: set by the notary, enforced by code, never left to a model.

A rule is data with a fixed meaning. Every place that writes a document for the office or sends a
form calls the checks below before it acts; a violated rule stops the action with a sentence that
names the rule. The model may be told about required wording so that drafts comply from the
start, but that is only a convenience: the check runs whatever the model wrote.

Kinds:
  musi_zawierac       a document (of a given kind, or any) must contain this wording
  nie_moze_zawierac   a document must never contain this wording
  pole_wymagane       a form is never sent while this field is empty or missing
  godziny_wysylki     forms are sent only on working days, between these hours
  pseudonimizacja     pseudonymisation cannot be switched off
"""
import json
import re
import threading
import time
import unicodedata
from datetime import date, datetime, timedelta

CASE = "zasady-kancelarii"
NAME = "zasady.json"
KINDS = ("musi_zawierac", "nie_moze_zawierac", "pole_wymagane", "godziny_wysylki", "pseudonimizacja")
MAX_RULES = 100


class RuleViolation(Exception):
    """Fixed message naming the rule; safe to show."""


def norm(text) -> str:
    text = str(text or "").lower().replace("ł", "l")
    text = "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")
    return " ".join(re.sub(r"[^\w§]+", " ", text).split())


def _easter(year: int) -> date:
    a, b, c = year % 19, year // 100, year % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    return date(year, month, (h + l - 7 * m + 114) % 31 + 1)


def is_working_day(day: date) -> bool:
    """Monday to Friday, except Polish public holidays (ustawa o dniach wolnych od pracy)."""
    if day.weekday() >= 5:
        return False
    fixed = {(1, 1), (1, 6), (5, 1), (5, 3), (8, 15), (11, 1), (11, 11), (12, 24), (12, 25), (12, 26)}
    easter = _easter(day.year)
    moving = {easter + timedelta(days=1), easter + timedelta(days=60)}       # Easter Monday, Corpus Christi
    return (day.month, day.day) not in fixed and day not in moving


def describe(rule: dict) -> str:
    kind, scope = rule["rodzaj"], rule.get("dotyczy") or ""
    where = f" ({scope})" if scope else ""
    if kind == "musi_zawierac":
        return f"Każdy dokument{where} musi zawierać „{rule['tekst']}”."
    if kind == "nie_moze_zawierac":
        return f"Żaden dokument{where} nie może zawierać „{rule['tekst']}”."
    if kind == "pole_wymagane":
        return f"Formularz{where} nie zostanie wysłany bez wypełnionego pola „{rule['tekst']}”."
    if kind == "godziny_wysylki":
        return f"Formularze i pocztę wysyłam tylko w dni robocze od {rule['od']}:00 do {rule['do']}:00."
    return "Pseudonimizacji nie można wyłączyć."


def _applies(rule: dict, subject: str) -> bool:
    scope = norm(rule.get("dotyczy") or "")
    if not scope:
        return True
    subject = norm(subject)
    # "sprzedaży" in a rule should match "sprzedaz" in a file name: compare word stems.
    return all(any(word[:5] in token for token in subject.split()) for word in scope.split())


def validate(rule: dict) -> dict:
    if not isinstance(rule, dict) or rule.get("rodzaj") not in KINDS:
        raise ValueError("unknown rule")
    clean = {"rodzaj": rule["rodzaj"], "dotyczy": " ".join(str(rule.get("dotyczy") or "").split())[:80]}
    if clean["rodzaj"] in {"musi_zawierac", "nie_moze_zawierac", "pole_wymagane"}:
        clean["tekst"] = " ".join(str(rule.get("tekst") or "").split())[:300]
        if len(norm(clean["tekst"])) < 2:
            raise ValueError("rule needs wording")
    if clean["rodzaj"] == "godziny_wysylki":
        start, end = int(rule.get("od", 8)), int(rule.get("do", 16))
        if not 0 <= start < end <= 24:
            raise ValueError("invalid hours")
        clean.update(od=start, do=end)
    return clean


class Rules:
    """Stored in the vault: encrypted, versioned, every change in the access log."""

    def __init__(self, vault):
        self._vault, self._lock = vault, threading.Lock()

    def _document(self):
        return next((d for d in self._vault.summaries({CASE}) if d["name"] == NAME), None)

    def all(self) -> list[dict]:
        found = self._document()
        if found is None:
            return []
        _, _, data = self._vault.get(found["id"], actor="zasady")
        return json.loads(data)

    def _store(self, rules: list[dict], actor: str) -> None:
        data = json.dumps(rules, ensure_ascii=False, indent=1).encode()
        found = self._document()
        if found is None:
            self._vault.put(None, 0, NAME, data, actor=actor, case=CASE)
        else:
            self._vault.put(found["id"], found["version"], NAME, data, actor=actor)

    def add(self, rule: dict, actor: str) -> dict:
        clean = validate(rule)
        with self._lock:
            rules = self.all()
            if any({k: v for k, v in r.items() if k != "utworzono"} == clean for r in rules):
                raise ValueError("duplicate rule")
            if len(rules) >= MAX_RULES:
                raise ValueError("too many rules")
            clean["utworzono"] = int(time.time())
            self._store(rules + [clean], actor)
        return clean

    def remove(self, number: int, actor: str) -> dict:
        with self._lock:
            rules = self.all()
            if not 1 <= number <= len(rules):
                raise ValueError("no such rule")
            removed = rules.pop(number - 1)
            self._store(rules, actor)
        return removed

    # ------------------------------------------------------------ checks
    def check_document(self, name: str, text: str, kind_hint: str = "") -> None:
        """Before a document is stored for the office. `kind_hint`: e.g. the drafting instruction."""
        plain, subject = norm(text), f"{name} {kind_hint} {text[:400]}"
        broken = []
        for number, rule in enumerate(self.all(), 1):
            if not _applies(rule, subject):
                continue
            if rule["rodzaj"] == "musi_zawierac" and norm(rule["tekst"]) not in plain:
                broken.append((number, rule))
            if rule["rodzaj"] == "nie_moze_zawierac" and norm(rule["tekst"]) in plain:
                broken.append((number, rule))
        if broken:
            raise RuleViolation("Nie zapiszę, bo dokument łamie zasady kancelarii: "
                                + " ".join(f"{n}. {describe(r)}" for n, r in broken)
                                + " Popraw tekst albo zmień zasadę w panelu stanowiska.")

    def check_send(self, procedure: str, report: list[dict], now: datetime | None = None) -> None:
        """Before a form is sent. `report`: what autofill entered, field by field."""
        now = now or datetime.now()
        filled = {norm(r["field"]) for r in report if r.get("state") == "filled" and str(r.get("value", "")).strip()}
        broken = []
        for number, rule in enumerate(self.all(), 1):
            if rule["rodzaj"] == "godziny_wysylki":
                if not (is_working_day(now.date()) and rule["od"] <= now.hour < rule["do"]):
                    broken.append((number, rule))
            elif rule["rodzaj"] == "pole_wymagane" and _applies(rule, procedure):
                if not any(norm(rule["tekst"]) == field or norm(rule["tekst"]) in field for field in filled):
                    broken.append((number, rule))
        if broken:
            raise RuleViolation("Nie wyślę, bo to łamie zasady kancelarii: "
                                + " ".join(f"{n}. {describe(r)}" for n, r in broken))

    def check_setting(self, pseudonymize: bool) -> None:
        if not pseudonymize and any(r["rodzaj"] == "pseudonimizacja" for r in self.all()):
            raise RuleViolation("Zasada kancelarii nie pozwala wyłączyć pseudonimizacji.")

    def required_wording(self, subject: str) -> list[str]:
        """Wording the model is asked to include (a convenience; the check above decides)."""
        return [r["tekst"] for r in self.all() if r["rodzaj"] == "musi_zawierac" and _applies(r, subject)]


# ------------------------------------------------------------ the notary's sentence -> a rule
QUOTE = re.compile(r"[„\"“”']([^„\"“”']{2,300})[”\"“']")
TYPES = ("sprzedaży", "sprzedaż", "darowizny", "darowizna", "pełnomocnictwa", "pełnomocnictwo", "testamentu",
         "testament", "hipoteki", "hipoteka", "dziedziczenia", "spółki", "dożywocia", "służebności", "najmu",
         "zamiany", "działu spadku", "zniesienia współwłasności", "majątkowej małżeńskiej")


def parse(sentence: str) -> dict | None:
    """Understand the few rule shapes the code can enforce. None: not one of them."""
    plain = norm(sentence)
    quoted = QUOTE.search(sentence)
    scope = next((t for t in TYPES if norm(t) in plain.split() or f" {norm(t)} " in f" {plain} "), "")
    if "pseudonimiz" in plain and re.search(r"zawsze|nie wolno wylacz|nigdy nie wylacz|nie mozna wylacz", plain):
        return {"rodzaj": "pseudonimizacja"}
    hours = re.search(r"od (\d{1,2})(?::00)? do (\d{1,2})(?::00)?", plain)
    if re.search(r"wysyl|wysyla|skladan|zloz", plain) and (hours or "robocz" in plain) and not quoted:
        start, end = (int(hours.group(1)), int(hours.group(2))) if hours else (0, 24)
        return {"rodzaj": "godziny_wysylki", "od": start, "do": end}
    if quoted is None:
        return None
    wording = quoted.group(1).strip()
    if re.search(r"\bpole\b", plain) and re.search(r"wysyl|wypelnion|wymagan|puste", plain):
        procedure = QUOTE.findall(sentence)
        return {"rodzaj": "pole_wymagane", "tekst": wording,
                "dotyczy": procedure[1].strip() if len(procedure) > 1 else ""}
    if re.search(r"\b(nigdy|nie moze|nie moga|nie wolno|zakaz|zabronion|bez)\b", plain):
        return {"rodzaj": "nie_moze_zawierac", "tekst": wording, "dotyczy": scope}
    if re.search(r"\b(musi|musza|zawsze|kazdy|kazda|wymagan|zawiera)", plain):
        return {"rodzaj": "musi_zawierac", "tekst": wording, "dotyczy": scope}
    return None
