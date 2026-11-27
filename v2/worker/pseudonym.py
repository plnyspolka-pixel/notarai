"""Reversible local pseudonymisation of Polish identifiers before text leaves the computer.

Identifiers with a checksum (PESEL, NIP, REGON, bank account) are replaced only when
the checksum holds, so ordinary numbers stay readable. The mapping lives in memory
for one request and is never written or sent.
"""
import re


def _weights_ok(digits: str, weights, modulus=11, transform=lambda r: r) -> bool:
    total = sum(int(d) * w for d, w in zip(digits, weights))
    return transform(total % modulus) == int(digits[len(weights)])


def _pesel(d):
    return (10 - sum(int(a) * w for a, w in zip(d, (1, 3, 7, 9, 1, 3, 7, 9, 1, 3))) % 10) % 10 == int(d[10])


def _nip(d):
    r = sum(int(a) * w for a, w in zip(d, (6, 5, 7, 2, 3, 4, 5, 6, 7))) % 11
    return r != 10 and r == int(d[9])


def _regon(d):
    weights = (8, 9, 2, 3, 4, 5, 6, 7) if len(d) == 9 else (2, 4, 8, 5, 0, 9, 7, 3, 6, 1, 2, 4, 8)
    return sum(int(a) * w for a, w in zip(d, weights)) % 11 % 10 == int(d[-1])


def _nrb(d):
    return int(d[2:] + "2521" + d[:2]) % 97 == 1


def _id_card(text):
    values = [ord(c) - 55 if c.isalpha() else int(c) for c in text]
    return sum(v * w for v, w in zip(values[:3] + values[4:], (7, 3, 1, 7, 3, 1, 7, 3))) % 10 == values[3]


def _digits(text):
    return re.sub(r"\D", "", text)


_SEP = r"[ \u00a0-]?"     # ordinary space, the non-breaking space Word inserts, or a hyphen
_RULES = (
    # E-mail first: a surname inside an address must not split it.
    ("EMAIL", re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+"), lambda m: True),
    ("RACHUNEK", re.compile(r"(?<![\w])(?:PL" + _SEP + r")?\d{2}(?:" + _SEP + r"\d{4}){6}(?![\w])"),
     lambda m: _nrb(_digits(m))),
    ("PESEL", re.compile(r"(?<!\d)\d{11}(?!\d)"), _pesel),
    ("NIP", re.compile(r"(?<!\d)(?:\d{10}|\d{3}[ -]\d{3}[ -]\d{2}[ -]\d{2}|\d{3}[ -]\d{2}[ -]\d{2}[ -]\d{3})(?!\d)"),
     lambda m: _nip(_digits(m))),
    ("KW", re.compile(r"(?<![A-Z0-9])[A-Z]{2}\d[A-Z]/\d{8}/\d(?!\d)"), lambda m: True),
    ("DOWOD", re.compile(r"(?<![A-Z0-9])[A-Z]{3}\s?\d{6}(?!\d)"), lambda m: _id_card(m.replace(" ", ""))),
    ("PASZPORT", re.compile(r"(?<![A-Z0-9])[A-Z]{2}\s?\d{7}(?!\d)"), lambda m: True),
    ("REGON", re.compile(r"(?<!\d)(?:\d{14}|\d{9})(?!\d)"), _regon),
    # Mobile 3-3-3 or landline 2-3-2-2; a following currency means it is an amount, not a number to hide.
    ("TELEFON", re.compile(
        r"(?<![\w+])(?:\+48[ -]?)?(?:\d{3}[ -]?\d{3}[ -]?\d{3}|\d{2}[ -]\d{3}[ -]\d{2}[ -]\d{2})"
        r"(?![\w])(?!\s*(?:zł|PLN|złot|,\d{2}))"), lambda m: len(_digits(m)) in (9, 11)),
)
_KINDS = "RACHUNEK|PESEL|NIP|KW|DOWOD|PASZPORT|EMAIL|REGON|TELEFON|OSOBA|ZNACZNIK"
_PLACEHOLDER = re.compile(r"\[(?:" + _KINDS + r")_\d+(?:_[A-Z]+)?\]")
_VOWELS = "aeiouyąęó"
_ALTERNATIONS = (("ch", "sz"), ("k", "c"), ("g", "dz"), ("r", "rz"), ("ł", "l"), ("t", "ci"), ("d", "dzi"))


def _stems(token: str) -> list[str]:
    """Stems that survive Polish declension: Marek -> Mark-, Olga -> Oldz-, Mucha -> Musz-."""
    lowered = token.lower()
    stems = {lowered}
    if len(lowered) >= 3 and lowered[-1] in _VOWELS:
        stems.add(lowered[:-1])
    for stem in list(stems):
        if len(stem) >= 4 and stem[-2] == "e" and stem[-1] not in _VOWELS:     # fleeting e: Dudek -> Dudk-
            stems.add(stem[:-2] + stem[-1])
    for stem in list(stems):
        for ending, replacement in _ALTERNATIONS:
            if stem.endswith(ending) and len(stem) > len(ending) + 1:
                stems.add(stem[:-len(ending)] + replacement)
                break
    return sorted((s for s in stems if len(s) >= 2), key=len, reverse=True)


def _letters(index: int) -> str:
    out = ""
    while True:
        out = chr(65 + index % 26) + out
        index = index // 26 - 1
        if index < 0:
            return out


class Pseudonymizer:
    """One instance per request. `names` are people or companies known from the case."""

    def __init__(self, names=()):
        self._forward: dict[str, str] = {}
        self._back: dict[str, str] = {}
        self._counts: dict[str, int] = {}
        self._names = []
        for index, name in enumerate(dict.fromkeys(n.strip() for n in names if n and n.strip()), 1):
            parts = [self._inflected(token) for token in name.split()]
            if parts:
                self._names.append((index, re.compile(r"(?<!\w)" + r"\s+".join(parts) + r"(?!\w)")))
        # A surname on its own ("Kowalski oświadcza") after the full names, so full matches win.
        for index, name in enumerate(dict.fromkeys(n.strip() for n in names if n and n.strip()), 1):
            tokens = name.split()
            surname = tokens[-1].strip(".,;") if len(tokens) > 1 else ""
            if len(surname) >= 4 and all(part.isalpha() for part in surname.split("-")):
                self._names.append((index, re.compile(r"(?<!\w)" + self._inflected(surname) + r"(?!\w)")))

    @staticmethod
    def _inflected(token: str) -> str:
        token = token.strip(".,;")
        parts = []
        for part in token.split("-"):          # Kowalska-Nowak: each half declines on its own
            if len(part) >= 3 and part.isalpha():
                # The first letter must be a capital in the text, so "Lipa" never swallows "lipca".
                first = re.escape(part[0].upper())
                tails = "|".join(re.escape(stem[1:]) for stem in _stems(part))
                parts.append(f"{first}(?i:(?:{tails})\\w{{0,5}})")
            else:
                parts.append(re.escape(part))
        return "-".join(parts)

    def _token(self, kind: str, original: str, key: str) -> str:
        if key in self._forward:
            return self._forward[key]
        self._counts[kind] = self._counts.get(kind, 0) + 1
        token = f"[{kind}_{self._counts[kind]}]"
        self._forward[key], self._back[token] = token, original
        return token

    def _person(self, index: int, original: str) -> str:
        key = f"OSOBA:{index}:{original}"
        if key in self._forward:
            return self._forward[key]
        variant = self._counts.get(f"OSOBA:{index}", 0)
        self._counts[f"OSOBA:{index}"] = variant + 1
        token = f"[OSOBA_{index}]" if variant == 0 else f"[OSOBA_{index}_{_letters(variant - 1)}]"
        self._forward[key], self._back[token] = token, original
        return token

    def hide(self, text: str) -> str:
        # Text that already looks like one of our placeholders (an earlier draft, or a document
        # trying to plant one) is itself hidden, so it can never read another value back.
        text = _PLACEHOLDER.sub(lambda m: self._token("ZNACZNIK", m.group(0), "ZNACZNIK:" + m.group(0)), text)
        for kind, pattern, valid in _RULES:
            def swap(match, kind=kind, valid=valid):
                found = match.group(0)
                if not valid(found):
                    return found
                return self._token(kind, found, kind + ":" + re.sub(r"[\s\u00a0-]", "", found).upper())
            text = pattern.sub(swap, text)
        for index, pattern in self._names:
            text = pattern.sub(lambda m, i=index: self._person(i, m.group(0)), text)
        return text

    def reveal(self, text: str) -> tuple[str, list[str]]:
        """Put originals back. Returns the text and any placeholders the model invented."""
        unknown = []

        def swap(match):
            token = match.group(0)
            if token in self._back:
                return self._back[token]
            unknown.append(token)
            return token
        return _PLACEHOLDER.sub(swap, text), unknown

    @property
    def replaced(self) -> int:
        return len(self._back)
