# Koszty produkcji „Komputerku…” i moc obliczeniowa — ustalenia z 13.11.2026

Ceny sprawdzone 13.11.2026 (cenniki fal, HeyGen, RunPod, Vast, Salad, Modal, Google, Azure, Anthropic).
Pełny przegląd rynku (modele otwarte, TTS po polsku, darmowe compute) jest w osobnym raporcie poza repo;
tu są tylko wnioski dla tego serialu i narzędzia, które je wdrażają.

## 1. Gdzie naprawdę idą pieniądze
| Pozycja | Dziś | Uwaga |
|---|---|---|
| Wideo i głos jednego odcinka 35 s (`README.md` §5, `awatary.md`) | **ok. 5,8 USD** (×1,5 z poprawkami ≈ 8–12 USD) | już niedrogo; HeyGen Avatar 6 Turbo to dobra decyzja |
| Pisanie biblii, scenariuszy, pakietów V4 w sesjach agentowych Claude | **1–10 USD za odcinek, dziesiątki USD za pakiet** | sesja czyta biblię i repo od nowa przy każdym zadaniu; to największy, niewidoczny koszt |
| Abonamenty (ElevenLabs 22, HeyGen 29, Descript 24–35 USD) | ~75–90 USD/mies. | stałe, niezależne od liczby odcinków |
| Aplikacja NotarAI na Bedrock (skany klientów, rozmowy, projekty) | effort `max` wszędzie, bez cache | osobny temat: `docs/cache-promptu.md` |

Wniosek: najpierw tokeny i abonamenty, dopiero potem GPU.

## 2. Co zostało wdrożone w tym PR
| Narzędzie | Co robi | Oszczędność |
|---|---|---|
| `narzedzia/odcinek_json.py` | scenariusz EPxx.md → `odcinki/EPxx.json` jednym wywołaniem Bedrock (wymuszone narzędzie = zawsze poprawny JSON); biblia + prompty + obsada + kamery (31 374 tokeny) jako stały prefiks za punktem cache | **zmierzone 13.11.2026 (Sonnet 4.6):** EP01 0,30 USD z zapisem cache, EP02 0,13 USD z odczytem cache (cache odczyt 31 374, pełne wejście 4 825) zamiast 1–10 USD w sesji agentowej; `--dry-run` liczy bez klucza |
| `narzedzia/koszty_odcinka.py` | wycena odcinek.json w trzech torach (obecny / tani hostowany / własne GPU) + log realnych wydatków | pokazuje, że tor GPU jest ~80 % tańszy, a tani hostowany ~65 % |
| `narzedzia/gpu/` | RunPod 4090 + ComfyUI + Wan 2.2 I2V z LoRA 4-krokową; paczka ujęć bez mowy z odcinek.json, każdy klip od razu na dysk i do logu kosztów | klip 5 s ≈ 0,01–0,02 USD zamiast 0,35 USD (Kling 2.5 Turbo Pro) |
| `bedrock.py` + `prompty.py` (aplikacja) | punkty cache w rozmowie o sprawie i na wzorze aktu | rozmowa o sprawie ok. 4× tańsza; wzór kancelarii czytany z cache |

## 3. Decyzje
1. **Zbliżenia mówiące zostają w HeyGen Avatar 6 Turbo** (0,039 USD/s). Otwarte modele (Wan2.2-S2V,
   LongCat, InfiniteTalk, LTX-2.3) przegrały test u3 na stabilności twarzy i polskim lip-syncu.
2. **Ujęcia bez mowy i klatki startowe przenosimy na własne GPU** (Wan 2.2 14B + LightX2V, Qwen-Image-Edit-2511,
   oba Apache 2.0). Wynajem RTX 4090 co sekundę (RunPod Community 0,34 USD/h; Salad batch 0,16; Modal 30 USD
   kredytów miesięcznie gratis). Zakup karty nie ma sensu poniżej ~300 h/mies.
3. **Głos narracji i gości: Google Chirp 3 HD** (30 polskich głosów, 1 mln znaków/mies. gratis) albo Azure (0,5 mln
   gratis, zwraca visemy). Głosy v2 głównej obsady zostają w ElevenLabs dla spójności - ale na PAYG (0,08 USD/1k),
   nie na abonamencie Creator: cały sezon to < 4 tys. znaków dialogu.
4. **„Mówiące w planie” (A/C):** przetestować EchoMimicV3 i InfiniteTalk na własnym GPU na 10 kwestiach z dźwiękiem.
   Jeśli lip-sync po polsku nie trzyma, zostaje WaveSpeed InfiniteTalk (0,03 USD/s) zamiast Kling Avatar v2 Pro (0,115).
5. **Darmowe GPU nie istnieje dla wideo:** Colab free łamie regulamin (tunelowanie UI), Kaggle (T4, 30 h/tydz.)
   uciągnie tylko obrazy i Wan 5B w 480p. Realnie darmowe: kredyty Modal 30 USD/mies., Beam 20 USD/mies.,
   darmowe tiery TTS i Gemini Flash. GCP trial nie daje GPU.
6. **Pułapki licencyjne UE:** HunyuanVideo / HunyuanVideo-Avatar (licencja wyklucza UE), MiniMax H3 (wyklucza UE),
   FLUX.1 dev/Kontext, Qwen-Image-2.1, XTTS v2, F5-TTS PL - niekomercyjne. Nie używać.

## 4. Dieta tokenowa dla pracy koncepcyjnej (biblia, scenariusze, pakiety)
- Jedno zapytanie = jeden artefakt w JSON/Markdown, z biblią w cache (`odcinek_json.py` jest wzorem).
- Sonnet 4.6 do pierwszej wersji, Opus 4.6 z `effort: low` tylko do kontroli continuity; Haiku 4.5 do napisów,
  opisów, tagów. Cache jest per model - jedna seria zadań = jeden model.
- Sesje agentowe (Claude Code) tylko do projektowania systemu i zmian w kodzie; nie do pisania odcinków.
- Bedrock batch inference daje −50 % przy generowaniu całego sezonu naraz (wejście z S3, wynik do 24 h) -
  do wdrożenia, gdy produkcja ruszy seryjnie.

## 5. Koszt odcinka 35 s po zmianach (`koszty_odcinka.py policz`)
| Tor | USD / odcinek | 8 odcinków |
|---|---|---|
| obecny (ElevenLabs + Nano Banana Pro + HeyGen + Kling Avatar + Kling 2.5) | 5,79 | 46 |
| tani hostowany (Chirp 3 HD + Seedream 4 + HeyGen Turbo + WaveSpeed InfiniteTalk + Replicate Wan 2.2) | 2,05 | 16 |
| własne GPU (Qwen-Image-Edit + Wan 2.2 + EchoMimic/InfiniteTalk; HeyGen Turbo na zbliżenia) | 1,09 | 9 |

Do tego: rozpisanie odcinka 0,13 USD (zmierzone, z cache) zamiast 1–10 USD, abonamenty −51 USD/mies. (ElevenLabs Creator, HeyGen Creator).

Wygenerowane `odcinki/EP01.json` i `EP02.json` są **szkicami do autoryzacji** (pole `_produkcja` zawiera model, zużycie tokenów i uwagi walidatora); nie zastępują scenariuszy kanonicznych z `marketing/komputerku/sezon-1/02_SCENARIUSZE/`.

## 6. Ryzyka
- Skrypty GPU powstały bez dostępu do karty - nazwy plików modeli i węzłów ComfyUI do potwierdzenia przy pierwszym
  uruchomieniu (`narzedzia/gpu/README.md`).
- Polski lip-sync w modelach audio-driven nikt nie zmierzył; decyzję podejmujemy po odsłuchu, nie po klatkach.
- Darmowe tiery znikają (Oracle zmniejszył ARM o połowę, Speechify kończy promocję 21.11.2026) - nie budować na nich SLA.
