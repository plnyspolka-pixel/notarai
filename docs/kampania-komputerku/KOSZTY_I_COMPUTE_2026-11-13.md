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

## 3a. Wariant bez zakładania nowych kont (wszystko na rachunku AWS aplikacji)
RunPod/Modal są najtańsze, ale wymagają nowego konta z kartą. Ten sam efekt da się osiągnąć na koncie AWS,
które już płaci za Bedrock i ECS:
- **GPU:** `infra/notarai-gpu-komfy.yaml` – instancja spot `g6.xlarge` (L4 24 GB, ok. 0,3 USD/h we Frankfurcie;
  `g6e.xlarge` L40S 48 GB ok. 0,9 USD/h) z ComfyUI postawionym tym samym skryptem co na RunPod, dyskiem na modele,
  dostępem przez SSM i automatycznym stopem po `TtlMinutes`. Wymaga limitu (quota) na instancje G w eu-central-1 –
  nowe konta mają 0 vCPU i trzeba złożyć wniosek w Service Quotas (jednorazowo, zwykle 1–2 dni).
  Deploy: `aws cloudformation deploy --stack-name notarai-gpu-komfy --template-file infra/notarai-gpu-komfy.yaml
  --parameter-overrides VpcId=... SubnetId=... AllowedCidr=<IP>/32 --capabilities CAPABILITY_NAMED_IAM`.
  **Nieprzetestowane** – pierwszy deploy z `TtlMinutes=60`; po paczce `aws ec2 stop-instances`, na stałe `delete-stack`.
- **Lektor:** `narzedzia/tts_polly.py` – Amazon Polly, polskie głosy Ola (neural/generative) i Ewa; 12 mies. darmowe
  1 mln znaków neural miesięcznie, potem 16 USD/1M; Speech Marks dają visemy do rigu 2D bez osobnego rozpoznawania mowy.
  Jakość niżej niż ElevenLabs v3, wystarczająca na narrację i głosy epizodyczne; główna obsada zostaje w ElevenLabs.
- **Czego to nie załatwia:** klucz Bedrock w środowisku sesji nie daje uprawnień do EC2/Polly – do deployu potrzebna
  rola lub profil AWS operatora (ten sam, którym wdrażacie `notarai-aplikacja`).

## 4. Dieta tokenowa dla pracy koncepcyjnej (biblia, scenariusze, pakiety)
- Jedno zapytanie = jeden artefakt w JSON/Markdown, z biblią w cache (`odcinek_json.py` jest wzorem).
- Sonnet 4.6 do pierwszej wersji, Opus 4.6 z `effort: low` tylko do kontroli continuity; Haiku 4.5 do napisów,
  opisów, tagów. Cache jest per model - jedna seria zadań = jeden model.
- Sesje agentowe (Claude Code) tylko do projektowania systemu i zmian w kodzie; nie do pisania odcinków.
- Bedrock batch inference daje −50 % przy generowaniu całego sezonu naraz (wejście z S3, wynik do 24 h) -
  do wdrożenia, gdy produkcja ruszy seryjnie.

## 5. Koszt odcinka: do tej pory i po zmianach (na prawdziwych odcinkach sezonu 1)

Wyliczenie `narzedzia/sezon_koszty.py --markdown` na 8 szkicach `odcinki/EP01–EP08.json` rozpisanych
13.11.2026 (Sonnet 4.6, powtórki ×2). Odcinki wyszły dłuższe niż 35 s z koncepcji (78–187 s), więc kwoty są
wyższe niż w `README.md` §5, ale proporcje między torami takie same.

| Odcinek | Czas | Ujęć | obecny | tani hostowany | gpu_4090 | LLM (zmierzony) |
|---|---|---|---|---|---|---|
| EP01 „Poniedziałek, 8:57” | 187 s | 42 | 26,57 $ | 10,64 $ | 6,01 $ | 0,30 $ |
| EP02 „Proszę nie przy nim” | 111 s | 23 | 17,17 $ | 7,45 $ | 4,86 $ | 0,13 $ |
| EP03 „U nas się tak nie pisze” | 78 s | 19 | 11,33 $ | 5,20 $ | 3,52 $ | 0,21 $ |
| EP04 „Wczoraj tego nie było” | 102 s | 18 | 12,64 $ | 5,64 $ | 3,71 $ | 0,10 $ |
| EP05 „Przyszło mailem” | 96 s | 21 | 12,83 $ | 5,41 $ | 3,48 $ | 0,12 $ |
| EP06 „Kto ma tę sprawę?” | 112 s | 26 | 19,52 $ | 7,44 $ | 4,11 $ | 0,13 $ |
| EP07 „Pokaż mi to na komputerze” | 104 s | 22 | 15,05 $ | 5,29 $ | 2,54 $ | 0,11 $ |
| EP08 „To moja decyzja” | 106 s | 25 | 19,86 $ | 7,76 $ | 4,41 $ | 0,14 $ |
| **Sezon (8 odc.)** | | | **134,97 $** | **54,83 $** | **32,63 $** | **1,24 $** |
| Średnio na odcinek | | | 16,87 $ | 6,85 $ | 4,08 $ | 0,15 $ |

LLM: EP01 i EP03 zapisały cache (31 374 tokeny), pozostałe czytały go z cache (0,10–0,14 $ za odcinek).

### Do tej pory kontra teraz (średni odcinek sezonu, ok. 110 s)
| Składnik | Do tej pory | Teraz: tani hostowany | Teraz: własne GPU |
|---|---|---|---|
| Wideo, klatki, awatary, głos | 16,87 $ (ElevenLabs + Nano Banana Pro + HeyGen + Kling Avatar + Kling 2.5) | 6,85 $ | 4,08 $ (z czego 3,3 $ to zbliżenia HeyGen) |
| Rozpisanie odcinka (LLM) | 1–10 $ (sesja agentowa czytająca biblię od nowa) | 0,15 $ (zmierzone) | 0,15 $ (zmierzone) |
| Abonamenty na odcinek (przy 8 odc./mies.) | ~10 $ (ElevenLabs Creator 22 + HeyGen Creator 29 + Descript ~30 = ~81 $/mies.) | ~4 $ (Descript zostaje; HeyGen PAYG; ElevenLabs Starter 5 $ albo Chirp 0 $) | ~5 $ (jak obok + dysk sieciowy 7 $/mies.) |
| **Razem na odcinek** | **28–37 $** | **~11 $** | **~9 $** |
| **Sezon 8 odcinków** | **220–300 $** | **~90 $** | **~75 $** |

Najtańszy tor (własne GPU) zostawia w HeyGen Avatar 6 Turbo ok. 80 % kosztu wideo. Dalsze cięcie wymaga
zaliczenia polskiego lip-syncu przez EchoMimicV3 / InfiniteTalk (NA-12 pkt 4) - wtedy odcinek spada do ~2 $.
Nie liczymy czasu ludzi, który po tych zmianach staje się głównym kosztem.

Wygenerowane `odcinki/EP01–EP08.json` są **szkicami do autoryzacji** (pole `_produkcja` zawiera model, zużycie tokenów
i uwagi walidatora); nie zastępują scenariuszy kanonicznych z `marketing/komputerku/sezon-1/02_SCENARIUSZE/`.

## 6. Ryzyka
- Skrypty GPU powstały bez dostępu do karty - nazwy plików modeli i węzłów ComfyUI do potwierdzenia przy pierwszym
  uruchomieniu (`narzedzia/gpu/README.md`).
- Polski lip-sync w modelach audio-driven nikt nie zmierzył; decyzję podejmujemy po odsłuchu, nie po klatkach.
- Darmowe tiery znikają (Oracle zmniejszył ARM o połowę, Speechify kończy promocję 21.11.2026) - nie budować na nich SLA.
