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
| Tor GPU V6 (postać w planie → LTX → InfiniteTalk) | finyou `kampania/tor-gpu-v6` | buduje inny agent (commit daf226fe: `qwenedit.postac`, łańcuch `@slug`, jedno wynajęcie); fabryka ma jeden punkt styku `plan.adapter_gpu_v6` |
| Montaż na Cloudflare v2 | finyou `kampania/render-cf-v2`, `services/ai-clip/rolki/odcinek-cf.mjs` | wdrożony: `POST https://finyou-render.financeyou.workers.dev/zadanie`, `Authorization: Bearer RENDER_TOKEN`, wynik w `studio-media/rolki/serial/<id>/`; zlecenie z fabryki przechodzi prawdziwy `sprawdzOdcinek` |
| Magazyn mediów | Supabase „Finance you produkcja”, eu-central-1, publiczny bucket `studio-media` | adresy publiczne `https://vkzndnaoxhdxrxlpntcb.supabase.co/storage/v1/object/public/studio-media/…` |

Fabryka czyta te pliki przez `git show origin/<gałąź>:<ścieżka>`; po scaleniu z `master`
pierwszeństwo ma drzewo robocze. Gałęzie można nadpisać zmiennymi `FABRYKA_GALEZ_*`.

## 1. Scenariusz odcinka V6 (`marketing/komputerku/sezon-<n>/odcinki/sNNeMM.json`)

Domyślnie pisze go Claude w zaplanowanej sesji na podstawie promptu z `scenariusz --tylko-prompt`,
a fabryka tylko sprawdza i zapisuje: `scenariusz sNNeMM --waliduj plik.json` (kod wyjścia 1 przy
problemach). Opcjonalnie Bedrock eu-central-1 (`scenariusz sNNeMM` bez flag, wymaga poświadczeń AWS).

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
 "sceny": [{"scena": "sc1", "inputs": [{"ujecie": "u1", "postac": "helena", "voice_id": "…", "text": "[calm] …",
            "wynik": "https://…/studio-media/notarai/serial/s01e09/audio/u1.mp3"}]}]}
```

Tylko `eleven_v4`, `eleven_v4_turbo`, `eleven_v3`, `eleven_v3_conversational` (reguła repozytorium);
inny model przerywa plan. Głosy i karty postaci są w `tools/fabryka/obsada.json`; postać bez głosu
(Irena, Paweł, Kaczmarkowie, klienci) przerywa plan: najpierw Voice Design `eleven_ttv_v3`, potem wpis.
Głosy zaprojektowane 23.11.2026: Zosia `tYPZw7Cd3hWj7tv9LB6s`, Teresa `RXa8NBs5lQ95KXJJN1sg`,
Sowa `VPhviQ2vuUZzYt9E2nf9`. Cięcie dialogu na kwestie po znacznikach czasu (`/with-timestamps`),
wynik każdej kwestii pod adresem `wynik`.

## 3. Zlecenie GPU (`zlecenia/sNNeMM/gpu.json`, kontrakt `gpu-v6`)

Jedno wynajęcie na wszystkie ujęcia dnia. **Punkt styku z torem V6: `tools/fabryka/plan.py →
adapter_gpu_v6()`**; tylko ta funkcja zna nazwy pól toru. Łańcuch na ujęcie z postacią:

```json
[{"slug": "k-s01e09-u1-klatka-s101", "workflow": "qwenedit.postac",
  "image": "scenografia/rendery/s02/K03_helena_zblizenie_dzien.jpg", "image_ref": "<karta postaci>",
  "who": "notariuszka, 56 lat", "pose": "…", "mark": {"nazwa": "M_Helena_szczyt"}, "seed": 101},
 {"slug": "k-s01e09-u1-s101", "workflow": "infinitetalk.a2v", "image": "@k-s01e09-u1-klatka-s101",
  "audio": "https://…/notarai/serial/s01e09/audio/u1.mp3", "seconds": 3.0, "seed": 101}]
```

Ujęcie nieme bez postaci: tylko `ltx25.flf2v` (`image` = `image_last` = render planu, ruch z `klatki.mjs`).
Mowa jedno ziarno (InfiniteTalk ok. 5 min GPU), nieme dwa ziarna. **Do ustalenia z torem V6:** karty
postaci (`image_ref`: `karta` w `obsada.json` jest pusta), ścieżki renderów planów w wynajęciu (repo
notarai vs studio-media), piksele znacznika (`opis.json → znaczniki_w_kadrze_px`). Po wyborze ziarna
zaakceptowany klip trafia pod `studio-media/notarai/serial/<id>/klipy/<ujecie>.mp4`.

## 4. Zlecenie montażu (`zlecenia/sNNeMM/montaz.json`, kontrakt `odcinek-cf`)

Dokładnie schemat `sprawdzOdcinek` z `services/ai-clip/rolki/odcinek-cf.mjs` (finyou `kampania/render-cf-v2`),
wysyłany jako `{"odcinek": …}` na `POST https://finyou-render.financeyou.workers.dev/zadanie`
z `Authorization: Bearer RENDER_TOKEN`:

```json
{"odcinek": {
  "id": "s01e09", "cel": "rolki/serial/s01e09",
  "ujecia": [
    {"typ": "klip", "url": "https://…/notarai/serial/s01e09/klipy/u1.mp4", "od": 0, "do": 3.0, "dzwiek": "brak"},
    {"typ": "obraz", "url": "https://…/notarai/serial/s01e09/warstwy/u7.png", "czas": 5.0, "fokus": [0.5, 0.5]},
    {"typ": "kolor", "kolor": "#071D49", "czas": 1.5}],
  "glosy": [{"typ": "nagranie", "url": "https://…/notarai/serial/s01e09/audio/u1.mp3", "start": 0.0}],
  "napisy": [{"od": 0.0, "do": 3.0, "tekst": "…"}],
  "tlo": {"url": "https://…/notarai/serial/podklad/pokoj_dzien.mp3"},
  "plansza_koncowa": {"tekst": "Na motywach prawdziwych spraw z polskich sądów. Osoby i szczegóły zmienione.", "czas": 3},
  "znaczek_ai": true, "plakat_s": 1, "wersja_16x9": true}}
```

Mapowanie: ujęcia GPU i nagrania ekranu → `klip` (dźwięk klipu wyłączony, mowa z `glosy`), dokumenty
(`dokumenty.py`) → `obraz` z powolnym najazdem, plansza tytułowa → `kolor` + napis, plansza końcowa
i znaczek AI robi montaż. Wszystkie adresy https z hosta Supabase projektu (lista dozwolonych hostów
renderera). Wynik: `studio-media/rolki/serial/<id>/<id>.mp4`, `<id>-16x9.mp4`, `<id>.jpg`,
`<id>-napisy.json`; tekst VTT wraca tylko w wyniku zadania (render-upload nie przyjmuje `.vtt`).
**Do zrobienia raz:** wgrać podkład pokoju `notarai/serial/podklad/pokoj_dzien.mp3`.

## 5. Kolejka publikacji (`serial/odcinki.json`, format z PR #95)

```json
{"id": "s01e09", "sezon": 1, "odcinek": 9, "tytul": "…", "publish_at": "2026-11-27T09:00:00+01:00",
 "opis": "…", "kotwica": "Na motywach prawdziwych spraw…", "pytanie": "…",
 "pliki": {"wideo": "https://…", "plakat": "https://…", "napisy": "https://…"},
 "czas_s": 75, "status": "gotowy|w_produkcji", "akceptacja": "uzasadnienie konsultanta"}
```

Pliki wyłącznie jako `https://` w `studio-media` (Supabase, eu-central-1); domyślnie adresy wyniku
montażu v2 (`plan.url_wyniku`). Napisy `.vtt` opcjonalne (renderer ich nie wgrywa). `gotowy` tylko
z wideo i akceptacją. Nowy odcinek
idzie na koniec kolejki (najbliższy wolny slot po ostatnim zajętym, bez dziur). Wpis zastępczy bez wideo
(np. dzisiejszy `s01e01` z PR #95) nie zajmuje slotu i jest zastępowany.

## 6. Karta sprawy (`sezon-<n>/03_PRODUKCJA/KARTA_SPRAWY_<ID>.md`)

Szkic z kroku `karta`: wiersz katalogu, metadane z API SAOS (`/api/judgments/<id>`, nagłówek
`Accept: application/json`), fragmenty uzasadnienia od „UZASADNIENIE” po anonimizacji całego tekstu
(inicjały, imiona i nazwiska, skład sądu, sygnatury, miejscowości sądów, adresy, daty, lata, kwoty,
metraże, PESEL), wprost: „prawomocność: SAOS jej nie podaje”. Sekcję „Mechanizm dla serialu” uzupełnia
konsultant (Claude) przed scenariuszem. Pozycje spoza SAOS (uchwały SN, komunikaty) dostają kartę bez
fragmentów.
