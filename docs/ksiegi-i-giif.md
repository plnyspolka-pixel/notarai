# Księgi notarialne, wnioski KW (repertorium C) i zgłoszenia do GIIF

Stan na 08.11.2026. Kod: `ksiegi_notarialne.py`, `wnioski_kw.py`, `giif.py`,
`giif_xml.py`, schematy `giif_xsd/`, ekrany `static/ksiegi.js`. Testy:
`test_ksiegi_notarialne.py`, `test_ksiegi_s3.py`, `test_ksiegi_ui.py`.
Dane pokazowe: `scripts/dane_pokazowe_ksiegi.py`. Scenariusz testu z notariuszem:
`docs/testy-z-notariuszem-ksiegi.md`.

## 1. Księgi kancelarii

Rozporządzenie MS z 12.04.1991 w sprawie prowadzenia ksiąg notarialnych
(t.j. Dz.U. 2018 poz. 2039), § 1 ust. 1, oraz repertorium C z systemu EKW:

| Księga | Klucz | Numeracja |
|---|---|---|
| Repertorium A — czynności (poza protestami) | `repertorium_a` | roczna, `Rep. A nr N/RRRR`, nadaje serwer |
| Repertorium P — protesty | `repertorium_p` | roczna, nadaje serwer |
| **Repertorium C** — wnioski wieczystoksięgowe złożone w systemie teleinformatycznym | `repertorium_c` | **numer z systemu MS**: `REP.C/NOTA/N/RR` |
| Księga depozytowa (§ 4) | `depozytowa` | ciągła |
| Dziennik przesyłanych dokumentów | `dziennik_przesylanych` | ciągła |
| Dziennik korespondencyjny | `dziennik_korespondencyjny` | ciągła |
| Skorowidz do rep. A | `/repertorium_a/skorowidz` | wyliczany |

**Repertorium C** to centralne repertorium wniosków elektronicznych prowadzone
przez system MS. Numer powstaje „z chwilą zarejestrowania wniosku w centralnym
repertorium wniosków elektronicznych” i składa się z oznaczenia REP.C, kodu
podmiotu (NOTA — notariusze), kolejnego numeru i dwóch ostatnich cyfr roku
(§ 68 rozporządzenia MS z 15.02.2016 w sprawie zakładania i prowadzenia ksiąg
wieczystych w systemie teleinformatycznym, Dz.U. poz. 312). Przepis nie podaje
separatorów; zapisujemy `REP.C/NOTA/1234/26`, a numer wpisany w innej postaci
normalizujemy. W notarai repertorium C to kancelaryjny rejestr tych wniosków:
numer REP.C, data złożenia, rep. A, numer KW, sąd, żądania, opłata, a potem
przebieg w sądzie (numer w dzienniku KW — § 71, wpis, zwrot, oddalenie),
każda zmiana z historią.

Zasady wpisane w kod: numer nadaje serwer (rep. C — system MS), repertorium
jest chronologiczne, poprawki zostają w historii (było/jest, kto, kiedy, powód),
uwagi o wypisach, sumy należności dzienne i miesięczne.
Data czynności nie może być z przyszłości; poprawka daty nie może przenieść
czynności do innego roku ani złamać kolejności numerów. Wydruk do oprawienia
(A4 poziomo, z poprawkami i sumami miesięcznymi) i eksport CSV są w zakładce
każdej księgi.

**Uwaga prawna:** rozporządzenie z 1991 r. wymaga ksiąg oprawionych, z
ponumerowanymi stronami. Wersja w notarai to rejestr roboczy z pełną historią
i podstawą do wydruku; czy może zastąpić księgę papierową, zależy od przepisów
o elektronicznym repertorium (sprawdzić nowelizację Dz.U. 2025 poz. 1793).

## 2. Wnioski do ksiąg wieczystych — jak to działa i co robi notarai

Prawo: notariusz składa wniosek o wpis **wyłącznie przez system
teleinformatyczny** (art. 626⁴ KPC, art. 92 § 4 PrNot), z **kwalifikowanym
podpisem elektronicznym**. System rejestruje wniosek w REP.C i w tej samej
chwili umieszcza wzmiankę w księdze (§ 68). Podstawa wpisu „akt notarialny”
zawiera m.in. numer rep. A, datę, notariusza i siedzibę kancelarii.

Publicznego API do składania wniosków nie ma, więc podpis i wysłanie zostają
w portalu MS. Obieg w notarai:

1. **Przygotowanie** (`POST .../repertorium_a/{id}/wnioski-kw`): sąd, numer KW
   (z sumą kontrolną), uczestnicy (PESEL osoby, na rzecz której następuje wpis;
   imiona rodziców nabywcy), żądania per dział księgi (I-O, I-Sp, II, III, IV),
   podstawa wpisu uzupełniana z rep. A, opłata sądowa liczona z
   `taksa.OPLATY_SADOWE` — każde żądanie osobno. Lista braków na bieżąco.
2. **Pakiet do portalu** (`GET .../pakiet`): kroki w kolejności formularza
   z przyciskami „Kopiuj”, kończące się krokiem „STOP — podpis i wysłanie”.
   Te same dane są gotowe dla pomocnika (`formularze/wniosek_kw_portal_ms.yaml`,
   status: szkic).
3. **Złożenie** (`POST .../status` ze `status=zlozony`, numerem REP.C i datą):
   tylko kompletny wniosek; powstaje wpis w **repertorium C**. Ten sam numer
   REP.C nie wejdzie dwa razy.
4. **Przebieg** — dozwolone przejścia: złożony → w sądzie / wpis dokonany /
   zwrot / oddalony / odrzucony / cofnięty; w sądzie → te same (z dopisaniem
   sygnatury). Stany końcowe się nie zmieniają — ponowne złożenie to nowy wniosek
   z nowym numerem REP.C. Każda zmiana zapisuje się w rep. C z historią.
   Złożenie i przebieg zapisują rep. A i rep. C w jednej zmianie pliku, więc
   dwa równoczesne kliknięcia nie utworzą dwóch wpisów w rep. C.
5. Numeru REP.C ani stanu nie da się zmienić zwykłą poprawką w rep. C, a ręczny
   wpis do rep. C jest zablokowany — każdy wpis ma swój wniosek w rep. A.

**Do zrobienia (wymaga konta notariusza):** selektory pól formularza w portalu
MS dla pomocnika. Trzeba raz przejść wniosek na zalogowanym koncie w trybie
podglądu i zapisać selektory w YAML; do tego czasu działa kopiuj-wklej.

## 3. GIIF i Szef KAS

- Od 1.03.2023 notariusz przekazuje informacje o czynnościach do GIIF i Szefa
  KAS **wyłącznie elektronicznie przez SI*GIIF**, w XML według XSD
  (komunikat KAS z 28.11.2022; eNotariusz).
- Art. 72 ust. 4 ustawy AML: transakcje > 15 000 EUR (`dlaGIIF=true`);
  pozostałe czynności z PCC/SD, APD i EPS idą tylko do KAS (`dlaGIIF=false`).

### Plik XML (`giif_xml.py`)

- Schemat **CRWDE 2026/04/28/14250** (GIIF + Szef KAS, od 30.06.2026,
  komunikat nr 110) z importami w `giif_xsd/` — walidacja offline (lxml, bez
  sieci), sprawdzona też niezależnie `xmllint --schema`.
- Reguły spoza XSD z opisu schematu (`docs/giif/opis-schematu-notarialnego-v4.1.txt`):
  INF.2 (udziały zbywców i nabywców sumują się do 1, inna strona 0/1),
  INF.3 (suma wartości = kwota), INF.4 (APD/EPS: kwota 0, `dlaGIIF=false`),
  INF.7 (adres TERYT i numer domu albo obręb + działka), sumy kontrolne
  PESEL, NIP, KW, oświadczenie o VAT dla nieruchomości, numer CREWAN
  (`XX900` dla aktów nie zgłaszanych do CREWAN — komunikat nr 101).
- Kartę wstępną notarai buduje z rep. A i zgłoszenia (strony, role
  zbywca/nabywca, udziały, numer KW, powierzchnia, pokoje). Kancelaria
  uzupełnia resztę w edytorze karty; błędy widać od razu.
- Zatwierdzenie karty do GIIF i KAS wymaga pliku bez błędów; zapisujemy ten plik
  i jego SHA-256. `GET /api/giif/{id}/xml?pobierz=1` zwraca dokładnie zatwierdzony
  plik (późniejsza zmiana ustawień go nie zmienia). Każda zmiana karty cofa do szkicu.
- Dodatkowe reguły z opisu pól: INF.4 w całości (APD/EPS: kwota 0, PLN, wartości 0,
  bez VAT, udział 1/1), INF.3 liczone na wartościach przed zaokrągleniem, najwyżej
  2 miejsca po przecinku, udziały ≥ 1 i nie większe niż całość, parter = 1
  (kondygnacja 0 niedozwolona), numer KW tylko dla nieruchomości w Polsce, daty
  nie z przyszłości, rok repertorium nie późniejszy niż rok aktu.
- UPO w XML jest odczytywane i sprawdzane (numer referencyjny = numer przesyłki,
  NIP = NIP notariusza); UPO w PDF zapisujemy jako skrót.
- Zgłoszenie utworzone z rep. A ma zablokowany numer i datę aktu (od daty liczy się termin).

### Słowniki — skąd kody

Kody `TytulTr`, `IdSlPrzedmiotTyp`, `charakterPodmiotu`, `RodzajDokumentu`,
`FormaOrganizacyjna` i urząd skarbowy (`nrSekwJs`, słownik USK) są w
słownikach SI*GIIF (`giif.mofnet.gov.pl/api/web/slowniki/...`), dostępnych po
zalogowaniu (z zewnątrz blokuje je ochrona antybotowa). Kancelaria wpisuje je
raz w „Ustawieniach GIIF”, a w karcie można je zmienić. Poprawność kodu
sprawdza SI*GIIF przy przyjęciu pliku (status X = plik odrzucony w całości).

### Podpis, szyfrowanie, wysyłka (`docs/giif/podpis-i-szyfrowanie-sigiif.txt`)

- Plik: XML UTF-8, podpis **CAdES** (nie XAdES), SHA-256/384/512, następnie
  szyfrowanie CMS EnvelopedData (AES-128/256-CBC) certyfikatem GIIF.
- Kanały: strona SI*GIIF albo web service `https://www.giif.mofnet.gov.pl/api/rest2018`.
  Nazwa pliku dowolna (komunikat nr 8).
- Statusy (komunikat nr 13): Z → O → P → R; X = błędny, W = wyjaśniony.
  UPO (`giif_xsd/UPO2018.xsd`) przez API od statusu P, na stronie od statusu R.
- notarai **nie podpisuje i nie szyfruje** — podpis kwalifikowany jest
  notariusza. Notariusz pobiera XML, podpisuje i szyfruje (narzędzie GIIF
  „Bezpieczny plik”), wysyła w SI*GIIF, a w notarai rejestruje identyfikator
  przesyłki i UPO (skrót SHA-256).

### Czego jeszcze nie ma

- **Schemat 14252** („tylko do GIIF”) — XSD jest w `giif_xsd/`, generator na
  razie tylko dla 14250.
- **Pole `WartoscBezBonifikaty`** (opis v4.1): w XSD 14250 go nie ma, a numeru
  CRWDE nowszego schematu nie znaleźliśmy. Dodamy, gdy GIIF opublikuje schemat.
- **Zawiadomienia art. 74/86/89** — mają osobne schematy; obieg działa, XML nie.
- **Wysyłka przez REST API** — opis API i uwierzytelnianie są za logowaniem.
  Pierwszy krok: konto testowe na `test.giif.mofnet.gov.pl`.

## 4. Kolejne kroki

1. Na koncie notariusza: selektory formularza wniosku KW w portalu MS
   (pomocnik, tryb podglądu) oraz słowniki SI*GIIF do ustawień.
2. Konto testowe SI*GIIF: wysłanie pliku wygenerowanego przez notarai
   i sprawdzenie statusu P/R.
3. Generator dla schematu 14252 i zawiadomień AML.
4. Potwierdzić termin 7 dni (`giif.TERMIN_DNI`) z komunikatem GIIF o liczeniu terminów.
