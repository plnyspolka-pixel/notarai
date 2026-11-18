# NotarAI — Komputerku… / BRAND PACK zgodny z aktualnym produktem

**Data opracowania: 11.11.2026**

Ten pakiet zastępuje poprzednią bordowo-złotą propozycję. Zachowuje ludzką, ciepłą estetykę kancelarii, ale całą identyfikację systemową przejmuje z realnego NotarAI: oryginalny niebiesko-cyjanowy sygnet, jasne UI, Montserrat, granat/błękit/cyjan.

## Od czego zacząć
1. Otwórz `01_marki/BRAND_BOARD_POPRAWIONY.png` i `01_marki/KEY_VISUAL_16x9.png` — szybki kierunek wizualny.
2. Zobacz `02_bohaterowie/obsada_4_postacie.png` oraz `07_referencje_fotograficzne/kancelaria_zespol_kadr_glowny.jpg` — stała obsada i scenografia.
3. Wczytaj `01_marki/tokens.css` i `01_marki/oryginalny_sygnet_z_repo.svg` do edytora.
4. Skorzystaj z kompletów `03_plansze_video/{9x16,16x9,1x1}` i `04_grafika_systemowa`.
5. Przekaż realizatorowi dokumenty z `05_biblia_produkcji`.

## Zasada ważniejsza od wszystkich szablonów
**Nie zastępuj oryginalnego logo NotarAI logiem pióra, orła ani nowym symbolem.** Kancelaria może wyglądać ciepło, ale produkt jest blue-tech. Żadne ekrany marki nie mogą przejść w bordowo-złotą estetykę.

## Co ma status koncepcyjny
Bohaterowie i ich wygląd, scenografia, storyboardy, plansze i makieta UI są materiałami autorskimi / koncepcyjnymi. Właściwa aplikacja służy do nagrania docelowych ekranów. Rozpoznawanie słowa wybudzającego „Komputerku” nie zostało potwierdzone w bieżącej implementacji; dziś funkcjonują przyciski mikrofonu i transkrypcja w wybranych trybach.

## Poprawki v2 (11.11.2026)
- Wszystkie plansze i grafiki tekstowe (`01_marki`, `02_bohaterowie/obsada_4_postacie.png`, `03_plansze_video`, `04_grafika_systemowa`) wyrenderowane ponownie **prawdziwym Montserratem** (OFL, @fontsource/montserrat 5.1.0) zamiast zastępczego fontu. Źródło: `../narzedzia/render_plansz.js` — zmiana tekstu = zmiana w skrypcie i ponowny render, bez ręcznej edycji PNG.
- Znak słowny jak na notarai.pl: Montserrat 800, „ai” w #00BFE8; na ciemnym tle sygnet na białej płytce (oryginalne kolory, bez przemalowania).
- Makieta UI ma pieczątkę „MAKIETA POGLĄDOWA — nie jest zrzutem ekranu aplikacji”.
- Znaczek „AI” w rogu w `OVERLAY_TRANSPARENT.png` (cały film), jak w rolkach Finance You. Belki „Treść wygenerowana przez AI” i dopisków o AI na planszach nie używamy (12.11.2026).
