# Fabryka odcinków „Komputerku…”

Dzienna produkcja serialu na publikację 09:00 i 16:00 bez końca, za grosze i z minimum pracy ludzi.
Kod: `tools/fabryka/`. Kontrakty JSON: [KONTRAKTY.md](KONTRAKTY.md). Testy: `tests/test_fabryka.py`.

## Dzienny przebieg (jedno polecenie)

```bash
python -m tools.fabryka dzien --adres https://<magazyn-UE>/serial
```

Kolejno, bez kroków płatnych:
1. **stan:** bufor gotowych odcinków po teraz; paczka = 2 odcinki, a 4, gdy bufor < 4 (BIBLIA §8.3);
   kolejne numery (po s01e40 od razu s02e01) i najbliższe wolne sloty.
2. **karta:** dla kotwic z planu sezonu (BIBLIA §6.3–6.4) szkic karty z SAOS, bez danych osobowych.
3. **scenariusz:** Bedrock eu-central-1, biblia + katalog planów w bloku z cache (płacimy raz na paczkę),
   bramka automatyczna, jedna runda poprawek modelu.
4. **plan:** dla scenariuszy bez problemów zlecenia `glosy.json`, `gpu.json`, `montaz.json`.
5. raport `marketing/komputerku/sezon-1/dziennik/RRRR-MM-DD.json`.

Kroki płatne i publikacja (po przebiegu):
6. **głosy:** ElevenLabs `eleven_v4` (zapas `eleven_v3`), Text to Dialogue po scenie, przez konektor
   ElevenLabs albo `fu.text_to_speech`; nigdy modele v1/v2 (gdy narzędzie nie daje v3+, przerwać).
7. **GPU:** jedno wynajęcie Salad na cały dzień: `ai-clip.yml` (finyou, `pay=true`, `max_usd=3`) albo
   `finyou-render` (`{"gpu": {...}}`). Bramka ai-clip (`ai-clip.mjs ocena`): SSIM klatki końcowej ≥ 0,85,
   transkrypcja ≥ 0,95, dźwięk; odrzucone ujęcie = poprawka tylko jego, nowe ziarno.
8. **ekrany:** nagranie prawdziwej aplikacji na koncie demo (Playwright) dla funkcji ze scenariusza;
   funkcja niesprawdzona tego dnia = scena bez ekranu (dokument albo cięcie).
9. **montaż:** `montaz.json` → wersje 9:16 i 16:9, plakat, napisy `.vtt`, do magazynu w UE.
10. **akceptacja i kolejka:**
    `python -m tools.fabryka publikuj s01e09 --wideo https://… --plakat https://… --napisy https://… --akceptacja "…"`,
    commit `serial/odcinki.json` na `master`. O 09:00 i 16:00 `serial-publikacja.yml` publikuje sam.

## Zadanie w chmurze (do harmonogramu, codziennie 05:37 czasu polskiego)

> Jesteś producentem serialu „Komputerku…” w repo plnyspolka-pixel/notarai. Uruchom
> `python -m tools.fabryka dzien --adres <magazyn>` na najnowszym `master`. Dla każdego odcinka
> z raportu, którego karta sprawy ma pustą sekcję „Mechanizm dla serialu”, przeczytaj kartę,
> uzupełnij mechanizm (notariusz wypada korzystnie, zero danych osobowych) i ponów scenariusz.
> Przejrzyj każdy scenariusz bez problemów jako konsultant: realizm procedury notarialnej, ton,
> zgodność z biblią; popraw albo odrzuć. Następnie wykonaj kroki 6–10 z docs/fabryka/README.md:
> głosy wyłącznie `eleven_v4`/`eleven_v3`, jedna paczka GPU (max 3 USD), nagrania ekranów tylko
> dla funkcji, które dziś sprawdzisz w aplikacji demo, montaż, Twoja akceptacja z uzasadnieniem
> w kolejce, commit i pull request do `master` z kolejką. Jeśli bufor spadnie poniżej 2 odcinków,
> zrób odcinek awaryjny (dokumenty, głosy, jedno ujęcie mówione). Raport: koszt, odrzuty, co
> zablokowało. Nie publikuj nic poza notarai.pl i nie podawaj nazwiska żadnego notariusza.

## Akceptacja (bez panelu ludzi)

Odcinek jest gotowy, gdy: scenariusz przeszedł `walidatory.sprawdz` bez problemów; każde ujęcie GPU
przeszło bramkę ai-clip; montaż przeszedł kontrolę dźwięku; Claude jako konsultant wpisał akceptację
z uzasadnieniem (pole `akceptacja` w kolejce). Właściciel może zatrzymać odcinek (status
`w_produkcji` albo usunięcie wpisu przed slotem). Nazwisko notariusza nigdy nie pada.

## Koszt odcinka (z dzienników wydatków ai-clip, 15–22.11.2026)

| Składnik | Pomiar | Na odcinek 75 s |
|---|---|---|
| GPU Salad RTX 5090 | 0,60 USD/h (`high`), 0,25 USD/h (`batch`); ujęcie mówione InfiniteTalk ok. 5 min (przebiegi 11–13 ujęć za 0,73–1,05 USD), nieme LTX 3 s ok. 0,005 USD | ok. 10 ujęć mówionych × 1 ziarno + 4 nieme × 2 ≈ **0,55 USD**; z poprawkami ok. 0,7 USD; z `batch` ok. 0,3 USD |
| Rozruch GPU | ok. 5 min, raz na paczkę dnia | ≈ 0,025 USD |
| Głosy ElevenLabs v3/v4 | ok. 0,08 USD / 1000 znaków | ≈ 0,05 USD |
| Scenariusz Bedrock | biblia ok. 30 tys. znaków w cache | ≈ 0,1–0,3 USD |
| Dokumenty, plansze, montaż w CI, ekrany | 0 USD | 0 |
| **Razem** | | **ok. 0,7–1,1 USD (3–4,5 zł)**; 2 odcinki dziennie ≈ 1,5–2,2 USD |

Największe oszczędności: jedno ziarno dla mowy, jedna paczka GPU na dzień, ruch kamery z `klatki.mjs`
(0 USD), plany z Blendera zamiast generowanych klatek, priorytet `batch` gdy bufor ≥ 4.

## Co jeszcze jest ręczne albo zablokowane

1. **Krok „postać w planie”** (render planu + karta postaci → klatka startowa): tor GPU V6 w finyou nie
   istnieje (`kampania/tor-gpu-v6` brak). Bez niego `gpu.json` nie ma pola `image`.
2. **Montaż v2 na Cloudflare** (`kampania/render-cf-v2` brak) i `RENDER_TOKEN` jako sekret GitHub.
3. **Magazyn mediów w UE** dla `pliki.*` (decyzja: S3 eu-central-1 czy Supabase po sprawdzeniu regionu).
4. **Głosy nowych postaci** (Zosia, Teresa, Sowa, klienci): Voice Design `eleven_ttv_v3` i wpis w `plan.GLOSY`.
5. **Plany 1, 3–10 z Blendera:** fabryka widzi tylko plany z `opis.json`; dziś tylko `s02`.
6. **PR #95 i #93** niescalone: fabryka czyta je z gałęzi.
7. **Mechanizm w karcie sprawy** i przegląd scenariusza robi Claude w zadaniu dziennym (nie człowiek).
8. **Bedrock:** krok scenariusza potrzebuje poświadczeń AWS (rola zadania albo profil); bez nich
   `dzien --bez-llm` zapisuje gotowe prompty.
