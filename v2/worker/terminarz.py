"""The office calendar: appointments said in a sentence, kept encrypted in the vault.

"termin w piątek 10:00 podpisanie aktu Kowalski", "dodaj termin 5 grudnia o 9:30 Nowak",
"termin jutro 14 odbiór wypisu", "co mam jutro", "kalendarz". Dates are read by code, not by the
model, so an appointment is never invented. Notes from conversations add appointments too, marked
"z rozmowy, do sprawdzenia".
"""
import datetime as dt
import re
import secrets
import unicodedata

MONTHS = {"stycznia": 1, "styczen": 1, "lutego": 2, "luty": 2, "marca": 3, "marzec": 3, "kwietnia": 4,
          "kwiecien": 4, "maja": 5, "maj": 5, "czerwca": 6, "czerwiec": 6, "lipca": 7, "lipiec": 7,
          "sierpnia": 8, "sierpien": 8, "wrzesnia": 9, "wrzesien": 9, "pazdziernika": 10, "pazdziernik": 10,
          "listopada": 11, "listopad": 11, "grudnia": 12, "grudzien": 12}
WEEKDAYS = {"poniedzialek": 0, "wtorek": 1, "srode": 2, "sroda": 2, "czwartek": 3, "piatek": 4, "sobote": 5,
            "sobota": 5, "niedziele": 6, "niedziela": 6}
SHORT = ["pn", "wt", "śr", "czw", "pt", "sob", "nd"]


def _plain(text: str) -> str:
    text = text.lower().replace("ł", "l")
    return "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")


def parse_when(sentence: str, now: dt.datetime) -> tuple[dt.datetime, str] | None:
    """(start, what is left of the sentence) or None when no day is named. Time defaults to 9:00."""
    words = sentence.split()
    plain = [_plain(w).strip(",.;") for w in words]
    day, used = None, set()
    for i, word in enumerate(plain):
        if word in {"dzis", "dzisiaj"}:
            day, used = now.date(), {i}
        elif word == "jutro":
            day, used = now.date() + dt.timedelta(days=1), {i}
        elif word == "pojutrze":
            day, used = now.date() + dt.timedelta(days=2), {i}
        elif word in WEEKDAYS:
            ahead = (WEEKDAYS[word] - now.weekday()) % 7 or 7
            day, used = now.date() + dt.timedelta(days=ahead), {i}
            if i > 0 and plain[i - 1] in {"w", "we"}:
                used.add(i - 1)
        elif re.fullmatch(r"\d{1,2}\.\d{1,2}(\.\d{2,4})?", word):
            parts = [int(p) for p in word.split(".")]
            year = parts[2] if len(parts) == 3 else now.year
            year = year + 2000 if year < 100 else year
            try:
                day = dt.date(year, parts[1], parts[0])
            except ValueError:
                continue
            if len(parts) == 2 and day < now.date():
                day = day.replace(year=now.year + 1)
            used = {i}
        elif word.isdigit() and i + 1 < len(plain) and plain[i + 1] in MONTHS:
            year, extra = now.year, {i, i + 1}
            if i + 2 < len(plain) and re.fullmatch(r"20\d\d", plain[i + 2]):
                year, extra = int(plain[i + 2]), extra | {i + 2}
            try:
                day = dt.date(year, MONTHS[plain[i + 1]], int(word))
            except ValueError:
                continue
            if year == now.year and len(extra) == 2 and day < now.date():
                day = day.replace(year=now.year + 1)
            used = extra
        if day is not None:
            break
    if day is None:
        return None
    hour, minute = 9, 0
    for i, word in enumerate(plain):
        if i in used:
            continue
        found = re.fullmatch(r"(\d{1,2})[:.](\d{2})", word) or (
            re.fullmatch(r"(\d{1,2})", word) if i > 0 and plain[i - 1] in {"o", "godz", "godzina", "godzinie"} else None)
        if found and int(found.group(1)) < 24 and (found.lastindex == 1 or int(found.group(2)) < 60):
            hour, minute = int(found.group(1)), int(found.group(2)) if found.lastindex == 2 else 0
            used |= {i} | ({i - 1} if i > 0 and plain[i - 1] in {"o", "godz", "godzina", "godzinie"} else set())
            break
    rest = " ".join(w for i, w in enumerate(words) if i not in used).strip(" ,.-–:")
    return dt.datetime.combine(day, dt.time(hour, minute)), rest


def label(start: dt.datetime, now: dt.datetime, *, all_day: bool = False) -> str:
    if start.date() == now.date():
        day = "dziś"
    elif start.date() == now.date() + dt.timedelta(days=1):
        day = "jutro"
    else:
        day = f"{SHORT[start.weekday()]} {start.day}.{start.month:02d}"
    return f"{day}, cały dzień" if all_day else f"{day} {start.hour}:{start.minute:02d}"


class Calendar:
    def __init__(self, vault, clock=dt.datetime.now, origin=None):
        """`origin()`: this station's id, so only the station that added an entry sends it to notarai.pl."""
        self._vault, self._clock, self._origin = vault, clock, origin

    def now(self) -> dt.datetime:
        return self._clock().replace(second=0, microsecond=0)

    def add(self, start: dt.datetime, title: str, *, case=None, source="notariusz", actor="local-admin") -> dict:
        title = " ".join(title.split())[:200] or "Termin"
        entry = {"start": start.isoformat(timespec="minutes"), "title": title, "case": case, "source": source}
        if self._origin is not None:
            entry["origin"] = self._origin()
        ident = secrets.token_hex(6)
        self._vault.calendar_put(ident, entry, actor=actor)
        return {"id": ident, **entry}

    def delete(self, ident: str, *, actor="local-admin") -> bool:
        return self._vault.calendar_delete(ident, actor=actor)

    def upcoming(self, days: int = 14, *, cases=None, start: dt.date | None = None) -> list[dict]:
        """Appointments from today (or `start`) for `days` days, earliest first; `cases` limits a device."""
        first = dt.datetime.combine(start or self.now().date(), dt.time())
        last = first + dt.timedelta(days=days)
        items = []
        for entry in self._vault.calendar():
            when = dt.datetime.fromisoformat(entry["start"])
            if first <= when < last and (cases is None or entry.get("case") in cases):
                items.append({**entry, "label": label(when, self.now(), all_day=bool(entry.get("all_day")))})
        return sorted(items, key=lambda item: item["start"])

    def from_note(self, termin: str, title: str, case: str | None) -> dict | None:
        """An appointment heard in a conversation, when its day can be read; marked for checking."""
        parsed = parse_when(termin, self.now())
        if parsed is None:
            return None
        return self.add(parsed[0], title + " (z rozmowy, do sprawdzenia)", case=case, source="rozmowa",
                        actor="listening")
