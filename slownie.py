"""Kwoty slownie po polsku - do autonaprawy zasady "kwoty cyframi i slownie".

    slownie_kwoty("250.000,00 zł") -> "dwieście pięćdziesiąt tysięcy złotych"
    slownie_kwoty("1 001,50")      -> "tysiąc jeden złotych pięćdziesiąt groszy"

Liczy deterministycznie, wiec nie wymaga modelu i nie myli sie w odmianie.
"""
import re

_JEDNOSCI = ["", "jeden", "dwa", "trzy", "cztery", "pięć", "sześć", "siedem", "osiem", "dziewięć"]
_NASTKI = ["dziesięć", "jedenaście", "dwanaście", "trzynaście", "czternaście", "piętnaście",
           "szesnaście", "siedemnaście", "osiemnaście", "dziewiętnaście"]
_DZIESIATKI = ["", "", "dwadzieścia", "trzydzieści", "czterdzieści", "pięćdziesiąt",
               "sześćdziesiąt", "siedemdziesiąt", "osiemdziesiąt", "dziewięćdziesiąt"]
_SETKI = ["", "sto", "dwieście", "trzysta", "czterysta", "pięćset", "sześćset", "siedemset",
          "osiemset", "dziewięćset"]
_RZEDY = [("", "", ""), ("tysiąc", "tysiące", "tysięcy"), ("milion", "miliony", "milionów"),
          ("miliard", "miliardy", "miliardów")]


def forma(liczba: int, pojedyncza: str, mnoga: str, dopelniacz: str) -> str:
    """1 zloty, 2-4 zlote, 5+ zlotych (12-14 tez "zlotych")."""
    if liczba == 1:
        return pojedyncza
    if liczba % 10 in (2, 3, 4) and liczba % 100 not in (12, 13, 14):
        return mnoga
    return dopelniacz


def _trojka(n: int) -> list[str]:
    slowa = [_SETKI[n // 100]]
    reszta = n % 100
    if 10 <= reszta < 20:
        slowa.append(_NASTKI[reszta - 10])
    else:
        slowa += [_DZIESIATKI[reszta // 10], _JEDNOSCI[reszta % 10]]
    return [s for s in slowa if s]


def liczba_slownie(n: int) -> str:
    if n == 0:
        return "zero"
    if n < 0:
        return "minus " + liczba_slownie(-n)
    czesci = []
    rzad = 0
    while n:
        trojka = n % 1000
        if trojka:
            slowa = _trojka(trojka)
            if rzad:
                nazwa = forma(trojka, *_RZEDY[rzad])
                # "tysiąc", nie "jeden tysiąc" - jak w aktach
                slowa = [nazwa] if trojka == 1 else slowa + [nazwa]
            czesci.insert(0, " ".join(slowa))
        n //= 1000
        rzad += 1
        if rzad >= len(_RZEDY) and n:
            raise ValueError("Kwota poza zakresem")
    return " ".join(czesci)


def parsuj_kwote(tekst: str) -> tuple[int, int]:
    """'250.000,00 zł' / '250 000,5' / '1000' -> (zlote, grosze)."""
    czysty = re.sub(r"[^\d,]", "", tekst.replace(".", "").replace(" ", ""))
    if "," in czysty:
        zl, gr = czysty.split(",", 1)
        gr = (gr + "0")[:2] if gr else "00"
    else:
        zl, gr = czysty, "00"
    return int(zl or 0), int(gr)


def slownie_kwoty(tekst: str) -> str:
    zl, gr = parsuj_kwote(tekst)
    wynik = f"{liczba_slownie(zl)} {forma(zl, 'złoty', 'złote', 'złotych')}"
    if gr:
        wynik += f" {liczba_slownie(gr)} {forma(gr, 'grosz', 'grosze', 'groszy')}"
    return wynik
