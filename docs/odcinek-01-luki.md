# Odcinek 01 „Poniedziałek, 8:57” — analiza luk w kodzie

Stan sprawdzony na `origin/master` @ `7fb4864` (12.11.2026), przed zmianami
z gałęzi `claude/odcinek-01-ekrany`. Testy bazowe: **1300 przechodzi,
2 pominięte** (`pytest`, 2 min 48 s; testy UI Playwright uruchamiają się
w Chromium).

Cel: każdą scenę z ekranem NotarAI nagrać na prawdziwym interfejsie, na
fikcyjnych danych demo, w trybie lokalnym i w SaaS (app.notarai.pl).

Legenda stanu: **jest** — działa end-to-end w obu trybach; **częściowo** —
działa, ale czegoś brakuje do sceny albo do jednego z trybów; **brak**.

| # | Funkcja (scena) | Stan | Co trzeba zrobić | Pliki |
|---|---|---|---|---|
| 1 | Kalendarz: termin jutro 11:30, rodzaj „sprzedaż nieruchomości”, powiązany ze sprawą Ireny Nowak, przejście do sprawy (sc. 03) | **częściowo** | Termin z godziną, rodzajem, sprawą, kontrolą kolizji i telefonami stron — jest (`kalendarz.py`, `test_kalendarz*.py`). Brakuje: (a) rodzaju „sprzedaż nieruchomości” (jest tylko ogólne „sprzedaż”), (b) przejścia z terminu do sprawy — przy terminie widać nazwę sprawy i telefony, ale nie ma przycisku „Otwórz sprawę”, (c) oznaczenia sprawy (sygnatura) przy terminie. Bez automatycznej rezerwacji przez agenta — tak zostaje. | `kalendarz.py`, `static/index.html` (sekcja `etap6`, `rysujNajblizsze`, `otworzDzien`) |
| 2 | Ta sama sprawa na telefonie, ten sam identyfikator (sc. 04) | **częściowo** | Układ pod 390 px jest (menu ☰, aparat w górnym pasku). Brakuje: adresu, który otwiera konkretną sprawę (`/#sprawa=<id>` — także po zalogowaniu), i widocznego oznaczenia sprawy w nagłówku widoku sprawy, identycznego z tym w kalendarzu. | `static/index.html` (`wczytajSprawe`, `pokaz`, obsługa `location.hash`) |
| 3 | „Pliki sprawy” → „Aparatem” → zdjęcie → „Wyślij”; JPG w archiwum sprawy, widoczny na komputerze Marty; zdjęcie nie uruchamia odczytu (sc. 05) | **częściowo** | Aparat, miniatury, „Wyślij (n)”, zapis `POST /api/sprawy/{id}/pliki`, S3 przez `magazyn.utrwal_sprawe` — jest (`test_aparat_ui.py`). Zdjęcie trafia tylko do `zalaczniki/`, odczytu nie uruchamia (sprawdzone w kodzie; brak testu, który by tego pilnował). Brakuje: odświeżania listy „Pliki sprawy” na drugim urządzeniu — lista ładuje się tylko przy otwarciu sprawy, więc na komputerze Marty zdjęcie pojawia się dopiero po ponownym kliknięciu sprawy. | `app.py` (`dodaj_pliki_sprawy`), `static/index.html` (`rysujPlikiSprawy`), `test_aparat_ui.py` |
| 4 | Weryfikacja odczytu z filtrem „Wymagają uwagi” (sc. 06) | **jest** | Pola z `odczyt.json`, filtr „Wymagają uwagi (n)” włączany domyślnie, czerwone pola: błędna suma kontrolna (PESEL, KW), brak danych, niska pewność; rozbieżności między dokumentami model zgłasza jako niską pewność z uwagą, a lista „Rozbieżności” jest nad polami. Do zrobienia tylko dane demo z 1–3 takimi polami (krok 3). | `app.py` (`_zwaliduj`), `walidacja.py`, `static/index.html` (`rysujPola`) |
| 5 | „Sporządź projekt” → „Sporządzam projekt…” → „Projekt dokumentu” na wzorze kancelarii i zasadach (sc. 08–10) | **częściowo** | Wzór kancelarii (legenda, `??`, `//`), zasady i styl z `docs/styl-i-zasady.md`, kontrola zgodności, strumień NDJSON ze znakami życia co 15 s (ALB nie zrywa) — jest. Brakuje: (a) postępu — jest tylko napis, bez czasu, który upłynął; (b) pracy w innych widokach — po zakończeniu UI przełącza na „Projekt dokumentu” niezależnie od tego, gdzie jest użytkownik; (c) odporności na przerwanie połączenia — serwer kończy projekt, ale UI o tym nie wie: po odświeżeniu strony albo na drugim urządzeniu nie widać, że projekt się pisze, i można go zlecić drugi raz; (d) znaczniki `<<BRAK>>` i `<<WYBOR>>` w podglądzie mają ten sam kolor — mają się wyraźnie różnić. | `app.py` (`generuj_projekt`, `_generuj_projekt`, `wczytaj_sprawe`), `static/index.html` (`btn-generuj`, `pokazProjekt`) |
| 6 | „Pobierz jako Word” — prawdziwy DOCX, znaczniki czytelne w Wordzie (sc. 10) | **częściowo** | `GET /api/sprawy/{id}/plik` zwraca DOCX z oznaczeniem AI w metadanych — jest. Znaczniki są w pliku zwykłym tekstem: zachowane, ale niewyróżnione, łatwo je przeoczyć na wydruku. Trzeba je wyróżnić (zakreślacz i pogrubienie, inny kolor dla BRAK i WYBOR) bez zmiany treści. | `dokumenty.py` (`tekst_na_docx`), `test_dokumenty.py` |
| 7 | Uprawnienia kont: Basia (sekretariat), Kuba (aplikant), Marta i Helena (notariusze) | **brak** | Są tylko role administracyjne `wlasciciel` / `czlonek` — każdy członek zespołu może wszystko (odczyt, projekt, usunięcie sprawy, rejestry). Trzeba dodać stanowisko osoby w zespole (notariusz / aplikant / sekretariat), egzekwowane na serwerze (middleware, 403) i odwzorowane w UI (ukryte przyciski), ustawiane przez właściciela w oknie „Zespół kancelarii”. Tryb lokalny (jedno stanowisko bez logowania) bez zmian. | `autoryzacja.py`, nowy `stanowiska.py`, `static/index.html` (okno zespołu), `test_zespol.py` |

## Zakres uprawnień przyjęty dla filmu

| Działanie | Sekretariat (Basia) | Aplikant (Kuba) | Notariusz (Marta, Helena) |
|---|---|---|---|
| Kalendarz, osoby i telefony, przesyłki | tak | tak | tak |
| Lista spraw, otwarcie sprawy, podgląd pól i projektu, pobranie DOCX | tak | tak | tak |
| Pliki sprawy: dodanie (z pliku, aparatem), pobranie | tak | tak | tak |
| Pliki sprawy: usunięcie | nie | tak | tak |
| Nowa sprawa z odczytem skanów, rozmowa o sprawie | nie | tak | tak |
| Poprawki pól, „Sporządź projekt” | nie | tak | tak |
| Sprawdzenia w rejestrach (KRZ, EKW, AML, CRBR), Klikamy, formularze | nie | tak | tak |
| Usunięcie sprawy | nie | nie | tak |
| Zapis w księgach i repertoriach, zmiana stylu i zasad kancelarii, GIIF (także podgląd) | nie | nie | tak |

Właściciel kancelarii (rola administracyjna) ma zawsze pełne uprawnienia
notariusza. Osoba bez nadanego stanowiska — jak dotąd — pełne (zgodność
wstecz z kancelariami założonymi przed tą zmianą).

NotarAI przygotowuje projekt; nie podpisuje, nie wysyła i nie rozstrzyga.
Żadna rola nie dostaje funkcji „podpisz” ani „wyślij za notariusza” — takich
funkcji nie ma i nie dodajemy ich. Stałego nasłuchu hasła „Komputerku” nie
dodajemy: w filmie Marta klika przycisk. Zdjęcie dokumentu jest plikiem
w sprawie, nie stwierdzeniem tożsamości.

## Czego nie da się sprawdzić bez dostępu z zewnątrz

- Czas sporządzania projektu przez prawdziwy model (Bedrock, eu-central-1)
  na wzorze demo — w tym środowisku nie ma poświadczeń AWS. Pomiar lokalny
  idzie na atrapie modelu (mierzy tylko aplikację). Pozycja w
  `docs/czeka-na-dostep.md`.
- Przebieg na app.notarai.pl (S3 + Cognito, dwa urządzenia) — wymaga
  wdrożenia tej gałęzi i założenia kont demo. Pozycja w
  `docs/czeka-na-dostep.md`.

## Wynik (gałąź `claude/odcinek-01-ekrany`)

| # | Funkcja | Stan teraz | Co dodano | Testy |
|---|---|---|---|---|
| 1 | Kalendarz → sprawa | **jest** | Rodzaj „sprzedaż nieruchomości”; przy terminie oznaczenie sprawy (sygnatura) i przycisk „Otwórz sprawę” — w „Najbliższych terminach” i w oknie dnia. | `test_odcinek01_ui.py`, `test_kalendarz*.py` |
| 2 | Ta sama sprawa na telefonie | **jest** | Adres `/#sprawa=<id>` (ustawia się sam po otwarciu sprawy, działa też przez logowanie); oznaczenie sprawy w nagłówku „Weryfikacja odczytu” i „Projekt dokumentu” — to samo co w kalendarzu. | `test_odcinek01_ui.py` (390 px, bez poziomego przewijania) |
| 3 | Zdjęcie aparatem do plików sprawy | **jest** | Lista „Pliki sprawy” odświeża się sama co 15 s (i po powrocie do karty), bez migania; test, że zdjęcie nie wywołuje modelu ani nie zmienia odczytu. | `test_projekt_w_tle.py::test_zdjecie_do_plikow_nie_uruchamia_odczytu`, `test_odcinek01_ui.py`, `test_aparat_ui.py` |
| 4 | Weryfikacja odczytu | **jest** | Bez zmian w kodzie; dane demo mają 3 pola „wymagają uwagi” (rozbieżna powierzchnia, brak dowodu kupującego, data aktu). | `test_odcinek01_ui.py` |
| 5 | „Sporządź projekt” | **jest** | Stan pracy przy sprawie (`projekt-stan.json`, w S3 razem ze sprawą), `GET /api/sprawy/{id}/projekt/stan`, 409 przy drugim zleceniu, porzucony stan wygasa po 2 h; w UI zegar „Sporządzam projekt… m:ss”, praca w innych widokach, powiadomienie „Projekt gotowy — Otwórz projekt” zamiast przerzucania widoku, wznowienie po odświeżeniu / na drugim urządzeniu (pytanie serwera co 10 s); `<<BRAK>>` żółte, `<<WYBOR>>` turkusowe. | `test_projekt_w_tle.py`, `test_rozmowa.py`, `test_odcinek01_ui.py` |
| 6 | „Pobierz jako Word” | **jest** | Znaczniki w DOCX zakreślone i pogrubione (BRAK — żółty, WYBOR — turkus), treść bez zmian. | `test_dokumenty.py::TestZnacznikiWWordzie`, `test_odcinek01_ui.py` |
| 7 | Stanowiska zespołu | **jest** | `stanowiska.py` + egzekwowanie w middleware (403 z opisem), `PUT /api/zespol/{email}/stanowisko`, stanowisko przy zaproszeniu, `GET /api/zespol` zwraca uprawnienia; UI chowa przyciski, pola tylko do odczytu dla sekretariatu, wybór stanowiska w oknie „Zespół kancelarii”. | `test_stanowiska.py`, `test_odcinek01_ui.py` |

Dane demo: `scripts/demo_odcinek01.py` (`przygotuj`, `serwer`). Zrzuty:
`docs/odcinek-01-zrzuty/` (z atrapą modelu — tekst projektu zaczyna się od
„PRÓBA NAGRANIA”, do filmu trzeba nagrać przebieg z Bedrock, NA-7).

Czas projektu: na atrapie modelu (3 s) cały przebieg w UI trwa 3,3–3,5 s,
czyli narzut aplikacji ≈ 0,3–0,5 s. Czas prawdziwego modelu — NA-7.
