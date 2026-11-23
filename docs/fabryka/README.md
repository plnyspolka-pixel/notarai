# Fabryka odcinków „Komputerku…”

Dzienna produkcja serialu na publikację 09:00 i 16:00 bez końca, za grosze i z minimum pracy ludzi.
Media: Supabase „Finance you produkcja” (eu-central-1), publiczny bucket `studio-media`.
Kod: `tools/fabryka/`. Kontrakty JSON: [KONTRAKTY.md](KONTRAKTY.md). Testy: `tests/test_fabryka.py`.

## Dzienny przebieg (jedno polecenie)

```bash
python -m tools.fabryka dzien
```

Kolejno, bez kroków płatnych:
1. **stan:** bufor gotowych odcinków po teraz; paczka = 2 odcinki, a 4, gdy bufor < 4 (BIBLIA §8.3);
   kolejne numery (po s01e40 od razu s02e01) i najbliższe wolne sloty.
2. **karta:** dla kotwic z planu sezonu (BIBLIA §6.3–6.4) szkic karty z SAOS, bez danych osobowych.
3. **prompt scenariusza:** `marketing/komputerku/sezon-<n>/odcinki/sNNeMM.prompt.json` (biblia, kontrakt,
   katalog planów, plan sezonu, karta, poprzedni odcinek). Scenariusz pisze Claude w zaplanowanej sesji
   (bez Bedrock); `--bedrock` włącza drogę przez Bedrock eu-central-1, gdy są poświadczenia AWS.
4. raport `marketing/komputerku/sezon-1/dziennik/RRRR-MM-DD.json`.

Potem w tej samej sesji:
5. **scenariusz → bramka:** Claude zapisuje JSON i uruchamia
   `python -m tools.fabryka scenariusz sNNeMM --waliduj /tmp/sNNeMM.json` (kod 1 = poprawić i powtórzyć).
6. **zlecenia:** `python -m tools.fabryka plan sNNeMM` → `glosy.json`, `gpu.json`, `montaz.json`.
7. **głosy:** ElevenLabs `eleven_v4` (zapas `eleven_v3`), Text to Dialogue po scenie, przez konektor
   ElevenLabs albo `fu.text_to_speech`; nigdy modele v1/v2 (gdy narzędzie nie daje v3+, przerwać).
   Kwestie do `studio-media/notarai/serial/<id>/audio/<ujecie>.mp3`.
8. **GPU:** jedno wynajęcie Salad na cały dzień przez tor V6 (finyou `kampania/tor-gpu-v6`, `ai-clip.yml`
   `pay=true`, `max_usd=3`, `priority=batch` gdy bufor ≥ 4). Bramka ai-clip (`ai-clip.mjs ocena`):
   kontrola klatki „postać w planie”, SSIM klatki końcowej ≥ 0,85, transkrypcja ≥ 0,95, dźwięk; odrzut =
   poprawka tylko tego ujęcia. Zaakceptowane klipy do `studio-media/notarai/serial/<id>/klipy/<ujecie>.mp4`.
9. **warstwy:** dokumenty z `dokumenty.py` (PNG) i nagrania prawdziwej aplikacji na koncie demo
   (Playwright) do `studio-media/notarai/serial/<id>/warstwy/`; funkcja niesprawdzona tego dnia = bez ekranu.
10. **montaż:** `montaz.json` → `POST https://finyou-render.financeyou.workers.dev/zadanie`
    (`Authorization: Bearer RENDER_TOKEN`, treść `{"odcinek": …}`), potem `GET /zadanie/<id>` do końca.
    Wynik w `studio-media/rolki/serial/<id>/` (9:16, 16:9, plakat, napisy JSON).
11. **akceptacja i kolejka:** `python -m tools.fabryka publikuj sNNeMM --akceptacja "…"` (adresy wyniku
    montażu domyślne), commit `serial/odcinki.json`, pull request do `master`. O 09:00 i 16:00
    `serial-publikacja.yml` publikuje sam.

## Zadanie w chmurze (do harmonogramu, codziennie 05:37 czasu polskiego)

> Jesteś producentem i konsultantem serialu „Komputerku…” w repo plnyspolka-pixel/notarai.
> Na najnowszym `master` uruchom `python -m tools.fabryka dzien`. Dla każdej karty sprawy z pustą
> sekcją „Mechanizm dla serialu” przeczytaj kartę (fragmenty są już bez danych osobowych), uzupełnij
> mechanizm tak, żeby notariusz wypadał korzystnie, i zapisz kartę. Dla każdego odcinka z raportu
> przeczytaj `…/odcinki/sNNeMM.prompt.json`, napisz scenariusz JSON dokładnie według zawartego tam
> kontraktu i biblii, zapisz go poza repo i sprawdź
> `python -m tools.fabryka scenariusz sNNeMM --waliduj <plik>`; poprawiaj, aż bramka przejdzie (najwyżej
> 3 rundy, potem odcinek awaryjny: dokumenty, głosy, jedno ujęcie mówione). Przejrzyj scenariusz jako
> konsultant: realizm procedury notarialnej, ton, zgodność z biblią. Potem kroki 6–11 z
> docs/fabryka/README.md: głosy wyłącznie `eleven_v4`/`eleven_v3`, jedna paczka GPU (max 3 USD),
> nagrania ekranów tylko dla funkcji, które dziś sprawdzisz w aplikacji demo, montaż przez finyou-render,
> Twoja akceptacja z uzasadnieniem w kolejce, commit i pull request do `master`. Raport: koszt, odrzuty,
> co zablokowało. Nie publikuj nic poza notarai.pl i nie podawaj nazwiska żadnego notariusza.

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
| Scenariusz | pisze Claude w zaplanowanej sesji (Bedrock opcjonalnie) | 0 USD poza sesją |
| Dokumenty, plansze, montaż w CI, ekrany | 0 USD | 0 |
| **Razem** | | **ok. 0,6–0,8 USD (2,5–3,5 zł)**; 2 odcinki dziennie ≈ 1,2–1,6 USD |

Największe oszczędności: jedno ziarno dla mowy, jedna paczka GPU na dzień, ruch kamery z `klatki.mjs`
(0 USD), plany z Blendera zamiast generowanych klatek, priorytet `batch` gdy bufor ≥ 4.

## Co jeszcze jest ręczne albo zablokowane

1. **Tor GPU V6** (finyou `kampania/tor-gpu-v6`, inny agent): fabryka podaje łańcuch przez
   `plan.adapter_gpu_v6`; brakuje kart postaci (`karta` w `tools/fabryka/obsada.json`) i ustalenia,
   skąd wynajęcie bierze rendery planów.
2. **`RENDER_TOKEN`** musi być dostępny w sesji (sekret), żeby wysłać montaż.
3. **Głosy** Ireny, Pawła, Kaczmarków i klientów: Voice Design `eleven_ttv_v3` i wpis w `obsada.json`.
4. **Podkład pokoju** `studio-media/notarai/serial/podklad/pokoj_dzien.mp3` do wgrania raz.
5. **Plany 1, 3–10 z Blendera:** fabryka widzi tylko plany z `opis.json`; dziś tylko `s02`.
6. **PR #95 i #93** niescalone: fabryka czyta je z gałęzi.
