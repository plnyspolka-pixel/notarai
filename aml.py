"""Sprawdzenie stron czynnosci na listach sankcyjnych i PEP - spoiwo.

Laczy strony sprawy (osoby.osoby_ze_sprawy), listy (aml_listy) i dopasowanie
(aml_dopasowanie) w wpisy sladu audytowego (rejestry.WynikSprawdzenia).

Zasady:
 - automat sam stwierdza tylko "brak trafien"; kazde trafienie od progu to
   status "wpis" i sprawa do decyzji notariusza (falszywe_trafienie albo
   potwierdzone, z uzasadnieniem),
 - w sladzie nie ma pelnych PESEL-i (maska) - nazwiska stron sa tam, bo
   slad lezy w katalogu sprawy, ktora i tak je zawiera,
 - PEP: funkcja trwajaca albo zakonczona w ciagu 12 miesiecy = PEP;
   starsze = "byly PEP" (do oceny ryzyka, nie do wstrzymania czynnosci),
 - logi: etykieta roli, liczba trafien, czas. Bez nazwisk.
"""
from __future__ import annotations

import logging
import re
import time

import aml_dopasowanie as dop
import aml_listy
import rejestry
import walidacja

log = logging.getLogger("pieczapp.aml")

KATEGORIA_REJESTRU = {"SANKCJE": "sankcje", "PEP": "pep"}
ZRODLA_OPIS = {"sankcje": "listy UE, ONZ i MSWiA", "pep": "API Sejmu, KPRM i Wikidata"}


def podmiot(imie_nazwisko: str, pesel: str = "", obywatelstwa: list[str] | None = None) -> dop.Podmiot:
    """Strona czynnosci jako podmiot dopasowania. Date urodzenia bierzemy z
    PESEL - to jedyne, co o niej wiemy na pewno. Obywatelstwa nie zgadujemy."""
    cyfry = re.sub(r"\D", "", pesel or "")
    data = rok = None
    if len(cyfry) == 11 and walidacja.pesel(cyfry)[0]:
        d = walidacja._data_z_peselu(cyfry)
        if d:
            data, rok = d.isoformat(), d.year
    return dop.Podmiot(nazwy=[imie_nazwisko], data_urodzenia=data, rok_urodzenia=rok,
                       obywatelstwa=list(obywatelstwa or []))


def _trafienie(o: dop.Ocena, r: dop.Rekord, kategoria: str) -> dict:
    lata = [dop.data_czesciowa(d)[1] for d in r.daty_urodzenia]
    wpis = {
        "nazwa_na_liscie": r.nazwy[0],
        "zrodlo": r.zrodlo,
        "etykieta_zrodla": aml_listy.ETYKIETY.get(r.zrodlo, r.zrodlo),
        "wynik": o.razem,
        "pasmo": o.pasmo,
        "wynik_nazwy": o.wynik_nazwy,
        "data_urodzenia": o.data,
        "ograniczenie": o.ograniczenie,
        "rok_urodzenia_na_liscie": next((x for x in lata if x), None),
        "program": r.program,
        "wpisano": r.wpisano,
        "adres": r.adres_zrodla,
    }
    if kategoria == "pep":
        wpis["funkcje"] = [f.get("tytul") for f in r.funkcje[:3] if f.get("tytul")]
        wpis["status_pep"] = dop.pep_status(r)
    return wpis


def sprawdz_osobe(imie_nazwisko: str, pesel: str = "", etykieta: str = "",
                  rejestr: str = "SANKCJE") -> rejestry.WynikSprawdzenia:
    """Jedna strona czynnosci na jednej kategorii list -> wpis sladu."""
    kategoria = KATEGORIA_REJESTRU[rejestr]
    maska = rejestry.maskuj_pesel(pesel) if re.sub(r"\D", "", pesel or "") else ""
    zapytanie = imie_nazwisko.strip() + (f" ({maska})" if maska else "")
    start = time.time()
    if not aml_listy.gotowe(kategoria):
        return rejestry.WynikSprawdzenia(
            rejestr=rejestr, zapytanie=zapytanie, status="niedostepny", etykieta=etykieta,
            szczegoly=f"{etykieta} - listy ({ZRODLA_OPIS[kategoria]}) nie zostaly jeszcze pobrane; "
                      "administrator odswieza je w panelu albo robi to watek w tle.",
            zrodlo=ZRODLA_OPIS[kategoria])
    indeks, opis_list = aml_listy.indeks(kategoria)
    trafienia = indeks.szukaj(podmiot(imie_nazwisko, pesel))
    if kategoria == "pep":
        # Byli PEP (funkcja zakonczona ponad 12 miesiecy temu) nie wstrzymuja
        # czynnosci - zostaja w opisie, ale nie robia z wpisu "trafienia".
        aktywne = [(o, r) for o, r in trafienia if dop.pep_status(r) != "byly_pep"]
        byli = len(trafienia) - len(aktywne)
        trafienia = aktywne
    else:
        byli = 0
    lista = [_trafienie(o, r, kategoria) for o, r in trafienia]
    zrodlo = ", ".join(opis_list)
    log.info("AML %s: %s trafien=%d czas=%.1fs", rejestr, etykieta or "strona", len(lista), time.time() - start)
    if not lista:
        szczegoly = f"{etykieta} - brak trafien" + (f" ({byli} wpisow o bylych PEP)" if byli else "")
        return rejestry.WynikSprawdzenia(rejestr=rejestr, zapytanie=zapytanie, status="brak_wpisu",
                                         szczegoly=szczegoly.strip(" -"), zrodlo=zrodlo, etykieta=etykieta)
    najwyzsze = lista[0]
    szczegoly = (f"{etykieta} - {len(lista)} trafien do decyzji notariusza; najwyzsze {najwyzsze['wynik']}/100 "
                 f"({najwyzsze['pasmo']}, {najwyzsze['etykieta_zrodla']})")
    if najwyzsze["ograniczenie"]:
        szczegoly += f"; {najwyzsze['ograniczenie']}"
    return rejestry.WynikSprawdzenia(rejestr=rejestr, zapytanie=zapytanie, status="wpis",
                                     szczegoly=szczegoly.strip(" -"), zrodlo=zrodlo, etykieta=etykieta,
                                     trafienia=lista)


def sprawdz_strony(strony: list[dict], rejestry_: tuple[str, ...] = ("SANKCJE", "PEP")) -> list[rejestry.WynikSprawdzenia]:
    """[{imie_nazwisko, pesel, etykieta}] -> wpisy dla kazdej strony i kazdej listy."""
    wyniki = []
    for s in strony:
        nazwa = (s.get("imie_nazwisko") or "").strip()
        if not nazwa:
            continue
        for r in rejestry_:
            wyniki.append(sprawdz_osobe(nazwa, s.get("pesel", ""), s.get("etykieta") or s.get("rola", ""), r))
    return wyniki


def decyzja(wpisy: list[dict], indeks: int, decyzja_: str, uzasadnienie: str,
            kto: str = "") -> rejestry.WynikSprawdzenia:
    """Decyzja notariusza o trafieniu: nowy wpis sladu wskazujacy na stary.
    Stary wpis zostaje bez zmian - slad jest tylko dopisywany."""
    if decyzja_ not in ("falszywe_trafienie", "potwierdzone"):
        raise ValueError("Decyzja: falszywe_trafienie albo potwierdzone")
    if len((uzasadnienie or "").strip()) < 10:
        raise ValueError("Uzasadnienie decyzji musi miec co najmniej 10 znakow")
    if re.search(r"\d{11}", uzasadnienie):
        raise ValueError("Uzasadnienie nie moze zawierac numeru PESEL")
    if not 0 <= indeks < len(wpisy):
        raise ValueError("Nie ma takiego wpisu w sladzie")
    stary = wpisy[indeks]
    if stary.get("rejestr") not in ("SANKCJE", "PEP", "CRBR") or stary.get("status") != "wpis" or stary.get("decyzja"):
        raise ValueError("Decyzje podejmuje sie tylko o trafieniu bez wczesniejszej decyzji")
    if any(w.get("decyzja") and w.get("dotyczy") == indeks for w in wpisy):
        raise ValueError("O tym trafieniu juz zapadla decyzja - slad sie nie zmienia, zmiana wymaga nowego sprawdzenia")
    return rejestry.WynikSprawdzenia(
        rejestr=stary["rejestr"], zapytanie=stary["zapytanie"],
        status="brak_wpisu" if decyzja_ == "falszywe_trafienie" else "wpis",
        szczegoly=uzasadnienie.strip(), zrodlo="decyzja notariusza", kto=kto,
        etykieta=stary.get("etykieta", ""), decyzja=decyzja_, dotyczy=indeks,
    )
