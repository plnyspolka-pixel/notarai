# Wycena produkcji: odc. 01 „Poniedziałek, 8:57” (scenariusz produkcyjny V1)

Stan: 12.11.2026. Ceny fal z `get_pricing` z tego dnia; HeyGen Avatar 6 zmierzone na koncie (ok. 0,078 USD/s, Turbo 0,039 USD/s);
kurs 1 USD ≈ 3,7 zł. Założenie: wszystkie ekrany NotarAI nagrywamy z prawdziwej aplikacji (sesja „funkcje pod odcinek 01” uzupełnia braki w kodzie).

## Układ filmu (zasada: najpierw wstrząs, potem intro)

| Blok | Czas | Skąd | Koszt |
|---|---|---|---|
| Trzęsienie ziemi = sc. 01 „Nie ma jeszcze dziewiątej” | 5 s | ujęcia z banku (zegar, telefon, drzwi, drukarka) + głos Kuby zza kadru | w b-rollu |
| Intro 5 „Komputerku, przywitaj się” | 8 s | gotowe | 0 |
| Sc. 02–12 | ok. 76 s | ujęcia mówione, b-roll, nagrania ekranów | niżej |
| Outro „Siódemka” z tekstem sc. 13 („Mniej chaosu…”, „ciąg dalszy nastąpi”) | 6 s | ponowny render `render_intro.js` | 0 |
| **Razem** | **ok. 95 s** | | |

## Ujęcia

**Ekrany (nagranie prawdziwej aplikacji, Playwright, konto demo): ok. 22 s, 0 zł.** Kalendarz (sc. 03), sprawa na telefonie i aparat
(sc. 04–05; widok mobilny, aparat zasilany plikiem wideo z fikcyjnym dokumentem, prawdziwe „Wyślij”), pliki na komputerze Marty,
Weryfikacja odczytu (sc. 06), Sporządź projekt / Sporządzam projekt… (sc. 08–09), Projekt dokumentu i Pobierz jako Word (sc. 10).
Kwestie w tych scenach idą głosem zza kadru, bez ruchu ust.

**Ujęcia mówione (kadr wzorcowy → HeyGen Avatar 6 Model API): ok. 45 s na ekranie.** Osiem ustawień, każde wielokrotnie:

| # | Ustawienie | Sceny | Kadr |
|---|---|---|---|
| T1 | Basia przy telefonie w sekretariacie | 02, 03, 04, 05 | nowy (z K3m) |
| T2 | Klient przy ladzie | 02, 04 | nowy + nowa postać epizodyczna |
| T3 | Marta wychodzi z teczką | 02 | nowy |
| T4 | Marta przy laptopie | 03, 05, 06, 08, 10 | **jest** (K5m) |
| T5 | Kuba obok Marty | 06, 10 | nowy |
| T6 | Helena w drzwiach gabinetu, okulary w dłoni | 07 | nowy |
| T7 | Helena przy biurku | 11, 12 | **jest** (K2m) |
| T8 | Basia w uchylonych drzwiach | 12 | nowy |

**B-roll bez mowy (kadr → fal image-to-video, klip 5 s, w filmie 1–2 s): 14 klipów.**

| Bank (do kolejnych odcinków) | Tylko ten odcinek |
|---|---|
| B1 zegar ścienny (8:57, wariant 9:24 przez tanią edycję) | E1 klient podaje dokument Basi |
| B2 telefon na biurku dzwoni | E2 Basia fotografuje dokument telefonem |
| B3 drzwi się otwierają, wchodzi klient (K7) | E3 Marta przekazuje projekt Helenie |
| B4 drukarka wypuszcza wydruk (K3) | E4 Kuba wyjaśnia dane z klientem (sc. 09) |
| B5 Basia odbiera telefon | E5 Marta przegląda dokumenty (sc. 09) |
| B6 Helena odkłada długopis (zbliżenie dłoni) | E6 Helena w rozmowie zawodowej (sc. 09) |
| B7 Kuba z teczką czeka | E7 Marta i Kuba wymieniają uśmiechy (sc. 07) |

## Koszt

| Pozycja | Wyliczenie | Wariant standard | Wariant oszczędny |
|---|---|---|---|
| Kadry nowych ustawień i b-rollu (Nano Banana Pro edit, 0,15 USD) | 18 kadrów × 3 próby | 8,10 | 5,40 (2 próby) |
| Postać epizodyczna „klient” (arkusz, raz, do banku) | 8 obrazów | 1,20 | 1,20 |
| Ujęcia mówione HeyGen Avatar 6 (0,078 USD/s) | 45 s × 1,5 podejścia | 5,30 | 2,60 (Turbo 0,039 USD/s w planach średnich) |
| B-roll fal | 14 × 5 s × 1,5 podejścia | 7,35 (Kling 2.5 Turbo Pro, 0,07 USD/s) | 3,50 (Wan 2.5, 0,05 USD/s, 1 podejście) |
| Głosy ElevenLabs (dialog scen, ok. 1200 znaków × 3) + głos klienta | | 0,50 | 0,50 |
| Efekty dźwiękowe (ok. 10) i podkład napięcia | | 0,50 | 0,30 |
| Ekrany, montaż, napisy, outro (lokalnie) | | 0 | 0 |
| **Suma** | | **≈ 23 USD ≈ 85 zł** | **≈ 13,5 USD ≈ 50 zł** |
| **Z zapasem 30% na poprawki** | | **≈ 30 USD ≈ 110 zł** | **≈ 18 USD ≈ 65 zł** |

**Bank ujęć:** B1–B7, klient epizodyczny i kadry T1, T3, T6 (ok. 8–9 USD) wracają w kolejnych odcinkach; odc. 02+ szacunkowo
**15–20 USD** każdy przy podobnej długości. Każde ujęcie zapisujemy z kadrem, promptem, ID zadania i plikiem w `pakiet/11_bank_ujec/`
(jak `postac.json`), żeby nie generować drugi raz.

**Czas ludzi** (realnie największy koszt): akceptacja 18 kadrów (ok. 30 min), przegląd ujęć (ok. 60 min), autoryzacja prawna i notariusza.

## Ryzyka

- Ekrany zależą od sesji „funkcje pod odcinek 01”: dopóki nie domknie luk, sceny 03–10 nie mają materiału.
- Generowanie projektu trwa kilkanaście minut; w filmie skracamy to przeskokiem 8:57 → 9:24 (sc. 09), nagranie ekranu w dwóch częściach.
- Ujęcia z dwiema osobami (T5): ruch ust tylko mówiącej postaci; druga może być sztywna. W razie problemu: kontrplan z dwóch kadrów.
- Wan 2.5 (wariant oszczędny) słabiej trzyma twarze; do ujęć z postaciami lepiej Kling, do rekwizytów (zegar, telefon, drukarka) wystarczy Wan.
