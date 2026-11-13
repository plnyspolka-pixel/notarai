# Lista kontrolna produkcji (wnioski z odc. 01) — obowiązuje od odc. 02

Każdy punkt to błąd, który już raz poprawialiśmy. Przy każdej części odcinka sprawdzam całą listę, zanim wyślę plik do akceptacji.
Część pozycji sprawdza automat: `narzedzia/kontrola_odcinka.py <plik.mp4>` (dźwięk) i `narzedzia/klatki_kontrolne.sh <plik.mp4>` (arkusz klatek co 1 s).

## A. Scenariusz i kanon

| # | Błąd z odc. 01 | Zasada |
|---|---|---|
| A1 | Pan Zenon — postać spoza kanonu | Tylko postacie z `sezon1/BIBLIA_INTRYGI_SEZONU_1.md` i kanonu odcinka. Nowa postać = najpierw w biblii/obsadzie. |
| A2 | „Przyniosłem dokument” — abstrakcyjnie | Każdy dokument nazwany konkretnie (D-numer z biblii, czego dotyczy, od kogo). |
| A3 | „od zarządcy, od zarządcy” — powtórzenie frazy | Czytam wszystkie kwestie po kolei; ta sama fraza nie wraca w dwóch sąsiednich kwestiach (też „termin wydania lokalu” — synonimy). |
| A4 | Brak pauz / pauzy wszędzie | Jedna–dwie pauzy na scenę, w momentach napięcia, gdy widz jest już zaangażowany. Wpisane w scenariuszu. |
| A5 | Ręczne obejście funkcji (Kuba „dopisuje” wynik KW) | Na ekranie bez ręcznego przepisywania. Brakującą funkcję zlecam w kodzie i pokazuję gotową. |
| A6 | Funkcje niewdrożone | Tylko prawdziwe funkcje + to, co zlecone do kodu (zapis w kanonie). Bez automatycznego importu maili, bez „komputerku” jako komendy. |
| A7 | Zegar 9:24 z błędnymi wskazówkami | Nie generuję wskazówek zegara — czas pokazuje karta czasu. |

## B. Obraz i ciągłość

| # | Błąd z odc. 01 | Zasada |
|---|---|---|
| B1 | Basia „pisze na drukarce” (klawiatura przed drukarką) | Każdy kadr przy biurku: monitor i klawiatura przed postacią, drukarka z boku. Oglądam kadr przed zleceniem ruchu. |
| B2 | Helena z okularami na twarzy i w dłoni | Jedna para okularów; w opisie kadru i ruchu zawsze, gdzie są okulary. Helena: przy biurku w okularach, w drzwiach z okularami w dłoni. |
| B3 | „Zdejmuje okulary”, a okulary zostają | Nie zlecam w ruchu gestów z rekwizytami (zdejmowanie, zakładanie). Gest = osobne ujęcie albo wcale. |
| B4 | Inne biurko Heleny między scenami | Te same kadry bazowe scenografii (bank z odc. 01) w całym odcinku; nowe kadry tylko z tych samych zdjęć bazowych. |
| B5 | Basia z szerokim uśmiechem przy niepewnej kwestii | Opis ruchu zgodny z tonem kwestii; sprawdzam klatki z ruchem ust. |
| B6 | Nieme ruchy ust (Basia przy telefonie bez głosu) | Każde ujęcie, w którym ktoś mówi, ma swoją kwestię w dźwięku. Inaczej ujęcie bez mowy (Kling/kadr). |
| B7 | Kalendarz pokazywał „dziś = 12”, a akcja dzieje się 16/17.11 | Kadruję ekrany tak, żeby nie było sprzecznych dat; dane demo z datą akcji. |
| B8 | Ucięte ekrany (wąski kadr), PESEL w zbliżeniu | Tryb panel; zbliżenia omijają PESEL (dane fikcyjne, ale nie eksponujemy). |
| B9 | Zrzut przed odpowiedzią asystenta („…”) | Nagrywanie czeka na koniec odpowiedzi (`#stan2c` bez „odpowiada”). |
| B10 | Karty imion zastępczym fontem | Renderer warstw ładuje fonty przez plik (`goto`), sprawdzam podgląd karty. |

## C. Dźwięk (automat: `kontrola_odcinka.py`)

| # | Błąd z odc. 01 | Zasada |
|---|---|---|
| C1 | „bez sena”, „z KW” — przekręcone słowa | Każda kwestia przez transkrypcję przed ruchem ust; skróty zapisuję fonetycznie („e-ka-wu”). |
| C2 | Martwa cisza (tło −60 LUFS, za mocno ściszony gwar) | Tła tylko znormalizowane (`amb_recepcja_n`, −30 LUFS); automat zgłasza każde miejsce < −38 LUFS dłuższe niż 1,5 s poza listą zamierzonych pauz. |
| C3 | Hałas przy długopisie (szum pliku podbity 4×) | Z efektu biorę tylko czysty fragment; automat zgłasza efekty z poziomem szumu wyższym niż −55 dB. |
| C4 | Jeden dzwonek zamiast chaosu | Telefony: dwa dzwonki, drugi ciszej w tle następnego ujęcia. |
| C5 | Cisza pod planszami (zapowiedź, czerń) | Muzyka dopasowana do długości (tempo/przycięcie), tło pod czernią. |
| C6 | Za krótkie nagranie → błąd HeyGen | Kwestie < 2 s dopełniam ciszą przed zleceniem. |

## D. Technika i koszty

| # | Błąd z odc. 01 | Zasada |
|---|---|---|
| D1 | Plik > 100 MB (limit GitHub) | Pełny odcinek CRF 23, preset slow (ok. 70 MB / 3 min). |
| D2 | Dwa okna wyboru głosu, sprzeczne decyzje | Głos/twarz wybieram raz, zapisuję ID w `postac.json`; nigdy dwóch równoległych wyborów. |
| D3 | Drogie warianty | Wariant oszczędny: HeyGen Turbo, 1 wariant kadru, bank ujęć, jedno podejście; poprawki tylko wskazanych ujęć. |
| D4 | Klucz z odrzuconego zlecenia fal | Po odmowie — nowy klucz zlecenia. |

## E. Współpraca
| E1 | Pytania o drobne wybory (twarz, głos) | Takie decyzje podejmuję sam i zapisuję; pytam tylko o rzeczy, które zmieniają fabułę lub koszt. |
| E2 | Intro z podtytułem „Odcinek 1 · Księga nadawcza w pięć minut” (wartość domyślna) | Intro renderuję dla każdego odcinka z `EPIZOD="Odcinek N · Tytuł"` jako `intro/INTRO_5_komputerku_9x16_odcNN.mp4`; sprawdzam podtytuł w arkuszu klatek. |
| C7 | Ucięte końcówki kwestii („…sprzedaż chce przeprowadzić”): HeyGen oddaje wideo ok. 0,16 s krótsze niż głos | Po pobraniu ujęć zawsze `narzedzia/dopelnij_ujecia.py <katalog>` (pełny głos + przytrzymana ostatnia klatka); w montażu długość ujęć z pliku (`None`), nie wpisana na sztywno. |
| A8 | „Sprzedaż chce przeprowadzić.” — zdanie brzmiało jak urwane | Każda kwestia kończy się domkniętą informacją (kto, co, kiedy); bez odwróconego szyku na końcu kwestii. Czytam kwestie na głos przed nagraniem. |
| C8 | „Synchronizacja siada” (odc. 03): nieruchome kadry z najazdem miały 5/6 długości (obraz czytany w 25 kl./s), obraz uciekał o 3 s przed głosem | Obraz z pliku graficznego zawsze `-framerate 30`; długość ujęcia zaokrąglona do pełnej klatki; skrypt montażu sprawdza, że suma klatek = oś dźwięku (odc. 03: `assert`). Poprawione też w montażu odc. 01 i 02. |
