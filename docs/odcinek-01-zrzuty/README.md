# Odcinek 01 — zrzuty kluczowych stanów

Zrzuty z prawdziwego interfejsu na danych demo (`scripts/demo_odcinek01.py`),
zrobione testem `test_odcinek01_ui.py`:

    NOTARAI_ZRZUTY=docs/odcinek-01-zrzuty pytest test_odcinek01_ui.py

Tryb: lokalny serwer demo z logowaniem i stanowiskami (jak SaaS), Chromium,
komputer 1440×900, telefon 390×844, skala 2. **Projekt sporządziła atrapa
modelu**, nie Bedrock — dlatego tekst zaczyna się od „PRÓBA NAGRANIA”. Do
filmu nagrywamy ten sam przebieg z prawdziwym modelem (`docs/czeka-na-dostep.md`, NA-7).
Wszystkie dane są fikcyjne.

| Plik | Scena | Kto | Stan |
|---|---|---|---|
| 01-kalendarz-termin-jutro.png | 03 | Basia (sekretariat) | termin jutro 11:30, „sprzedaż nieruchomości”, KPS 47/2026, „Otwórz sprawę” |
| 02-sprawa-z-kalendarza-sekretariat.png | 03 | Basia | sprawa otwarta z terminu; bez „Sporządź projekt”, pola tylko do odczytu |
| 03-telefon-ta-sama-sprawa.png | 04 | Kuba (aplikant), telefon | ta sama sprawa, to samo oznaczenie KPS 47/2026 |
| 04-telefon-aparat.png | 05 | Kuba | aparat (w teście: udawana kamera Chromium), „Wyślij (1)” |
| 05-telefon-zdjecie-w-sprawie.png | 05 | Kuba | zdjęcie JPG w „Plikach sprawy” |
| 06-komputer-marty-zdjecie-widoczne.png | 05 | Marta (notariusz) | to samo zdjęcie na komputerze, bez odświeżania |
| 07-weryfikacja-wymagaja-uwagi.png | 06 | Marta | filtr „Wymagają uwagi (3)” |
| 08-sporzadzam-projekt.png | 08 | Marta | „Sporządzam projekt… 0:01” |
| 09-projekt-gotowy-powiadomienie.png | 09 | Marta | w kalendarzu: „Projekt gotowy — Otwórz projekt” |
| 10-projekt-dokumentu.png | 10 | Marta | „Projekt dokumentu”, raport zasad, BRAK żółty, WYBOR turkus |
| 11-zespol-stanowiska.png | — | Helena (właścicielka) | stanowiska w oknie „Zespół kancelarii” |
| 12-word-znaczniki.png | 10 | — | pobrany DOCX (render LibreOffice), znaczniki zakreślone |
| projekt-demo-atrapa.docx | 10 | — | sam plik z „Pobierz jako Word” (atrapa modelu) |
