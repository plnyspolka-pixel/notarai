"""Wykonanie zlecenia z notarai na komputerze notariusza.

Zlecenie przychodzi z serwera gotowe: adres formularza, selektory pol i
wartosci do wpisania. Pomocnik mimo to sprawdza je po swojemu, bo to on
siedzi przy zalogowanej sesji notariusza i to jego reka wpisuje. Serwer moze
sie pomylic albo mapowanie moze byc zle - ostatnie slowo ma ta strona.

Zasady z docs/formularze.md, wszystkie egzekwowane tutaj:
  - pomocnik wypelnia pola i zatrzymuje sie przed wyslaniem; nie zna operacji
    "kliknij przycisk wysylki" i odmawia zlecenia, ktore w nia celuje,
  - tryb podgladu jest domyslny, tryb faktyczny wymaga jawnego zadania,
  - mapowanie w statusie "szkic" nie wpisuje niczego,
  - strona musi byc ta, o ktorej mowi zlecenie,
  - do pola hasla ani PIN-u nie wpisujemy nigdy, choćby zlecenie tak kazalo.

W raporcie nie ma wartosci pol. Serwer i tak je zna, bo je przyslal, a raport
trafia do logow - dane osobowe nie maja tam czego szukac.
"""
from __future__ import annotations

import logging

log = logging.getLogger("notarai.pomocnik.wykonanie")

POLA_ZLECENIA = ("system", "adres", "gotowosc", "przycisk_wysylki", "kroki")
TYPY_ZABRONIONE = ("password",)
CZAS_NA_FORMULARZ = 15  # sekund; strona rejestru potrafi dociagac pola


class OdmowaWykonania(RuntimeError):
    """Pomocnik odmawia wykonania calego zlecenia.

    Tresc trafia do notariusza i do logow, wiec nie wolno w niej umieszczac
    wartosci pol.
    """


def _sprawdz_ksztalt(zlecenie: dict) -> None:
    brakujace = [p for p in POLA_ZLECENIA if not zlecenie.get(p)]
    if brakujace:
        raise OdmowaWykonania("Zlecenie niekompletne: brak " + ", ".join(brakujace))
    if not isinstance(zlecenie["kroki"], list):
        raise OdmowaWykonania("Zlecenie niekompletne: kroki nie sa lista")


def _sprawdz_przycisk_wysylki(zlecenie: dict) -> None:
    """Zadne pole nie moze wskazywac przycisku wysylki.

    To najwazniejsza kontrola w calym pomocniku. Gdy zlecenie w nia celuje,
    odmawiamy CALOSCI, a nie tylko tego kroku: skoro mapowanie jest bledne
    albo podmienione, reszcie tez nie ufamy.
    """
    wysylka = str(zlecenie["przycisk_wysylki"]).strip()
    for krok in zlecenie["kroki"]:
        if str(krok.get("selektor", "")).strip() == wysylka:
            raise OdmowaWykonania(
                f"Odmowa: zlecenie kaze dzialac na przycisku wysylki ({krok.get('pole', '?')})."
            )


def _sprawdz_strone(zlecenie: dict, strona) -> None:
    adres = str(zlecenie["adres"])
    if not strona.url.startswith(adres):
        raise OdmowaWykonania(
            "Otwarta strona nie jest formularzem tego rejestru. "
            "Zaloguj sie i otworz wlasciwy formularz."
        )
    gotowe = strona.poczekaj_na(zlecenie["gotowosc"], CZAS_NA_FORMULARZ) \
        if hasattr(strona, "poczekaj_na") else strona.istnieje(zlecenie["gotowosc"])
    if not gotowe:
        raise OdmowaWykonania(
            "Formularz nie jest gotowy - nie widze pola, ktore powinno na nim byc."
        )


def plan(zlecenie: dict) -> list[dict]:
    """Co pomocnik zrobilby, gdyby ruszyl. Nie dotyka przegladarki."""
    return [
        {
            "pole": krok.get("pole", ""),
            "selektor": krok.get("selektor", ""),
            "typ": krok.get("typ", "tekst"),
            "ma_wartosc": bool(str(krok.get("wartosc") or "").strip()),
            "wykonano": False,
            "uwaga": "" if str(krok.get("wartosc") or "").strip() else "brak wartosci",
        }
        for krok in zlecenie.get("kroki", [])
    ]


def wykonaj(zlecenie: dict, strona) -> dict:
    """Wypelnia formularz na JUZ otwartej, zalogowanej stronie.

    Zwraca raport bez wartosci pol. Nie wysyla formularza - pomocnik nie ma
    czym go wyslac.
    """
    _sprawdz_ksztalt(zlecenie)
    _sprawdz_przycisk_wysylki(zlecenie)

    tryb = zlecenie.get("tryb", "podglad")
    raport = {
        "system": zlecenie["system"],
        "tryb": "podglad",
        "kroki": plan(zlecenie),
        "bledy": [],
        "zatrzymano_przed": "przyciskiem wysylki - wysyla czlowiek",
    }
    if tryb != "faktyczny":
        return raport
    if zlecenie.get("status_mapowania") != "gotowe":
        raport["bledy"].append(
            "Mapowanie ma status 'szkic' - tryb faktyczny zablokowany"
        )
        return raport

    _sprawdz_strone(zlecenie, strona)
    raport["tryb"] = "faktyczny"

    for krok, wpis in zip(zlecenie["kroki"], raport["kroki"]):
        wartosc = str(krok.get("wartosc") or "").strip()
        if not wartosc:
            continue
        selektor = str(krok.get("selektor", ""))
        try:
            _odmow_jesli_haslo(selektor, strona)
            _wykonaj_krok(krok.get("typ", "tekst"), selektor, wartosc, strona)
            wpis["wykonano"] = True
        except OdmowaWykonania as blad:
            wpis["uwaga"] = str(blad)
            raport["bledy"].append(f"{wpis['pole']}: {blad}")
        except Exception as blad:  # noqa: BLE001 - raport, nie wyjatek; bez wartosci pol
            wpis["uwaga"] = str(blad)
            raport["bledy"].append(f"{wpis['pole']}: {blad}")

    log.info("zlecenie %s: wpisano %d z %d pol, bledy=%d, nie wyslano",
             zlecenie["system"], sum(k["wykonano"] for k in raport["kroki"]),
             len(raport["kroki"]), len(raport["bledy"]))
    return raport


def _odmow_jesli_haslo(selektor: str, strona) -> None:
    if not hasattr(strona, "typ_pola"):
        return
    if strona.typ_pola(selektor) in TYPY_ZABRONIONE:
        raise OdmowaWykonania(
            "Odmowa: to pole hasla. Haslo i PIN karty wpisuje wylacznie notariusz."
        )


def _wykonaj_krok(typ: str, selektor: str, wartosc: str, strona) -> None:
    if typ == "tekst":
        strona.wpisz(selektor, wartosc)
    elif typ == "lista":
        strona.wybierz(selektor, wartosc)
    elif typ == "pole_wyboru":
        strona.zaznacz(selektor, wartosc.lower() in ("tak", "true", "1"))
    else:
        raise OdmowaWykonania(f"Nieznany typ pola: {typ}")
