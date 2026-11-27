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
| Telefon w kancelarii | Pocket w przeglądarce, uprawnienia odczyt/zapis i per sprawa | przeglądarka |
| Telefon poza kancelarią | Parowanie kodem QR, szyfrowanie od telefonu do komputera, klucz nie opuszcza telefonu | przeglądarka przez lokalny przekaźnik |
| Panel stanowiska | Kod odzyskiwania, kopie, urządzenia, logowanie do AI, dziennik, zużycie | przeglądarka |

## Czego nie dało się sprawdzić stąd

- Instalator Windows i usługa Windows: zmieniłem je, ale testy Windows uruchamia dopiero GitHub po otwarciu pull requesta.
- Przekaźnik w AWS: logika przetestowana, szablon przeszedł walidację, ale stos nie jest utworzony.
- Logowanie stanowiska przez Cognito: przetestowane na atrapie; wymaga utworzenia stosu `notarai-v2-bedrock`.
- Microsoft Word: przetestowane z LibreOffice; z Wordem mechanizm jest ten sam (plik i blokada `~$`), ale nie był uruchomiony.

## Decyzje dla właściciela

1. **Utworzenie zasobów AWS** (nic nie powstało bez zgody):
   - `infra/notarai-v2-bedrock.yaml`: logowanie stanowisk do AI. Nie przechowuje danych.
   - `infra/notarai-v2-przekaznik.yaml`: przekaźnik dla telefonu. Przechowuje tylko identyfikatory połączeń.
   - `infra/notarai-v2-kopia.yaml`: kopie poza kancelarią. **Przechowuje zaszyfrowane dane osobowe**; wymaga
     świadomej zgody i zmiany zapisu „żadnego S3” w README.
2. **Gdzie opublikować stronę Pocket dla telefonu** (musi być pod HTTPS, np. `notarai.pl/pocket`).
3. **Prawdziwe dane**: nadal zablokowane. Warunki zwolnienia blokady są w README („Release gates”).

## Co zostaje do zrobienia

- Podpis instalatora i kanał aktualizacji (wymaga certyfikatu do podpisu kodu).
- RejNET i inne programy kancelarii przez automatyzację okien (wymaga dostępu do środowiska testowego; patrz `docs/czeka-na-dostep.md`).
- Rozliczanie zużycia AI po stronie NotarAI (dziś licznik jest lokalny, na stanowisku).
- Niezależny przegląd bezpieczeństwa przed pierwszymi prawdziwymi danymi.
