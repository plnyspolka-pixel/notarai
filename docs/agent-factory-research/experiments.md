# Reproducible experiments — backlog

Status wszystkich poniższych: **PROPOSED / NOT RUN**. Liczby są kryteriami docelowymi, a nie zmierzonymi wynikami. Przed każdą płatną próbą operator podaje limit kosztu i zatwierdza dostawcę oraz region.

## EXP-01: Agent Harness Tournament (P0, CPU + opcjonalny model GPU)

Hipoteza: poprawnie prowadzony agent na tańszym modelu może zwiększyć liczbę zaakceptowanych zmian bez pogorszenia bezpieczeństwa.
- Porównaj istniejący Codex/vLLM worker z wybraną implementacją OpenHands albo Prime Agent, bez łączenia obydwu na początek.
- Test: >=15 syntetycznych lub otwartoźródłowych zadań odtwarzanych ze znanej rewizji.
- Miary: task solved, test pass rate, regressions, review minutes, cost/task PLN, latency p95, policy violations.
- Gating: wynik niezależnego testera; train/dev/test split; koszt i zmiany w repo nie mogą być ukryte w promptach.
- Artefakty: raport przed/po + diff + log JSONL bez PII.

## EXP-02: Self-Improvement, autoresearch vs ShinkaEvolve (P0, GPU tylko z zatwierdzeniem)

Hipoteza: ewolucja promptów, hiperparametrów lub kodu inferencji poprawi koszt na zaakceptowane zadanie.
- Jeden zamrożony baseline, stałe dane testowe i budżet iteracji.
- Warianty: Karpathy autoresearch, ShinkaEvolve, GEPA/DSPy; każda próba w izolacji.
- Nagroda: przewaga tylko gdy testy poprawności przechodzą; kara za długi czas, koszt, ryzyko.
- Silny zestaw holdout + ocena stabilności wielokrotnej, aby uniknąć overfit do bench.
- STOP: poprawka próbuje zmieniać testy, evaluator, polityki egress, dane referencyjne lub sekret.

## EXP-03: Agent-World Synthetic Company (P0, CPU + LLM on approved route)

Hipoteza: można wytrenować obsługę wielu API bez dotykania rzeczywistych kont.
- Zbuduj lokalne, stanowe symulatory: CRM, płatności fikcyjne, kalendarz, dokumenty i umowne API.
- Użyj Agent-World jako materiału architektonicznego, NeMo Data Designer do próbek i Verifiers do oceny stanu końcowego.
- Mierniki: % rzeczywiście zakończonych procesów, błędy transakcyjne, nieuprawnione działania, retry/idempotency.
- Hard stop: żadnych rzeczywistych płatności, podpisów, przelewów, maili i dostępu do systemów NotarAI.

## EXP-04: Self-Curating Skills (P1, CPU, ewentualne drogie RL w osobnym etapie)

Hipoteza: nadzorowana biblioteka skilli zwiększa skuteczność w przyszłych zadaniach.
- Zainspiruj się SkillOS i MemSkill; porównaj warianty no-skill / static-skill / learned-skill.
- Wymagaj provenance każdego skilla i testów regresji; nigdy nie pozwalaj agentowi zmieniać swoich polityk bezpieczeństwa.
- Mierniki: delta success rate na holdout, odsetek regresji, długość kontekstu i koszt.

## EXP-05: Video-Coder x Blender x LTX (P1, GPU only after cost approval)

Hipoteza: kontrolowany draft 3D daje bardziej powtarzalny ruch postaci i kamery niż text-to-video.
- W pełni fikcyjna scena i bohaterowie. Generuj ruch w Blender Python, przekazuj draft do zgodnego modelu wideo.
- Na początek 2–3 ujęcia. Zapisz prompt, Blender scene, seedy, checkpoint i warunki GPU.
- Mierniki: zgodność z ruchem, stabilność sceny, czas montażu, koszt zaakceptowanej sekundy filmu.
- Alternatywne R&D: VerseCrafter / WorldinWorld / World-R1. Nie twierdź, że są kompatybilne z LTX bez testów.

## EXP-06: Video Factory Automated Critic (P1)

Hipoteza: selektywne powtórki ujęć oszczędzają GPU w porównaniu z pełnym rerenderem.
- Comfy MCP steruje workflowem; VBench + ocena ekspercka + testy wizualne niezależne od generatora.
- Randomized A/B: full rerender vs single-shot repair. Uwzględnij koszt całej pętli, nie tylko pracy generatora.
- Mierniki: koszt za zatwierdzony klip, liczba poprawek, spójność postaci i audio.
- Brak automatycznego użycia wizerunków/głosów realnych osób bez podstawy prawnej.

## EXP-07: ForgeKernel micro-benchmark (R&D, wybrany GPU)

Hipoteza: wąsko wybrany operator na konkretnej karcie może być zoptymalizowany lepiej niż baseline.
- Zacznij od jednego operatora z referencją i testami numerycznymi; bez modyfikacji prod inference.
- Mierniki: correctness tolerance, median/P95 throughput, peak VRAM i reproducibility.
- Zapisz model GPU i wersje CUDA, Triton, sterownika, compiler flags.
- Tylko GPU z limitem budżetowym i udokumentowaną możliwością zatrzymania zadań.

## EXP-08: HyperAgents / RLM safety test (R&D, izolacja bez sieci)

Hipoteza: rekurencyjne przetwarzanie kontekstu i kontrolowana ewolucja harnessu podnoszą skuteczność.
- Prime Agent: benchmark pracy z dużym syntetycznym repo. HyperAgents: małe, deterministyczne zadanie w kontenerze bez sieci.
- Obowiązkowo niezależny evaluator, zatwierdzony scope plików i read-only system policy.
- Licencja HyperAgents według README CC BY-NC-SA: wykorzystanie komercyjne wymaga uprzedniego sprawdzenia.
- Fail closed: gdy agent próbuje zmienić testy, własny sandbox albo uzyskać dostęp do hosta.

## EXP-09: Voice Latency & Polish Quality (P2)

- Porównaj Pipecat i LiveKit z dopuszczonymi ASR/TTS na nagraniach syntetycznych.
- Mierz latency turn-taking, rozpoznanie mowy polskiej, przerwania, zgodność głosów, koszt i stabilność.
- Brak prawdziwych rozmów klientów i danych biometrycznych w zbiorach badawczych.

## EXP-10: Distributed Inference Reality Check (R&D)

- Porównaj 1 GPU vs 2 heterogeniczne węzły (Nakshatra) na dokładnie tym samym modelu, jeśli wspierany.
- Zapisz koszt godzinowy, transfer, time-to-first-token i tokeny/s.
- Zakończ eksperyment, jeśli sieć niweluje oszczędności.

## Wspólny protokół

1. Approved task ID + signed operator budget envelope (0 PLN domyślnie).
2. Repo/commit pin + dependency/license review + synthetic test set.
3. Isolated worker + deny-all network except explicit approved endpoints.
4. Baseline, no modifications to evaluator; holdout locked and hashed.
5. Execution trace metadata only; PII scanner; hard timeout and kill-switch.
6. Independent evaluation; generate report with confidence intervals where meaningful.
7. Artifact + reproduction script + hash + actual cost; propose PR, never merge.
