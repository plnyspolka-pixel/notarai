# Kalkulator taksy notarialnej dla klientów

Stan na 07.11.2026.

## Co to jest

Publiczny kalkulator kosztów czynności notarialnej dla klientów kancelarii:
strona `notarai.pl/kalkulator/` (plik `strona/kalkulator/index.html`, ta sama
strona pod `app.notarai.pl/kalkulator`). Klient opisuje sprawę zwykłym językiem
albo wypełnia krótki formularz; dostaje rozbicie na taksę, wypisy, PCC, opłaty
sądowe, listę dokumentów do przyniesienia i gotową wiadomość do skopiowania.

Dwa źródła pomysłu, oba „od notariuszy dla notariuszy”:

- **C.A.R. - Cyfrowy Asystent Rejenta** (Łukasz Kupis,
  https://lukaszkupis-dev.github.io/CAR/), darmowa aplikacja PWA. Wzięliśmy
  z niej: układ kalkulacji (czynność 1 i 2 z częścią stawki, wypisy × strony,
  przełączniki PCC / hipoteka / I grupa, opłata sądowa, wniosek KW, opłata
  rejestracyjna), wartości domyślne (6 wypisów × 6 stron dla aktu, 1 × 2 dla
  czynności stałej, PCC 19 zł i 200 zł sądowe przy hipotece, opłata
  rejestracyjna 5 zł), listę czynności ze stałą stawką z podopcjami (wybór
  prawa, protokół, CRWAN, wniosek KW, hipoteka), stawki od płacy minimalnej
  (1/4 przy przeniesieniu własności ze spółdzielni, 1/10 przy najmie
  okazjonalnym), wykaz dokumentów pogrupowany wg urzędów oraz formę wiadomości
  dla klienta (opis funkcji wg instrukcji użytkownika C.A.R.).
- **Kalkulator Taksy 2026** (instalator Windows `KalkulatorTaksy_Instalator_1.0.3.exe`,
  Inno Setup, aplikacja .NET/WPF „Kalkulator taksy notarialnej”), ten sam plik
  pod linkami Proton Drive i Google Drive. Nie udało się go rozpakować w
  środowisku sesji (uruchomienie pobranego narzędzia zostało zablokowane przez
  politykę uprawnień), więc z tego projektu wzięliśmy tylko tyle, ile widać
  w metadanych. Do uzupełnienia ręcznie: porównać jego listę czynności i
  domyślne z `taksa.py`.

## Skąd stawki

Każda liczba w `taksa.py` ma źródło w tekście aktu, sprawdzonym w Dzienniku
Ustaw 07.11.2026:

- rozporządzenie MS z 28.06.2004 r. w sprawie maksymalnych stawek taksy
  notarialnej, tekst jednolity **Dz.U. 2024 poz. 1566**
  (https://www.dziennikustaw.gov.pl/D2024000156601.pdf) - tabela „2004”
  (czynności do 4.11.2026),
- rozporządzenie zmieniające z 13.10.2026 r., **Dz.U. 2026 poz. 1370**
  (https://www.dziennikustaw.gov.pl/D2026000137001.pdf), w życiu od
  **5.11.2026** - tabela „2026”: § 3 pkt 7 i 8 (progi powyżej 2 mln i 5 mln,
  limit 25 000 / 15 000 zł), § 8 (testament 200/300/400, odwołanie 50,
  zwolnienie od obciążeń 200, pełnomocnictwo 100/200, oświadczenie spadkowe
  100), § 9 (protokoły 900/1300/500), § 10-10b, § 12 (wypisy 12/10/8 zł),
  § 13 (poświadczenia), § 15c (wniosek KW 300 zł), § 16 (400 zł), § 17
  (100/200 zł za godzinę poza kancelarią),
- części stawki: § 6 (1/2) i § 7 (1/4 i 1/10) - lista w `taksa.RODZAJE`
  z paragrafem przy każdej pozycji,
- opłaty sądowe: ustawa o kosztach sądowych w sprawach cywilnych (200 zł wpis
  własności, hipoteki i ograniczonego prawa, 150 zł roszczenie i wpis po
  dziedziczeniu, 100 zł założenie KW, wykreślenie, inny wpis),
- PCC: 2 % sprzedaż, 1 % odpłatna służebność/użytkowanie, 0,5 % umowa spółki,
  19 zł hipoteka na wierzytelność o nieustalonej wysokości,
- płaca minimalna 2026: 4806 zł.

Pozycja „opłata rejestracyjna 5 zł” pochodzi z domyślnych ustawień C.A.R.
i **nie wynika z rozporządzenia o taksie**. Zostaje jako stała
`taksa.OPLATA_REJESTRACYJNA`, bo tak liczą kancelarie korzystające z C.A.R.;
jeśli kancelaria jej nie pobiera, wystarczy ją wyzerować.

## Jak to działa

- `taksa.py` - silnik. Czysty Python, Decimal, bez modelu. `oblicz(parametry)`
  zwraca pozycje (netto, VAT, brutto, podstawa prawna), sumy, uwagi (limit
  taksy, rabat, brak PCC), dokumenty i gotowy tekst. Tabela stawek wybierana
  po dacie czynności. Testy: `test_taksa.py` (liczby policzone ręcznie z aktu).
- `kalkulator.py` - API bez logowania (`/api/taksa`, `/api/taksa/oblicz`,
  `/api/taksa/rozmowa`). Rozmowa: model (Bedrock, profil `eu.`, bez myślenia)
  dostaje prompt `prompty.TAKSA` + katalog identyfikatorów z `taksa.py`
  i zwraca JSON `{"odpowiedz", "kalkulacja"}`; kwoty liczy `taksa.oblicz`.
  W kolejnych turach model widzi wynik kalkulatora policzony na nowo na
  serwerze (parametry z przeglądarki nie są brane na słowo). Limity: 40
  wiadomości na IP na godzinę i 1500 na dobę na proces (`PIECZAPP_KALKULATOR_*`),
  wiadomość do 1500 znaków, historia do 24 tur, pole-pułapka dla automatów.
  CORS tylko dla `/api/taksa` i tylko dla domen z `PIECZAPP_KALKULATOR_ORIGINS`
  (domyślnie notarai.pl). Treści rozmów nie zapisujemy i nie logujemy.
- `strona/kalkulator/index.html` - strona (samodzielna: własne style w pliku,
  żeby działała i na hostingu az.pl, i z aplikacji). Czat + formularz bez
  asystenta + karta wyniku z przyciskiem „Kopiuj kalkulację”.
- W aplikacji kancelarii link „Kalkulator taksy” w pasku bocznym: notariusz
  liczy i kopiuje wiadomość dla klienta, jak w C.A.R.

## Wdrożenie

1. Aplikacja: zwykła ścieżka (etap 2 i 3 z `SAAS.md`). Zmiennych środowiskowych
   nie trzeba dodawać, domyślne są włączone.
2. Strona: `infra\strona.ps1 wyslij` wysyła katalog `strona\` razem z
   `kalkulator\index.html`. Strona woła `https://app.notarai.pl/api/taksa`.
3. Wyłączenie asystenta (zostaje formularz): `PIECZAPP_KALKULATOR=false`.

## Co sprawdzić po wdrożeniu

- `curl https://app.notarai.pl/api/taksa` zwraca katalog z `"wniosek_kw": 300.0`.
- Na `notarai.pl/kalkulator/` formularz liczy (CORS), czat odpowiada.
- Przykład kontrolny: sprzedaż lokalu 450 000 zł, kredyt 400 000 zł, 6 wypisów
  × 6 stron = 12 633,69 zł brutto (taksa 1 580,55 + hipoteka 728,78 + PCC
  19 + wypisy 531,36 + PCC 9 000 + sąd 200 + 200 + wniosek KW 369 + 5).
