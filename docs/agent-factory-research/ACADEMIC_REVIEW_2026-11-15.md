# Agent Forge — akademicki przegląd dowodów, 15 listopada 2026

**Charakter:** scoping review / selektywny przegląd krytyczny, NIE formalny systematic literature review i NIE niezależna replikacja badań. Źródła pierwotne, recenzowane i preprinty są w \`academic-evidence.json\`. Zawarte liczby to wyniki **raportowane przez autorów** i dotyczą konkretnych modeli, benchmarków, budżetów i środowisk. Brak uruchomienia GPU.

## Główna teza badawcza

Agent Forge powinien traktować optymalizację policy/model weights, agent harness, data distribution, evaluator i serving jako rozdzielne, eksperymentalnie porównywalne elementy. Zmiany we wszystkich naraz uniemożliwiają przypisanie efektu. Celem jest poprawa *zaakceptowanych, bezpiecznych zadań na jednostkę kosztu*, a nie liczby wygenerowanych commitów ani tokenów.

## Strategia wyszukiwania i oceny

- Data odcięcia: 2026-11-15. Źródła: ACL Anthology (EMNLP/Findings/AACL), NeurIPS proceedings, PMLR (ICML), arXiv (oznaczono jako preprinty), GitHub autorów, Microsoft Research i metodologia Princeton.
- Priorytet źródeł: peer-reviewed empirical study > empirical preprint z kodem i danymi > preprint bez artefaktów > repo README > marketing lub leaderboard. **Recenzja naukowa nie zastępuje niezależnej reprodukcji**.
- Wykluczenia: brak metody testowej, niepowtarzalny wynik bez dostępnej procedury, brak podstawowych danych model/sprzęt/zadanie/metryka; informacje opublikowane po dacie odcięcia.
- Dla każdego twierdzenia: identyfikator źródła, metryka i mianownik, grupa kontrolna, sposób selekcji prób, budget/time, wariancja/seedy, zagrożenia dla trafności, rodzaj licencji, dostępność kodu.
- Nie pobierano ani nie uruchamiano kodu z badanych repozytoriów. Ich istnienie na GitHubie nie dowodzi bezpieczeństwa i możliwości reprodukcji.

## Pytanie 1: harness czy aktualizacja wag?

**Self-HPO** (arXiv:2610.22791, kod MSR-Orchard/Self-HPO) naprzemiennie modyfikuje harness i uczy politykę przez RL. Raportuje poprawę Qwen3.5-35B-A3B na SWE-bench Verified z 61.0 do 69.5. **RHO** (Findings EMNLP 2026, doi 10.18653/2026.findings-emnlp.2439) analizuje wcześniejsze trajektorie i wybiera zmiany harnessu na podstawie self-preference; autorzy raportują 0.59 -> 0.78 na SWE-bench Pro. Wyniki nie są porównywalne między publikacjami.

**Kontrdowód:** badanie arXiv:2610.34938 o retrospektywach Claude Code opisuje 30 spraw SWE-bench Verified, 125 zmian kandydackich i ograniczony wpływ wybranych poprawionych harnessów. W 7 ewaluacjach z zaobserwowanym problemem tylko 3 zmiany go ograniczyły. Przyjmujemy więc hipotezę testowalną, nie bezwarunkową tezę o samodoskonaleniu.

**Ablacja EXP-A:** identyczny model/sprzęt/dane i limit żądań, ramiona: static harness, static+retrieved memory, RHO-style retrospective, DSPy/GEPA, self-HPO dopiero po budżetowanym etapie RL. Zamrożony benchmark z ukrytymi testami, co najmniej 30 różnych spraw oraz 3 ziarna na sprawę jako orientacyjny minimalny próg eksploracyjny (przed głównym badaniem wykonać power analysis). Nie wybieraj zwycięzcy po przeglądaniu wyników holdout.

## Pytanie 2: skąd wziąć naprawdę wartościowe zadania?

**WildAWM** (MSR-Orchard, arXiv:2610.26828) udostępnia 341 par środowisko-zadanie, łącząc GUI, MCP, pliki i CLI we wspólnym stanie; powstawanie kolejnych dni jest deterministyczne. **AutoEnvScaling** (arXiv:2610.14163) wprowadza autonomicznego projektanta środowisk treningowych: poprawa Terminal-Bench 2.1 z 41.1 do 53.3 dotyczy określonej konfiguracji w pracy.

**Ryzyko:** zadania syntetyczne mogą mieć trywialne skróty, ukryte przecieki etykiet, nierealistyczną złożoność lub błędne weryfikatory. Odrębnie mierzyć: % środowisk dających się odtworzyć, % wykrywających pustą odpowiedź, % wykrywających celowe obejście i trafność na prawdziwych otwartych zadaniach testowych. Na starcie żadnych danych klientów NotarAI.

**Ablacja EXP-B:** przygotuj min. 30 fikcyjnych procesów SaaS z właściwymi stanami. Zrób próby pozytywne/negatywne dla każdej rubryki. Porównaj naukę z promptów, ze zwykłych zapisów działań i z weryfikowanych stanów terminalnych.

## Pytanie 3: czy agent potrafi wiarygodnie sprawdzić samego siebie?

**ExecCritic** (arXiv:2609.09133) konstruuje testy z kontraktów zachowania i wykorzystuje je w pętli naprawy. Raportowany wynik 72.6% SWE-bench Verified (+11.4pp wobec wariantu bez generowanych testów) nie jest dowodem, że każdy wygenerowany test jest poprawny.

**SpecBench** (arXiv:2605.21384, kod WecoAI/SpecBench) rozdziela testy dostępne podczas rozwiązywania problemu i testy kompozycyjne ukryte. **Reward Hacking Benchmark** (ICML 2026) stwierdza w zadaniach z narzędziami zachowania wykorzystujące słabości miernika. **AgentHallu** (EMNLP 2026) wskazuje, że znalezienie pierwotnego błędnego kroku jest trudne nawet dla silnych modeli.

**Ablacja EXP-C:** wyniki testów publicznych vs holdout; permutacje danych wejściowych, testy metamorfizmu, sabotaż test runnera, próby modyfikacji evaluator/CI, podejrzane semantycznie odpowiedzi i niezależna kontrola patchy. Każda próba naruszenia hard policy blokuje promocję bez względu na pass rate. Różnice pass rate raportuj razem z liczebnością i przedziałem niepewności.

## Pytanie 4: które kroki w długiej trajektorii były istotne?

**TRACE** (Microsoft, 2026) przypisuje nagrody przy granicach wywołań narzędzi na podstawie zmian prawdopodobieństwa prawidłowej odpowiedzi według zamrożonego modelu referencyjnego. To ciekawe dla długich epizodów, ale wymaga wiarygodnej odpowiedzi referencyjnej i kosztownego treningu. **AgentHallu** i **Agent-Trident** (Findings EMNLP 2026) wskazują potrzebę rozdzielenia błędnej oceny możliwości rozwiązania, planowania i wykonania.

**Ablacja EXP-D:** dla tej samej puli trajektorii porównaj scoring wyłącznie terminalny, scoring na poziomie wywołań narzędzia i scoring z niezależnym obserwatorem. Bez RL zanim nie udowodnimy, że funkcja oceny jest odporna na obejście.

## Pytanie 5: czy LLM-as-a-judge może być arbitrem?

**All Verdicts are Not Equal** (AACL 2026, DOI 10.18653/2026.aacl-long.207) oraz praca workshopowa o niestabilności ocen pokazują flipy przy replikacjach i bias związany z kolejnością. Nawet 100% zgodności wewnętrznej nie implikuje trafności względem etykiet referencyjnych.

**Ablacja EXP-E:** gdy kryterium wymaga oceny semantycznej, randomizuj kolejność A/B, wykonaj powtórzenia, zgłoś Cohen's kappa / spójność i rozbieżności z ręcznie ocenioną, losowaną próbką. Zawsze z oddzielną listą obiektywnych bramek (testy CI, bezpieczeństwo, formalny stan aplikacji).

## Pytanie 6: czy optymalizacja GPU naprawdę obniży koszt?

**The Silent Hyperparameter** (arXiv:2605.19537) podaje, że sam silnik inferencji może przesuwać wyniki benchmarku nawet o 16.6 punktów procentowych w badanych konfiguracjach. Oznacza to, że backend, scheduler, precision, kontekst i KV cache muszą być zapisane obok model-id.

**Bursts That Outlast Themselves** (arXiv:2611.13412, 10 listopada 2026) raportuje degradację vLLM/SGLang po krótkich burstach ruchu przy prefix cache: w określonych przebiegach mniej cache hits nakręca wzrost kolejki. **Dual-Pool Token-Budget Routing** (arXiv:2604.08075) raportuje oszczędności GPU-hours 31-42% w dużych flotach, czego NIE wolno przenosić jako prognozy na jedną kartę wynajmowaną na kilka godzin.

**Ablacja EXP-F:** 1 vs 2 instancje, kontekst krótki vs długi, różny concurrency, cache-on/off, fixed warm-up i burn-in, workload replay ze skryptowanych sesji. Mierz TTFT P50/P95/P99, TPOT, input/output tokens, KV occupancy, OOM/retry, throughput, rzeczywiste rozliczenie GPU-hour i koszt **zaakceptowanego** zadania. Zablokuj testy dostępu do danych klienta.

## Pytanie 7: jak sprawdzać produkcję filmów wideo?

**PVBench** (arXiv:2610.26711) rozdziela 46 wymiarów z 600 promptami, w tym geometrię, kinematykę i zachowanie praw fizyki. **GeoPhys** (NeurIPS 2026) bada geometrię trajektorii cech zamrożonego enkodera; **The Invisible Hand of Physics** (NeurIPS 2026) bada reprezentacje fizyki w latentach modeli dyfuzyjnych, w tym LTX-Video; **HumanScore** (NeurIPS 2026) proponuje biologicznie interpretowalne metryki ludzkiego ruchu.

**Ablacja EXP-G:** standardowy text-to-video kontra draft 3D + wideo warunkowane, ten sam scenariusz i limity GPU, 3-5 seedów na ujęcie, ślepe porównanie człowieka, zgodność trajektorii kamery, liczba błędów continuity, fizyka i koszt zatwierdzonej sekundy. Wskaźniki automatyczne trzeba kalibrować z ocenami ludzi.

## Protokół statystyczny Agent Forge

- Jednostka losowania: zadanie/case. Wiele seedów na zadanie jest skorelowanych; nie traktuj ich jako niezależnych.
- Kontrola baseline i wariantu musi używać tych samych spraw, porównywalnych zasobów i stałych granic czasu/budżetu.
- Główna metryka: sukces niezależnego holdout połączony z brakiem policy violations. Metryki drugorzędne: koszt PLN/zaakceptowany task, p95 latency, review-minutes, cache/GPU time.
- Raportuj task-cluster bootstrap CI oraz exact task-level sign test; sam p-value nie dowodzi wielkości efektu. Obowiązuje prerejestracja hipotez i korekta wielokrotnych porównań, gdy wybieramy spośród wielu wariantów.
- Split DEV (optymalizacja) / HOLDOUT (jeden finalny test). Nie używaj holdout do iteracyjnego doboru promptów.
- Zapisuj commit model/harness, model checkpoint, engine version, precision, batching, GPU, region, dataset/evaluator SHA, sampling, max steps, downtime, retry, cache strategy, koszt rzeczywisty vs szacowany.
- Samodzielna zmiana narzędzi ewaluacyjnych przez badanego agenta jest niedopuszczalna. Oddziel repo i uprawnienia evaluatora.
- Statystyki prezentowane na syntetycznych przykładach nie są dowodem poprawy jakiegokolwiek modelu.

## Co naprawdę implementowano

- tools/agent_factory/forge_research_stats.py: walidacja ograniczonego zbioru anonimowych danych, analiza par, bootstrap na klastrach zadań i dokładny test znaków; zero sieci.
- tools/agent_factory/forge_research_cli.py: analiza przykładu generowanego syntetycznie, bez dostępu do modeli i chmury.
- test_agent_forge_research.py: negatywne przypadki (złe schematy, duplikaty, PII payload, fałszywa proweniencja i bezpieczeństwo).
- Żadna analiza nie autoryzuje automatycznego awansu, wdrożenia ani zakupów GPU.

## Ograniczenia obecnego poziomu dowodów

To wstęp do programu badawczego, nie meta-analiza. Nie wyliczono pooled effect i nie przeprowadzono formalnej oceny ryzyka biasu dla każdego artykułu. Wyniki autorów różnią się liczbą prób, modelami, budżetami i definicjami sukcesu. Również badanie METR z 2025 pokazało w jednym RCT 19% spowolnienia doświadczonych programistów przy pomocy wczesnych narzędzi AI, a aktualizacja z 2026 opisuje silne źródła selection bias; nie wyciągamy z tego uniwersalnego wniosku o obecnych agentach.

## Bibliografia i śledzenie źródeł

Plik academic-evidence.json zawiera 24 rekordy z tytułami, statusem publikacji, datą, URL, kodem i głównym zagrożeniem metodologicznym. Źródła i ograniczenia nie mogą być traktowane jako nadanie licencji komercyjnej na pobrany kod, modele, checkpointy i dane.
