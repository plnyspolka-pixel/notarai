# Zgodność V4 z PR #20

Baseline: 5e58dd03b79ba1228657ec858b3116e84e5f659d, 12.11.2026.

## Zachowane
Helena, Marta, Basia, Kuba; role i wygląd z BIBLIA_POSTACI.md. Kancelaria-v2 i obsada-v2 według KANCELARIA_I_POSTACIE.md. Kamery K1–K9 oraz źródłowe warianty postaci, m.in. K2m, bez dopisywania fikcyjnych pozycji kamer. Montserrat i tokens.json. Oryginalny sygnet static/notarai-symbol.svg i gotowy logotyp pakiet/01_marki/logo_kampanijne_poziome_light.png. Starszy static/logo.png nie należy do aktualnej identyfikacji kampanii i nie jest używany. Format 30–40 s i adaptacje. Stałe głosy, pipeline ElevenLabs → HeyGen/fal → nagrania produktu → montaż → kontrola. Człowiek ocenia wynik. Mały znaczek AI przez cały film zgodnie z najnowszym README; ocena prawna pozostaje bramką.

## Świadome rozwinięcie
V4 dodaje 8 koncepcji według późniejszych ustaleń rozmowy. Historyczne 6 scenariuszy nie jest przepisywane i nie jest uruchamiane pod nową numeracją. Proponowana ścieżka po przyjęciu pakietu: docs/kampania-komputerku/v4/. Nie zmieniać istniejących JSON-ów postaci i scenografii. Eksport do odcinek-szablon.json dopiero po późniejszej autoryzacji scenariusza.

## Rozstrzygnięte różnice źródeł
Opis PR mówi o warstwie AI 0–5 s, lecz najnowszy README i scenariusze wymagają znaczka przez cały film: V4 przyjmuje nowszą regułę. Starsza biblia dopuszcza makiety; nowszy README wymaga autentycznych ekranów produktu: V4 używa nagrań dla działających funkcji, a plany pokazuje jako odrębne koncepcje. Szablon odcinka ma v1, ale README wskazuje v2: V4 zachowuje schemat kluczy, wymaga aktualnych zatwierdzonych referencji v2. W odczytanej karcie Heleny v2 avatar_id jest pusty, a zatwierdzenie kadrów null: ich użycie pozostaje zablokowane. Dokument kokpitu zabrania uznania gałęzi za wdrożoną produkcyjnie: V4 nie nadaje jej takiego statusu.

## Ograniczenia zgodności
Przejrzano PR i wybrane pliki przy baseline. Nie sprawdzono kompletnego stanu odrębnego repozytorium Finance You, połączeń usług, cen ani kont produkcyjnych. Kompatybilność jest dokumentacyjna i koncepcyjna względem wskazanego head, nie certyfikacją uruchomienia pipeline. Każda zmiana head wymaga ponownego przeglądu.

## Źródła

- [docs/kampania-komputerku/README.md](https://github.com/plnyspolka-pixel/notarai/blob/5e58dd03b79ba1228657ec858b3116e84e5f659d/docs/kampania-komputerku/README.md)
- [docs/kampania-komputerku/KANCELARIA_I_POSTACIE.md](https://github.com/plnyspolka-pixel/notarai/blob/5e58dd03b79ba1228657ec858b3116e84e5f659d/docs/kampania-komputerku/KANCELARIA_I_POSTACIE.md)
- [docs/kampania-komputerku/odcinek-szablon.json](https://github.com/plnyspolka-pixel/notarai/blob/5e58dd03b79ba1228657ec858b3116e84e5f659d/docs/kampania-komputerku/odcinek-szablon.json)
- [docs/kampania-komputerku/scenariusze.md](https://github.com/plnyspolka-pixel/notarai/blob/5e58dd03b79ba1228657ec858b3116e84e5f659d/docs/kampania-komputerku/scenariusze.md)
- [docs/kampania-komputerku/pakiet/01_marki/tokens.json](https://github.com/plnyspolka-pixel/notarai/blob/5e58dd03b79ba1228657ec858b3116e84e5f659d/docs/kampania-komputerku/pakiet/01_marki/tokens.json)
- [docs/kampania-komputerku/pakiet/05_biblia_produkcji/BIBLIA_POSTACI.md](https://github.com/plnyspolka-pixel/notarai/blob/5e58dd03b79ba1228657ec858b3116e84e5f659d/docs/kampania-komputerku/pakiet/05_biblia_produkcji/BIBLIA_POSTACI.md)
- [docs/kampania-komputerku/pakiet/05_biblia_produkcji/BIBLIA_WIZUALNA.md](https://github.com/plnyspolka-pixel/notarai/blob/5e58dd03b79ba1228657ec858b3116e84e5f659d/docs/kampania-komputerku/pakiet/05_biblia_produkcji/BIBLIA_WIZUALNA.md)
- [docs/kampania-komputerku/pakiet/09_scenografia_v2/scenografia.json](https://github.com/plnyspolka-pixel/notarai/blob/5e58dd03b79ba1228657ec858b3116e84e5f659d/docs/kampania-komputerku/pakiet/09_scenografia_v2/scenografia.json)
- [docs/kampania-komputerku/pakiet/10_obsada_v2/postacie/helena/postac.json](https://github.com/plnyspolka-pixel/notarai/blob/5e58dd03b79ba1228657ec858b3116e84e5f659d/docs/kampania-komputerku/pakiet/10_obsada_v2/postacie/helena/postac.json)
- [docs/kokpit-operacyjny.md](https://github.com/plnyspolka-pixel/notarai/blob/5e58dd03b79ba1228657ec858b3116e84e5f659d/docs/kokpit-operacyjny.md)
