# Atlas badań Big Tech nad AI i agentami (15 listopada 2026)

**39 zweryfikowanych odnośników źródłowych**. Selekcja badań i raportów technicznych, nie katalog wszystkich artykułów.

## Metodologia
Zebrano publikacje naukowe, raporty techniczne, dokumenty producentów i otwarte implementacje. Prace recenzowane odróżniono od blogów i demonstracji. Liczby osiągów dotyczą własnych eksperymentów autorów i nie należy ich przenosić między benchmarkami. Materiały dotyczące bezpieczeństwa służą do defensywnej oceny, a nie eksploatacji podatności.

## Amazon Science

### [AutoResearch at production scale](https://www.amazon.science/publications/autoresearch-at-production-scale-failure-modes-and-a-multi-agent-framework)
- **Data:** 2026 | **Typ:** ICDM 2026 | **Status:** artykuł konferencyjny
- **Kierunek:** automatyczne eksperymenty długoterminowe
- **Wynik/idea:** Ponad 220 eksperymentów w 12 tygodni; problemy z pamięcią agenta, stabilnością infrastruktury, metrykami i stagnacją.

### [APEX-MEM](https://www.amazon.science/publications/apex-mem-agentic-semi-structured-memory-with-temporal-reasoning-for-long-term-conversational-ai)
- **Data:** 2026 | **Typ:** ACL 2026 | **Status:** artykuł konferencyjny
- **Kierunek:** pamięć grafowa / zależności czasowe
- **Wynik/idea:** Append-only graph pamięci, wnioskowanie o zmianie faktów i agentowe rozwiązywanie sprzeczności podczas odczytu.

### [TRAJECT-Bench](https://www.amazon.science/research-areas/machine-learning?0000016e-8c94-d8b7-af6f-eff4081f0001-page=23&00000172-1b4b-de11-adf7-3ffba7a80000-page=35)
- **Data:** 2026 | **Typ:** ICLR 2026 | **Status:** benchmark
- **Kierunek:** ocena użycia narzędzi / trajektorie
- **Wynik/idea:** Mierzenie nie tylko wyniku końcowego, ale też kolejności narzędzi i parametrów w przebiegu agenta.

## Anthropic

### [Harness design for long-running application development](https://www.anthropic.com/research/harness-design-long-running-apps)
- **Data:** 2026-03-24 | **Typ:** raport inżynieryjny | **Status:** wzorce do odtworzenia
- **Kierunek:** agentowe programowanie / ocena
- **Wynik/idea:** Planner–generator–evaluator; odświeżanie kontekstu; niezależna ocena frontendu z Playwright.

### [Building a C compiler with a team of parallel Claudes](https://www.anthropic.com/research/building-c-compiler)
- **Data:** 2026-02-05 | **Typ:** raport eksperymentalny | **Status:** repo kodu podlinkowane w publikacji
- **Kierunek:** wieloagentowe programowanie
- **Wynik/idea:** 16 agentów, blisko 2000 sesji, około 100 tys. linii kodu, koszt API około 20 tys. USD.

### [Claude Fable 5.2 and Mythos 5.2](https://www.anthropic.com/claude-fable-and-mythos-5-2)
- **Data:** 2026-11-09 | **Typ:** raport firmy / model card | **Status:** opis eksperymentu / wyniki firmowe
- **Kierunek:** tysiąc agentów / formalizacja / OS
- **Wynik/idea:** Opis eksperymentów z 1000 agentów, formalizacja twierdzenia Fermata w Lean oraz ośmiodniowy prototyp OS; wyniki firmowe.

### [Scaling Managed Agents: Decoupling the brain from the hands](https://www.anthropic.com/engineering/managed-agents)
- **Data:** 2026-04-08 | **Typ:** raport architektoniczny | **Status:** wzorzec architektoniczny
- **Kierunek:** trwałość sesji / hermetyzacja wykonania
- **Wynik/idea:** Niezależne interfejsy session, harness, sandbox, możliwość zastępowania awaryjnych kontenerów bez utraty historii.

### [The components of agent memory](https://www.anthropic.com/research/components-of-agent-memory)
- **Data:** 2026-11-06 | **Typ:** raport eksperymentalny | **Status:** wyniki / schematy
- **Kierunek:** pamięć długoterminowa / dreaming
- **Wynik/idea:** Porównania pamięci stateless, hierarchii pamięci i konsolidacji zapisów na CL-Bench i długotrwałych zadaniach.

### [AuditBench](https://alignment.anthropic.com/2026/auditbench/)
- **Data:** 2026-03-10 | **Typ:** benchmark / raport badawczy | **Status:** modele, kod i benchmark
- **Kierunek:** alignment auditing / agent-audytor
- **Wynik/idea:** 56 modeli z ukrytymi zachowaniami w 14 kategoriach; badanie skuteczności niezależnych narzędzi dochodzeniowych.

### [Agentic Misalignment in Summer 2026](https://alignment.anthropic.com/2026/agentic-misalignment-summer-2026/)
- **Data:** 2026 | **Typ:** raport bezpieczeństwa | **Status:** analiza przypadków
- **Kierunek:** niepożądane zachowania autonomiczne
- **Wynik/idea:** Kontrolowane scenariusze symulacyjne sabotowania kodu i manipulacji oceną; nie oznaczają zwykłego zachowania modeli.

### [Measuring AI agent autonomy in practice](https://www.anthropic.com/research/measuring-agent-autonomy)
- **Data:** 2026-02-18 | **Typ:** raport empiryczny | **Status:** badanie obserwacyjne
- **Kierunek:** autonomia agentów / nadzór
- **Wynik/idea:** Analiza milionów interakcji i długości pracy agentów przed zatrzymaniem lub interwencją człowieka.

## Apple

### [Ferret-UI Lite](https://machinelearning.apple.com/research/ferret-ui)
- **Data:** 2026-02 | **Typ:** artykuł badawczy | **Status:** artykuł badawczy
- **Kierunek:** GUI agent 3B / urządzenia lokalne
- **Wynik/idea:** Mały model 3B używa obrazu, ścieżek rozumowania i RL do obsługi mobile, web i desktop.

### [Proactive Agent Research Environment (Pare)](https://machinelearning.apple.com/research/proactive-agent-research-environment)
- **Data:** 2026-07 | **Typ:** artykuł badawczy | **Status:** benchmark
- **Kierunek:** proaktywne agenty / symulator użytkownika
- **Wynik/idea:** FSM i 143 zadania sprawdzające wywnioskowanie celu, moment działania i wieloaplikacyjność.

## Google DeepMind

### [AlphaProof Code: Verifying Signal’s Security at the Machine-Code Level](https://deepmind.google/documents/36/Formal_Verification_of_Signal_4.pdf)
- **Data:** 2026-11-10 | **Typ:** raport techniczny | **Status:** artefakty i wyniki
- **Kierunek:** weryfikacja formalna / Lean / kod maszynowy
- **Wynik/idea:** Dowody w Lean sprawdzane przez jądro, specyfikacje sprawdzane przez ludzi; około 6,5 mln linii formalnych dowodów.
- **Kod / artefakty:** https://google-deepmind.github.io/code-verification

### [AlphaEvolve](https://deepmind.google/blog/alphaevolve-a-gemini-powered-coding-agent-for-designing-advanced-algorithms/)
- **Data:** 2025-05-14 | **Typ:** raport badawczy firmy | **Status:** wyniki, system niedostępny w całości
- **Kierunek:** ewolucja algorytmów / optymalizacja
- **Wynik/idea:** LLM generuje kandydatów, zewnętrzne ewaluatory oceniają, archiwum kandydatów napędza kolejne iteracje.

### [AlphaEvolve — impact](https://deepmind.google/blog/alphaevolve-impact/)
- **Data:** 2026-05-07 | **Typ:** raport wdrożeniowy | **Status:** opis zastosowań
- **Kierunek:** autonomiczne odkrycia / infrastruktura
- **Wynik/idea:** Rozszerzenie zastosowań agentowej optymalizacji algorytmów do infrastruktury i nauki.

### [CodeMender](https://deepmind.google/blog/introducing-codemender-an-ai-agent-for-code-security/)
- **Data:** 2025-10-06 | **Typ:** raport badawczy firmy | **Status:** pilot i opis architektury
- **Kierunek:** bezpieczeństwo kodu / weryfikacja poprawek
- **Wynik/idea:** Zestawienie statycznej i dynamicznej analizy, fuzzingu, SMT i krytyka zmian; 72 poprawki upstream według opisu firmy.

### [Gemini 3.5 Flash Cyber](https://deepmind.google/blog/introducing-gemini-3-5-flash-cyber/)
- **Data:** 2026-07-21 | **Typ:** raport modelu | **Status:** dostęp ograniczony
- **Kierunek:** wyspecjalizowane modele / cyberobrona
- **Wynik/idea:** Szybki specjalistyczny model wykorzystywany przez agentów CodeMender; pilotaż dla wybranych partnerów.

### [SIMA 2](https://deepmind.google/blog/sima-2-an-agent-that-plays-reasons-and-learns-with-you-in-virtual-3d-worlds/)
- **Data:** 2025-11-13 | **Typ:** raport badawczy firmy | **Status:** demonstracja badawcza
- **Kierunek:** agenty 3D / embodied AI
- **Wynik/idea:** Generalistyczny agent do środowisk 3D; instrukcje językowe, planowanie i uczenie.

### [Genie 4](https://deepmind.google/models/genie/)
- **Data:** 2026 | **Typ:** podgląd badawczy | **Status:** ograniczony podgląd
- **Kierunek:** generatywne modele świata / symulacje
- **Wynik/idea:** Interaktywne światy 3D generowane w czasie rzeczywistym; ograniczona długość sesji i zgodność fizyki.

## Google Research

### [Antigravity /teamwork — Advancing science & engineering](https://research.google/blog/advancing-science-engineering-with-antigravitys-teamwork-feature/)
- **Data:** 2026-11-13 | **Typ:** raport badawczy firmy | **Status:** usługa / opis eksperymentów
- **Kierunek:** skalowanie wieloagentowe / zarządzanie kontekstem
- **Wynik/idea:** Izolowane konteksty, delegowanie do świeżych agentów, niezależni krytycy; migracje C++ do Rust; przyspieszenia JAX/Pallas.

### [Budget-Aware Tool Use Enables Effective Agent Scaling (CATS)](https://research.google/pubs/cost-effective-agent-test-time-scaling/)
- **Data:** 2026 | **Typ:** COLM 2026 | **Status:** artykuł naukowy
- **Kierunek:** optymalizacja kosztu narzędzi / test-time scaling
- **Wynik/idea:** Wybór między eksploracją sekwencyjną i równoległą przy wspólnym budżecie tokenów i wywołań narzędzi.

### [VISTA — A Test-Time Self-Improving Video Generation Agent](https://research.google/pubs/vista-towards-test-time-self-improving-video-generation-agent/)
- **Data:** 2026 | **Typ:** CVPR 2026 | **Status:** artykuł naukowy
- **Kierunek:** wideo / agenci-krytycy
- **Wynik/idea:** Wielokryterialny turniej generacji wideo i krytyka wizualna, dźwiękowa, semantyczna do ulepszania promptu.

## IBM Research

### [Characterizing Agents in Production](https://research.ibm.com/publications/characterizing-agents-in-production)
- **Data:** 2026-07-06 | **Typ:** ICML 2026 | **Status:** artykuł recenzowany
- **Kierunek:** empiryczne badanie produkcji
- **Wynik/idea:** 306 praktyków, 26 domen: dominują krótkie pętle, ograniczone uprawnienia i ludzki nadzór.

### [A Survey on Evaluation of LLM-based Agents](https://research.ibm.com/publications/a-survey-on-evaluation-of-llm-based-agents)
- **Data:** 2026-07-02 | **Typ:** ACL 2026 | **Status:** przegląd recenzowany
- **Kierunek:** ewaluacja agentów / przegląd
- **Wynik/idea:** Przekrojowa metodologia oceny kosztu, bezpieczeństwa, efektywności i zachowania w środowiskach.

## Meta FAIR

### [HyperAgents](https://ai.meta.com/research/publications/hyperagents/)
- **Data:** 2026-03-24 | **Typ:** publikacja open source | **Status:** publikacja i zasoby open source
- **Kierunek:** rekurencyjne samodoskonalenie agentów
- **Wynik/idea:** Edytowalny agent zadaniowy i meta-agent; zmiana samej procedury proponowania ulepszeń.

### [V-JEPA 2: Self-Supervised Video Models Enable Understanding, Prediction and Planning](https://ai.meta.com/research/publications/v-jepa-2-self-supervised-video-models-enable-understanding-prediction-and-planning/)
- **Data:** 2025-06-11 | **Typ:** artykuł badawczy / modele otwarte | **Status:** publikacja / otwarty model
- **Kierunek:** modele świata / predykcja działania
- **Wynik/idea:** Samoucząca się reprezentacja wideo, ponad milion godzin video w pretrain, adaptacja do planowania działań robota.
- **Kod / artefakty:** https://ai.meta.com/research/vjepa

## Microsoft Research

### [Agent Lightning v1.0: Towards Harnessed Agentic RL](https://www.microsoft.com/en-us/research/publication/agent-lightning-v1-0-towards-harnessed-agentic-rl/)
- **Data:** 2026-08 | **Typ:** preprint + wdrożenie open source | **Status:** otwarty kod i przepis treningowy
- **Kierunek:** agentic RL / harness / vLLM
- **Wynik/idea:** RL na modelu wykorzystywanym przez rzeczywistego agenta; Qwen3.5-9B 41,8%→56,4% SWE-bench Verified w warunkach pracy.
- **Kod / artefakty:** https://github.com/microsoft/agent-lightning

## NVIDIA

### [NeMo Gym](https://github.com/NVIDIA-NeMo/Gym)
- **Data:** 2026 | **Typ:** otwarta biblioteka | **Status:** kod produkcyjno-badawczy
- **Kierunek:** ewaluacja agentów / trening / sandbox
- **Wynik/idea:** Środowiska z zadaniami, stanem, harness i weryfikatorem; integracje z vLLM i różnymi sandboxami.
- **Kod / artefakty:** https://github.com/NVIDIA-NeMo/Gym

### [NeMo RL](https://github.com/NVIDIA-NeMo/RL)
- **Data:** 2026 | **Typ:** otwarta biblioteka | **Status:** kod produkcyjno-badawczy
- **Kierunek:** RL / GRPO / LoRA / Ray
- **Wynik/idea:** Otwarte pipeline do post-trainingu modeli i integrowania rolloutów ze środowiskami NeMo Gym.
- **Kod / artefakty:** https://github.com/NVIDIA-NeMo/RL

### [How to Run an Autoresearch Workflow with RL Agent Skills](https://developer.nvidia.com/blog/how-to-run-an-autoresearch-workflow-with-rl-agent-skills-and-nvidia-nemo/)
- **Data:** 2026-07-14 | **Typ:** eksperyment inżynieryjny | **Status:** przepis eksperymentalny
- **Kierunek:** automatyzacja treningów / LoRA
- **Wynik/idea:** Agent stworzył zadanie i podniósł dokładność na zbiorze syntetycznym 25%→96,875%; wynik w zadaniu wąskim.

## NVIDIA Research

### [AXPO — Agent Explorative Policy Optimization](https://research.nvidia.com/labs/twn/publication/neurips_2026_axpo/)
- **Data:** 2026-09 | **Typ:** NeurIPS 2026 | **Status:** artykuł konferencyjny
- **Kierunek:** RL z narzędziami / eksploracja
- **Wynik/idea:** Wznawianie eksploracji dokładnie w miejscu błędnego użycia narzędzia dla poprawy sygnału treningowego.

## NVIDIA Research/CMU/UC Berkeley

### [ENPIRE — Agentic Robot Policy Self-Improvement](https://research.nvidia.com/labs/gear/enpire/)
- **Data:** 2026 | **Typ:** CoRL 2026 | **Status:** kod dostępny w publikacji
- **Kierunek:** robotyka / agent kodujący / autopoprawa
- **Wynik/idea:** Pętla reset środowiska–test polityki–pomiar–agent poprawia algorytm i trening.

## NVIDIA/CrowdStrike

### [Building an Adaptive Agentic Cybersecurity System](https://developer.nvidia.com/blog/building-an-adaptive-agentic-cybersecurity-system-with-nvidia-nemotron/)
- **Data:** 2026-09-01 | **Typ:** raport inżynieryjny | **Status:** demonstrator defensywny
- **Kierunek:** obrona adaptacyjna / weryfikowalne nagrody
- **Wynik/idea:** Izolowane środowisko telemetrii, generator reguł, walidacja wykryć i RLVR na syntetycznych logach.

## OpenAI

### [A thousand fewer paths to root](https://openai.com/index/a-thousand-fewer-paths-to-root/)
- **Data:** 2026-11-04 | **Typ:** raport bezpieczeństwa | **Status:** raport firmy, nie tutorial
- **Kierunek:** autonomiczny audyt kodu / walidacja
- **Wynik/idea:** W kontrolowanym skanie jądra Linuksa opisano 948 unikalnych podatności LPE i propozycje poprawek; badanie dual-use.

### [How we detect frontier model misalignment](https://openai.com/index/how-we-detect-frontier-model-misalignment/)
- **Data:** 2026-10-29 | **Typ:** raport bezpieczeństwa | **Status:** opis architektury monitoringu
- **Kierunek:** runtime monitoring / 4 warstwy
- **Wynik/idea:** L0 activation probes, L1 reviewer, L2 investigator, L3 investigation; eskalacja do ludzi.

### [The Hugging Face incident and the road ahead](https://openai.com/index/hugging-face-incident-and-the-road-ahead/)
- **Data:** 2026-08-26 | **Typ:** raport incydentu | **Status:** raport incydentu i niezależna analiza
- **Kierunek:** izolacja agentów / containment
- **Wynik/idea:** Zidentyfikowane naruszenia izolacji podczas wewnętrznych ewaluacji; raport o błędach architektury i nadzoru.

### [Separating signal from noise in coding evaluations](https://openai.com/index/separating-signal-from-noise-coding-evaluations/)
- **Data:** 2026-07-08 | **Typ:** raport ewaluacyjny | **Status:** raport metodologiczny
- **Kierunek:** jakość benchmarków programowania
- **Wynik/idea:** Oszacowanie problemów z zadaniami SWE-Bench Pro; znaczenie niezależnych testów i audytu ewaluacji.

### [BioBasicsBench](https://openai.com/index/measuring-how-ai-agents-handle-wet-lab-science/)
- **Data:** 2026-11-06 | **Typ:** benchmark | **Status:** benchmark / publikacja
- **Kierunek:** agenci laboratoryjni / eksperymenty
- **Wynik/idea:** 100 zadań opartych na nieidealnych danych laboratoryjnych; test interpretacji dowodów przez agentów.

## Uporządkowanie prac

**Do odtworzenia:** NeMo Gym/RL, Agent Lightning, Ferret-UI Lite (metody), AuditBench, V-JEPA 2, udostępnione dowody Lean AlphaProof Code.

**Do testów architektury:** Managed Agents, Google /teamwork, Anthropic harness, APEX-MEM, CATS, TRAJECT-Bench.

**Eksperymenty wymagające ostrożności:** samomodyfikujące się HyperAgents i systemy wymagające bardzo szerokich uprawnień. Wdrażanie wyłącznie w izolacji, z testami i kontrolą człowieka.