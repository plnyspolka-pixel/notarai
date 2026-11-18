# Kierunki laboratorium — od 17.11.2026

Kolejne eksperymenty wynikające ze [stanu wiedzy](STAN-WIEDZY.md). Wszystkie
mają status **PROPONOWANE / NIEURUCHOMIONE**. Płatne GPU dopiero po Twojej
zgodzie i z limitem kosztu. Każdy eksperyment idzie według protokołu Agent
Forge: te same karty, te same ziarna, ukryte testy, podział DEV/HOLDOUT.
Z poprawkami z B7: 3–5 powtórzeń na kartę i przedziały bayesowskie lub dokładne
zamiast przedziałów z CLT.

**Główna miara wszędzie:** koszt (USD) na **przyjętą** zmianę, czyli zmianę,
która przeszła ukryte testy i przegląd. Dla wariantów bezpieczeństwa:
skuteczność ataku (ASR) przy zachowanej użyteczności.

Koszty GPU liczone dla RTX 5090 na Salad (0,25–0,60 USD/h) plus stały rozruch
kodera ok. 25 min. Eksperymenty o wspólnym rozruchu warto łączyć w jedną paczkę.

## Tor 0: wdrożenia bez eksperymentu (literatura jest wystarczająco mocna)

| # | Co | Dlaczego (źródło) | Koszt |
|---|---|---|---|
| W1 | Inwentarz serwerów MCP i skilli używanych w sesjach Claude Code i przez kodera. Przypięcie wersji i skrótu **całego** rekordu narzędzia, aktualizacja tylko po przeglądzie | ETUDE 97,6% skuteczności także przeciw Claude Code (S058); sam opis nie wystarcza (S059); skille do 80% (S016) | praca Claude, bez GPU |
| W2 | Bramka „na każde wywołanie” w serwerze MCP Finance You dla narzędzi wysyłających i płacących: lista adresatów, limit kwoty, idempotencja, przy braku pewności odmowa | S021 (wypłata na domyślnych ustawieniach LangChain), S001, S019 | praca Claude; obszar zastrzeżony, więc tylko z Twoją akceptacją |
| W3 | Koder: nowa zależność w diffie = lista dozwolonych i wiek paczki w rejestrze; na GPU tylko `safetensors` + `trust_remote_code=False` + skrót modelu | S051, S035, S036 | mała karta |
| W4 | Dopisanie do protokołu Agent Forge: powtórzenia kart, przedziały bayesowskie, korekta sędziego LLM | L057, L058, L059 | dokument |
| W5 | Radar co tydzień w GitHub Actions (bez klucza, ok. 0,02 USD) i przegląd w poniedziałek | tempo z tabeli w stanie wiedzy | mały workflow |

## Tor 1: tanie eksperymenty na koderze (P0)

### K1. Sufit modelu: pass@k na naszych kartach
- **Pytanie:** czy Qwen „umie” nasze karty, tylko nie za pierwszym razem? To
  rozstrzyga, czy w ogóle iść w RL, w destylację czy w best-of-n (B4).
- **Plan:** 30 kart × k ∈ {1, 4, 8}. Wybór kandydata przez ukryte testy, a osobno
  przez sędziego Qwen3-8B z losową kolejnością.
- **Miary:** pass@1, pass@4, pass@8 oraz koszt na przyjętą zmianę dla best-of-4
  i best-of-8 wobec pojedynczej próby.
- **Decyzja:** jeśli best-of-4 obniża koszt na przyjętą zmianę, staje się
  domyślne. Jeśli pass@8 − pass@1 > 15 pp, RL ma sens (K7); w przeciwnym razie
  ważniejsze są dane (K6).
- **Koszt:** ok. 4–6 h GPU (2–4 USD). Źródła: L007, L053, L054, L060.

### K2. Polityka kontekstu w harnessie kodera
- **Ramiona:** (a) pełna historia, (b) maskowanie starych obserwacji co krok,
  (c) maskowanie paczkami co 5 kroków, (d) (c) + przycinanie powtórzonych
  logów testów.
- **Miary:** odsetek przyjętych zmian, tokeny na przyjętą zmianę, trafienia
  prefix cache w vLLM (metryka serwera), czas przebiegu.
- **Decyzja:** przyjmujemy najtańsze ramię, które nie traci więcej niż 1 pp
  przyjęć według dolnej granicy przedziału.
- **Koszt:** 30 kart × 3 powtórzenia × 4 ramiona, ok. 8–10 h GPU (3–6 USD).
  Źródła: L042, L043, L032, L045.

### K3. Karty po angielsku czy po polsku
- **Pytanie:** czy polskie karty, CLAUDE.md i prompty kosztują nas dwa razy
  więcej tokenów i obniżają wynik małego modelu?
- **Plan:** te same 30 kart w dwóch wersjach językowych, tłumaczonych przez
  Claude i sprawdzonych ręcznie. Teksty widoczne dla klienta zostają po polsku
  w obu ramionach.
- **Miary:** tokeny wejścia, przyjęte zmiany, błędy w polskich napisach w kodzie.
- **Koszt:** ok. 3 h GPU (1–2 USD). Źródła: L065, L066.

### K4. Format eskalacji do Claude
- **Ramiona:** przy niezaliczonej karcie Claude dostaje (a) cały transkrypt
  kodera albo (b) stan repo, kartę i streszczenie porażki w ok. 200 tokenach.
- **Miary:** przyjęte zmiany po eskalacji, tokeny Claude na przyjętą zmianę,
  minuty przeglądu.
- **Koszt:** koszt API Claude, bez dodatkowego GPU (porażki zbieramy z K1–K2).
  Źródła: L039, L038.

### K5. Zmyślone paczki w pracy kodera
- **Plan:** w trajektoriach i diffach z K1–K2 policzyć importy i zależności
  nieistniejące w PyPI/npm, potem sprawdzić, ile z nich zatrzymuje bramka z W3.
- **Miary:** odsetek zmyślonych nazw na 100 kart, skuteczność bramki.
- **Koszt:** CPU, z danych K1–K2. Źródła: S051.

## Tor 1b: proces pracy z agentami — bez GPU (P0, dopisane 17.11)

| # | Zmiana | Źródło | Jak zmierzyć |
|---|---|---|---|
| W6 | **Testy do karty pisze Claude, koder ich nie widzi** (ukryte testy akceptacyjne + „test sabotażu”: celowo zła poprawka musi oblać) | P046, P048, P049, T030 | różnica „agent mówi: gotowe” vs ukryte testy, per model |
| W7 | Szablon karty: decyzje biznesowe + kryteria akceptacji + „najpierw pytania”; dozwolony wynik „zmiana niepotrzebna”; zakaz kart otwartych („popraw”, „zrefaktoruj”) | P031, P033, P052, P053 | odsetek kart przyjętych za pierwszym razem, rundy przeglądu |
| W8 | 5 najczęściej łamanych reguł z CLAUDE.md → hooki / reguły „deny”; przy każdej regule krótkie „dlaczego”; przegląd CLAUDE.md raz w miesiącu | P025, P027–P029, P044 | naruszenia docierające do Ciebie, 2 tygodnie przed i po |
| W9 | Równoległe karty: rozłączne pliki i wspólny interfejs zapisany przed startem | P010, P034 | konflikty przy scalaniu |
| W10 | Ty zatwierdzasz w kilku zaplanowanych punktach paczkami, nie każdą zmianę; Claude przy decyzjach tłumaczy „dlaczego” | P041, P054–P056 | Twoje minuty na przyjętą zmianę |

## Tor 2: trening na jednej karcie (P1, po torze 1)

**Przepis (synteza działu C stanu wiedzy, każdy krok osobno mierzony):**

1. **Ramię kontrolne za darmo:** GEPA/ACE — ewolucja promptu i podręcznika
   kodera z przyjętych i odrzuconych trajektorii; podział po repozytoriach;
   awarie infrastruktury odsiane (T036, T037, T042, T043).
2. **Pula zadań:** nasze karty po „teście sabotażu” (T030) + błędy
   generowane w naszych repo metodą BugPilot / samogry (D080, T015) +
   SWE-Mirror (D012) po sprawdzeniu licencji.
3. **Filtr:** obecny model 4× na kartę; zostają karty rozwiązane 1–3 razy na 4,
   ułożone od łatwych do trudnych (T019, T021, T044).
4. **SFT (LoRA):** strata tylko na tokenach modelu, maskowanie błędnych kroków,
   domieszka ogólnego kodu, przewaga własnych przyjętych przebiegów modelu nad
   trajektoriami Claude, bez długiego „myślenia” (T044, T046, T060, T062).
   Proporcja danych publicznych i własnych — **hipoteza do testu, brak pracy,
   która ją rozstrzyga** (np. 50% nasze / 35% publiczne trajektorie / 15%
   tool-use i ogólne).
5. **Preferencje:** DPO na parach przyjęta/odrzucona dla tej samej karty albo
   Claude poprawia tylko pierwszy błędny krok (T048, T057).
6. **RL tylko przy plateau SFT:** najpierw RAFT (iterowane SFT z rejection
   sampling), potem RLOO/GRPO z korektą logprobów vLLM; dla MoE routing replay
   (T004, T008, T013).
7. **Bramki przed użyciem:** świeże karty z datą po danych treningowych,
   regresja ogólnego kodu, wyciek (S041), prompt injection (D041, D042) +
   fałszywe alarmy (D045), SAST, skaner sekretów na danych treningowych
   (D053), czyszczenie PII (D065–D067).

**Czyszczenie danych przed treningiem jest warunkiem, nie opcją:** trajektorie
przechodzą skaner sekretów i usuwanie PII — także wtedy, gdy „nie powinno tam
być” danych osobowych (A6, S044).

### K6. Pierwszy adapter LoRA z przyjętych trajektorii
- **Warunek startu:** co najmniej 300 przyjętych trajektorii (koder albo Claude)
  bez obszarów zastrzeżonych i bez danych osobowych, przepuszczonych przez
  gitleaks i SAST.
- **Ramiona:** (a) Qwen bazowy, (b) LoRA na naszych trajektoriach po
  wycięciu pętli i zbędnych odczytów, (c) gotowy model lub zbiór z L016
  (po sprawdzeniu licencji).
- **Miary:** przyjęte zmiany na HOLDOUT (karty młodsze niż dane treningowe)
  i regresja na ogólnym benchmarku kodu.
- **Bramki przed użyciem:** test wycieku (kanarki i atak typu LoRA-Leak, S041),
  test prompt injection (InjecAgent, S003) i SAST na generowanym kodzie
  (S056, S057).
- **Koszt:** 8–15 h GPU (5–9 USD) plus ewaluacja. Źródła: L001, L002, L016–L020,
  S039–S041, S062.

### K7. RL ze sprawdzalną nagrodą — tylko jeśli K1 pokaże zapas
- GRPO lub GSPO na LoRA, nagroda = odsetek zaliczonych testów + linter (L010,
  L013).
- **Kontrole obowiązkowe:** losowa nagroda (L008) i druga rodzina modeli.
- **Koszt:** 15–30 h GPU. Tylko po K1 i K6.

### K8. Kwantyzacja i dekodowanie spekulatywne
- **Ramiona:** AWQ-4bit, FP8, FP8 + kwantyzacja KV cache; każde z dekodowaniem
  spekulatywnym z n-gramów (prompt lookup) i bez.
- **Miary:** tokeny/s, przyjęte zmiany, koszt na przyjętą zmianę.
- **Bonus:** n-gramy na edycji kodu to luka w literaturze (B6), więc wynik może
  być publikowalny.
- **Koszt:** ok. 6 h GPU (2–4 USD). Źródła: L024–L030, L069.

## Tor 3: laboratorium bezpieczeństwa (P1)

### K9. Odporność agentów z narzędziami na prompt injection
- **Środowisko:** AgentDojo (banking + workspace) i InjecAgent na Qwen w vLLM,
  bez żadnych naszych danych.
- **Ramiona:** (a) brak obrony, (b) spotlighting, (c) polityka w stylu Progent
  poza modelem, (d) uproszczony CaMeL (planista widzi tylko zadanie).
- **Miary:** użyteczność, ASR przy ataku statycznym, ASR przy 50 rundach ataku
  adaptacyjnego.
- **Po co:** wybór wzorca dla bramki W2 na danych, a nie z ulotki producenta
  (S004, S005).
- **Koszt:** ok. 6–10 h GPU.

### K10. Zatrucie i podmiana narzędzi MCP
- Kopia naszych serwerów MCP w piaskownicy z danymi fikcyjnymi. Przypadki
  w stylu MCPTox (S013) i aktualizacje w stylu ETUDE (S058).
- **Ramiona:** bez przypięcia, przypięcie opisu, przypięcie całego rekordu,
  przypięcie całego rekordu + bramka W2.
- **Miary:** ASR, liczba wykonanych fikcyjnych wypłat lub wysyłek, fałszywe
  odmowy na 50 zwykłych zadaniach, liczba zmian do ręcznego zatwierdzenia
  (zmęczenie zatwierdzaniem, S059).
- **Koszt:** CPU + mały model; można też na API.

### K11. Fuzzing naszych parserów w wolnym czasie GPU
- Parsery XML EKW, obwieszczeń KRZ i importów wyciągów. LLM generuje
  i mutuje dane wejściowe, uprząż fuzzingu pisze koder (S031, S032, S030).
- **Miary:** pokrycie kodu, liczba unikalnych awarii, czas do pierwszego błędu.

### K12. Kanały boczne na Supabase (bez GPU)
- Sprawdzić, czy jakiekolwiek API (PostgREST, MCP) pozwala klientowi albo
  agentowi filtrować po kolumnach wrażliwych tabel objętych RLS, oraz
  przeprowadzić test czasowy na kopii z danymi fikcyjnymi (S048).
- Do tego testy BOLA generowane przez agenta dla każdego punktu końcowego
  z identyfikatorem (S047).

## Tor 4: pytania otwarte do śledzenia przez radar

- Czy węzły SaladCloud dzielą GPU między najemców i co z tego wynika dla
  kodu, który tam wysyłamy (S054, S060). Pytanie do dostawcy i do Twojej
  decyzji (A5).
- Czy pojawi się głowica EAGLE-3 dla modelu Qwen, którego używamy (L027).
- Rowhammer na GDDR7 / RTX 5090 (S055).
- Polskie modele: kolejne wersje Bielika i PLLuM jako tani pomocnik do
  polskich podzadań obok modelu kodu (L067–L071).

### K13. GEPA kontra LoRA-SFT na naszych kartach
- Ok. 200 kart, Qwen 14B. Ramiona: prompt bazowy, GEPA/ACE, LoRA-SFT według
  przepisu, oba razem.
- **Miara:** koszt na przyjętą zmianę na HOLDOUT.
- **Koszt:** szacunek agenta badawczego ok. 30 h GPU (8–18 USD). Źródła: T037, T044.

### K14. Ablacja SFT
- Ramiona: strata maskowana vs pełna; domieszka ogólnego kodu vs brak;
  własne przebiegi modelu vs trajektorie Claude.
- **Koszt:** 4 adaptery LoRA + ewaluacja, ok. 40 h GPU. Źródła: T044, T046, T062.

### K15. Polski mini-zbiór dla agentów (luka w literaturze)
- 100–200 fikcyjnych zadań tool-use po polsku na kopiach naszych narzędzi
  (CRM, kalendarz, dokumenty), wzorem τ-bench-LILT (D024) i MASSIVE-Agents
  (D025).
- Do tego polski zbiór testowy PII z fikcyjnymi numerami PESEL, do sprawdzania
  pseudonimizacji.
- Budowa bez GPU; potem ewaluacja kodera i Bielika.

## Kolejność (propozycja)

0. Bez GPU, od zaraz: **W6, W7, W8** (proces pracy). Według literatury dają
   więcej niż trening, bo zapisują to, czego model sam z siebie nie zrobi.
1. Bez GPU: **W1, W3, W4, W5**, a W2 po Twojej akceptacji (obszar zastrzeżony).
2. Jedna paczka GPU (wspólny rozruch): **K1 + K2 + K3**, razem ok. 15–20 h,
   10–15 USD. Wyniki K4 i K5 powstają z tych samych przebiegów.
3. Po zebraniu 300 przyjętych trajektorii: najpierw **K13** (czy trening
   w ogóle wygrywa z GEPA), potem **K6/K14**, potem K8. K7 tylko przy zapasie
   z K1.
4. Równolegle, bez wpływu na produkcję: **K9, K10, K12, K15**.
