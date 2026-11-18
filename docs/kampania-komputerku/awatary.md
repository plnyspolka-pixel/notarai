# Postacie w ruchu: HeyGen „na maksa” vs open-source

Stan na 12.11.2026. Test praktyczny: odc. 1, ujęcie **u3**, Basia: „Kubusiu. Ten komputer drukuje od czasów Unii Lubelskiej.” (3,88 s). Audio wyciągnięte z obecnego pliku ujęcia, czyli ten sam voice_id ElevenLabs `XxH7vHpT0p7INeJx8ihA`. Głosów nie ruszano.

Pliki testowe są w [`podglady/awatary_test/`](podglady/awatary_test/):

- [`u3_porownanie_siatka.mp4`](podglady/awatary_test/u3_porownanie_siatka.mp4): wszystkie wersje naraz, siatka 5×2, z dźwiękiem.
- [`u3_klatki_t1.0s.jpg`](podglady/awatary_test/u3_klatki_t1.0s.jpg) i [`u3_klatki_t2.2s.jpg`](podglady/awatary_test/u3_klatki_t2.2s.jpg): ta sama klatka we wszystkich wersjach.
- [`u3_twarze_3fps.jpg`](podglady/awatary_test/u3_twarze_3fps.jpg): zbliżenie twarzy, 3 klatki na sekundę. Wiersze 0–9 mają numerację jak w tabeli niżej.
- `u3_<wersja>.mp4`: każda wersja osobno (540×960, z oryginalnym audio).

## TL;DR: rekomendacja

1. **Domyślnie zostajemy w HeyGen, ale zmieniamy silnik.** Zamiast obecnego „photo avatar” na domyślnym silniku renderujemy przez `POST /v3/videos` z `engine: {type: "heygen-avatar-6-turbo"}` i `motion_prompt` (mimika, spojrzenie, postawa).
   - Kosztuje tyle co Avatar IV (ok. 0,04 USD/s).
   - Daje wyraźnie więcej mimiki: brwi „znad okularów”, ruch barków i tułowia.
   - Twarz zostaje stabilna i mamy 1080×1920.
   - Na odcinek 35 s wychodzi ok. **1,4 USD**.
2. **Ujęcia, w których gest ręki niesie gag**, robimy w **HeyGen Avatar V** (ok. 0,085 USD/s, szacunek z salda).
   - W teście jako jedyny HeyGen sam oderwał dłoń od drukarki i gestykulował.
   - Nie da się nim sterować (`motion_prompt` dla photo avatara bez digital twina jest odrzucany).
   - Z open-source podobny ruch rąk dał **Wan2.2-S2V** (Apache-2.0) przez fal. Ma jednak tylko 576p przy 16 fps i trochę „zmiękcza” twarz.
3. **Open-source nie zastępuje dziś HeyGena 1:1** w naszym torze (kadr wzorcowy 2K + polski WAV → 9:16 1080p).
   - Najlepsze modele z ruchem ciała (Wan2.2-S2V, LongCat-Avatar, MultiTalk/InfiniteTalk) dają 480–580p, 16–25 fps i dryf tożsamości.
   - LongCat w teście zmienił Basi fryzurę (pojawił się kok), a MultiTalk odwrócił ją od kamery.
   - LTX-2.3 w trybie audio-to-video praktycznie nie ruszał ustami przy polskim audio.
   - Warto je trzymać jako tor zapasowy i do „ujęć ruchowych”, z upscalem. Darmowe nie są: hostowane kosztują 0,10–0,60 USD/s, więcej niż HeyGen Avatar 6 Turbo.

**Proponowany koszt odcinka 35 s:**
- **ok. 1,5–2,5 USD**: HeyGen Avatar 6 Turbo z 1–2 ujęciami w Avatar V, plus ok. 30% zapasu na powtórki.
- **Obecnie:** domyślny Avatar IV photo, ok. 1,35 USD.

## Wyniki testu u3 (ocena z klatek i podglądu)

| # | Wersja | Ruch ciała | Mimika | Usta (PL) | Artefakty / spójność twarzy | Rozdz. | Koszt testu |
|---|---|---|---|---|---|---|---|
| 0 | **Obecne**: HeyGen photo avatar, silnik domyślny (`generate_avatar_video`) | prawie zero, dłonie przyklejone | umiarkowana | dobre | stabilna | 720×1280 | – |
| 1 | HeyGen **Avatar IV** + `motion_prompt` + `expressiveness: high` | lekki ruch głowy i tułowia, dłonie stoją | wyraźna | dobre | **okulary zmieniają oprawki i odblask** (klatki 3–5) | 1080×1920 | ok. 0,15 $ |
| 2 | HeyGen **Avatar 6** + `motion_prompt` | barki i tułów, przechylenie głowy | **najlepsza**: brwi znad okularów, ironia | dobre | stabilna | 1080×1920 | ok. 0,30 $ |
| 3 | HeyGen **Avatar 6 Turbo** + `motion_prompt` | jak 2 | jak 2, minimalnie mniej subtelna | dobre | stabilna | 1080×1920 | **0,15 $** (zmierzone) |
| 4 | HeyGen **Avatar 6 Model API** (surowy kadr, bez awatara) + prompt z gestem | jak 2; **polecenie „podnieś rękę i wskaż” zignorowane** | jak 2 | dobre | stabilna, kadr 1072×1920 (bez przycięcia awatara) | 1072×1920 | 0,30 $ (zmierzone) |
| 5 | HeyGen **Avatar V** (bez `motion_prompt`, bo jest odrzucany) | **gest otwartą dłonią, dłoń odrywa się od drukarki** | dobra | dobre | stabilna | 1080×1920 | ok. 0,33 $ |
| 6 | **Wan2.2-S2V-14B** (open, Apache), fal, 580p | **najwięcej gestów rąk**, obrót głowy | dobra | dobre, ruchliwe | twarz lekko „przerysowana”, miękka | 576×1024, 16 fps | ok. 0,57 $ |
| 7 | **LongCat-Video-Avatar** (open, MIT), fal, 480p | duży obrót do drukarki | średnia | trudno ocenić (odwrócona) | **zmiana fryzury (kok), dryf tożsamości** | 448×832, 16 fps | ok. 0,87 $ (min. segment 5,8 s) |
| 8 | **LTX-2.3** audio-to-video (open, licencja LTX), fal | prawie zero | minimalna | **usta prawie zamknięte, brak lip-syncu** | stabilna | 1080×1920, 24 fps | ok. 0,37 $ |
| 9 | **MultiTalk** (open, Apache), fal `ai-avatar/multi`, 480p | gesty dłoni | średnia | słabo widoczne | odwraca głowę od kamery; klip ucięty do 3,24 s (81 klatek) | 448×832 | ok. 0,65–0,8 $ |

**Wydatki na testy:**
- HeyGen: saldo portfela spadło z 32,43 do 31,20 USD, czyli **1,23 USD** za 6 renderów.
- fal: **ok. 2,8 USD**, w budżecie.

**Uwagi do testu:**
- Ocena opiera się na klatkach co 0,33–0,5 s i na zbliżeniach twarzy, a nie na pomiarze LSE/SyncNet. Przed decyzją produkcyjną trzeba obejrzeć [`u3_porownanie_siatka.mp4`](podglady/awatary_test/u3_porownanie_siatka.mp4) z dźwiękiem.
- **Kadrowanie:** photo avatar HeyGena (wiersze 0–3 i 5) przycina i lekko powiększa kadr względem wzorca. Model API (4) i modele fal biorą cały kadr 1536×2752.
- **Motion prompt:** silnie wpływa na mimikę i głowę. Gest dłoni, która w kadrze leży na obiekcie, był ignorowany we wszystkich wariantach HeyGen. Avatar V wykonał gest „sam z siebie”.

## Część A: HeyGen, co jest w API (dokumentacja developers.heygen.com, 11.2026)

**Ważne:**
- API **v1/v2 jest po sunsecie (31.10.2026)**. Cały ruch idzie przez v3.
- Nasze `generate_avatar_video` (MCP fu) renderowało silnikiem domyślnym, czyli Avatar IV bez `motion_prompt`. Stąd sztywne ciało.
- **Nasze 4 awatary:** wszystkie są `photo_avatar` i mają `supported_api_engines`: `avatar_v`, `avatar_iv`, `avatar_iii`, `heygen-avatar-6`, `heygen-avatar-6-turbo` (sprawdzone na Basi przez `GET /v3/avatars/looks/{id}`).

| Silnik (`engine.type`) | Co daje | Sterowanie | Koszt API |
|---|---|---|---|
| `avatar_iii` | Najstarszy; photo do 1080p, DT do 4K | brak `motion_prompt` | 0,99 $/min photo (0,0165 $/s) |
| `avatar_iv` (domyślny) | Photo, DT, studio, dowolny obraz (`type: image`) | `motion_prompt`, `expressiveness: low/medium/high` (tylko photo/obraz) | **2,31 $/min photo (0,0385 $/s)**; DT 4,83 $/min |
| `avatar_v` | „Najwyższa wierność”, animacja z look-referencji | `motion_prompt` i `more_blinking` **tylko gdy grupa ma digital twina** (`engine.reference_look_id`), inaczej 400 | DT 7,20 $/min; photo nieopublikowane, **u nas ok. 0,085 $/s** (szacunek z salda) |
| `heygen-avatar-6` | Najnowszy, rekomendowany; do 2K | `motion_prompt` (do 1200 zn.), `engine.motion_expressiveness: default/less`, `engine.reference_look_id` | nieopublikowane; **zmierzone ok. 0,078 $/s** |
| `heygen-avatar-6-turbo` | Jak wyżej, szybciej | jak wyżej | nieopublikowane; **zmierzone ok. 0,039 $/s** |
| `type: cinematic_avatar` | Scena z promptu: kamera, ruch, do 3 postaci w kadrze, 5–15 s; modele `seedance_2` / `heygen_video_1` | `prompt` zamiast skryptu, głos z looka | **7,30 $ za klip 720p**, 17,67 $ za 1080p |

**Dodatkowe możliwości i ograniczenia:**
- **Avatar 6 Model API**: `POST /v3/models/avatars`, potem polling `GET /v3/models/videos/{id}`. Animuje dowolny obraz z audio bez zakładania awatara: wysyłasz kadr wzorcowy i WAV, dostajesz pełny kadr 9:16. Przetestowane (wiersz 4).
- **Emocje i kamera:** w v3 nie ma osobnych pól „emotion” ani „camera”. Steruje się nimi wyłącznie tekstem `motion_prompt` (Avatar 6) lub `prompt` (cinematic).
- **Pełna sylwetka:** nie ma osobnego trybu. Liczy się kadr źródłowy, a sterować można przez `aspect_ratio` i `fit`.
- **Tło:** `background` (kolor lub obraz), `remove_background`, `output_format: webm` dla przezroczystości.

**Ceny:** https://help.heygen.com/en/articles/10060327-heygen-api-pricing-explained (aktualizacja 9.11.2026). Rozliczenie pay-as-you-go w USD, 1 kredyt ≈ 0,05 $.
- **Uwaga do panelu fu:** `heygen_status` pokazuje `remaining_quota` (1946) i `credits_estimate` (32,43). Ta druga wartość to w praktyce **saldo w USD** (`/v3/users/me` → `wallet.remaining_balance`), a nie „kredyty”.

### Awatary „z wideo” i pełniejsze postacie bez prawdziwych ludzi

- **Digital twin** (`POST /v3/avatars`, `type: digital_twin`, nagranie 15–600 s) jest dostępny przez API na PAYG: 2,13 $ za utworzenie.
  - Wymaga jednak **zgody nagranej kamerką przez tę samą osobę** (`POST /v3/avatars/{group}/consent`, hostowana strona).
  - Własne nagranie zgody albo pominięcie zgody to tylko Enterprise.
  - **Wniosek:** z wygenerowanego klipu fikcyjnej postaci nie zrobimy twina. Nie ma kto nagrać zgody.
- **Model API z `reference_videos`:** referencja wideo realistycznego człowieka to tylko Enterprise (422 `realistic_human_reference_not_allowed`). Wideo postaci animowanych lub ilustrowanych przechodzi, ale nasz styl jest fotorealistyczny.
- **Prompt avatar** (`type: prompt`, postać w pełni syntetyczna, bez zgody, do 3 `reference_images`): można nim zrobić nowe looki (stroje, ujęcia) tej samej postaci z `avatar_id` = obecny look.
  - Renderuje na Avatar V, IV i III.
  - Nie testowane, bo dodaje looki do produkcyjnej grupy postaci.
  - Dokumentacja nie mówi, że prompt-look odblokowuje `motion_prompt` w Avatar V. Wymagany jest look „digital twin albo kuratorowany”.
- **Ścieżka „photo → klip ruchu → twin”** jest więc dla nas zamknięta.
- **Co realnie daje pełniejszą postać:**
  - (a) Avatar 6 lub 6 Turbo z `motion_prompt`;
  - (b) Avatar V do gestów;
  - (c) kadr wzorcowy z miejscem na ręce, czyli dłonie nie oparte o przedmiot, bo każdy silnik niechętnie je stamtąd odrywa;
  - (d) do ujęć z akcją (chodzenie, podawanie teczki) generacja image-to-video (Kling / Wan / Seedance) jako B-roll bez mowy, a kwestię mówioną dajemy w ujęciu awatarowym.
- **Cinematic Avatar** robi „prawdziwą scenę” z kamerą, ale kosztuje 7,30 $ za klip i nie bierze naszego WAV (głos z looka). Do serii z dialogiem ElevenLabs się nie nadaje.

## Część B: open-source (przegląd GitHub/HF, 11.2026)

**Kryterium:** kadr + polski WAV → mówiąca postać 9:16, a do tego licencja **komercyjna w UE**.

| Model | Co robi | Licencja (kod / wagi) | Komercja w PL | VRAM | Hosting (koszt/s) | Ocena dla nas |
|---|---|---|---|---|---|---|
| **Wan2.2-S2V-14B** (Alibaba) | pół lub całe ciało, gesty, kamera | Apache / Apache | ✅ | ≥80 GB | fal `fal-ai/wan/v2.2-14b/speech-to-video` 0,10 / 0,15 / 0,20 $ (480 / 580 / 720p); **fal wycofuje 4.01.2027**; Replicate `wan-video/wan-2.2-s2v` | **najlepszy ruch rąk w teście**; 16 fps, miękka twarz |
| **LongCat-Video-Avatar 1.5** (Meituan) | pół ciała, gesty, 2 osoby | MIT / MIT | ✅ | 48–80 GB | fal `fal-ai/longcat-single-avatar/...` 0,15 $/jedn.: 480p = 1 jedn./s, 720p = 4 jedn./s (**0,60 $/s**) | ekspresyjny, ale **dryf tożsamości** (fryzura) |
| **InfiniteTalk / MultiTalk** (MeiGen) | głowa + ciało, kilka osób, dubbing wideo→wideo | Apache / Apache | ✅ | 14B, z offloadem od 24 GB | fal `fal-ai/ai-avatar/multi` 0,20 $/s; `fal-ai/infinitalk` wycofany; WaveSpeed / Atlas ok. 0,03–0,06 $/s | gesty OK, odwraca głowę, 480p |
| **EchoMimicV3 (+Flash)** (Ant) | głowa lub pół ciała | Apache / Apache | ✅ | 12–16 GB (RTX 4090) | fal `fal-ai/echomimic-v3` 0,20 $/s | nie testowany; tani self-host |
| **LTX-2.3 / 2.5** (Lightricks) | audio-to-video, natywne 9:16 | Apache / LTX Community | ⚠️ darmowe < 10 mln $ przychodu | 24–48 GB | fal `fal-ai/ltx-2.3/audio-to-video` 0,10 $/s; `lightricks/ltx-2.5/audio-to-video/*` | **w teście brak lip-syncu** |
| **LiveAvatar** (Alibaba-Quark) | streaming, długie wideo (LoRA na S2V) | Apache | ✅ | 48–80 GB | brak | ostry obraz, mało ruchu; research preview |
| **SoulX-FlashTalk / FlashHead** | real-time talking head | Apache | ✅ | 80 GB / mały | fal `fal-ai/flashtalk` 0,02 $/s, `fal-ai/flashhead` 0,005 $/s | tanio, mało ruchu ciała |
| **SkyReels-V3-A2V** | avatar, wiele postaci, do 200 s | Skywork Community | ⚠️ licencja do przeczytania | <24 GB (FP8) | brak | do obserwacji |
| **HuMo, OmniAvatar, FantasyTalking, StableAvatar** | starsze, 480p | Apache / MIT | ✅ (StableAvatar: kod bez LICENSE) | różnie | StableAvatar na fal | wyprzedzone |
| **Hallo 1/2/3, Sonic, LivePortrait, SadTalker** | głowa | MIT / CC BY-NC (Sonic) / InsightFace NC | ❌ lub ⚠️ | – | – | **odpadają** (głowa lub licencja) |
| **HunyuanVideo-Avatar / HunyuanVideo 1.5** (Tencent) | ciało, emocje, wiele osób | Tencent Community | **❌ licencja wyłącza UE** | – | – | **odpada** |
| **MuseTalk 1.5, LatentSync 1.6** | lip-sync na gotowym wideo | MIT / OpenRAIL++ | ✅ | 4–18 GB | – | do **poprawy ust** po generacji ruchu |
| **Wan2.2-Animate-2** | przenosi ruch z nagrania na postać | Apache | ✅ | duży | – | opcja hybrydowa: ktoś odgrywa gest kamerką, potem MuseTalk lub LatentSync dla ust |
| **Ovi, MOVA, daVinci-MagiHuman** | wspólne audio+wideo | Apache | ✅ | duży | `fal-ai/ovi` | generują **własny** głos, nie biorą WAV z ElevenLabs |
| Wan 2.5 / 2.6 / 3.0 | – | **wag nie ma** (tylko API) | – | – | – | nie są otwarte |

Zamknięte modele na fal, dla porównania cen: Kling AI Avatar v2 std / pro 0,056 / 0,115 $/s, OmniHuman v2 0,105 $/s, MiniMax H3 Max lip-sync 0,05 $/s, HeyGen Avatar IV i V przez fal 0,10 $/s.

### Top kandydaci do zastąpienia HeyGena i koszt odcinka 35 s (1 podejście)

| Kandydat | Hosted | Self-host (RunPod) | Wysiłek | Uwagi |
|---|---|---|---|---|
| **Wan2.2-S2V** | fal 580p: **5,25 $**; 720p: 7 $ | H100/H200, ok. 5–10 $, wolny (ok. 30 min / 10 s) | średni (fal); duży (self-host) | jedyny open model z ruchem rąk jak Avatar V; fal go wycofuje |
| **InfiniteTalk** | WaveSpeed ok. **1–2 $** | H100, ok. 2–3 $ | średni (ComfyUI) | Apache, dojrzały ekosystem; ciało sztywniejsze |
| **LongCat-Avatar 1.5** | fal 480p: **5,25 $** (720p: 21 $) | H200, ok. 5–6 $ | średni | MIT, dialog 2 osób; trzeba pilnować tożsamości |
| **EchoMimicV3-Flash** | fal **7 $** | RTX 4090 / L40S, ok. 1–2 $ | średni | najtańszy self-host |
| **LTX-2.3 A2V** | fal **3,50 $** | <1 $ | niski | odrzucony po teście (brak ust) |
| *dla porównania:* HeyGen Avatar 6 Turbo | **1,4 $** | – | zero (już zintegrowane) | 1080p, stabilna twarz |

Do kosztu open-source trzeba doliczyć upscale 480/576p → 1080p (np. przez fal) i poprawę ust (MuseTalk / LatentSync), czyli kolejne kroki i koszty. **Ze względu na koszt open-source nie ma dziś sensu**. Ma sens jako niezależność od dostawcy i do ujęć gestowych (Wan-S2V), ewentualnie przy self-hoście na dużą skalę.

**Prywatność:** postacie są fikcyjne, więc wejście nie zawiera danych osobowych. Przy prawdziwych osobach fal, Replicate i HeyGen oznaczają przetwarzanie poza UE, co trzeba uwzględnić zgodnie z CLAUDE.md (RODO).

## Następne kroki (propozycja)

1. W panelu fu: `generate_avatar_video` nie wystawia `engine` ani `motion_prompt`. Do czasu rozbudowy narzędzia ujęcia serii renderujemy przez `heygen_api_request` → `POST /v3/videos` z body jak niżej, potem `get_heygen_video` ze `store=true`.
2. Do biblii produkcji dopisać przy każdej kwestii scenariusza kolumnę „motion_prompt” (spojrzenie, brwi, gest, postawa).
3. Kadry wzorcowe, w których postać ma gestykulować, generować z dłońmi wolnymi, nie opartymi o przedmiot.
4. Opcjonalnie przetestować Avatar V z prompt-lookiem w osobnej, testowej grupie, czy odblokowuje `motion_prompt`.

```json
{
  "type": "avatar",
  "avatar_id": "bcfed60999bda078a1a57f273118066b",
  "audio_url": "https://.../u3_basia.mp3",
  "engine": { "type": "heygen-avatar-6-turbo" },
  "motion_prompt": "She looks over the top of her glasses with dry irony, raises her eyebrows, tilts her head slightly and taps the printer twice with her right hand while speaking. Shoulders and torso move naturally.",
  "aspect_ratio": "9:16",
  "resolution": "1080p"
}
```

## ID renderów testowych (HeyGen, linki wygasają ok. 7 dni; kopie są w repo)

| Wersja | video_id |
|---|---|
| avatar_iv + motion | `ff68b885830ea412d9b76c1b6f78a0b1` |
| avatar-6 + motion | `78d2d11a71c2dd68986b8c4e7cf4d4d5` |
| avatar-6-turbo + motion | `57dfe62579d062c44df6feac9b57a2e8` |
| avatar_v | `1da5747f58829c2888ed6aceceeee4f2` |
| avatar-6 Model API | `b9a3302ec1d443efb2bfe007ebf954b2` |

## Źródła

- **HeyGen:**
  - https://developers.heygen.com/models.md
  - https://developers.heygen.com/reference/create-video.md
  - https://developers.heygen.com/docs/models/avatar-6.md
  - https://developers.heygen.com/avatar-v.md
  - https://developers.heygen.com/avatar-iv.md
  - https://developers.heygen.com/cinematic-avatar.md
  - https://developers.heygen.com/docs/avatar-from-video.md
  - https://developers.heygen.com/docs/avatar-consent.md
  - https://developers.heygen.com/docs/avatar-from-prompt.md
  - https://developers.heygen.com/endpoint-version-comparison.md
  - https://help.heygen.com/en/articles/10060327-heygen-api-pricing-explained
- **Open-source:**
  - https://github.com/meituan-longcat/LongCat-Video
  - https://huggingface.co/MeiGen-AI/InfiniteTalk
  - https://huggingface.co/Wan-AI/Wan2.2-S2V-14B
  - https://huggingface.co/BadToBest/EchoMimicV3
  - https://huggingface.co/Lightricks/LTX-2.5-Pre-Trained
  - https://github.com/Alibaba-Quark/LiveAvatar
  - https://huggingface.co/Skywork/SkyReels-V3-A2V-19B
  - https://raw.githubusercontent.com/Tencent-Hunyuan/HunyuanVideo-Avatar/main/LICENSE
  - https://raw.githubusercontent.com/jixiaozhong/Sonic/main/LICENSE
  - https://tight.studio/blog/open-source-talking-avatar-models/ (niezależny test, 08.2026)
  - https://www.runpod.io/pricing
- **Ceny fal:** z konektora fal (`get_pricing`) z 12.11.2026.
