"""Przebieg testowy bez interfejsu: wzor + skany z jednego folderu -> odczyt -> projekt.

Uzycie:  python przebieg_testowy.py "C:\\sciezka\\do\\folderu"

W folderze musza byc: jeden plik .docx/.txt bedacy wzorem (nazwa NIE zaczyna sie
od "prompt"), opcjonalnie "prompt*.docx" lub "prompt*.txt" z poleceniem, oraz
skany (.pdf/.png/.jpg). Wyniki laduja w podfolderze "wynik_pieczapp".

To jest jedyne miejsce w aplikacji, ktore zapisuje odczytane dane na dysk
poza dane/sprawy - celowo, do recznej oceny jakosci. Nie uruchamiaj na
sprawach klientow bez potrzeby.
"""
import json
import sys
import time
from datetime import datetime
from pathlib import Path

import app
import bedrock
import dokumenty


def glowna(folder: Path) -> int:
    wynik = folder / "wynik_pieczapp"
    wynik.mkdir(exist_ok=True)
    raport = wynik / "raport.txt"
    linie: list[str] = []

    def pisz(tekst: str = "") -> None:
        print(tekst)
        linie.append(tekst)

    pisz(f"pieczapp - przebieg testowy {datetime.now():%Y-%m-%d %H:%M}")
    pisz(f"folder: {folder}")

    wzory = [
        p for p in folder.iterdir()
        if p.suffix.lower() in (".docx", ".txt") and not p.name.lower().startswith("prompt")
    ]
    if any(p.suffix.lower() == ".docx" for p in wzory):
        wzory = [p for p in wzory if p.suffix.lower() == ".docx"]  # .txt to notatki, nie wzor
    prompty_pliki = [p for p in folder.iterdir() if p.name.lower().startswith("prompt")]
    skany = sorted(
        p for p in folder.iterdir()
        if p.suffix.lower() in (".pdf", *dokumenty.OBRAZY)
    )
    if len(wzory) != 1:
        pisz(f"BLAD: oczekiwano dokladnie jednego wzoru, znaleziono {len(wzory)}: {[w.name for w in wzory]}")
        raport.write_text("\n".join(linie), encoding="utf-8")
        return 1
    wzor = wzory[0]
    polecenie = dokumenty.wzor_na_tekst(prompty_pliki[0]).strip() if prompty_pliki else ""

    pisz(f"wzor: {wzor.name}")
    pisz(f"polecenie: {'z pliku ' + prompty_pliki[0].name if prompty_pliki else '(brak)'}")
    pisz(f"skany: {[s.name for s in skany]}")

    analiza = dokumenty.analizuj_wzor(dokumenty.wzor_na_tekst(wzor))
    pisz(f"pola we wzorze: {len(analiza['pola'])}, legenda: {len(analiza['legenda'])}, warianty: {analiza['warianty']}")
    strony = dokumenty.opisz_strony(skany)
    pisz(f"stron do modelu: {len(strony)}")

    pisz()
    pisz("--- ETAP 1: odczyt danych ze skanow (Bedrock) ---")
    start = time.time()
    try:
        odczyt, _ = bedrock.odczytaj_sprawe(strony, analiza["pola"], polecenie, analiza["legenda"])
    except Exception as blad:
        pisz(f"BLAD odczytu: {type(blad).__name__}: {blad}")
        raport.write_text("\n".join(linie), encoding="utf-8")
        return 2
    pisz(f"czas: {time.time() - start:.0f} s")

    pola = app._zwaliduj(odczyt.get("pola", []))
    (wynik / "odczyt.json").write_text(
        json.dumps(
            {"pola": pola, "braki": odczyt.get("braki", []), "rozbieznosci": odczyt.get("rozbieznosci", [])},
            ensure_ascii=False, indent=2,
        ),
        encoding="utf-8",
    )
    wypelnione = [p for p in pola if p["wartosc"]]
    bledne = [p for p in pola if p["walidacja_ok"] is False]
    niskie = [p for p in pola if p["pewnosc"] == "niska"]
    pisz(f"pol zwroconych: {len(pola)}, wypelnionych: {len(wypelnione)}, "
         f"z bledna walidacja: {len(bledne)}, niska pewnosc: {len(niskie)}")
    pisz(f"braki wg modelu: {len(odczyt.get('braki', []))}, rozbieznosci: {len(odczyt.get('rozbieznosci', []))}")
    pisz("szczegoly w odczyt.json")

    pisz()
    pisz("--- ETAP 2: sporzadzanie projektu (Bedrock) ---")
    start = time.time()
    try:
        projekt = bedrock.sporzadz_projekt(analiza["tresc"], pola, polecenie, analiza["legenda"])
    except Exception as blad:
        pisz(f"BLAD generowania: {type(blad).__name__}: {blad}")
        raport.write_text("\n".join(linie), encoding="utf-8")
        return 3
    pisz(f"czas: {time.time() - start:.0f} s")
    (wynik / "projekt.txt").write_text(projekt, encoding="utf-8")
    dokumenty.tekst_na_docx(projekt, wynik / "projekt.docx")
    pisz(f"projekt: {len(projekt)} znakow, <<BRAK:>> x{projekt.count('<<BRAK:')}, "
         f"<<WYBOR:>> x{projekt.count('<<WYBOR:')}")
    pisz()
    pisz(f"GOTOWE. Wyniki w: {wynik}")
    raport.write_text("\n".join(linie), encoding="utf-8")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)
    sys.exit(glowna(Path(sys.argv[1])))
