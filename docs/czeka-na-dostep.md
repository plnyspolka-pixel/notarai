# Czeka na dostęp — zadania do zrobienia na żywo

Rejestr rzeczy, których nie da się dokończyć bez dostępu z zewnątrz (konto
notariusza, środowisko testowe urzędu, dokument, którego nie ma publicznie).
Gdy pojawia się dostęp, robimy test **na żywo z notariuszem** według kroków
z danej pozycji i odhaczamy ją tutaj.

Zasady:
- Nowe zadanie tego typu = nowa pozycja `NA-n` na końcu listy (numerów nie
  używamy ponownie).
- Każda pozycja mówi: czego brakuje, co zrobić na żywo, gdzie w kodzie to
  wpiąć i kiedy uznajemy ją za zamkniętą.
- Na żywo nie wpisujemy prawdziwych danych klientów do środowisk testowych,
  nie klikamy „podpisz”/„wyślij” za notariusza, nie zapisujemy haseł ani PIN-ów.
- Zamknięta pozycja: status `zrobione` + data + commit; nie kasujemy jej.

Statusy: `czeka` · `w toku` · `zrobione` · `porzucone (powód)`

---

## NA-1. Portal MS — formularz wniosku wieczystoksięgowego (pomocnik)

- **Status:** czeka
- **Brakuje:** konta notariusza w systemie teleinformatycznym MS (EKW) — adres
  formularza po zalogowaniu i selektory pól.
- **Na żywo:**
  1. Notariusz loguje się sam (certyfikat / podpis), my podłączamy pomocnika
     do jego przeglądarki w trybie podglądu.
  2. Przechodzimy jeden wniosek z danymi pokazowymi
     (`scripts/dane_pokazowe_ksiegi.py`), zapisujemy selektory każdego pola.
  3. Sprawdzamy, czy portal ma import wniosku z pliku (XML) albo „wczytaj szkic”
     — jeśli tak, to lepsza droga niż wypełnianie pól.
  4. Zapisujemy **dokładny format numeru REP.C** pokazany po złożeniu
     (separatory) i sposób powiadamiania o wpisie.
  5. STOP przed „podpisz i wyślij”.
- **W kodzie:** `formularze/wniosek_kw_portal_ms.yaml` (status `szkic` → `gotowe`),
  `wnioski_kw.dane_formularza`, `wnioski_kw.normalizuj_rep_c`.
- **Zamknięte, gdy:** pomocnik wypełnia formularz w trybie podglądu bez błędów
  i notariusz potwierdza zgodność z tym, co wpisałby ręcznie.

## NA-2. SI*GIIF — słowniki kodów

- **Status:** czeka
- **Brakuje:** słowników dostępnych po zalogowaniu w SI*GIIF
  (`giif.mofnet.gov.pl/api/web/slowniki/...`, z zewnątrz blokowane):
  TytulTr, rodzaje przedmiotów (z flagami K/U/Z/H/E i atrybutem „A” =
  nieruchomość), charakter podmiotu (Z/N/I), rodzaje dokumentów, formy
  organizacyjne, USK (urząd skarbowy kancelarii).
- **Na żywo:** notariusz loguje się do SI*GIIF, pobieramy/zapisujemy słowniki
  (eksport albo zrzuty), wpisujemy kody kancelarii w „Ustawieniach GIIF”.
- **W kodzie:** `giif.POLA_USTAWIEN`, edytor karty w `static/ksiegi.js` (listy
  wyboru zamiast wpisywania kodów), `giif_xml.bledy_regul` (wymagane pola
  nieruchomości wg flag K/U/Z/H/E).
- **Zamknięte, gdy:** karta wybiera kody z list, a reguły pól nieruchomości
  działają według flag słownika.

## NA-3. SI*GIIF — próbna wysyłka pliku i UPO (środowisko testowe)

- **Status:** czeka (najważniejszy test GIIF)
- **Brakuje:** konta na `https://test.giif.mofnet.gov.pl` i opisu REST API
  (`/api/rest2018`, dostępny po zalogowaniu).
- **Na żywo:**
  1. Karta z danymi pokazowymi → „Pobierz XML do podpisu”.
  2. Notariusz podpisuje (CAdES) i szyfruje („Bezpieczny plik”), wysyła na
     środowisko testowe.
  3. Sprawdzamy status (Z → O → P → R; X = odrzucony — zapisać kod i komunikat).
  4. Pobieramy UPO w XML i wgrywamy do notarai.
- **W kodzie:** `giif_xml.py` (reguły dla błędów zgłoszonych przez SI*GIIF),
  `giif.odczytaj_upo` (test na prawdziwym UPO w `test_ksiegi_notarialne.py`),
  decyzja o wysyłce przez REST API.
- **Zamknięte, gdy:** plik z notarai ma status R na środowisku testowym, a UPO
  wgrywa się bez ostrzeżeń.

## NA-4. Rejestr Zastrzeżeń PESEL (moduł KRN „Rejestry Notarialne”)

- **Status:** czeka
- **Brakuje:** adresu modułu i selektorów pola PESEL / przycisku „Sprawdź”
  (konto notariusza w Rejestrach Notarialnych KRN).
- **Na żywo:** jak NA-1 — podgląd, jedno sprawdzenie na danych testowych,
  selektory do YAML.
- **W kodzie:** `formularze/rejestry_notarialne_pesel.yaml` (status `szkic`),
  `docs/formularze.md`.
- **Zamknięte, gdy:** pomocnik wpisuje PESEL w trybie podglądu i zatrzymuje się
  przed „Sprawdź”.

## NA-5. Program kancelaryjny notariusza — przeniesienie bieżącego roku

- **Status:** czeka
- **Brakuje:** nazwy programu i informacji, czy ma eksport (CSV/XML) repertorium.
- **Na żywo:** eksport repertorium A z bieżącego roku (bez danych osobowych
  albo na kopii) i porównanie kolumn z `ksiegi_notarialne.KSIEGI`.
- **W kodzie:** nowy import do `ksiegi_notarialne` (numery zachowane z programu).
- **Zamknięte, gdy:** rok w notarai zgadza się z księgą kancelarii co do numerów.

## NA-6. Potwierdzenia prawne

- **Status:** czeka
- **Do potwierdzenia (prawnik / notariusz / komunikaty):**
  - termin przekazania informacji do GIIF/KAS — `giif.TERMIN_DNI = 7`
    i sposób liczenia (komunikat GIIF nr 15);
  - czy repertorium może być prowadzone elektronicznie zamiast ksiąg
    oprawionych (nowelizacja Dz.U. 2025 poz. 1793);
  - nowy XSD z polem `WartoscBezBonifikaty` (opis v4.1) — numer CRWDE, gdy GIIF
    go opublikuje.
- **W kodzie:** `giif.TERMIN_DNI`, `docs/ksiegi-i-giif.md`, `giif_xml.CRWDE`.

---

Szczegóły działania: `docs/ksiegi-i-giif.md`. Scenariusz spotkania:
`docs/testy-z-notariuszem-ksiegi.md`.
