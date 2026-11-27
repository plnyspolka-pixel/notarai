# NotarAI 2.0: co działa i co wymaga decyzji

Stan na 27.11.2026. Tryb próbny: wyłącznie fikcyjne dokumenty, nic nie jest wdrożone na produkcję,
V1 pozostaje nietknięte.

## Co działa (sprawdzone testami)

| Obszar | Co robi | Jak sprawdzone |
| --- | --- | --- |
| Sejf | Dokumenty i wersje zaszyfrowane na komputerze kancelarii, osobny klucz na dokument, sprawy | testy automatyczne |
| Odzyskiwanie | Kod odzyskiwania do wydruku, plik kopii, odtworzenie na nowym komputerze, wymiana klucza | ćwiczenie „komputer przepadł” w testach |
| Kopie bez pamiętania | Raz na dobę kopia na wskazany dysk i (po włączeniu) poza kancelarię | testy automatyczne |
| Dziennik dostępu | Kto i kiedy czytał albo zapisał dokument; wykrywa zmianę wpisów | testy automatyczne |
| Asystent sprawy | Pytania do dokumentów i projekt aktu; zapis dopiero po zatwierdzeniu dokładnej treści | testy + przeglądarka |
| Ochrona danych w AI | PESEL, NIP, REGON, dowód, KW, rachunek, telefon, e-mail i wskazane osoby zastępowane znacznikami | testy + próba na żywo z Bedrock w UE |
| Blokada AI | Tylko modele UE, sprawdzenie na koncie, że treść wywołań nie jest zapisywana | testy + próba na żywo |
| Taksa | Liczy program (ten sam silnik co w V1), nie model | testy automatyczne |
| Edycja w Wordzie | Otwórz do edycji, zapisz do sejfu jako kolejną wersję, kopia robocza znika z dysku | testy, w tym prawdziwy LibreOffice |
| Rozmowa zamiast formularzy | Jedno okno czatu w Pocket i w panelu; polecenia zdaniem, potwierdzenia przyciskiem | testy + przeglądarka |
| Kafelki | Pulpit ustawiany przez notariusza: narzędzia z katalogu i własne, przeciąganie, chowanie; domyślnie pusty | testy + przeglądarka |
| Poczta | Thunderbird (wprost z plików), klasyczny Outlook, folder .eml; tylko odczyt, wiadomość do sprawy jednym zdaniem | testy na plikach Thunderbirda; Outlook na atrapie |
| Uczenie przez pokazanie | Nagranie ekranu z komentarzem zamienia się w procedurę do zatwierdzenia; dla sprawy powstają wartości do każdego pola z przyciskiem „Kopiuj” | testy + przeglądarka + próba na żywo z Bedrock |
| Telefon w kancelarii | Pocket w przeglądarce, uprawnienia odczyt/zapis i per sprawa | przeglądarka |
| Telefon poza kancelarią | Parowanie kodem QR, szyfrowanie od telefonu do komputera, klucz nie opuszcza telefonu | przeglądarka przez lokalny przekaźnik |
| Panel stanowiska | Kod odzyskiwania, kopie, urządzenia, logowanie do AI, dziennik, zużycie | przeglądarka |

## Jak się tego używa

Jedno okno rozmowy, w Pocket i w panelu stanowiska. Piszesz zwykłym zdaniem, bez tabel i formularzy:

- „nowa sprawa kowalski-2026”, „dokumenty”, „otwórz umowa”
- „strony: Jan Kowalski, Anna Nowak” (zapamiętane w sejfie dla sprawy, na każdym urządzeniu)
- „kto jest sprzedającym?”, „przygotuj umowę sprzedaży lokalu”
- „policz taksę od sprzedaży lokalu za 500 tys.”
- w panelu: „zrób kopię”, „kod odzyskiwania”, „dodaj telefon tylko do odczytu dla sprawy kowalski-2026”,
  „cofnij telefon”, „kto czytał umowa?”, „otwórz umowa w Wordzie”, „zapisz do sejfu”,
  „wyłącz pseudonimizację”, „włącz dostęp spoza kancelarii”

- kafelki: „narzędzia”, „dodaj kafelek Taksa”, „dodaj kafelek Pełnomocnictwo KW: przygotuj pełnomocnictwo…”, „ukryj kafelki”
- poczta (panel): „połącz pocztę”, „poczta”, „maile od Kowalskiego”, „dodaj mail 2 do sprawy”
- procedury: „nagraj procedurę Wniosek o wpis w KW” (panel), potem na każdym urządzeniu „wypełnij wniosek o wpis w KW”

### Jak działa łączenie z dowolnym programem

Zamiast osobnej integracji dla każdego programu i każdej strony urzędowej notariusz pokazuje czynność raz:
włącza nagrywanie, wypełnia formularz na fikcyjnej sprawie i mówi, co wpisuje i dlaczego. Z kilku ujęć ekranu
i komentarza powstaje procedura (pole, skąd wartość, powód), którą notariusz poprawia i zatwierdza. Dla kolejnych
spraw program przygotowuje gotowe wartości do skopiowania. Wpisuje albo wkleja je notariusz, więc działa to
w każdym programie i nic nie zostaje wysłane bez jego wiedzy. Samodzielne klikanie w programach to następny,
osobny krok (niżej).

Polecenia zmieniające stan rozpoznaje program według stałych sformułowań, nie model. Rzeczy
nieodwracalne (cofnięcie urządzenia, porzucenie zmian, nowy kod) wymagają potwierdzenia przyciskiem.
Pseudonimizacja jest ustawieniem kancelarii: domyślnie włączona, wyłączasz ją jednym zdaniem.

## Co jest utworzone w AWS (eu-central-1, 27.11.2026, za zgodą właściciela)

| Stos | Co zawiera | Dane |
| --- | --- | --- |
| `notarai-v2-bedrock` | logowanie stanowisk do AI; dostęp tylko dla kont z grupy `notarai-v2` | żadnych |
| `notarai-v2-przekaznik` | przekaźnik dla telefonu: `wss://qj7nel6in9.execute-api.eu-central-1.amazonaws.com/v1` | identyfikatory połączeń, 3 godziny |
| `notarai-v2-kopia` | bucket `notarai-v2-kopie` na kopie poza kancelarią | zaszyfrowane kopie, klucz ma tylko kancelaria |

Żeby kancelaria mogła używać AI, jej konto trzeba dodać do grupy `notarai-v2` w puli logowania.
Adresy tych usług instalator wpisuje sam (`installer/preset.json`); wszystko pozostaje wyłączone,
dopóki notariusz tego nie włączy.

## Czego nie dało się sprawdzić stąd

- Instalator Windows i usługa Windows: zmieniłem je, ale testy Windows uruchamia dopiero GitHub po otwarciu pull requesta.
- Przekaźnik w AWS: stos działa, funkcja przyjęła prawdziwy podpis stanowiska i odrzuciła fałszywy oraz powtórzony;
  pełnej próby telefon–przekaźnik–stanowisko stąd nie wykonałem, bo to środowisko nie przepuszcza WebSocket.
  Uruchom z własnego komputera: `python tests/live_relay.py wss://qj7nel6in9.execute-api.eu-central-1.amazonaws.com/v1`.
- Logowanie stanowiska przez Cognito: przetestowane na atrapie; próba na żywo wymaga konta w grupie `notarai-v2`.
- Outlook: napisany pod klasycznego Outlooka i sprawdzony na atrapie; na prawdziwym Outlooku nie był uruchomiony.
  Nowy Outlook nie ma interfejsu automatyzacji, tam zostaje folder z plikami .eml.
- Rozpoznawanie mowy z nagrania: działa lokalnie po doinstalowaniu `faster-whisper` (nie jest w instalatorze);
  sprawdzone na atrapie. Bez niego komentarz wpisuje się ręcznie.
- Nagrywanie ekranu: sprawdzone w Chromium na zastępczym obrazie ekranu, nie na prawdziwym pulpicie Windows.
- Microsoft Word: przetestowane z LibreOffice; z Wordem mechanizm jest ten sam (plik i blokada `~$`), ale nie był uruchomiony.

## Decyzje dla właściciela

1. **Publikacja strony Pocket pod `notarai.pl/pocket/`**: pliki przygotowuje `python tools/export_pocket.py`.
   Publikacja idzie przez `strona/` i pull request do `master`, czyli z osobnej gałęzi.
2. **Prawdziwe dane**: nadal zablokowane. Warunki zwolnienia blokady są w README („Release gates”).

## Co zostaje do zrobienia

- Samodzielne wypełnianie pól przez program (klikanie i pisanie w cudzym oknie albo na stronie): procedury mają
  już do tego potrzebne dane, ale wykonanie wymaga testów na Windows i w przeglądarce z rozszerzeniem.
- Rozpoznawanie mowy w instalatorze (dziś osobna paczka) i maskowanie danych na zrzutach ekranu.
- Podpis instalatora i kanał aktualizacji (wymaga certyfikatu do podpisu kodu).
- RejNET i inne programy kancelarii przez automatyzację okien (wymaga dostępu do środowiska testowego; patrz `docs/czeka-na-dostep.md`).
- Rozliczanie zużycia AI po stronie NotarAI (dziś licznik jest lokalny, na stanowisku).
- Niezależny przegląd bezpieczeństwa przed pierwszymi prawdziwymi danymi.
