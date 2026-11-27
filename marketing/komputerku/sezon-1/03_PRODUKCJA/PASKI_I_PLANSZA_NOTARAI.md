# Paski postaci i plansza końcowa notarai (standard od 27.11.2026)

Każdy odcinek serialu dostaje domyślnie:

1. **Pasek postaci** (lower third) przy pierwszym pojawieniu się każdej mówiącej lub widocznej
   postaci w odcinku, także Heleny. Jeden pasek na postać na odcinek, ok. 3,5–3,8 s.
   - Treść: nazwa · rola · myśl (kursywa, najwyżej ok. 7 słów, konkretna dla sytuacji odcinka).
   - **Notariuszki (Helena, Marta, Teresa) tylko z imieniem i rolą, nigdy z nazwiskiem**
     („Helena · notariuszka · …”). Pozostali: imię, nazwisko i rola z `01_KANON/BIBLIA_INTRYGI.md`.
   - Adrian Sowa to „pośrednik”; nazwa biura nigdy nie pada. Żadnych prawdziwych firm ani danych klientów.
   - Postać słyszana, a niewidoczna (telefon, głos zza drzwi) dostaje dopisek w roli:
     „w słuchawce” albo „głos zza kadru”.
   - Wygląd: belka cyjan→indygo, tabliczka z nazwą w granacie marki (Montserrat 800), rola na
     indygo wersalikami, myśl kursywą (Inter) na półprzezroczystym granacie; wejście wycieraniem
     od lewej z poświatą krawędzi, wyjście w odwrotnej kolejności.
   - Miejsce: lewa strona, nad napisami dialogowymi. Napisy (styl `Napisy` w finyou-render) kończą
     się na y=1503, a ich ramka zaczyna się na 1476 − 58·n (n wierszy); pasek staje 50 px nad
     najwyższym napisem ze swojego okna czasu (co najmniej nad 3 wierszami, czyli dół ok. y=1252).
     Znaczek „AI” i tytuł są u góry kadru. Wersja 16:9 z Workera to cały kadr 9:16 na rozmytym
     tle, więc pasek mieści się w niej bez przycinania.
   - Napisy nie mogą na siebie zachodzić w czasie (libass podnosi wtedy nowy napis nad stary na cały
     czas jego trwania i wjeżdża w pasek). `paski.py` skraca koniec napisu do startu następnego − 0,04 s.

2. **Plansza notarai** (ok. 4,5 s) na końcu ujęć, tuż przed planszą Workera „Na motywach
   prawdziwych spraw…” (3 s): sygnet i znak „notarai”, jedno zdanie łączące problem odcinka
   z tym, co produkt naprawdę robi, stopka „Każdy projekt sprawdza i zatwierdza notariusz.”
   i przycisk „notarai.pl”. Kolory i krój ze `strona/` (granat #071d49 / #061437, indygo
   #2b52d9, cyjan #29d5f3, Montserrat). Ostatnie 0,35 s przechodzi w kolor planszy Workera.
   - Zdanie odcinka bierzemy wyłącznie z funkcji opisanych na `strona/index.html` i w `README.md`.
     Bez gwarancji i bez funkcji „w planach”.
   - Bez lektora: plansza to reklama, a głos Heleny (notariuszki) nie może jej firmować.

## Jak dodać do nowego odcinka
1. Dopisz odcinek w `03_PRODUKCJA/paski.json` (`odcinki.sNNeMM.paski` i `plansza_notarai.linia`).
   `ujecie` to id ujęcia ze scenariusza (u1, u10…); `od` (domyślnie 0,3 s) przesuwa start;
   `przez_ciecie: true` pozwala paskowi przejść na następny klip tej samej sceny.
2. Po przygotowaniu zlecenia montażu (`montaz.json` dla finyou-render) uruchom lokalnie:
   `python3 services/ai-clip/rolki/paski.py <montaz.json> paski.json <klipy lokalne> <wyjście>`
   (repo finyou; `--podglad` daje tylko klatki PNG i raport).
3. Wyślij pliki z `<wyjście>/wysylka.txt` (wyslij.mjs) i zleć `<wyjście>/montaz.json` na
   finyou-render (`POST /zadanie`). Nic nie idzie przez GitHub Actions.
4. Sprawdź 1–2 klatki: pasek nie dotyka napisów, plansza czytelna.
