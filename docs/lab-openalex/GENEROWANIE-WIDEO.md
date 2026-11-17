# Generowanie obrazów i wideo na otwartych modelach — stan wiedzy, 17.11.2026

Jak skutecznie robić materiały wideo na **otwartych, bezpłatnych modelach**
(wagi do pobrania, render na własnym lub wynajętym GPU): jakie workflow, co
ludzie przetestowali, jakie wyniki podają, jak używać agentów, powtórek
i poprawek. Pisane pod `ai-clip` (finyou): LTX-2.5 w ComfyUI na RTX 5090 32 GB
z SaladCloud, ujęcia z klatek kluczowych, gadające głowy po polsku.

Źródła: 100 prac z OpenAlex w trzech rejestrach, wszystkie potwierdzone
weryfikatorem (`potwierdzona` 100/100):

| Rejestr | Prefiks | Prac | Zakres |
|---|---|---|---|
| [`zrodla/media-modele.jsonl`](zrodla/media-modele.jsonl) | M | 35 | modele bazowe, klatki i kamera, spójność postaci, mowa i usta, obraz na klatki, przyspieszanie na 1 GPU |
| [`zrodla/media-agenci.jsonl`](zrodla/media-agenci.jsonl) | N | 35 | przepisywanie promptu, agent-reżyser, pętla krytyka, skalowanie w czasie generacji, dostrajanie preferencji, praktyka twórców |
| [`zrodla/media-ocena.jsonl`](zrodla/media-ocena.jsonl) | Q | 30 | benchmarki, modele nagrody, VLM jako sędzia, artefakty, usta i tożsamość, ocena ludzka |

Ta sama praca występuje dwa razy: VideoReward to N027 i Q010.

**Pewność** jak w [STAN-WIEDZY.md](STAN-WIEDZY.md): **mocne** — kilka
niezależnych prac, w tym recenzowane; **średnie** — jedna dobra praca albo
kilka preprintów; **słabe** — pojedynczy świeży preprint. Liczby są zawsze
„według autorów”, na ich modelach i zbiorach. Kluczowe liczby sprawdziłem
w pełnych streszczeniach OpenAlex. Około połowa prac to preprinty, a prawie
żadna nie mierzy kosztu względem zysku właśnie na otwartych modelach wideo.
Liczby z tych prac to hipotezy do sprawdzenia u nas, nie gotowe ustawienia.

---

## Najkrócej: 10 rzeczy, które z tego wynikają

1. **Moc obliczeniową wydawaj na ziarna, nie na kroki.** Dokładanie kroków
   odszumiania przestaje pomagać po kilkudziesięciu, a przeszukiwanie szumu
   z oceniaczem dalej poprawia wynik (N022, N024). → **mocne**
2. **Ile ziaren opłaca się renderować, zależy od jakości bramki, nie od
   modelu.** Best-of-N jest ograniczone błędami oceniacza (N026). Zanim
   zwiększysz N, zmierz, ile złych klipów bramka przepuszcza. → **średnie**
3. **Najpierw tani podgląd wielu ziaren, potem pełny render kilku najlepszych.**
   Dodatkowe próby kieruj do ujęć, które wypadły słabo (N023, N025, N013).
   → **średnie**
4. **Przepisywanie promptu przez LLM pomaga, ale tylko dopasowane do stylu
   podpisów, na których uczono model** (N001–N006). Do tego trzeba pilnować,
   żeby przepisany prompt nie odpłynął od scenariusza (N007). → **mocne**
5. **Agent-reżyser zyskuje głównie przed renderem:** plan, scenariusz pod
   możliwości modelu, spójność postaci. Ten etap kosztuje tokeny, nie godziny
   GPU (N008–N013). → **średnie**
6. **Poprawiaj tylko zepsuty fragment i najlepiej na etapie klatki kluczowej**
   (N015, N019, M027). Kolejne poprawki krok po kroku wygrywają z losowaniem
   nowych prób przy tym samym budżecie (N018). → **średnie**
7. **VLM (model językowo-wizualny) nadaje się do oceny treści, nie do
   automatycznego odrzucania z powodu jakości czy ruchu ust.** GPT-4o zgadza
   się z głosem ludzi w 49,19% (Q017). Wiele modeli jest bliskich losowości
   przy wykrywaniu artefaktów (Q021). Sędziowie omni słabo oceniają
   synchronizację dźwięku z obrazem (N021). → **mocne**
8. **Do bramki dodaj gotowe, otwarte miary**, zamiast samemu wymyślać progi:
   wymiary VBench, oceniacz nagrody wideo do rankingu ziaren, ArcFace dla
   tożsamości, LSE i AV-HuBERT dla ust (Q001, Q002, Q009, Q010, Q023, Q025,
   Q027). → **mocne**
9. **Wynik miary ust w pliku nie mówi, co zobaczy widz.** LSE nie korelował
   z przesunięciem dźwięku zmierzonym na wyjściu (r od −0,066 do +0,083).
   Dźwięk spóźniał się o 79–211 ms w każdym badanym układzie (Q026).
   → **słabe**, ale tanie do sprawdzenia
10. **Na jednej karcie najwięcej dają gotowe przyspieszenia:** 8-bitowa uwaga,
    4-bitowa kwantyzacja modelu obrazowego, cache kroków (M033, M034, M030).
    → **średnie/mocne**

---

## A. Modele i workflow

### A1. Które otwarte modele — **mocne** (raporty techniczne, wysoko cytowane)

- **LTX-Video / LTX-2** (M002, M001). VAE kompresuje obraz 1:192 (32×32×8
  pikseli na token). Stąd wymiary i długości „skaczą” u nas w schodkach.
  Według autorów pierwsza wersja renderowała 5 s w 768×512 w 2 s na H100.
  LTX-2 ma osobne strumienie wideo (14B) i audio (5B) z wielojęzycznym
  koderem tekstu i generuje mowę razem z obrazem.
- **Wan** (M003): modele 1,3B i 14B, do ośmiu zadań (I2V, edycja,
  personalizacja). Wersja 1,3B potrzebuje 8,19 GB VRAM. Wszystko otwarte.
- **HunyuanVideo 1.5** (M004): 8,3B, celuje w karty konsumenckie.
  **Licencja Tencent nie obowiązuje w UE** (patrz METODYKA ai-clip) — tylko
  jako punkt odniesienia.
- **CogVideoX** (M006) i **SkyReels-V2** (M007, długie ujęcia „filmowe”) to
  dalsze punkty odniesienia. Stable Video Diffusion (M008) pokazało przepis
  na trening w trzech etapach i ruch kamery przez LoRA.

**Dla nas:** LTX-2.5 zostaje głównym modelem, bo jako jedyny daje dźwięk
i mowę w jednym przebiegu za ok. 0,005 USD na ujęcie (zmierzone u nas,
METODYKA). Wan jest naturalnym drugim modelem do porównań. Jego ekosystem
(InfiniteTalk, FantasyTalking, VACE, Phantom) to najszerszy zestaw narzędzi
do gadających głów i spójności postaci.

### A2. Klatki kluczowe i kamera — **średnie**

- Jawne warunki **dla każdej klatki** między dwiema klatkami kluczowymi
  stabilizują ujęcia „pierwsza–ostatnia klatka”, zwłaszcza przy dużym ruchu
  (FCVG, CVPR 2025, M009). Autorzy dopasowują linie z obu klatek
  i interpolują je klatka po klatce.
- Sterowanie kamerą działa jako nakładka na zamrożony model (CameraCtrl,
  M010). Można też przerenderować istniejące wideo po nowej trajektorii
  (ReCamMaster, M011).
- **VACE** (M012): jedno wejście na referencję, maskę i wideo. Jeden model
  robi wtedy referencja→wideo, wideo→wideo i edycję fragmentu.

**Dla nas:** to potwierdza kierunek `klatki.mjs` (test B: klatka końcowa
0,93–0,98, zmierzone u nas). Następny krok z literatury: przy dużym ruchu
między klatkami podać model **klatkę pośrednią** albo prowadnice dla każdej
klatki, zamiast liczyć, że model sam „domorfuje”.

### A3. Ta sama postać w wielu ujęciach — **średnie**

- **Bez trenowania LoRA na każdą osobę:** Phantom (M013, ICCV) i Concat-ID
  (M014) trzymają tożsamość z obrazu referencyjnego. Concat-ID ostrzega
  o kompromisie: im mocniej zablokowana tożsamość, tym mniej swobody mimiki.
- **Wiele ujęć naraz:** Long Context Tuning (M015) rozciąga uwagę na
  wszystkie ujęcia sceny. HoloCine (M016) generuje całą scenę wielu ujęć
  w jednym przebiegu.
- Dla obrazu klasyką jest IP-Adapter (M017): adapter 22M parametrów,
  działa razem z tekstem.

**Dla nas:** u nas tożsamość trzyma klatka kluczowa z FLUX/edycji. Literatura
podpowiada dwa usprawnienia. Pierwsze: generować klatki wszystkich ujęć
z tej samej referencji modelem edycyjnym (FLUX.1 Kontext dobrze trzyma
postać przez wiele kolejnych edycji, M027). Drugie: mierzyć dryf tożsamości
(C4).

### A4. Mowa i usta — **średnie**, polski to luka

- Najmocniejsze otwarte drogi do gadającej głowy:
  - **InfiniteTalk** (M020): dubbing z rzadkich klatek. Zachowuje klatki
    kluczowe, gesty i drogę kamery, a ruch dorabia pod nowy dźwięk, w
    kawałkach dowolnej długości.
  - **FantasyTalking** (M019, ACM MM): poprawia usta klatka po klatce maską
    ust i pozwala sterować tym, jak mocno ruszają się głowa i ciało.
  - **Hallo3** (M021), **OmniHuman-1** (M018, wagi niejasne), **MuseTalk**
    (M023, 30 FPS w 256×256 na V100).
- **LatentSync** (M022): modele warunkowane dźwiękiem uczą się skrótów
  z obrazu i ignorują dźwięk. Nadzór SyncNet to naprawia (dokładność
  StableSyncNet 91% → 94% na HDTF). Nadaje się do **poprawiania samych ust**
  w gotowym klipie.
- **MultiTalk** (M025, Interspeech): dokładność ust spada dla języków słabo
  obecnych w danych. Zbiór 420 h w 20 językach wyraźnie poprawia wynik. To
  jedyna praca o wielojęzyczności, jaką znalazłem. Polskiego wprost nie
  bada nikt.

**Dla nas:** zgadza się z testem D (sync od −0,38 do 0,62, zależny od ziarna
i postaci; zmierzone u nas). Workflow z literatury: **wideo z LTX z klatkami
kluczowymi → osobny przebieg naprawy ust** (LatentSync albo InfiniteTalk na
Wan) tylko dla klipów, które bramka ust odrzuciła. To tańsze niż renderowanie
kolejnych ziaren całego ujęcia.

### A5. Obraz na klatki kluczowe — **mocne**

FLUX/SD3 (M026), SDXL (M028), edycja poleceniem: InstructPix2Pix (M029)
i FLUX.1 Kontext (M027). **Licencje:** otwarte wagi FLUX.1 [dev] i Kontext
[dev] są według mojej wiedzy niekomercyjne, a licencje Stability się
zmieniały. Przed użyciem w produkcji trzeba to sprawdzić na kartach modeli
(streszczenia tego nie mówią).

### A6. Tanio na jednej karcie — **średnie/mocne**

| Metoda | Według autorów | Uwagi |
|---|---|---|
| SageAttention (M033) | ok. 2,1× FlashAttention2, prawie bez straty | najprostsze do włączenia w ComfyUI |
| SVDQuant + Nunchaku (M034) | FLUX 12B: 3,5× mniej pamięci, 3,1× szybciej niż W4A16 **na RTX 5090** (NVFP4), LoRA bez ponownej kwantyzacji | FLUX i LTX mieszczą się razem na 32 GB |
| TeaCache (M030) | do 4,41× przy −0,07% VBench | bez treningu, cache kroków |
| Sliding Tile Attention (M031) | uwaga to 800 z 945 s klipu 720p; 945 → 685 s bez treningu, 268 s po dostrojeniu | dla HunyuanVideo |
| Sparse VideoGen (M032) | 2,28–2,33× bez treningu | CogVideoX, HunyuanVideo |
| Self Forcing (M035) | strumieniowanie w czasie rzeczywistym na 1 GPU | autoregresja, kierunek na później |

**Dla nas:** w teście C koszt klipu to głównie stały narzut ok. 10 s, a nie
długość (zmierzone u nas). Przyspieszenia uwagi pomogą więc najbardziej przy
dłuższych i większych ujęciach. Na krótkie elementy lepiej działa wsadowanie.

---

## B. Agenci, powtórki i poprawki

### B1. Przepisywanie promptu — **mocne**

- Promptist (N001): model językowy uczony najpierw na ręcznych promptach,
  potem RL. Bije ręczną inżynierię promptów na Stable Diffusion, najbardziej
  na nietypowych promptach.
- OPT2I (N002): LLM w pętli poprawia prompt pod miarę zgodności tekstu
  z obrazem. Do +24,9% DSG bez treningu i bez pogorszenia FID.
- Wideo:
  - **RAPO / RAPO++** (N003, N004): przepisują prompt do rozkładu promptów
    treningowych modelu. Wersja ++ dodaje pętlę z oceną zgodności, ruchu
    i spójności i zyskuje na pięciu modelach T2V.
  - **Prompt-A-Video** (N006): uczy przepisywacza osobno pod każdy model
    wideo.
- **Ryzyko:** przepisany prompt odpływa znaczeniem od zamiaru, a sam szum
  (ziarno) zmienia wynik tak mocno jak prompt (POS, N007).
- Praktyka ludzi: z iteracją prompty zbiegają się do stylu, który lubi dany
  model (N035). Doświadczeni użytkownicy budują szablony ze slotami
  i słownik pojęć (N031, N033).

**Dla nas:** METODYKA ma już szablony promptów. Literatura każe zrobić dwie
rzeczy. Pierwsza: prompt dla LTX pisać po angielsku, długo, w stylu jego
podpisów treningowych (opis kadru, ruchu, światła, kamery). Polski zostaje
tylko w kwestii mówionej. Druga: każdy przepisany prompt sprawdzać ze
scenariuszem (lista faktów: kto, co, gdzie). Z czasem z promptów, które
przeszły bramkę, powstanie zbiór do douczenia małego przepisywacza.
Zastrzeżenie z testu A: przy modelu destylowanym (CFG 1) opisem w prompcie
nie uspokoiliśmy mimiki. Prompt steruje treścią lepiej niż drobną grą
aktorską.

### B2. Agent-reżyser — **średnie**

| Praca | Co robi | Według autorów |
|---|---|---|
| VideoDirectorGPT (N008) | LLM rozpisuje „plan wideo”: sceny, obiekty z układem, grupy spójności | lepsza spójność wielu scen |
| DreamFactory (N009) | wieloagentowy, iteracja klatek kluczowych | miary: odległość twarzy i stylu między scenami |
| FilmAgent (N010) | reżyser, scenarzysta, aktor, operator poprawiają się nawzajem | 3,98/5 w ocenie ludzi; zespół GPT-4o lepszy niż pojedynczy o1 (sceny 3D, nie dyfuzja) |
| VideoGen-of-Thought (N011) | szkic ujęć → specyfikacja w 5 domenach z samosprawdzeniem → tokeny tożsamości | +20,4% spójności twarzy, +17,4% stylu, 10× mniej ręcznych poprawek |
| MAViS (N012) | pętla „zbadaj–sprawdź–popraw” na każdym etapie; scenariusz pisany pod możliwości generatora | — |
| AniMaker (N013) | wielu kandydatów na ujęcie, wybór przeszukiwaniem drzewa (MCTS), ocena w kontekście sąsiednich ujęć | jeden słaby klip psuje całość |

**Dla nas:** najtańsza i najbardziej sprawdzona część to **planowanie przed
renderem**. Scenariusz pisany pod to, co model umie: krótkie elementy, mało
osób w kadrze, ruch kamery z klatek. Do tego karta postaci i spójności dla
każdego ujęcia. AniMaker pokazuje też, że ujęcie trzeba oceniać razem
z sąsiednimi (ciągłość), a nie tylko osobno.

### B3. Pętla krytyka i poprawka fragmentu — **średnie**

- Idea2Img (N014), SLD (N015), GenArtist (N016), Maestro (N017): VLM ocenia,
  planuje poprawkę i edytuje. SLD naprawia większość błędnych obrazów
  w liczeniu obiektów, atrybutach i relacjach przestrzennych.
- **Poprawki krok po kroku kontra losowanie przy tym samym budżecie** (N018):
  +16,9% (ConceptMix), +13,8% (T2I-CompBench), +12,5% (Visual Jenga),
  a ludzie woleli metodę w 58,7% do 41,3%.
- **VideoRepair** (N019): automatycznie generowane pytania wskazują źle
  wygenerowany obszar, a model przerabia tylko ten obszar. Poprawne obiekty
  zostają nietknięte.

**Dla nas:** poprawki robić na **klatce kluczowej** (edycja obrazu kosztuje
sekundy), a wideo renderować dopiero z poprawionej klatki. Przy wideo
najpierw spróbować naprawy fragmentu (usta, maska), a całe ujęcie losować od
nowa dopiero na końcu.

### B4. Ile ziaren i jak wybierać — **średnie/mocne**

- N022 i N024: przeszukiwanie szumu z oceniaczem skaluje się lepiej niż
  kroki. Wyszukiwanie typu bandyta: do +164% nad punktami odniesienia.
- Video-T1 (N023): więcej obliczeń w czasie generacji konsekwentnie poprawia
  wideo. Tańszy wariant rozwija i przycina gałęzie klatka po klatce.
- ScalingNoise (N025): kandydaci oceniani na **podglądzie z jednego kroku
  odszumiania**, zanim zrobi się pełny render.
- **ROC-n-reroll** (N026): sufit zysku wyznacza krzywa ROC oceniacza. Przy
  stałym budżecie lepiej działa „renderuj, aż bramka przyjmie” niż
  „wyrenderuj N i wybierz najlepszy”. Zysku z małego budżetu nie da się
  przenieść na duży.

**Dla nas:** dziś renderujemy 3–4 ziarna na ujęcie mówione (test D). Zmiana
z literatury: **sekwencyjnie z bramką** — ziarno 1, bramka, ewentualnie
ziarno 2 i tak dalej, z limitem — zamiast stałego N. Dodatkowe próby idą do
ujęć, które odpadają. Najpierw trzeba jednak wiedzieć, ile złych klipów
bramka przepuszcza (C5).

### B5. Douczanie preferencji — **średnie**, na później

VideoReward + Flow-DPO dla modeli przepływowych, takich jak LTX (N027).
Dalej VideoDPO (N028), VADER (N029) i DenseDPO (N030). Ważne z DenseDPO:
oceny całego klipu ciągną w stronę **statycznych** klipów, a oceny krótkich
odcinków poprawiają ruch przy 1/3 etykiet. **Dla nas:** pary
„przyjęte / odrzucone ziarno tego samego ujęcia” zbierają się same przy
bramce. To darmowy zbiór do późniejszego LoRA-DPO. Przy ocenie ludzi trzeba
uważać na skrzywienie w stronę bezruchu.

### B6. Jak pracują twórcy — **średnie**

Wywiady i badania (N031–N034): praca to cykl „napisz, oceń, popraw prompt”.
Narzędzia T2V poszerzają zakres freelancerów audiowizualnych. Główne bariery
to dopasowanie wyniku do zamiaru i wiedza o promptowaniu. Nic tu nie
przeczy naszej metodyce. To raczej argument za kartą ujęcia i szablonami.

---

## C. Ocena: jak wiedzieć, że klip jest dobry

### C1. Gotowe wymiary zamiast własnych progów — **mocne**

- **VBench** (Q001): 16 rozdzielnych wymiarów, m.in. spójność obiektu,
  migotanie, płynność ruchu, ilość ruchu, z otwartymi oceniaczami
  i ocenami ludzi. **VBench++** (Q002) dodaje obraz→wideo, czyli nasz
  przypadek z klatkami. VBench-2.0 (Q003) dodaje wierność człowieka, fizykę
  i zdrowy rozsądek.
- EvalCrafter (Q004): 17 miar i **wagi dopasowane do ocen ludzi**, lepsze
  niż zwykła średnia.
- DEVIL (Q006): ocena ruchu względem zamierzonego poziomu, korelacja
  Pearsona z ludźmi powyżej 90%.
- Miara bez GPU: sam FFmpeg mierzy zamrożenia, migotanie, drganie
  i powtórzone klatki (Q022). Świeży preprint bez cytowań.

**Dla nas:** naszą miarę „ruch” (średnia różnica klatek) warto zastąpić
albo uzupełnić miarami VBench: płynnością, migotaniem i ilością ruchu.
Do tego DEVIL, bo mierzy ruch **względem zamierzonego**, a my chcemy
spokojnej mimiki, nie bezruchu.

### C2. Oceniacze nagrody do rankingu ziaren — **średnie**

- VisionReward (Q009): o 17,2% trafniej przewiduje preferencje ludzi niż
  VideoScore.
- VideoReward (Q010/N027): pisany pod modele przepływowe.
- VideoScore2 (Q008): 44,35 w swojej dziedzinie i 50,37 poza nią. Za mało
  na twarde „przyjmij/odrzuć”, wystarczy do kolejności.
- Dla obrazów (klatki kluczowe): ImageReward (Q011), PickScore (Q012),
  **VQAScore** (Q016). Ranking 3–9 kandydatów według VQAScore jest
  2–3× skuteczniejszy niż według PickScore, HPSv2 czy ImageReward.
- Q-Align (Q013): oceny słowne zamiast liczb, otwarte wagi.
- Ogólne modele jakości wideo nie widzą zniekształceń typowych dla AI
  (AIGV-Assessor, Q014).

**Dla nas:** oceniacz nagrody **porządkuje** ziarna, a twarde progi zostają
na miarach technicznych (dźwięk, klatka końcowa, usta, tożsamość). VQAScore
do wyboru klatki kluczowej spośród kilku wariantów FLUX.

### C3. VLM jako sędzia — **mocne** (że jest zawodny)

- Q015: porównując pary, VLM zbliża się do ludzi, ale oceny punktowe
  i rankingi mocno od nich odbiegają.
- Q017: najlepszy GPT-4o zgadza się z głosem ludzi w 49,19%, otwarte modele
  wypadają gorzej.
- Q021: 19 modeli przy wykrywaniu artefaktów, wiele bliskich losowości.
- Q018: VLM pomijają jedną modalność i zmieniają werdykt pod wpływem
  nieistotnych zmian.
- N020: małe wyspecjalizowane oceniacze biją otwarte VLM w zgodności
  i jakości. VLM są trafniejsze, gdy dostają skalę słowną niż liczbową.

**Dla nas:** jeśli wprowadzimy krytyka VLM (EXP-06 w METODYCE), to tylko
**w parach**, ze skalą słowną, do pytań o treść („czy w kadrze jest jedna
osoba”, „czy jest laptop”). Usta, migotanie i artefakty zostają przy miarach
wyspecjalizowanych.

### C4. Usta i tożsamość — **średnie**

- Standard to LSE-D/LSE-C z SyncNet (Wav2Lip, Q023). AV-HuBERT daje drugi,
  niezależny sygnał (Q025).
- SyncNet nie był projektowany do wielu drobnych rozjazdów, jakie powstają
  przy dubbingu (Q024). LSE nie przewiduje rozjazdu, który zobaczy widz
  (Q026).
- **Tożsamość:** podobieństwo osadzeń twarzy ArcFace (Q027) między portretem
  referencyjnym a klatkami klipu, minimum i średnia. DreamFactory (N009)
  liczy to samo między ujęciami.

**Dla nas:** naszą zgrubną korelację ruchu z dźwiękiem zastąpić LSE-C/LSE-D
plus miarą AV-HuBERT. Dodać ArcFace jako bramkę dryfu postaci. Raz zmierzyć
rozjazd dźwięku po złożeniu odcinka (FFmpeg) i w odtwarzaczu docelowym
(telefon).

### C5. Ocena człowieka — **mocne**

- FID i FVD rozmijają się z ludźmi. FVD prawie nie reaguje na zepsucie
  czasu i **nagradza nieruchome klipy** (Q029, Q030). Do gadających głów
  się nie nadaje.
- **Porównania w parach**, a nie oceny w skali 1–10 (Q015, Q017). Spisany
  protokół: instrukcja, skala, liczba ocen na klip, test statystyczny (Q028).
  Oceny słowne z poziomami (Q013) i oznaczanie wad według taksonomii
  artefaktów GeneVA (Q020).
- Ile ocen: literatura w streszczeniach tego nie podaje. Praktyczna
  propozycja (nie z literatury): 2–3 oceniających na parę, 100–200 par na
  porównanie, raportować zgodność między oceniającymi. Przy jednym
  oceniającym (dziś) zostaje test znaków z przedziałem, jak w T1.

**Dla nas:** ślepe pary z T1-A to dobry wzorzec. Pozostaje dopisać pole
„rodzaj wady” w arkuszu, żeby z ocen dało się uczyć wag bramki (EvalCrafter,
Q004).

---

## Workflow ai-clip według literatury

Etapy, które dziś mamy, plus to, co literatura każe dodać (**nowe**):

1. **Scenariusz → karty ujęć** (LLM). **Nowe:** scenariusz pod możliwości
   modelu (MAViS), karta spójności postaci i scen (VideoDirectorGPT),
   samosprawdzenie planu (VGoT). Koszt: tokeny.
2. **Prompt.** **Nowe:** długi angielski opis w stylu podpisów LTX
   (RAPO/Prompt-A-Video), sprawdzany listą faktów ze scenariusza (POS).
3. **Klatki kluczowe** (FLUX / edycja). **Nowe:** 3–4 warianty, ranking
   VQAScore, poprawka edycją zamiast nowego losowania (SLD, Kontext),
   wszystkie ujęcia z jednej referencji postaci.
4. **Wideo** (LTX-2.5, klatka startowa i końcowa). **Nowe:** ziarna
   sekwencyjnie z bramką i limitem (N026), dodatkowe próby do trudnych
   ujęć (AniMaker). Przy dużym ruchu klatka pośrednia (FCVG).
5. **Bramka automatyczna.** Dziś mamy dźwięk, klatkę końcową, ruch i sync.
   **Nowe:** LSE + AV-HuBERT, ArcFace, VBench (migotanie, płynność, ilość
   ruchu), FFmpeg (zamrożenia i duplikaty), oceniacz nagrody do kolejności.
6. **Naprawa fragmentu** zamiast nowego ziarna: **nowe:** usta przez
   LatentSync / InfiniteTalk, przerobienie zaznaczonego obszaru (VideoRepair,
   VACE).
7. **Ocena człowieka** w ślepych parach z kodem wady. Wyniki wracają do wag
   bramki (EvalCrafter) i do zbioru par preferencji (DenseDPO, na później).

---

## Proponowane eksperymenty (do zgody na koszt)

Koszt liczony z T1: 104 klipy w 69 min = 0,69 USD na RTX 5090 (zmierzone
u nas).

| # | Eksperyment | Miara sukcesu | Koszt GPU |
|---|---|---|---|
| G1 | **Kalibracja bramki** na klipach T1 po ocenie człowieka: ile złych klipów bramka przepuszcza, a ile dobrych odrzuca; dodać LSE, ArcFace i miary VBench | czułość i swoistość względem człowieka, przedział | 0 (klipy już są; miary na CPU lub krótko na GPU) |
| G2 | **Sekwencyjne ziarna z bramką** kontra stałe 4 ziarna na ujęcie mówione | ten sam odsetek przyjętych przy mniejszej liczbie renderów | ok. 0,3–0,5 USD |
| G3 | **Naprawa ust** (LatentSync) dla klipów odrzuconych za sync, kontra nowe ziarna | LSE-C, ślepe pary | ok. 0,5 USD + ok. 1 h integracji |
| G4 | **Prompt w stylu LTX** (angielski, długi) kontra obecne szablony, na ujęciach niemych | ślepe pary, zgodność z listą faktów | ok. 0,3 USD |
| G5 | **SageAttention** w obrazie ComfyUI | czas renderu przy niezmienionych miarach | ok. 0,2 USD |
| G6 | **Polski mini-zbiór ust** (sz/cz/rz, nosówki): 20 kwestii × 4 postacie, dźwięk→wideo | LSE + ocena; luka w literaturze (M025) | ok. 0,5 USD |

Kolejność: G1 jest darmowy i warunkuje G2 (bez znanej jakości bramki
optymalizacja liczby ziaren jest ślepa). Potem G3 i G4, a G5 i G6 przy
okazji większej paczki.

## Czego literatura nie mówi

- Nikt nie mierzy synchronizacji ust **po polsku**. MultiTalk mówi tylko
  ogólnie, że słabo reprezentowane języki wypadają gorzej.
- Brak liczb typu „ile ziaren na ujęcie” dla otwartych modeli wideo:
  zależy od oceniacza i trzeba to zmierzyć u nas (G1, G2).
- Prace agentowe rzadko podają koszt. Wyniki FilmAgent dotyczą scen 3D,
  a nie modeli dyfuzyjnych.
- Licencje: streszczenia ich nie podają. Tabela licencji w METODYCE ai-clip
  zostaje źródłem rozstrzygającym, a FLUX [dev] i Kontext [dev] trzeba do
  niej dopisać po sprawdzeniu kart modeli.

## Radar

Tematy do dopisania w `radar.json` przy najbliższym przeglądzie:
„test-time scaling video diffusion”, „talking head lip sync multilingual”,
„video reward model human preference”, „first-last frame video
interpolation”, „prompt optimization text-to-video”.
