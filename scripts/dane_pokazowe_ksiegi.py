"""Dane pokazowe ksiag, wnioskow KW i zgloszen GIIF - do pokazu i testow z notariuszem.

Uruchomienie (tryb lokalny, zapis do dane/ tej instalacji):
    python scripts/dane_pokazowe_ksiegi.py            # dopisuje dane pokazowe
    python scripts/dane_pokazowe_ksiegi.py --katalog /tmp/pokaz   # inny katalog danych

Wszystkie osoby i numery sa zmyslone (zestaw Sobczak/Pawlak), PESEL-e maja
poprawne sumy kontrolne, ale nie naleza do nikogo. Kody slownikowe GIIF sa
PRZYKLADOWE - przed wysylka do SI*GIIF trzeba je zastapic kodami ze slownikow.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config  # noqa: E402
from walidacja import WAGI_PESEL  # noqa: E402


def pesel(dziesiec: str) -> str:
    suma = sum(int(c) * w for c, w in zip(dziesiec, WAGI_PESEL))
    return dziesiec + str((10 - suma % 10) % 10)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--katalog", help="katalog danych zamiast dane/")
    args = parser.parse_args()
    if args.katalog:
        config.DANE = Path(args.katalog)
        config.DANE.mkdir(parents=True, exist_ok=True)

    import giif
    import ksiegi_notarialne as k

    sobczak, pawlak, nowak = pesel("8001011234"), pesel("9002021234"), pesel("7503031234")
    giif.zapisz_ustawienia({"nip": "5260250274", "nr_sekw_js": "1471", "tytul": "A01",
                            "charakter_zbywcy": "SPRZ", "charakter_nabywcy": "KUPU",
                            "rodzaj_dokumentu": "DO", "typ_przedmiotu_lokal": "111"})
    sprzedaz = k.dodaj("repertorium_a", {
        "data_czynnosci": "2026-11-03", "tresc": "Umowa sprzedazy lokalu mieszkalnego nr 2 przy ul. Lipowej 1",
        "strony": [{"nazwa": "Jan Sobczak", "rola": "sprzedajacy", "pesel": sobczak},
                   {"nazwa": "Anna Pawlak", "rola": "kupujaca", "pesel": pawlak}],
        "wartosc_przedmiotu": "650000", "wynagrodzenie": "1910", "vat": "439.30",
        "oplata_sadowa": "400", "podatek_pcc": "13000"})
    k.dodaj("repertorium_a", {
        "data_czynnosci": "2026-11-04", "tresc": "Pelnomocnictwo",
        "strony": [{"nazwa": "Piotr Nowak", "rola": "mocodawca", "pesel": nowak}],
        "wynagrodzenie": "30", "vat": "6.90"})
    k.dodaj("depozytowa", {"data_zlozenia": "2026-11-03", "rep_a": sprzedaz["oznaczenie"],
                           "skladajacy": "Anna Pawlak", "przedmiot": "Czesc ceny",
                           "kwota": "50000", "waluta": "PLN", "odbiorca": "Jan Sobczak"})
    k.dodaj("dziennik_korespondencyjny", {"data": "2026-11-05", "kierunek": "wplyw",
                                          "kontrahent": "Sad Rejonowy", "tresc": "Zawiadomienie o wpisie"})
    rep = k.zarejestruj_wniosek_kw(sprzedaz["id"], {
        "numer_kw": "WA4M/00160286/2", "sad": "Sad Rejonowy dla Warszawy-Mokotowa, XIII Wydzial KW",
        "uczestnicy": [{"nazwa": "Jan Sobczak", "rola": "zbywca", "pesel": sobczak},
                       {"nazwa": "Anna Pawlak", "rola": "nabywca", "pesel": pawlak, "imiona_rodzicow": "Adam, Ewa"}],
        "zadania": [{"rodzaj": "wpis_wlasnosci", "na_rzecz": ["Anna Pawlak"]}],
        "akt": {"notariusz": "notariusz pokazowy", "siedziba": "Warszawa"}})
    k.zmien_status_wniosku_kw(sprzedaz["id"], rep["wnioski_kw"][0]["id"], {
        "status": "zlozony", "numer_rep_c": "REP.C/NOTA/1234/26", "data_zlozenia": "2026-11-03"})
    z = giif.z_repertorium(sprzedaz["id"], kurs_eur="4.25")
    print(f"Gotowe: {sprzedaz['oznaczenie']}, wniosek REP.C/NOTA/1234/26, zgloszenie GIIF {z['id']} "
          f"(termin {z['termin']}). Katalog danych: {config.DANE}")


if __name__ == "__main__":
    main()
