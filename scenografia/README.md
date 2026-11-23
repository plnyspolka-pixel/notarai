# Scenografia „Komputerku…” (Blender, od zera)

Dziesięć planów zdjęciowych zbudowanych skryptami Pythona w Blenderze (bpy 5.3, Cycles CPU + OpenImageDenoise).
Wymiary w metrach, prawdziwe źródła światła (HDRI + słońce + portale okien + lampy), kamery 9:16 (1080×1920),
puste obiekty-znaczniki pozycji postaci. **Zero tekstu**: brak napisów, logo, godeł i marek; kartki puste,
teczki zamknięte, grzbiety segregatorów gładkie, ekrany monitorów białe.

## Plany

| Kod | Plan | Warianty | Kamery | Ocena (szczerze) |
|---|---|---|---|---|
| s01 | Recepcja i poczekalnia (lada Basi) | dzień, wieczór | 7 | dobra |
| s02 | Gabinet Heleny (stół, regały akt) | dzień, wieczór | 7 | dobra, render pełny w repo |
| s03 | Pokój Marty i Kuby (dwa biurka) | dzień, wieczór | 7 | poprawna |
| s04 | Korytarz z drzwiami kancelarii + klatka kamienicy | dzień, wieczór | 7 | dobra |
| s05 | Kancelaria Teresy (blok, mniejsza) | dzień, wieczór | 7 | poprawna |
| s06 | Kawiarnia, stolik przy oknie | dzień, wieczór | 6 | dobra |
| s07 | Ulica przed kancelarią (fasada, brama) | dzień, noc (mokry asfalt) | 6 | sterylna, użyteczna na plan ogólny |
| s08 | Parking na podwórzu z autem Marty | noc, dzień | 6 | poprawna: auta sąsiadów CC0 pod plandeką, auto Marty tylko rozmyte lub na krawędzi |
| s09 | Sala szkoleniowa (bez emblematów) | dzień | 6 | poprawna, pusta |
| s10 | Mieszkanie Ireny + klatka bez windy | dzień, wieczór | 7 | dobra |

Pełna lista kamer (nazwa, obiektyw, położenie, cel, przeznaczenie) i znaczników (położenie, obrót, opis,
pozycja w pikselach w każdym kadrze) jest w `rendery/<kod>/opis.json` po renderze, a źródłowo na końcu
każdego pliku `sety/sNN_*.py` (wywołania `w.kamera(...)` i `w.znacznik(...)`).
Konwencja nazw: `K01_plan_ogolny`, `K02_...` (kamery), `M_Helena_fotel`, `M_klient_lewy` (znaczniki).
Wysokość znacznika = wysokość oczu (stoi ok. 1,62 m, siedzi ok. 1,1-1,15 m).

## Orientacja siedzisk i postaci (kontrola automatyczna)
- Każde siedzisko (krzesło, fotel, sofa, krzesło biurowe i kawiarniane) stawia się z `patrz_na=(x, y)`:
  obrót liczy się sam z kierunku przodu modelu. Przód modeli Poly Haven zmierzono raz z geometrii
  i zapisano w `manifest.json` → `przod_modeli` (stopnie od osi +x przy obrocie 0; większość ma przód w -y).
  Siedzisko bez `patrz_na` przerywa budowę.
- `wspolne.kontrola_siedzisk` po zbudowaniu planu wylicza rzeczywisty przód każdego siedziska z jego
  geometrii (od oparcia do środka rzutu) i porównuje z kierunkiem do celu; odchylenie > 20° przerywa budowę.
  Wynik trafia do `opis.json` (`siedziska_kontrola`). Test negatywny: odwrócone o 180° krzesło jest wykrywane.
- Znaczniki postaci też mają `patrz_na` (konwencja: `obrot_z` 0 = postać patrzy w +y, 90 = w -x).
- `rendery/<kod>/rzut_z_gory.png` - rzut z góry (cięcie na 2,2 m): czerwone strzałki = przód siedzisk,
  zielone kropki = ich cele, niebieskie = znaczniki postaci z kierunkiem, żółte = kamery.
  Sam rzut i kontrola: `python scenografia/zbuduj.py --plan wszystkie --rzut` (ok. 15 s na plan).

## Widok za oknem
- Okna nie pokazują już szarej bryły: `wspolne.widok_za_oknem` stawia za oknem płaszczyznę z rozmytym zdjęciem
  podwórza (wycinek panoramy CC0 z Poly Haven, `tlo_okna.py`, plik w `tla/`). Widać ją tylko z kamery i przez szyby;
  nie świeci do wnętrza i nie rzuca cieni, więc światło planu się nie zmienia. Na razie s02 (dzień).

## Wyniki w `rendery/<kod>/`
- `<kamera>_<wariant>.jpg` - kadr 1080×1920,
- `<kamera>_<wariant>_glebia.png` - mapa głębi 16-bit, wartość = odległość od kamery w mm (65535 = tło),
- `ruch_<kamera>_<wariant>.mp4` - najazd 3 s, 24 kl/s, 540×960 (jeden na plan),
- `opis.json` - kamery, znaczniki, czasy renderu,
- `blend/<kod>.blend` - scena (bez tekstur, jeśli >15 MB nie trafia do repo).

## Odbudowa
```bash
python -m venv venv && . venv/bin/activate
pip install bpy==5.3.0 OpenEXR numpy pillow      # + ffmpeg w systemie
python scenografia/pobierz_zasoby.py              # zasoby CC0 do scenografia/.cache (nie w repo)
python scenografia/zbuduj.py --plan s02 --podglad # szybki podgląd 33%/12 próbek -> rendery/_tmp/podglad
python scenografia/zbuduj.py --plan s02           # pełny render (domyślnie 32 próbki)
python scenografia/zbuduj.py --plan wszystkie --kamery K01_plan_ogolny --bez-ruchu
```
Opcje: `--warianty dzien,noc`, `--probki 64`. Wspólne klocki (pokój, okna, drzwi, regały, lampy, kamery,
render, głębia, najazd) są w `wspolne.py`; każdy plan to jeden plik w `sety/`.

## Render: tylko Cloudflare (finyou-scena)
Twarda reguła właściciela (23.11.2026): **scenografia nigdy nie renderuje się na GitHub Actions**.
`zbuduj.py` i `tlo_okna.py` przerywają od razu, gdy działają na GHA (`tools/zakaz_gha.py`), a workflow
pilnuje `tools/zakaz_renderu_gha.py`; dawny `scenografia-render.yml` usunięty. Render idzie przez Worker
`finyou-scena` (Cloudflare Containers, kod w finyou `services/render-cf/scena/`, opis w
`services/render-cf/README.md`):

```bash
curl -X POST -H "Authorization: Bearer $RENDER_TOKEN" -H "Content-Type: application/json" \
  -d '{"plan":"s02","kadry":["K01_plan_ogolny"],"wariant":"dzien","ref":"scenografia/blender-v1"}' \
  https://finyou-scena.financeyou.workers.dev/scena            # -> {"id": ...}
curl -H "Authorization: Bearer $RENDER_TOKEN" https://finyou-scena.financeyou.workers.dev/scena/<id>
```
Kontener pobiera te skrypty w podanym refie (gałąź, tag albo pełny SHA) z publicznego repo, zasoby CC0
z Poly Haven (`pobierz_zasoby.py`), renderuje `zbuduj.py` (Cycles CPU + OIDN, 4 wątki: `SCENA_WATKI`)
i wysyła JPG, mapy głębi, `rzut_z_gory.png`, `opis.json` (i najazd MP4 przy `"ruch": true`) do
`studio-media/scenografia/<plan>/` (nazwy małymi literami, np. `k01_plan_ogolny_dzien.jpg`).
`"podglad": true` = szybki podgląd do `scenografia/<plan>/podglad/`. Zmiana sceny = push i nowe zlecenie.

Pomiar 23.11.2026 (standard-4: 4 vCPU, 12 GiB): s02 K01 dzień, 32 próbki: **156,6 s** renderu, 204 s całe
zadanie, ok. 0,02 USD za kadr (+ ok. 0,02 USD czuwania kontenera); obraz zgodny z `rendery/s02/` w repo
(średnia różnica 0,26/255, głębia identyczna). Wynik:
https://vkzndnaoxhdxrxlpntcb.supabase.co/storage/v1/object/public/studio-media/scenografia/s02/k01_plan_ogolny_dzien.jpg
(lub ręcznie z listą planów) renderuje każdy plan w osobnym jobie i commituje wyniki z `[skip ci]`.

## Czasy (zmierzone, 4 rdzenie CPU, 15 GB RAM)
- podgląd 360×640, 12 próbek: 6-19 s na kamerę,
- pełny kadr 1080×1920, 32 próbki + OIDN: **190-235 s** dzień, **135-147 s** wieczór (zmierzone na s02),
- mapa głębi: kilka sekund na kadr,
- najazd 3 s (72 klatki 540×960, 12 próbek): ok. 20 min (s02: 23 min),
- cały komplet (10 planów, ok. 100 kadrów + 10 najazdów) na CPU: ok. 8-10 h.
GPU (np. Salad RTX 4090/5090, Cycles OptiX) powinno dać rząd wielkości szybciej (10-20 s na kadr,
najazd w kilka minut); Cloudflare Containers nie mają GPU, więc to byłby wynajem zlecany z kontenera (jak tor `gpu` w finyou-render), nigdy z GitHub Actions.

## Zasoby (CC0)
Wszystkie modele, tekstury i HDRI pochodzą z Poly Haven, licencja CC0 (https://polyhaven.com/license).
Lista identyfikatorów z adresami: `manifest.json` (źródło: `https://polyhaven.com/a/<id>`);
po pobraniu `.cache/zasoby.json` zawiera ścieżki, URL i licencję każdego pliku. Pliki binarne nie są w repo.
Meble i rekwizyty, których brak w Poly Haven (lada, regały akt, segregatory, monitory, telefon, drukarka,
zegar bez cyfr, schody, auta, fotele biurowe), są modelowane proceduralnie w `wspolne.py`.

## Słabe strony
- Za oknami gabinetu Heleny stoi prosta fasada oficyny (tynk, ciemne okna; nie rzuca cieni), a szyby przyciemniają widok jak filtr ND. W pozostałych planach za oknem jest tylko panorama HDRI (przyciemniona tą samą szybą) - do dorobienia `podworze_za_oknem` per plan.
- s08: sąsiednie auta to model CC0 `covered_car` (auto pod plandeką). Auta Marty nie ma w Poly Haven (żadnego auta bez plandeki), więc jej auto jest proceduralne i widać je tylko rozmyte (85 mm, f/1,8) albo jako skrawek na krawędzi kadru. Ujęć z wnętrza auta i detalu klamki nie ma - wymagają prawdziwego modelu.
- s07: fasada czysta, bez brudu, szyldów i przechodniów - dobra na plan ogólny, gorsza na detal.
- s09: sala pusta i jednolita; brakuje tłumu (statyści do dorobienia w AI).
- Brak postaci: znaczniki wyznaczają miejsca i wysokość oczu, postacie wstawia dalszy etap (AI / compositing).
- 32 próbki + odszumianie: w ciemnych kątach (wariant wieczór/noc) możliwe plamy odszumiacza; do finału 64+ próbek na GPU.
- Najazdy w połowie rozdzielczości (540×960) - wystarczają jako referencja ruchu, nie jako materiał finalny.
