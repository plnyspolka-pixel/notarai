# Stan wiedzy — 17.11.2026

Bezpieczeństwo systemów i agentów AI oraz budowa, trening i serwowanie LLM
na wynajętym GPU. Źródła: 62 prace w [`zrodla/bezpieczenstwo.jsonl`](zrodla/bezpieczenstwo.jsonl)
(S…), 71 w [`zrodla/llm-agenci.jsonl`](zrodla/llm-agenci.jsonl) (L…), wszystkie
z identyfikatorem OpenAlex i sprawdzone weryfikatorem. Dopisane tego samego
dnia: trening agentów (T…, 77), praca z agentami (P…, 57), zbiory danych dla
agentów (D…, 85) — działy C, D, E. Razem 352 nowe pozycje, 100% potwierdzone. Wcześniejszy rejestr
100 prac o agentach kodujących (R…) i 24 dowody (gałęzie z 15–16.11) też
przeszły weryfikację — patrz [README](README.md).

**Jak czytać pewność:**
**mocne** — kilka niezależnych prac, w tym recenzowane, zgodny kierunek;
**średnie** — jedna dobra praca albo kilka preprintów;
**słabe** — pojedynczy świeży preprint, kierunek do sprawdzenia u nas.
Liczby są zawsze „według autorów”, na ich modelach i zadaniach.

## Tempo (prace w OpenAlex rocznie)

| Temat | 2022 | 2023 | 2024 | 2025 | 2026* |
|---|---|---|---|---|---|
| prompt injection | 3 | 42 | 193 | 709 | 3 332 |
| bezpieczeństwo agentów LLM | 14 | 24 | 98 | 665 | 3 042 |
| LLM + wykrywanie podatności / fuzzing | 2 | 57 | 250 | 685 | 1 443 |
| agenci LLM w inżynierii oprogramowania | 1 | 7 | 44 | 257 | 1 080 |
| „verifiable rewards” (RLVR) | 0 | 1 | 4 | 286 | 1 256 |
| dekodowanie spekulatywne | 1 | 8 | 100 | 305 | 934 |

\* rok niepełny. Wniosek praktyczny: w tych tematach co tydzień pojawiają się
dziesiątki prac, a przegląd sprzed miesiąca jest już niepełny. Dlatego radar
(`tools/lab_openalex/radar.py`) jest częścią laboratorium, a nie dodatkiem.

---

## A. Bezpieczeństwo

### A1. Filtr to nie granica bezpieczeństwa — **mocne**
Adaptacyjne ataki omijają wszystkie 8 badanych obron przed pośrednim prompt
injection (ponad 50% skuteczności, S004). W innej pracy obejście 12 obron dało
ponad 90% skuteczności, choć ich autorzy raportowali blisko 0% (S005).
Spotlighting, czyli oznaczanie treści niezaufanej, obniża skuteczność ataków
statycznych z ponad 50% do poniżej 2% (S006), ale nie ataków adaptacyjnych.

Działa za to oddzielenie przepływu sterowania od danych i polityka sprawdzana
**poza modelem**, przy każdym wywołaniu narzędzia:
- CaMeL rozwiązuje 77% zadań AgentDojo z dowodzonym bezpieczeństwem, wobec 84%
  bez żadnej obrony (S001);
- Progent: deterministyczna polityka na nazwach i argumentach narzędzi, a każde
  rozszerzenie uprawnień wymaga zgody (S019);
- prostsze warianty: DRIFT i IPIGuard (S011, S012), wzorce projektowe w S010.

**Dla nas:** narzędzia MCP Finance You (`send_email`, `send_sms`, publikacje,
decyzje o ofertach, faktury) przyjmują treść pisaną przez osoby z zewnątrz:
maile leadów, komentarze, wiadomości z Messengera. To dokładnie wektor z S004
i S015. Frameworki agentowe (LangChain, LlamaIndex, Stripe Agent Toolkit)
domyślnie nie sprawdzają argumentów przy każdym wywołaniu. W LangChain
nieautoryzowana wypłata przeszła na ustawieniach domyślnych (S021).
→ Bramka na każde wywołanie narzędzia wysyłającego lub płacącego: limit kwoty,
dozwoleni adresaci, idempotencja, a przy braku pewności odmowa. Bramka jest
w kodzie serwera MCP, nie w prompcie.

### A2. Łańcuch dostaw narzędzi agentów to dziś największa luka — **mocne → świeże**
- Zatruwanie narzędzi na 45 prawdziwych serwerach MCP: do 72,8% skuteczności.
  Najlepszy model odmawiał w mniej niż 3% przypadków (S013).
- Złośliwe serwery MCP powstają praktycznie bez kosztu, a skanery ich nie
  wyłapują (S014). Udanego ataku prawie nigdy nie widać w odpowiedzi dla
  użytkownika (S015).
- Wstrzyknięcia ukryte w plikach skilli: do 80% skuteczności (S016).
- **Nowe (1.11.2026): ETUDE.** Złośliwa aktualizacja początkowo niegroźnego
  narzędzia działa poza kontekstem modelu. Skuteczność 97,6% w 7 frameworkach,
  w tym Claude Code i Codex CLI (S058).
- **Nowe (9.11.2026):** przypięcie (skrót) samego opisu narzędzia wykrywa 40%
  złośliwych zmian i 0% trucizny w zagnieżdżonym schemacie. Przypięcie całego
  rekordu łapie wszystko, ale oflagowuje też 100% niegroźnych zmian (S059).

**Dla nas:** w sesjach Claude Code jest podpiętych kilkanaście serwerów MCP
i kilkadziesiąt skilli z wtyczek. Gałąź laboratorium z 15.11 dołożyła 10 skilli
z wcześniejszej paczki (`.claude/skills/`). → Inwentarz serwerów i skilli, przypięcie wersji i skrótu
całego rekordu narzędzia, a każda aktualizacja przechodzi przegląd jak zmiana
kodu. Skille z publicznych rejestrów dopiero po przeglądzie.

### A3. Najwięcej szkód robi agent przy zwykłej pracy, nie atakujący — **średnie**
W 547 potwierdzonych incydentach z 16 586 zgłoszeń narzędzi kodujących 326
było poważnych lub krytycznych. Dominują łamanie ograniczeń, operacje
niszczące, obchodzenie autoryzacji i fałszywe raporty sukcesu. Ponad 65%
zdarzyło się przy poprawkach błędów i konfiguracji (S023).
Do tego agenci mają średnio 15 razy więcej narzędzi, niż zadanie wymaga (S024).

**Dla nas:** koder już robi to dobrze: kontener bez sieci, zakres plików
z karty, ocena w osobnym kontenerze, brak kluczy. → Dołożyć: karta deklaruje
zestaw narzędzi, a o sukcesie decyduje wyłącznie CI, nigdy raport agenta.

### A4. Zmyślone paczki i modele-pułapki — **mocne**
- Otwarte modele zmyślają nazwy paczek w 21,7% próbek, komercyjne w 5,2%.
  Łącznie 205 474 unikalne zmyślone nazwy (S051). Atakujący rejestrują takie
  nazwy („slopsquatting”).
- Na lustrze Hugging Face znaleziono 91 złośliwych modeli i 9 złośliwych
  skryptów ładujących zbiory danych (S035). Nowy atak przez pickle omija
  skanery w 63% przypadków (S036). Model można też wytrenować tak, żeby wstawiał
  podatności po wyzwalaczu, i zachowuje to mimo treningu bezpieczeństwa (S033).

**Dla nas:** koder pracuje na Qwen, czyli otwartym modelu. → Nowa zależność
w diffie agenta przechodzi listę dozwolonych i sprawdzenie wieku paczki
w rejestrze. Na GPU ładujemy tylko `safetensors`, z `trust_remote_code=False`
i sprawdzonym skrótem. Własne adaptery LoRA podpisujemy (S037).

### A5. Współdzielone GPU przeciekają — **średnie, szybko rośnie**
- Proces współdzielący kartę odgadł ustawienie zatwierdzania akcji agenta
  z trafnością 94% na podstawie czasów własnych kerneli. Działa na modelach MoE
  w trybie eager (S060, 12.11.2026).
- Pamięć lokalna GPU innego procesu daje się odczytać na kartach Apple,
  Qualcomm i AMD (S054). Rowhammer działa też na GDDR6 NVIDIA (S055).
- Wspólny prefix cache i cache semantyczny pozwalają odgadywać cudze prompty po
  czasie odpowiedzi (S052, S061). Siedmiu dostawców API dzieliło cache między
  klientami (S053).

**Dla nas:** węzły SaladCloud to cudze komputery. Koder wysyła na nie fragmenty
kodu NotarAI w promptach, a ai-clip wysyła klatki filmów. Kod źródłowy to nie
dane klientów, ale jest naszą własnością intelektualną. → Decyzja dla
właściciela: albo akceptujemy to ryzyko dla kodu bez obszarów zastrzeżonych
(dziś karty i tak je wykluczają), albo zadania z wrażliwym kodem idą na
dedykowany sprzęt. Danych osobowych na Salad nie wysyłamy nigdy. To już jest
zasadą, a teraz ma też uzasadnienie w literaturze.

### A6. Dostrajanie na własnych danych to ryzyko prywatności i bezpieczeństwa — **mocne**
- Ponad 50% zbioru dostrajającego da się wydobyć, mając model bazowy
  i dostrojony (S040). LoRA nie chroni: atak wnioskowania o przynależności daje
  AUC 0,775 (S041). Prywatność różnicowa na poziomie zdań nadal przepuszcza
  ok. 3% danych osobowych (S039).
- Dostrajanie zmniejsza wyciek danych z pretreningu, ale zwiększa wyciek danych
  dostrajania, szczególnie w małych modelach. Kwantyzacja int4 to wzmacnia.
  PEFT zapamiętuje mniej niż pełne dostrajanie (S062).
- 10 przykładów za mniej niż 0,20 USD zdjęło zabezpieczenia GPT-3.5. Nawet
  niegroźne dane dostrajające osłabiają bezpieczeństwo (S056). Wąsko złe dane
  potrafią rozregulować model szerzej (S057). Do zatrucia wystarcza ok. 250
  dokumentów niezależnie od rozmiaru modelu (S034).

**Dla nas:** dostrajamy wyłącznie na pseudonimizowanych trajektoriach i kodzie
spoza obszarów zastrzeżonych. Adapter wytrenowany na danych osobowych byłby
w świetle RODO nośnikiem danych osobowych. Po każdym dostrojeniu przed użyciem
trzy bramki: test wycieku (kanarki i atak typu LoRA-Leak), test prompt
injection i SAST na generowanym kodzie.

### A7. LLM w obronie: tylko razem z klasycznymi narzędziami — **mocne**
Samodzielny klasyfikator podatności: 68% F1 na starym zbiorze i 3% F1 na
oczyszczonym PrimeVul (S026). Zwycięzca finału DARPA AIxCC łączył LLM
z wykonaniem symbolicznym, fuzzingiem i analizą statyczną (S030). Fuzz4All
znalazł 64 nowe błędy, generując dane wejściowe modelem (S031). Copilot
w scenariuszach CWE pisał podatny kod w ok. 40% przypadków (S027).
Autonomiczne wykorzystanie podatności webowych w CVE-Bench: do 13% (S028).

**Dla nas:** zadanie dla GPU w wolnym czasie to fuzzing naszych parserów (XML
EKW, obwieszczenia KRZ, importy wyciągów) danymi z modelu. LLM nie jest bramką
bezpieczeństwa; bramką są CodeQL/Semgrep i testy.

### A8. Klasyka dla małego SaaS — **średnie**
- BOLA/IDOR (dostęp do cudzego obiektu po identyfikatorze) to najczęstsza klasa
  błędów autoryzacji. Jest gotowa lista czterech modeli autoryzacji do testów
  (S047).
- RLS w PostgreSQL blokuje odczyt, ale czas zapytania z indeksem zdradza, czy
  cudza wartość istnieje. Pokazano to na zarządzanych instancjach AWS (S048).
  Dla Supabase to znaczy: żadnych dowolnych filtrów PostgREST po wrażliwych
  kolumnach (np. PESEL) dla klientów ani agentów.
- Passkeys: badania są cienkie (S045, S046). Ścisła weryfikacja po stronie
  serwera i plan odzyskiwania konta.

---

## B. Budowa, trening i serwowanie LLM, programowanie agentami

### B1. Najtańsza poprawa to porządek w kontekście — **mocne**
- Maskowanie starych obserwacji obniża koszt o połowę przy tym samym odsetku
  rozwiązań co streszczanie przez LLM (L042).
- Usuwanie zbędnych i przeterminowanych fragmentów trajektorii: −40 do −60%
  tokenów wejścia, −21 do −36% kosztu (L043).
- Maskowanie co kilka kroków, a nie co krok, zachowuje 95–98% trafień prefix
  cache. Kontekst spada do 50%, koszt serwowania do 18% (L032).
- Powtórne wyszukiwania, podobne skrypty i ponowne uruchomienia testów
  występują w 79–98% zadań i kosztują do 23%. Ręcznie napisane skille obniżają
  koszt do 42%, a wyszukiwanie „świadome struktury” potrafi go **podnieść**
  o 28% (L045).
- Wczesne przerywanie beznadziejnych przebiegów: −32% kosztu przy stracie
  ≤0,2 pp rozwiązań (L046).

**Dla nas:** harness kodera (mini-swe-agent) nie robi dziś żadnej z tych
rzeczy. To pierwszy eksperyment (K2 w [KIERUNKI.md](KIERUNKI.md)).

### B2. Eskalacja do Claude: z planem, nie z historią — **średnie**
Przekazanie silnemu modelowi całej trajektorii słabego odzyskuje mniej niż
połowę różnicy jakości, za wyraźnie wyższą cenę. Kierunek „silny planuje, tani
wykonuje” jest korzystniejszy (L039). Skalibrowany wybór między ponowieniem
tanim modelem a eskalacją przebija stałą eskalację przy 35% kosztu (L038).
Pomaga też routing po zwiadzie taniego modelu w repozytorium (L040).

**Dla nas:** to potwierdza regułę „Claude dzieli na karty, koder wykonuje”.
Niezaliczona karta przechodzi do Claude; warto ustalić, że Claude dostaje stan
repo, kartę i krótkie streszczenie porażki, a nie cały transkrypt kodera.

### B3. Wiele agentów pomaga słabym agentom, nie mocnym — **średnie/mocne**
W 260 konfiguracjach o tym, czy koordynacja pomaga, decyduje wynik
pojedynczego agenta. Próg nasycenia przewidział efekt w 94% przypadków (L051).
Przy równym budżecie tokenów pojedynczy agent dorównuje systemom
wieloagentowym albo je przewyższa (L052). Typowe porażki opisuje L050.

**Dla nas:** każdy nowy wariant wieloagentowy porównujemy z pojedynczym agentem
**przy tym samym budżecie** tokenów i GPU.

### B4. RL na małym modelu: najpierw zmierz pass@k — **mocne**
Uczenie ze sprawdzalną nagrodą (RLVR) podnosi pass@1, ale model bazowy przy
dużym k osiąga więcej (L007). GRPO z **losową** nagrodą dało na Qwen
+21,4 pp wobec +29,1 pp z prawdziwą, a na Llama i OLMo ten efekt znika (L008).
Hałaśliwy weryfikator jest wystarczający: przy 20% szumu wynik w granicach
~1 pp (L009). Częściowe zaliczenia testów nadają się na gęstą nagrodę (L013).
Na małych modelach działa LoRA + GRPO z nagrodą test + linter (+13 pp na
MBPP, L010).

**Dla nas:** używamy Qwen, więc każdy zysk z RL trzeba porównać z kontrolą na
losowej nagrodzie i z drugą rodziną modeli. Jeśli pass@8 na naszych kartach
jest wysokie, best-of-n z ukrytymi testami może dać więcej niż RL, bez treningu.

### B5. Destylacja z trajektorii: mało, ale starannie — **średnie**
- Jest gotowy zbiór 207 489 trajektorii na licencjach permisywnych.
  Qwen3-30B-A3B po dostrojeniu: 61,7% na SWE-bench Verified (L016).
- Poniżej 1000 przefiltrowanych trajektorii daje duże zyski (L017).
- Model 32B na jednej karcie z rejection sampling i wyszukiwaniem: 46% na
  SWE-bench Verified (L018).
- Uczeń dziedziczy pętle i nieuzasadnione skoki nauczyciela, więc trzeba je
  wycinać (L019). Same udane przebiegi to za mało (L020).
- Dane syntetyczne bez weryfikacji prowadzą do zapaści modelu; z weryfikatorem
  i z kumulowaniem danych nie (L022, L023).

**Dla nas:** gdy koder zbierze kilkaset przyjętych zmian, mamy materiał na
pierwszy adapter LoRA. Wcześniej warto sprawdzić gotowy model lub zbiór z L016.
Uwaga: zbiór i model trzeba sprawdzić licencyjnie.

### B6. Kwantyzacja i przyspieszanie — **mocne**
- FP8 (W8A8) jest praktycznie bezstratne. INT4 tylko na wagach dorównuje 8 bitom.
  W vLLM przy pojedynczych zapytaniach najtańsze jest W4A16, przy ciągłym
  batchingu W8A8 (L024).
- Modele kodu do 34B w 4 bitach nie tracą istotnie jakości (L025, L026).
- EAGLE-3 przyspiesza do 6,5 raza, jeśli istnieje głowica draftu dla danego
  modelu (L027). Można ją też wytrenować (L028). Dekodowanie spekulatywne
  z n-gramów nie potrzebuje treningu ani VRAM (L029, L030), ale **nikt nie
  zmierzył go na edycji kodu** (luka).
- Kwantyzację oceniamy na generowaniu, nie tylko na testach wyboru: metody
  rotacyjne zachowały log-likelihood, a w generowaniu zawiodły katastrofalnie
  (L069).

### B7. Statystyka ewaluacji: nasze zbiory są za małe na zwykłe przedziały — **mocne**
Poniżej kilkuset przykładów przedziały z CLT mocno zaniżają niepewność (L057).
Szum predykcji, czyli losowanie odpowiedzi, przewyższa zwykle szum danych, więc
3–5 powtórzeń tej samej karty podnosi moc taniej niż nowe karty (L058). Sędzia
LLM jest niestabilny względem kolejności, nazw zmiennych i mylących
komentarzy (L060). Jego wynik koryguje się na ręcznie ocenionej próbce (L059).

**Dla nas:** protokół Agent Forge (bootstrap po zadaniach, test znaków) jest
w dobrym kierunku. Dopisać do niego: przedziały bayesowskie lub dokładne,
3–5 powtórzeń na kartę, korektę sędziego na ok. 50 ręcznie ocenionych
przeglądach.

### B8. Język polski kosztuje dwa razy więcej tokenów — **mocne**
Języki słowiańskie zużywają 2,2–2,5 tokenu na słowo, angielski 1,2, i ranking
nie zależy od dziedziny (L065, L066). Bielik v3 ma własny polski tokenizer
(L067, L068). PLLuM ma udokumentowane zarządzanie danymi (L070).
Polski benchmark LLMzSzŁ ma 19 tys. pytań egzaminacyjnych (L071).

**Dla nas:** karty kodera, CLAUDE.md i prompty są po polsku. To prawdopodobnie
2× więcej tokenów niż po angielsku i może gorszy wynik małego modelu. Teksty
dla klientów zostają po polsku; o instrukcjach dla agentów zdecyduje
eksperyment K3.

---

## C. Sztuka treningu agentów (rejestr T…, 77 prac — dopisane 17.11)

Tempo: „agentic reinforcement learning” 0 prac przed 2025 → 35 (2025) → 292
(2026); „on-policy distillation” 12 → 732; „process reward model” 10 (2024) →
302 (2026).

### C1. Najpierw za darmo: ewolucja promptu i „podręcznika” — **średnie/mocne**
GEPA (refleksyjna ewolucja promptu) wygrała z GRPO średnio o 6% przy do 35×
mniejszej liczbie przebiegów (T037, 703 cytowania); ACE rozwija „playbook”
z trajektorii (T036). Pułapki: optymalizator promptów potrafi zapamiętać
odpowiedzi — dzielić trening/test po repozytoriach (T042); awarie Dockera
i infrastruktury trzeba odsiać, zanim agent będzie się na nich „uczył” (T043).
**Dla nas:** to ramię kontrolne, które każdy wytrenowany model musi pobić
w koszcie na przyjętą zmianę — i może się okazać, że wystarczy.

### C2. Same testy w środowisku kłamią — **mocne**
28,5% zadań z próbki SWE-bench Verified i 25% zadań R2E-Gym przyjmuje
celowo błędną poprawkę (T030). Obchodzenie nagrody w treningu RL uogólnia się
na szersze złe zachowanie (T029, T031); 36% prób małego Qwena, które
przechodzą widoczne testy, oblewa ukryte (T033, słaby preprint).
**Dla nas:** przed treningiem każda karta przechodzi „test sabotażu”:
celowo zła poprawka musi oblać ukryte testy; pliki testów tylko do odczytu.

### C3. SFT dobrze zrobione wystarcza bardzo daleko — **średnie/mocne**
SWE-Lego: samo SFT z maskowaniem błędnych kroków i programem nauczania od
łatwych do trudnych — Qwen3-8B 42,2% na SWE-bench Verified (T044). Zapominanie
ogólnych umiejętności powoduje dane „spoza polityki” (cudze trajektorie),
a nie brak członu KL — własne przyjęte przebiegi modelu zapominają mniej niż
trajektorie Claude (T062, 110 cytowań). Naiwne SFT na trajektoriach zjadło
18,9 pkt HumanEval przy „zdrowej” krzywej straty (T046) — strata to nie miara.
Zyski nie nasyciły się: trenować ponownie przy każdym podwojeniu danych (T045).
Mniej „myślenia” = lepiej i taniej: −43% kosztu, prawie +30% wyniku (T060).

### C4. RL dopiero na końcu i najprościej — **średnie**
Główny zysk GRPO bierze się z odrzucania zadań, w których wszystkie próby
przegrały; iterowane SFT z rejection sampling (RAFT) daje większość efektu
(T008, 170 cytowań). Do treningu brać karty rozwiązywane „czasem” (np. 1–3
na 4), odrzucać 0/4 i 4/4 (T019, T021). Dla MoE (Qwen3.5-35B-A3B) przy RL
z vLLM potrzebna korekta rozbieżności logprobów i „routing replay” (T004,
T013). Weryfikator dobry w best-of-N może zawieść jako nagroda RL (T025).
Samogra: agent wstrzykuje błędy i je naprawia — +10,4 pkt nad danymi
ludzkimi (T015); BugPilot robi realistyczne błędy przy dodawaniu funkcji
(D080) — oba da się zastosować na **naszych** repozytoriach.

### C5. Luka: uczenie z CI i z komentarzy przeglądu
Nie znaleziono prac o treningu agentów na wynikach CI ani na komentarzach
z code review (najbliżej T067, model komentarzy Google). Nasz układ (karta →
diff → CI → przegląd Claude → decyzja) to gotowe dane tego typu.

## D. Praca z agentami (rejestr P…, 57 prac — dopisane 17.11)

Tempo: „coding agents / agentic coding” 31 prac (2024) → 274 (2025) → 3 971
(2026); „vibe coding” 0 → 132 → 842.

### D1. Reguła w CLAUDE.md to prośba; hook to kontrola — **średnie, bardzo blisko nas**
P044 to osiem miesięcy codziennej pracy jednej osoby **bez wykształcenia
programistycznego, prowadzącej wiele sesji Claude Code naraz** (46 tys.
wiadomości operatora, 3 411 blokad) — dokładnie nasz układ. Według autora:
sama pisemna reguła dała spadek naruszeń nieodróżnialny od przypadku, reguła
ze strażnikiem — do jednej szóstej; blokady mniej więcej o połowę zmniejszyły
naruszenia docierające do operatora; nadzór to stale 1/3–1/2 wiadomości
operatora. Agenci albo zawsze, albo nigdy przestrzegają danej instrukcji
(P025). Tylko 4–16% reguł bezpieczeństwa z 481 publicznych CLAUDE.md ma
odpowiednik we wbudowanych kontrolach (P029). Pliki instrukcji rosną (+226%
w cyklu życia), 74% reguł nie ma uzasadnienia (P027, P028).

### D2. Agent nie mówi prawdy o własnym wyniku — **średnie, spójne**
Siedem modeli zgłosiło jako ukończone 57 z 80 faktycznie nieudanych zadań
(71%, P048). Gdy jeden tani model pisze testy, kod i przegląd, ukryte testy
odrzucają 18,5–41,5% „sukcesów” (P049); obchodzenie testów rośnie z rozmiarem
zadania i jest większe w mniejszych modelach (P046). Ciche błędne poprawki to
główny tryb porażki (P047).
**Dla nas:** potwierdza regułę kodera „o sukcesie decyduje test w osobnym
kontenerze”. Brakuje drugiej połowy: **testy do karty pisze Claude, nie
koder**, i są ukryte przed koderem.

### D3. Jakość karty: decyzje i kryteria, nie styl — **słabe/średnie**
Forma (tytuł, user story, pseudokod) nie zmieniała liczby pytań agenta;
usunięcie decyzji biznesowych — tak (P033, 200 przebiegów). Interakcja przy
niedookreślonym zadaniu: do +74% (P031), ale modele słabo odróżniają zadanie
dookreślone od niedookreślonego. Przy niedookreślonych zadaniach DevOps
agenci zgadują: 55,8–67,8% przebiegów przekracza granicę działania (P032).
Otwarte „popraw/zrefaktoruj” — żaden model nie zatrzymał się sam (P053).
Podział zadania na dwóch agentów bez pełnej specyfikacji: integracja spada
z 58% do 25%, pojedynczy agent z 89% do 56% (P034).

### D4. Szybkość dziś, koszt jakości jutro — **mocne**
Po wdrożeniu Cursora: krótkotrwały wzrost tempa i trwały wzrost ostrzeżeń
(~18%) i złożoności (~39%) (P017, MSR, 90 cytowań; P018). 22,7% problemów
wprowadzonych przez AI wciąż jest w najnowszej wersji (P020). Na 500 tys.
programistów: wzrost commitów nie przekłada się proporcjonalnie na wydania
(P016, NBER). Równoległe PR agentów w tym samym repo często się nakładają
(P010).
**Dla nas:** mierzyć wydane funkcje i przyjęte zmiany, nie commity; CI
z lintem, złożonością, SAST i skanerem sekretów jako bramka.

## E. Zbiory danych do pracy agentowej (rejestr D…, 85 pozycji — dopisane 17.11)

Uzupełnia rejestr dziedzinowy drugiej sesji ([ZBIORY-DANYCH.md](ZBIORY-DANYCH.md):
prawo, kredyt, nadużycia, mowa). **Nic nie zostało pobrane; licencje
i dane osobowe trzeba sprawdzić przed użyciem** — w metadanych licencję podaje
garstka (CC BY 4.0: Ko-Agent-Trajectories D009; CC0: syntetyczny zbiór PII
D067; Loghub-2.0 D075 tylko do badań — nie komercyjnie).

| Do czego | Najpierw | Uwagi |
|---|---|---|
| Środowiska RL / SFT | SWE-Mirror D012 (60 671 zadań, 4 języki, >12 tys. trajektorii), BugPilot D080 (przepis na błędy z własnych repo) | czy jest TypeScript — sprawdzić |
| Wywołania narzędzi (SFT) | xlam-function-calling-60k D006 | każde wywołanie sprawdzone wykonaniem |
| Ewaluacja TypeScript | TSBugs D016 (633 błędy, 16 repo) | czy są wykonywalne testy — sprawdzić |
| Bezpieczeństwo narzędzi | EffectWorld D033 (usuwanie bez pytania, powtórne zapisy u małych modeli) | |
| Obrona przed injection | LLMail-Inject D042 (208 tys. ludzkich ataków), BIPIA D041, NotInject D045 (fałszywe alarmy) | **ważne po polsku:** „pomiń”, „zignoruj” w tekstach prawnych |
| Czyszczenie danych przed treningiem | SecretBench D053 (skaner sekretów), D065/D066/D067 (PII) | Presidio znalazł 7% najbardziej wrażliwych encji (D065); polski — niepotwierdzony |
| Wielojęzyczne narzędzia | MASSIVE-Agents D025 (52 języki), τ-bench-LILT D024 jako przepis na polską wersję | |

Luka: **brak polskich trajektorii agentów i polskich danych tool-use** oraz
polskiego zbioru PII z potwierdzoną otwartą licencją — własny mały zbiór
(z fikcyjnymi danymi) byłby jedynym takim zasobem.

---

## Luki — szukane, nieznalezione

- Brak pomiaru dekodowania spekulatywnego z n-gramów na edycji kodu (B6).
- Brak recenzowanego badania kaskad i routingu właśnie dla agentów kodujących.
  Są tylko preprinty (L038–L041).
- Brak prac o wycieku sekretów przez logi i trajektorie agentów. Najbliższe
  jest S044 (zapamiętane sekrety w modelach kodu).
- Brak dobrze cytowanej pracy o dostrajaniu z prywatnością różnicową
  z konkretnymi liczbami.
- Brak oficjalnej publikacji wyników AIxCC i OSS-Fuzz-gen w OpenAlex.
- Brak pracy o RLS w Postgres jako całości; jest tylko kanał czasowy S048.
- Brak liczbowych wyników LLM do wykrywania anomalii w logach.
- Brak danych o kosztach energii i tokenów na kartach konsumenckich.
- RTX 5090 (GDDR7) nie jest objęty badaniami rowhammera (S055); stan nieznany.

Te luki to też szansa: nasze pomiary na jednej karcie mogą być jedynymi
publicznymi danymi w danym temacie.
