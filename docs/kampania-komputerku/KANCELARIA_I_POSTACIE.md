# Kancelaria i postacie: jak to jest zbudowane i jak dodać nową osobę

Wersja: **kancelaria-v2 / obsada-v2** (12.11.2026). Zastępuje ręcznie pisane prompty z obsady v1. Każdy obraz powstaje z tych samych klocków zapisanych w plikach, więc da się go odtworzyć.

## 1. Zasada

```
scenografia.json ──► plan.png (+ plan_K1..K9 z zaznaczoną kamerą)
      │
      ├─► K1 „ujęcie matki” (pusty pokój)  ← jedyne ujęcie robione „od zera”
      │        │
      │        ├─► karta materiałów (meble, mosiądz, parkiet, okno, drukarka)
      │        └─► K2..K9 plansze (puste kadry z każdej kamery) = K1 + materiały + plan kamery
      │
postacie/<slug>/postac.json ──► ref.jpg ─► arkusz.jpg ─► kadr na planszy (Kx) ─► HeyGen photo avatar
```

- **Jedno źródło prawdy:**
  - pokój jest opisany raz, w `pakiet/09_scenografia_v2/scenografia.json`: wymiary, ściany, materiały z kolorami HEX, światło, 9 stałych kamer z pozycją, wysokością, kierunkiem i obiektywem;
  - postać jest opisana raz, w `pakiet/10_obsada_v2/postacie/<slug>/postac.json`.
- **Nic nie powstaje z „gołego” promptu.**
  - Każda plansza dostaje jako referencje ujęcie matki K1, kartę materiałów i plan z zaznaczoną kamerą.
  - Każdy kadr postaci dostaje pustą planszę danej kamery, zdjęcie referencyjne postaci i jej arkusz.
- **Prompty składa skrypt** `narzedzia/kancelaria.py` z bloków `bloki_promptu` (pokój, układ, materiały, światło, styl, negatyw). Ten sam plik wejściowy daje to samo zlecenie.
- **Wersjonowanie.**
  - Zmiana pokoju to nowa wersja `kancelaria-v3`, a zmiana wyglądu postaci to `obsada-v3`. Nigdy nie podmieniamy po cichu w trakcie sezonu.
  - Zatwierdzone pliki mają w JSON-ie pole `zatwierdzona`/`zatwierdzony`.

## 2. Kancelaria (kancelaria-v2)

| Element | Kanon |
|---|---|
| Pokój | Kraków, kamienica, I piętro; 6,5 × 5 m, 3,4 m wysokości, biała sztukateria |
| Podłoga | dąb miodowy w jodełkę `#B98A52`, pod biurkiem dywan granat/krem |
| Ściany | ciepły krem `#EFE6D6`; na północnej boazeria orzechowa do 90 cm |
| Meble | **wszystkie** ciemny orzech `#5A3A22`; skóra koniak `#8A4B2A`; metal satynowy mosiądz `#B08D57` |
| Zachód | regały pod sufit, księgi granat/bordo/butelkowa zieleń, podświetlenie LED |
| Północ | obraz abstrakcyjny (ochra/łupek) między dwoma kinkietami; drzwi dwuskrzydłowe w narożniku NW; fikus w NE |
| Wschód | 3 wysokie okna w czarnych stalowych ramach ze szprosami, lniane firany, kamienica naprzeciw |
| Środek | biurko główne (Helena) frontem na południe, fotel koniak, 2 kremowe krzesła gości, lampa grzybek |
| SW | stół roboczy dla dwojga z laptopem (Marta / Kuba) |
| SE | sekretariat: komoda z szarą drukarką, małe biurko z monitorem (Basia) |
| Światło | przedpołudnie, miękkie dzienne z okien (5600 K) + ciepłe lampy (3000 K); bez słońca i kolorowych świateł |

**Kamery (stałe stanowiska, wszystkie 9:16):**

| Kamera | Co | Obiektyw | Typowe użycie |
|---|---|---|---|
| K1 | plan ogólny z południa na biurko główne | 28 mm | kadr A, grupa, **ujęcie matki** |
| K2 | biurko główne z przodu | 85 mm | Helena, rozmowy przy biurku |
| K3 | sekretariat z drukarką | 50 mm | Basia |
| K4 | stół roboczy przez ramię | 50 mm | kadr C z laptopem |
| K5 | stół roboczy en face | 50 mm | Marta, Kuba przy laptopie |
| K6 | biblioteka | 50 mm | rozmowa na stojąco |
| K7 | drzwi wejściowe | 35 mm | wejścia, goście |
| K8 | okno | 35 mm | przebitki |
| K9 | detal biurka | 85 mm | rekwizyty |

**Pliki:**
- plan: `pakiet/09_scenografia_v2/plan.png` (i `plan_K*.png`);
- plansze: `plansze/K*.jpg`, karta materiałów `plansze/materialy.jpg`;
- podgląd: `PODGLAD_plansze.jpg`.

**Nowe miejsce w kancelarii**, np. kuchnia albo poczekalnia:
1. Dopisz kamerę `K10` w `scenografia.json` (pozycja, azymut, obiektyw, pole `widac`).
2. Uruchom `kancelaria.py plan --kamera K10`, wgraj plan i zrób `zapisz plan K10 <url>`.
3. Uruchom `zlecenie plansza K10`.
4. Jeśli to nowa część pokoju, dopisz ją też do bloku `pokoj` i `uklad`. Wtedy zmiana jest wersją v3.

## 3. Jak wprowadzić nową postać (powtarzalnie)

Średni koszt: ok. **3–4 USD** w fal i ok. **1,3 USD** za utworzenie awatara HeyGen. Czasu człowieka: 15–20 min, głównie na akceptacje.

| Krok | Co robisz | Narzędzie | Brama |
|---|---|---|---|
| 0 | `python3 narzedzia/kancelaria.py nowa-postac <slug>` → wypełnij `postac.json`: imię, wiek, rola (PL i EN), wygląd (twarz, włosy, sylwetka), **stały strój z kolorami**, rekwizyty, charakter, relacje, strefa w kancelarii, kadry (kamera + poza po angielsku), profil ruchu, opis głosu | edytor | czy opis nie zderza się z obsadą (inna fryzura, kolor stroju, wiek) |
| 1 | `zlecenie postac <slug> ref` → fal (3 warianty); wybierz jeden → `zapisz postac <slug> ref <url>` | fal `nano-banana-pro/edit` | **akceptacja twarzy** (to jest tożsamość na cały sezon) |
| 2 | `zlecenie postac <slug> arkusz` → fal → `zapisz postac <slug> arkusz <url>` | fal | front, ¾ i profil to ta sama osoba |
| 3 | dla każdej kamery z `kadry`: `zlecenie postac <slug> kadr:K?` → fal (2 warianty) → `zapisz postac <slug> kadr:K? <url>` | fal | siatka kontrolna (pkt 5) |
| 4 | głos: Voice Design z `glos.opis_voice_design_en` (eleven_v3, 3 podglądy, wybór), zapis `elevenlabs_voice_id` | ElevenLabs | odsłuch 2 kwestii |
| 5 | `kancelaria.py podglad postacie` → arkusz kontrolny wszystkich postaci w kancelarii | — | spójność z resztą obsady |
| 6 | `kancelaria.py heygen <slug>` → body: `POST /v3/avatars` (`type: photo`) z kadrem głównym, potem `GET /v3/avatars/looks/{id}` (czy jest `heygen-avatar-6-turbo` i `avatar_v`) → wpis `heygen.avatar_id` | `heygen_api_request` | test 1 kwestii w Avatar 6 Turbo |
| 7 | `status: zatwierdzona`, commit, wpis w tabeli obsady poniżej | git | — |

**Zasady kadrów, żeby awatar mógł się ruszać:**
- **Dłonie wolne.** Nie mogą leżeć na przedmiocie, bo żaden silnik nie oderwie ręki od drukarki ani klawiatury (patrz `awatary.md`).
- **Twarz w pełni widoczna**, usta zamknięte, patrzy w obiektyw albo lekko obok.
- **Kadr główny** (`glowny: true`) to ten, z którego powstaje awatar HeyGen. Zwykle jest to medium shot 50 mm, bo z niego HeyGen sam robi zbliżenie.
- **Nowa postać nie może przypominać realnej osoby.** Wariant „ref” ma w prompcie „new fictional person”. Nie podajemy zdjęć prawdziwych ludzi jako referencji.

**Siatka kontrolna dla nowej postaci (człowiek, 2 minuty):**
1. Ta sama twarz w ref, arkuszu i kadrach?
2. Strój i kolory dokładnie z `postac.json`?
3. Skala postaci zgadza się z meblami (drzwi ok. 220 cm, blat 75 cm)?
4. Kancelaria bez zmian: orzech, jodełka, okna, światło z prawej/okien?
5. Dłonie wolne, twarz ostra?
6. Postać odróżnia się od obsady sylwetką i kolorem stroju, czyli jest czytelna w miniaturze 9:16?

## 4. Ruch i silniki (budżet)

Wyniki testów są w `awatary.md`. Zasady produkcyjne:

| Ujęcie | Silnik HeyGen | Koszt | Kiedy |
|---|---|---|---|
| standard: mówiąca postać | `heygen-avatar-6-turbo` + `motion_prompt` = `ruch.motion_prompt_baza` + akcja z odcinka | ok. 0,04 USD/s | domyślnie |
| gest jest puentą | `avatar_v` (bez motion_prompt) | ok. 0,085 USD/s | najwyżej 1–2 ujęcia na odcinek |
| kadr ze sceną (gest, ruch kamery) | `heygen-avatar-6` (pełny) | ok. 0,08 USD/s | gdy Turbo wychodzi płasko |
| reakcja bez mowy | fal image-to-video z planszy | — | przebitki |

**Jak nie palić budżetu:**
- Renderuj **jedną** kwestię testowo przed całym odcinkiem.
- Kwestie poniżej 1,5 s łącz z sąsiednią.
- Nie renderuj ponownie ujęć, w których zmienia się tylko napis albo grafika, bo to robi montaż.
- Awatara HeyGen twórz dopiero po akceptacji kadru głównego (każdy kosztuje ok. 1,3 USD).

## 5. Obsada v2: stan

| Postać | Strefa / kamera główna | ref + arkusz | Kadr w kancelarii-v2 | Głos | Awatar v2 |
|---|---|---|---|---|---|
| Helena | biurko główne / K2 | z obsady-v1 (zatwierdzone) | zatwierdzony 12.11 | `0YMlrD87k6Saqi6L1Joy` (v2) | `b10e796650c8b09ae190f57aad4f81e1` |
| Marta | stół roboczy / K5 (K4) | jw. | zatwierdzony 12.11 | `rOIbi11t4PdzPrW90No0` (v2) | `76568ce3a95191687ca7288be833801b` |
| Basia | sekretariat / K3 | jw. | zatwierdzony 12.11 | `vqyfbWoOfYmPoa0QNkKB` (v2) | `1e4d13ee1029a1f179e9bd725b200dfa` |
| Kuba | biblioteka / K6 (K7) | jw. | zatwierdzony 12.11 | `l49KzmmcER7qYZfvh1NN` (v2) | `ba3a449e3fac77633c11b7a52acdf95f` |

Głosy v2 i przepis nagrywania sceny (Text to Dialogue → cięcie → HeyGen z czystą mową): [`glosy.md`](glosy.md). Stan na żywo pokazuje `python3 narzedzia/kancelaria.py status`.

Odcinek 1 na obsadzie v2: `podglady/odc1_podglad_v3.mp4` (u1–u4: Avatar 6 Turbo + motion_prompt, głosy v2; składa `narzedzia/sklej_podglad_v3.sh`).

## 6. Ściąga poleceń

```bash
cd docs/kampania-komputerku
python3 narzedzia/kancelaria.py status
python3 narzedzia/kancelaria.py plan --kamera K3            # plan z zaznaczoną kamerą
python3 narzedzia/kancelaria.py zlecenie plansza K3          # JSON do fal (nano-banana-pro/edit)
python3 narzedzia/kancelaria.py zapisz plansza K3 <fal_url>
python3 narzedzia/kancelaria.py nowa-postac zenon
python3 narzedzia/kancelaria.py zlecenie postac zenon ref
python3 narzedzia/kancelaria.py zapisz postac zenon ref <fal_url>
python3 narzedzia/kancelaria.py zlecenie postac zenon kadr:K7
python3 narzedzia/kancelaria.py podglad postacie
python3 narzedzia/kancelaria.py heygen zenon
```

Zlecenia uruchamia się przez konektor fal (Claude: `run_model` / `submit_jobs` z wygenerowanym JSON-em). Skrypt nie trzyma kluczy, bo te są w konektorach.
