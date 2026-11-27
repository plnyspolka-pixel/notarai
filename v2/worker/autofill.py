"""Fill forms by itself; send only after the notary approves exactly what is on screen.

The same plan works for web pages and Windows programs. A target (web_fill.Browser or
win_fill.Desktop) lists the controls it sees with their visible labels; the plan matches each
procedure step to one control by its label, fills it, reads the value back, and stops before
any step marked as sending. Navigation buttons ("Dalej") are pressed automatically, because
they only move between pages of the same form.

Sending is a separate call that needs a confirmation token bound to a fingerprint of the
form at preview time. If anything changed since (the notary corrected a field, the page
reloaded), sending is refused and a fresh preview is shown. The send button is pressed once;
an uncertain outcome is never retried.
"""
import difflib
import hashlib
import json
import re
import secrets
import threading
import time
import unicodedata
from dataclasses import dataclass, field

ACTIONS = ("wpisz", "kliknij", "wyslij")
PREVIEW_TTL = 15 * 60
YES = {"tak", "t", "yes", "true", "1", "x", "zaznacz", "zaznaczone", "prawda"}


class FillError(Exception):
    """Fixed message, safe to show."""


def norm(text: str) -> str:
    text = str(text or "").lower().replace("ł", "l")
    text = "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")
    return " ".join(re.sub(r"[^a-z0-9]+", " ", text).split())


@dataclass
class Control:
    """One thing on screen. `ref` is the target's own handle for it."""
    ref: object
    kind: str                     # text | select | check | button
    label: str
    value: str = ""
    options: list = field(default_factory=list)


def action_of(step) -> str:
    akcja = norm(getattr(step, "akcja", "") or "")
    if akcja in ACTIONS:
        return akcja
    source = norm(getattr(step, "zrodlo", ""))
    if source.startswith(("wyslij", "zloz", "przeslij", "podpisz i wyslij")):
        return "wyslij"
    if source.startswith(("kliknij", "nacisnij", "wcisnij")):
        return "kliknij"
    return "wpisz"


def score(label: str, wanted: str) -> float:
    a, b = norm(label), norm(wanted)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    if a.startswith(b) or b.startswith(a):
        return 0.92
    words_a, words_b = set(a.split()), set(b.split())
    if words_b <= words_a or words_a <= words_b:
        return 0.88
    return difflib.SequenceMatcher(None, a, b).ratio()


def match(controls: list[Control], wanted: str, kinds: set[str], used: set[int]) -> Control | None:
    best, best_score = None, 0.0
    for control in controls:
        if control.kind not in kinds or id(control) in used:
            continue
        current = score(control.label, wanted)
        if current > best_score:
            best, best_score = control, current
    return best if best_score >= 0.8 else None


def choose_option(options: list[str], value: str) -> str | None:
    """The option a human would pick for this value: exact, then by meaning of words."""
    if not options:
        return None
    scored = sorted(((score(option, value), option) for option in options), reverse=True)
    return scored[0][1] if scored[0][0] >= 0.75 else None


def fingerprint(where: str, controls: list[Control]) -> str:
    seen = [(c.kind, c.label, c.value) for c in controls if c.kind != "button"]
    return hashlib.sha256(json.dumps([where, seen], ensure_ascii=False).encode()).hexdigest()


@dataclass
class Preview:
    token: str
    actor: str
    procedure: str
    case: str
    where: str
    fingerprint: str
    send_label: str | None
    expires: float
    report: list = field(default_factory=list)


class Autofill:
    def __init__(self, targets: dict, receipts=None, rules=None):
        """`targets`: {"strona": callable -> web target, "program": callable -> desktop target}."""
        self._targets, self._receipts, self._rules = targets, receipts, rules
        self._previews: dict[str, Preview] = {}
        self._lock = threading.Lock()

    def target(self, kind: str):
        factory = self._targets.get(kind)
        if factory is None:
            raise FillError("Na tym komputerze nie umiem jeszcze wypełniać "
                            + ("stron." if kind == "strona" else "programów Windows."))
        return factory()

    # ------------------------------------------------------------ filling
    def fill(self, procedure, values: list[dict], *, actor: str, case: str) -> dict:
        """Enter every value; press navigation buttons; stop before sending. Returns a preview."""
        kind = procedure.rodzaj or "strona"
        target = self.target(kind)
        target.focus(procedure.adres)
        report, send_label, used = [], None, set()
        controls = target.controls()
        for step, item in zip(procedure.kroki, values):
            action = action_of(step)
            if action == "wyslij":
                send_label = step.pole
                break
            if action == "kliknij":
                button = match(controls, step.pole, {"button"}, set())
                if button is None:
                    report.append({"field": step.pole, "state": "missing", "value": ""})
                    continue
                target.click(button)
                controls, used = target.controls(), set()      # a new page of the form
                report.append({"field": step.pole, "state": "clicked", "value": ""})
                continue
            value = str(item.get("value") or "")
            if not value:
                report.append({"field": step.pole, "state": "empty", "value": ""})
                continue
            control = match(controls, step.pole, {"text", "select", "check"}, used)
            if control is None:
                report.append({"field": step.pole, "state": "missing", "value": value})
                continue
            used.add(id(control))
            try:
                if control.kind == "select":
                    option = choose_option(control.options, value)
                    if option is None:
                        report.append({"field": step.pole, "state": "no-option", "value": value})
                        continue
                    target.choose(control, option)
                    expected = option
                elif control.kind == "check":
                    expected = "tak" if norm(value) in YES else "nie"
                    target.check(control, expected == "tak")
                else:
                    target.type(control, value)
                    expected = value
                read = target.read(control)
            except FillError:
                report.append({"field": step.pole, "state": "refused", "value": value})
                continue
            ok = norm(read) == norm(expected) or (control.kind == "text" and read.strip() == expected.strip())
            report.append({"field": step.pole, "state": "filled" if ok else "differs", "value": expected,
                           "read": read if not ok else ""})
        controls = target.controls()
        where = target.where()
        if send_label is not None and match(controls, send_label, {"button"}, set()) is None:
            send_label_found = False
        else:
            send_label_found = send_label is not None
        preview = Preview(secrets.token_urlsafe(16), actor, procedure.nazwa, case, where,
                          fingerprint(where, controls), send_label if send_label_found else None,
                          time.monotonic() + PREVIEW_TTL, report)
        with self._lock:
            now = time.monotonic()
            self._previews = {k: v for k, v in self._previews.items() if v.expires > now and v.actor != actor}
            self._previews[preview.token] = preview
        self._receipt(actor, "fill", procedure.nazwa, kind, "verified" if all(
            r["state"] in {"filled", "clicked"} for r in report) else "partial")
        return {"token": preview.token, "procedure": procedure.nazwa, "where": where, "kind": kind,
                "report": report, "send": send_label if send_label_found else None,
                "send_missing": send_label if send_label is not None and not send_label_found else None,
                "image": target.snapshot()}

    # ------------------------------------------------------------ sending
    def send(self, token: str, actor: str, kind: str) -> dict:
        with self._lock:
            preview = self._previews.get(token)
            if preview is not None and preview.actor == actor:
                del self._previews[token]          # one approval, one press; someone else's attempt does not use it up
            else:
                preview = None
        if preview is None or preview.expires <= time.monotonic():
            raise FillError("Ten podgląd wygasł. Napisz „wypełnij” jeszcze raz, a pokażę formularz ponownie.")
        if preview.send_label is None:
            raise FillError("Ta procedura nie ma kroku wysyłania. Wyślij formularz ręcznie.")
        if self._rules is not None:
            from .rules import RuleViolation

            try:
                self._rules.check_send(preview.procedure, preview.report)
            except RuleViolation as violation:
                raise FillError(str(violation)) from None
        target = self.target(kind)
        controls = target.controls()
        if target.where() != preview.where or fingerprint(target.where(), controls) != preview.fingerprint:
            raise FillError("Formularz zmienił się od podglądu. Napisz „wypełnij” jeszcze raz, żeby zobaczyć, co wyślę.")
        button = match(controls, preview.send_label, {"button"}, set())
        if button is None:
            raise FillError("Nie widzę przycisku wysyłania. Wyślij formularz ręcznie.")
        self._receipt(actor, "send", preview.procedure, kind, "started")
        try:
            target.click(button)
            after = target.where()
            image = target.snapshot()
            outcome = "sent" if after != preview.where else "uncertain"
        except Exception:
            # Pressed or not, the result is unknown: report it and never press again by ourselves.
            self._receipt(actor, "send", preview.procedure, kind, "uncertain")
            raise FillError("Nie wiem, czy formularz został wysłany. Sprawdź na ekranie, zanim spróbujesz ponownie.") from None
        self._receipt(actor, "send", preview.procedure, kind, outcome)
        return {"state": outcome, "where": after, "image": image}

    def _receipt(self, actor, action, procedure, kind, state):
        if self._receipts is not None:
            self._receipts(actor, action, procedure, kind, state)
