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


_RULES = (
    ("RACHUNEK", re.compile(r"(?<![\w])(?:PL\s?)?\d{2}(?:[ ]?\d{4}){6}(?![\w])"), lambda m: _nrb(_digits(m))),
    ("PESEL", re.compile(r"(?<!\d)\d{11}(?!\d)"), _pesel),
    ("NIP", re.compile(r"(?<!\d)(?:\d{10}|\d{3}-\d{3}-\d{2}-\d{2}|\d{3}-\d{2}-\d{2}-\d{3})(?!\d)"),
     lambda m: _nip(_digits(m))),
    ("KW", re.compile(r"(?<![A-Z0-9])[A-Z]{2}\d[A-Z]/\d{8}/\d(?!\d)"), lambda m: True),
    ("DOWOD", re.compile(r"(?<![A-Z0-9])[A-Z]{3}\s?\d{6}(?!\d)"), lambda m: _id_card(m.replace(" ", ""))),
    ("EMAIL", re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+"), lambda m: True),
    ("REGON", re.compile(r"(?<!\d)(?:\d{14}|\d{9})(?!\d)"), _regon),
    ("TELEFON", re.compile(r"(?<![\w+])(?:\+48[ -]?)?\d{3}[ -]?\d{3}[ -]?\d{3}(?![\w])"),
     lambda m: len(_digits(m)) in (9, 11)),
)
_PLACEHOLDER = re.compile(r"\[(?:RACHUNEK|PESEL|NIP|KW|DOWOD|EMAIL|REGON|TELEFON|OSOBA)_\d+(?:_[A-Z]+)?\]")


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
                self._names.append((index, re.compile(r"(?<!\w)" + r"\s+".join(parts) + r"(?!\w)", re.IGNORECASE)))
        # A surname on its own ("Kowalski oświadcza") after the full names, so full matches win.
        for index, name in enumerate(dict.fromkeys(n.strip() for n in names if n and n.strip()), 1):
            tokens = name.split()
            if len(tokens) > 1 and len(tokens[-1]) >= 4 and tokens[-1].isalpha():
                self._names.append(
                    (index, re.compile(r"(?<!\w)" + self._inflected(tokens[-1]) + r"(?!\w)", re.IGNORECASE)))

    @staticmethod
    def _inflected(token: str) -> str:
        token = token.strip(".,;")
        if len(token) >= 3 and token.isalpha():
            # Polish inflection: "Kowalski" -> "Kowalskiego", "Jan" -> "Janowi".
            stem = token[:-1] if len(token) >= 4 and token[-1].lower() in "aeiouyąę" else token
            return re.escape(stem) + r"\w{0,5}"
        return re.escape(token)

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
        if _PLACEHOLDER.search(text):
            # Otherwise a document could plant a token and read another party's value back.
            raise ValueError("text already contains pseudonym placeholders")
        for index, pattern in self._names:
            text = pattern.sub(lambda m, i=index: self._person(i, m.group(0)), text)
        for kind, pattern, valid in _RULES:
            def swap(match, kind=kind, valid=valid):
                found = match.group(0)
                if not valid(found):
                    return found
                return self._token(kind, found, f"{kind}:{_digits(found) or found.lower()}")
            text = pattern.sub(swap, text)
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
