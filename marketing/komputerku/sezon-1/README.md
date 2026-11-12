# Kancelaria pod Siódemką — sezon 1 (materiały produkcyjne V4)

**Status: DRAFT / do autoryzacji. Materiały nie są zatwierdzone do emisji ani automatycznej publikacji.**

## Cel
Mikroserial edukacyjno-fabularny dla notariuszy promujący NotarAI: sporządzanie projektów aktów notarialnych, uporządkowanie pracy zespołu, mobilne dokumenty, kalendarz, KRZ, EKW i lokalny pomocnik. Centralny konflikt to pośpiech i chaos kancelarii; NotarAI porządkuje informacje, lecz nie zastępuje oceny i czynności notariusza.

## Kolejność pracy
1. Zapoznaj się z `01_KANON/BIBLIA_INTRYGI.md` (źródło prawdy o postaciach, transakcji, dokumentach i motywacjach).
2. Scenariusze EP01–EP08 są w `02_SCENARIUSZE/`. EP01 zawiera notę continuity; **Paweł Nowak** przynosi dokument, nie wymyślony Zenon.
3. Każdy ekran rejestru i produktu nagrywaj w realnej aplikacji na danych syntetycznych, po teście działania.
4. Stosuj `03_PRODUKCJA/REUSE_I_QA.md`; jedno wnętrze, stała obsada, ujęcia wielokrotnego użycia i biblioteka dźwięków.
5. Przed publikacją: autoryzacja notariusza, zgodność produktu, korekta napisów i spójność mailingu.

## Wersja kanoniczna
Irena Nowak sprzedaje mieszkanie (56,40 m²) Joannie i Robertowi Kaczmarkom za 640 000 zł. Paweł Nowak, syn sprzedającej, koordynuje dokumenty, ale **nie ma pełnomocnictwa**; konflikt dotyczy dat wydania lokalu (1 grudnia / 15 stycznia). Brak przesądzania złej woli, pozorów przestępstwa lub automatycznego obowiązku odmowy czynności.

## Ważne ograniczenia produktu
- Odczyt skanów i tworzenie projektu Word są zaimplementowane w kodzie, lecz każda demonstracja wymaga rzeczywistego testu.
- Aparat telefonu dodaje zdjęcie do plików sprawy po **Wyślij**; dodanie nie uruchamia automatycznego ponownego odczytu.
- Kalendarz wiąże termin ze sprawą; nie należy twierdzić, że samodzielnie wykonuje wszystkie zadania CRM.
- Automatyczne przypisywanie przychodzących e-maili do spraw nie jest potwierdzone jako działające — nie pokazywać jako produkcyjnego automatu.
- Porównywanie kolejnych odczytów KW oraz autonomiczne alarmowanie o nowych wzmiankach wymaga osobnej implementacji/testu.
- Mikrofon wymaga kliknięcia; brak potwierdzonego mechanizmu stale nasłuchującego hasła „Komputerku”.
- Wniosek KW jest przygotowywany, lecz podpis i złożenie pozostają po stronie notariusza w urzędowym portalu.

## Repozytorium i status
Zmiana obejmuje wyłącznie **materiały marketingowe**. Nie modyfikuje kodu aplikacji, infrastruktury, konfiguracji ani produkcyjnej strony.
