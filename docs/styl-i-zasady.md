# Styl i zasady kancelarii (personalizacja projektów)

Ekran **Narzędzia → Styl i zasady kancelarii** (etap 9). Notariusz:

1. **pisze nieprzekraczalne zasady zwykłym zdaniem** – system sam rozpoznaje,
   czego dotyczą, w jakich aktach obowiązują i jak ich pilnować,
2. **uczy notarai swojego stylu**, wrzucając stare akty,
3. **poprawia wyuczony styl** – przypina wzorcowe sformułowania, ukrywa złe,
   przyjmuje zasady podpowiedziane z jego aktów,
4. w gotowym projekcie **zaznacza fragment** i jednym kliknięciem robi z niego
   zasadę („Nigdy tak nie pisz”, „Zamieniaj na…”) albo wzorcowe sformułowanie.

Każdy projekt, **zanim trafi do notariusza**, przechodzi przez kontrolę zasad,
a nad projektem jest raport zgodności.

## Przepływ projektu

```
wzór + polecenie ──► klasyfikacja rodzaju czynności (kategorie.py)
                      │
zasady + styl ──────► blok ZASADY KANCELARII / STYL KANCELARII w poleceniu dla modelu
                      │
                 model sporządza projekt (bedrock.sporzadz_projekt)
                      │
zasady.egzekwuj():   1. sprawdzenie zasad + konstrukcji aktu
                     2. autonaprawa bez modelu (zamiany, kwoty słownie, daty,
                        §, cudzysłowy, numeracja § z odesłaniami)
                     3. zostały naruszenia blokujące → 1 tura poprawki modelem
                        (przyjęta tylko gdy usuwa naruszenia i nie skraca aktu)
                     4. wytyczne opisowe → kontrola modelem
                      │
                 projekt + raport zgodności (zgodnosc.json w sprawie)
```

Gdy zasad nie da się wczytać, projekt powstaje, ale raport mówi wprost:
„projekt NIE został sprawdzony”.

## Moduły

| Plik | Rola |
| --- | --- |
| `kategorie.py` | Taksonomia: 21 rodzajów czynności, 14 części aktu, 11 obszarów zasad. Klasyfikator na słowach kluczowych (bez modelu). Nowa kategoria = wpis w słowniku. |
| `klauzule.py` | Uniwersalny silnik klauzul: rozbiór tekstu na drzewo (§ / ust. / pkt / lit. / tiret / akapit), części aktu, odesłania, kontrola konstrukcji, przenumerowanie §, pseudonimizacja szkieletów. |
| `zasady.py` | Zdanie notariusza → zasada (`interpretuj`), sprawdzanie, autonaprawa, `egzekwuj`, zapis w pliku kancelarii `zasady`. |
| `styl.py` | Analiza aktów, profil stylu (sformułowania, nawyki), podpowiedzi zasad, blok stylu dla modelu, zapis w pliku kancelarii `styl`. |
| `slownie.py` | Kwoty słownie po polsku (autonaprawa „kwoty cyframi i słownie”). |
| `personalizacja.py` | API `/api/personalizacja/*` i wpięcie w generowanie projektu. |
| `static/personalizacja.{js,css}` | Ekran etapu 9, raport nad projektem, pasek nad zaznaczeniem. |

Silnik klauzul wywodzi się z silnika umów Finance You
(`finyou: src/lib/contract-engine`): stamtąd zasada, że numeracja i odesłania
są sprawą kodu, a odesłanie do nieistniejącego miejsca jest błędem
konstrukcyjnym. Silnik finyou składa umowę z biblioteki klauzul; ten działa
w drugą stronę i przyjmuje dowolny tekst.

## Typy zasad

| Typ | Przykład zdania | Pilnowanie |
| --- | --- | --- |
| `zamiana` | Zamiast „w/w” pisz „wyżej wymieniony” | regułą, poprawiam sam (formy odmienione → poprawka modelu) |
| `zakaz_frazy` | Nigdy nie używaj słowa „niniejszy” | regułą, łapie też odmiany |
| `wymagana_fraza` | Każdy akt musi zawierać „Akt ten został odczytany…”; W darowiznach zawsze pouczenie o art. 9 ust. 1 | regułą |
| `wymagana_czesc` | W umowach sprzedaży zawsze wnioski wieczystoksięgowe | regułą (rozbiór na części) |
| `kwoty_slownie` | Kwoty zawsze cyframi i słownie | regułą, dopisuję sam |
| `separator_tysiecy` | Kwoty z kropką co trzy cyfry, np. 250.000,00 zł | regułą, poprawiam sam |
| `format_daty` | Daty zapisuj jak 03.12.2025 r. | regułą, poprawiam sam (bez dat w tytułach ustaw) |
| `spacja_paragraf` | Po § zawsze spacja | regułą, poprawiam sam |
| `cudzyslowy` | Cudzysłowy tylko polskie | regułą, poprawiam sam |
| `wytyczna` | Nazwiska stawających w komparycji wielkimi literami | model (do modelu idzie też jako zasada) |

Zakres („w umowach sprzedaży”, „w komparycji”) i siła („staraj się”, „unikaj”
→ tylko ostrzeżenie) są odczytywane ze zdania; notariusz może je zmienić
w podglądzie „Tak to rozumiem”. Zasady formatu (daty, kwoty, §, cudzysłowy)
są jedyne – nowa zastępuje poprzednią.

Wbudowana kontrola budowy aktu (można wyłączyć pojedynczo): ciągła numeracja §
i ustępów, odesłania wewnętrzne, niewypełnione luki wzoru (`??`, `{{…}}`,
`[POLE]`), nierozstrzygnięte warianty `//`.

## Dane osobowe (RODO)

- Z aktów do profilu trafiają **tylko szkielety klauzul** po pseudonimizacji
  (`{OSOBA}`, `{PESEL}`, `{ADRES}`, `{KWOTA}`…) i liczniki nawyków. Przed
  zapisem jest dodatkowa zapora `klauzule.ma_dane_osobowe` – szkielet z PESEL,
  numerem KW, dowodu albo e-mailem jest odrzucany.
- Wgrane pliki są czytane w katalogu tymczasowym i od razu usuwane; nazwy
  plików nie są zapisywane (wracają tylko do przeglądarki, która je wysłała).
- Logi zawierają wyłącznie liczby.
- Kancelaria w chmurze: pliki `zasady.json` i `styl.json` leżą pod prefiksem
  kancelarii (`kancelarie/{kancelaria}/`), więc usunięcie kancelarii usuwa je
  razem ze sprawami.

## Kancelaria „u siebie”

Zasady i styl leżą w folderze spraw notariusza, obok spraw:
`notarai-zasady.json` i `notarai-styl.json`. Serwer niczego nie zapisuje:

1. przeglądarka czyta oba pliki z folderu i dołącza je do każdego zapytania
   `/api/personalizacja/*` (pole `pliki_kancelarii`; odczyt stanu idzie przez
   `POST /api/personalizacja/stan`) oraz do `/api/projekt`,
2. serwer normalizuje je (`zasady.normalizuj`, `styl.normalizuj` – plik mógł
   zapisać starszy klient albo ktoś go zmienił ręcznie), a na czas zapytania
   `magazyn` czyta i zmienia je w pamięci (`magazyn.pliki_przegladarki_var`),
3. odpowiedź niesie nową wersję plików, przeglądarka zapisuje zmienione.

Bez wskazanego folderu zapis kończy się czytelnym komunikatem (409). Pliki
przysłane przez przeglądarkę kancelarii w chmurze są pomijane.

## Uprawnienia

Zasady nieprzekraczalne zmienia **właściciel kancelarii** (przy logowaniu
e-mailem). Członek zespołu je widzi, sprawdza nimi tekst, może uczyć styl
i oznaczać sformułowania. W trybie lokalnym – każdy.

## Koszt

Kontrola regułami i autonaprawa nie wołają modelu. Model jest wołany najwyżej
dwa razy dodatkowo na projekt: poprawka, gdy po autonaprawie zostały
naruszenia blokujące, i kontrola wytycznych opisowych, gdy takie są.
`PIECZAPP_POPRAWA_ZASAD=0` wyłącza oba wywołania.

## Rozbudowa

- **Nowy rodzaj czynności / część aktu** – wpis w `kategorie.RODZAJE` /
  `kategorie.CZESCI` (+ krótki wzorzec w `_ZAKRES_RODZAJOW` / `_ZAKRES_CZESCI`,
  żeby zdanie zasady rozpoznawało zakres).
- **Nowy typ zasady** – `zasady.TYPY`, rozpoznanie w `_rozpoznaj_typ`,
  sprawdzenie w `_naruszenia_reguly`, opcjonalnie naprawa w `napraw` i opis
  w `opisz`. Test w `test_personalizacja.py::TestInterpretacja`.
- **Nowy nawyk słownikowy** – wpis w `styl.SLOWNICTWO`.
