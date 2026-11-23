# Fabryka odcinków: kontrakty JSON

Jeden plik z umowami między krokami fabryki (`tools/fabryka`) a torami produkcji w repo finyou.
Stan na 23.11.2026. **Do ustalenia** oznacza miejsce, którego nie da się dziś sprawdzić w kodzie.

## Stan gałęzi, z których fabryka czyta

| Co | Gdzie | Stan 23.11.2026 |
|---|---|---|
| Biblia V6 | `marketing/komputerku/BIBLIA_V6.md` | jest na tej gałęzi (commity 45a2321, ff18518 przeniesione z `strona/serial-komputerku`, gdzie trafiły przez współdzielony katalog) |
| Plany zdjęciowe (Blender) | `scenografia/rendery/<plan>/opis.json`, gałąź `scenografia/blender-v1` | pełny render tylko `s02`; pozostałe 9 renderuje workflow GitHub |
| Kolejka publikacji | `serial/odcinki.json`, gałąź `strona/serial-komputerku` (PR #95) | format niżej; niescalone |
| Katalog spraw | `docs/research/notarial-casebook-2026/`, gałąź `research/notarial-casebook-court-ministry-2026-11` (PR #93) | draft |
| Tor GPU V6 (postać w planie → LTX → InfiniteTalk) | finyou `kampania/tor-gpu-v6` | **gałąź nie istnieje** (sprawdzone `git branch -r`); kontrakt `gpu-v6` niżej to propozycja oparta na `services/ai-clip` |
| Montaż na Cloudflare v2 | finyou `kampania/render-cf-v2` | **gałąź nie istnieje**; dziś `services/render-cf` na `ccr-695a7173-infinitetalk` czyta zlecenia z obrazu i wymaga `RENDER_TOKEN` |

Fabryka czyta te pliki przez `git show origin/<gałąź>:<ścieżka>`; po scaleniu z `master`
pierwszeństwo ma drzewo robocze. Gałęzie można nadpisać zmiennymi `FABRYKA_GALEZ_*`.

## 1. Scenariusz odcinka V6 (`marketing/komputerku/sezon-<n>/odcinki/sNNeMM.json`)

Pisze go krok `scenariusz` (Bedrock eu-central-1), sprawdza `walidatory.sprawdz`.

```json
{
  "id": "s01e09", "sezon": 1, "odcinek": 9, "slot": "09:00",
  "tytul": "…", "sprawa_kotwica": "A17", "prowadzi": "helena", "typ_otwarcia": "A",
  "muzyka": {"typ": "brak|ciepla|dzwieki_kancelarii", "pod_szczytem": false},
  "pytanie_koncowe": "…", "streszczenie": "…",
  "sceny": [{
    "id": "sc1", "rola": "zimne_otwarcie|tytul|swiat|zwrot1|praca|szczyt|zawieszenie|plansza_koncowa",
    "plan": "s02", "kamera": "K03_helena_zblizenie", "wariant": "dzien",
    "ujecia": [{
      "id": "u1", "typ": "mowiace|bez_mowy|dokument|ekran|plansza",
      "postac": "helena", "znacznik": "M_Helena_szczyt",
      "kwestia": "…", "kwestia_v3": "[calm] …", "czas_s": 3.5,
      "ruch_kamery": "statyczna|najazd|odjazd|w-lewo|w-prawo|w-gore|w-dol",
      "prompt_ruchu": "tylko ruch, po angielsku",
      "dokument": {"szablon": "notatka|porownanie_kw", "pola": {}, "fokus": "…"},
      "ekran": {"funkcja": "…"}, "tekst": "tylko plansze",
      "zart": false, "romans": false, "dozwolony_tekst": null
    }]
  }],
  "lista_kontrolna": {"czynnosc_jako_rama": {"ok": true, "jak": "…"}, "…": "12 punktów thrillera"},
  "_fabryka": {"problemy": [], "zuzycie": [], "model": "…"}
}
```

Bramka (`tools/fabryka/walidatory.py`): struktura i role scen, 60–90 s, otwarcie (bez planszy, ekranu,
dokumentu w 3 s; dwa głosy w 10 s; inny typ niż poprzednio), jeden szczyt, ekran poza ±5 s od szczytu,
dokument w kadrze, brak plansz w środku, zdanie planszy końcowej, ≤ 1 żart i ≤ 1 beat romansu (żart nigdy
kosztem klienta), kwestie z tagiem v3, zero tekstu w promptach obrazu, brak sygnatur, PESEL, odwołań
do SAOS i nazwiska konsultanta, brak śmiechu z taśmy, kotwica dozwolona (P05–P20 i H17 nigdy, P01 od
sezonu 2, ta sama kotwica raz na sezon poza „motyw/echo/wariant”), 12 punktów thrillera z uzasadnieniem,
plany/kamery/znaczniki istnieją w `opis.json`.

## 2. Zlecenie głosów (`zlecenia/sNNeMM/glosy.json`, kontrakt `glosy-v1`)

```json
{"kontrakt": "glosy-v1", "odcinek": "s01e09", "model_id": "eleven_v4", "model_zapasowy": "eleven_v3",
 "language_code": "pl", "settings": {"stability": 0.5}, "seed": 909, "tryb": "text-to-dialogue",
 "sceny": [{"scena": "sc1", "inputs": [{"ujecie": "u1", "postac": "helena", "voice_id": "…", "text": "[calm] …"}]}],
 "wynik": "audio/s01e09/<ujecie>.mp3"}
```

Tylko `eleven_v4`, `eleven_v4_turbo`, `eleven_v3`, `eleven_v3_conversational` (reguła repozytorium);
inny model przerywa plan. Postać bez stałego głosu (np. Zosia, Teresa, Sowa) przerywa plan: najpierw
Voice Design `eleven_ttv_v3`, potem wpis w `plan.GLOSY`. Cięcie dialogu na kwestie po znacznikach czasu
(`/with-timestamps`). **Do ustalenia:** gdzie odkładać mp3 (proponowane `studio-media/notarai/audio/`).

## 3. Zlecenie GPU (`zlecenia/sNNeMM/gpu.json`, kontrakt `gpu-v6`)

Format zgodny z `services/ai-clip` (pola ujęcia wybierają szablon: `audio` → InfiniteTalk, dwie klatki →
LTX-2.5 flf2v), plus pola V6:

```json
{"kontrakt": "gpu-v6", "defaults": {"width": 720, "height": 1280},
 "shots": [{"slug": "k-s01e09-u1-s101", "workflow": "infinitetalk.a2v", "audio": "audio/s01e09/u1.mp3",
            "seconds": 3.0, "seed": 101, "tlo_planu": "scenografia/rendery/s02/K03_helena_zblizenie_dzien.jpg",
            "postac": "helena", "znacznik": "M_Helena_szczyt", "track": "notarai", "concept": "…", "tags": []}]}
```

**Do ustalenia (tor V6):** krok „postać w planie”, czyli zamiana `tlo_planu` + `postac` + `znacznik`
(pozycja w pikselach z `opis.json → znaczniki_w_kadrze_px`) na klatkę startową `image`. Model edycji obrazu
na Salad (licencja komercyjna do sprawdzenia, METODYKA §8.1 pkt 3). Do czasu tego kroku `plan` daje
zlecenie, którego ai-clip jeszcze nie przyjmie (brak `image`). Mowa: jedno ziarno (InfiniteTalk ok. 5 min
GPU na ujęcie); nieme: dwa ziarna (LTX 3 s, grosze). Jedna paczka GPU na cały dzień.

## 4. Zlecenie montażu (`zlecenia/sNNeMM/montaz.json`, kontrakt `montaz-v6`)

```json
{"kontrakt": "montaz-v6", "odcinek": "s01e09", "formaty": ["9x16", "16x9"],
 "os_czasu": [{"ujecie": "u1", "od_s": 0, "do_s": 3, "zrodlo": {"typ": "gpu", "concept": "komputerku-s01e09-u1"},
               "kwestia": "…", "reakcja_po_s": 0}],
 "napisy": "…", "dzwiek": {"podklad": "pokoj_dzien", "muzyka": "brak", "kontrola": "poza mową <= -45 dB"},
 "znaczek_ai": true, "plansza_tytulowa": {"tekst": "…", "znak_dzwiekowy": "komputerku-v1", "czas_s": 1.5},
 "plansza_koncowa": "Na motywach prawdziwych spraw z polskich sądów. Osoby i szczegóły zmienione.",
 "cel": "https://<magazyn-UE>/serial/s01e09/", "wynik": ["s01e09.mp4", "s01e09-16x9.mp4", "s01e09.jpg", "s01e09.vtt"]}
```

Źródła: `gpu` (zaakceptowany klip z bramki ai-clip), `dokument` (`dokumenty.py`, 0 USD), `ekran` (nagranie
prawdziwej aplikacji na koncie demo z dnia produkcji), `plansza`. **Do ustalenia:** wejście `render-cf-v2`
(dziś montaż rolek `montaz-ci.mjs` przyjmuje `{katalog, przebiegi, rolki, cel}` i czyta pliki z obrazu).
Proponowane: v2 przyjmuje ten JSON z adresu w magazynie zamiast z obrazu.

## 5. Kolejka publikacji (`serial/odcinki.json`, format z PR #95)

```json
{"id": "s01e09", "sezon": 1, "odcinek": 9, "tytul": "…", "publish_at": "2026-11-27T09:00:00+01:00",
 "opis": "…", "kotwica": "Na motywach prawdziwych spraw…", "pytanie": "…",
 "pliki": {"wideo": "https://…", "plakat": "https://…", "napisy": "https://…"},
 "czas_s": 75, "status": "gotowy|w_produkcji", "akceptacja": "uzasadnienie konsultanta"}
```

Pliki wyłącznie jako `https://` w magazynie w UE. `gotowy` tylko z wideo i akceptacją. Nowy odcinek
idzie na koniec kolejki (najbliższy wolny slot po ostatnim zajętym, bez dziur). Wpis zastępczy bez wideo
(np. dzisiejszy `s01e01` z PR #95) nie zajmuje slotu i jest zastępowany. **Do ustalenia:** magazyn mediów
(S3 `notarai-serial` w eu-central-1 albo publiczny bucket Supabase po potwierdzeniu regionu UE).

## 6. Karta sprawy (`sezon-<n>/03_PRODUKCJA/KARTA_SPRAWY_<ID>.md`)

Szkic z kroku `karta`: wiersz katalogu, metadane z API SAOS (`/api/judgments/<id>`, nagłówek
`Accept: application/json`), fragmenty uzasadnienia od „UZASADNIENIE” po anonimizacji całego tekstu
(inicjały, imiona i nazwiska, skład sądu, sygnatury, miejscowości sądów, adresy, daty, lata, kwoty,
metraże, PESEL), wprost: „prawomocność: SAOS jej nie podaje”. Sekcję „Mechanizm dla serialu” uzupełnia
konsultant (Claude) przed scenariuszem. Pozycje spoza SAOS (uchwały SN, komunikaty) dostają kartę bez
fragmentów.
