"""Asysta w wypelnianiu formularzy w systemach urzedowych (SPEC, zadanie B).

Zasady wbudowane w kod, nie w dobra wole:
- czlowiek loguje sie sam; podlaczamy sie do JUZ otwartej przegladarki,
- domyslnie tryb podgladu (nic nie wpisujemy),
- przycisk wysylki jest znany silnikowi tylko po to, zeby NIGDY go nie kliknac,
- mapowanie pol w pliku .yaml obok, nie w kodzie,
- wartosci dobierane z tresci aktu maja cytat uzasadniajacy,
- w logach zero danych osobowych.
"""
from .dopasowanie import dopasuj  # noqa: F401
from .silnik import (  # noqa: F401
    Mapowanie,
    Raport,
    BladMapowania,
    wczytaj_mapowanie,
    dostepne_systemy,
    zaplanuj,
    wypelnij,
)
