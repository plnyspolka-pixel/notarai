# Katalog repozytoriów Agent Factory — 2026-11-15

**Status weryfikacji:** repozytoria poniżej zostały sprawdzone przez GitHub API pod kątem istnienia i braku archiwizacji w dniu 2026-11-15. Dla 9 najbardziej eksperymentalnych przeczytano początek README. **Nie** jest to audyt licencji, bezpieczeństwa, wersji i kompatybilności. Dane dotyczące wydajności autorów należy niezależnie odtworzyć. Żadnych automatycznych instalacji.

Priorytet P0 = najpierw przeanalizować/prototypować; P1 = kolejny etap; P2 = później; R&D = eksperyment naukowy, nie fundament produkcji.

## Autonomiczne badania i samodoskonalenie

| Priorytet | Repozytorium | Zastosowanie |
| --- | --- | --- |
| P0 | [karpathy/autoresearch](https://github.com/karpathy/autoresearch) | Autonomiczne cykle: zmiana kodu treningowego, pomiar, selekcja i dziennik prób |
| P0 | [SakanaAI/ShinkaEvolve](https://github.com/SakanaAI/ShinkaEvolve) | Ewolucyjne poszukiwanie wariantów programów z funkcją oceny |
| P1 | [SakanaAI/AI-Scientist-v2](https://github.com/SakanaAI/AI-Scientist-v2) | Hipotezy, eksperymenty, analiza wyników i raporty |
| P1 | [algorithmicsuperintelligence/openevolve](https://github.com/algorithmicsuperintelligence/openevolve) | Populacyjna ewolucja kodu i selekcja na podstawie testów |
| R&D | [facebookresearch/hyperagents](https://github.com/facebookresearch/hyperagents) | Samodoskonalenie agenta oraz sposobu prowadzenia optymalizacji; licencja non-commercial |
| P0 | [PrimeIntellect-ai/prime-agent](https://github.com/PrimeIntellect-ai/prime-agent) | Recursive Language Model, trwały REPL i continual harness |
| R&D | [belt-sh/skillos](https://github.com/belt-sh/skillos) | Eksperyment nad trenowaniem selekcji, aktualizacji i usuwania skilli |
| R&D | [RealLcz/MGM](https://github.com/RealLcz/MGM) | Mendel Goedel Machine: wieloliniowa ewolucja i łączenie agentów |
| P1 | [ViktorAxelsen/MemSkill](https://github.com/ViktorAxelsen/MemSkill) | Uczenie strategii zapamiętywania i dostosowywania pamięci |

## Dane syntetyczne, środowiska, RL

| Priorytet | Repozytorium | Zastosowanie |
| --- | --- | --- |
| P0 | [NVIDIA-NeMo/DataDesigner](https://github.com/NVIDIA-NeMo/DataDesigner) | Syntetyczne dane, walidatory, połączenie z narzędziami i ślady interakcji MCP |
| P1 | [NVIDIA-NeMo/Curator](https://github.com/NVIDIA-NeMo/Curator) | Czyszczenie, filtrowanie i deduplikacja zbiorów multimodalnych |
| R&D | [allenai/dolma](https://github.com/allenai/dolma) | Duże potoki przetwarzania korpusów treningowych |
| P2 | [argilla-io/distilabel](https://github.com/argilla-io/distilabel) | Dane instruktażowe i preferencyjne; zweryfikować aktywność maintainerów |
| P0 | [RUC-NLPIR/Agent-World](https://github.com/RUC-NLPIR/Agent-World) | Stanowe, wykonywalne środowiska narzędzi oraz weryfikowalne zadania |
| P1 | [microsoft/agent-lightning](https://github.com/microsoft/agent-lightning) | Uczenie agentów na podstawie ich śladów, nagród i wyników |
| P1 | [rllm-org/rllm](https://github.com/rllm-org/rllm) | Agentic RL z testami i środowiskami wykonywalnymi |
| P2 | [LegoX/Lego-RL](https://github.com/LegoX/Lego-RL) | RL dla agentów kodujących i danych trajektorii |
| P0 | [PrimeIntellect-ai/verifiers](https://github.com/PrimeIntellect-ai/verifiers) | Definicje środowisk, funkcji nagrody i weryfikatorów |
| P0 | [ServiceNow/BrowserGym](https://github.com/ServiceNow/BrowserGym) | Kontrolowane benchmarki zadań przeglądarkowych |
| P1 | [UKGovernmentBEIS/inspect_ai](https://github.com/UKGovernmentBEIS/inspect_ai) | Rygorystyczne ewaluacje i testowanie zachowania agentów |

## Wideo, world models i montaż

| Priorytet | Repozytorium | Zastosowanie |
| --- | --- | --- |
| P0 | [CYWang735/Video-Coder](https://github.com/CYWang735/Video-Coder) | Agent buduje scenę Blender Python, renderuje draft i steruje generatorem wideo |
| P0 | [Lightricks/LTX-2](https://github.com/Lightricks/LTX-2) | Rodzina LTX, generowanie wideo/audio, modele i workflowy |
| P0 | [Comfy-Org/comfy-mcp](https://github.com/Comfy-Org/comfy-mcp) | Sterowanie ComfyUI przez MCP i monitorowanie zadań |
| R&D | [Westlake-AGI-Lab/WorldinWorld](https://github.com/Westlake-AGI-Lab/WorldinWorld) | Zmiana trajektorii kamery i rekonstrukcja nowych ujęć z wideo |
| R&D | [TencentARC/VerseCrafter](https://github.com/TencentARC/VerseCrafter) | Sterowanie geometrią 4D, kamerą i ruchem obiektów |
| R&D | [microsoft/World-R1](https://github.com/microsoft/World-R1) | RL dla modeli wideo z geometrią i oceną trajektorii kamery |
| P1 | [NVIDIA/Cosmos](https://github.com/NVIDIA/Cosmos) | Modele świata, warunkowanie symulacjami i geometrią |
| P1 | [DepthAnything/Video-Depth-Anything](https://github.com/DepthAnything/Video-Depth-Anything) | Spójna czasowo estymacja głębi materiału wideo |
| P0 | [Vchitect/VBench](https://github.com/Vchitect/VBench) | Benchmark jakości, ruchu i zgodności wygenerowanego wideo |
| P0 | [remotion-dev/remotion](https://github.com/remotion-dev/remotion) | Programowy montaż, napisy, animacje i render końcowy |

## Agenci głosowi

| Priorytet | Repozytorium | Zastosowanie |
| --- | --- | --- |
| P1 | [pipecat-ai/pipecat](https://github.com/pipecat-ai/pipecat) | Streaming agentów głosowych i telefonicznych |
| P1 | [livekit/agents](https://github.com/livekit/agents) | Agenci realtime w audio/wideo |

## Agent harness, browser, durable workflows

| Priorytet | Repozytorium | Zastosowanie |
| --- | --- | --- |
| P0 | [OpenHands/OpenHands](https://github.com/OpenHands/OpenHands) | Runtime programistycznego agenta z narzędziami i środowiskiem |
| P0 | [langchain-ai/deepagents](https://github.com/langchain-ai/deepagents) | Planowanie, delegowanie, skille, pamięć i subagenci |
| P1 | [temporalio/temporal](https://github.com/temporalio/temporal) | Trwałe workflowy, retry, idempotencja i wznawianie |
| P1 | [vercel-labs/agent-browser](https://github.com/vercel-labs/agent-browser) | Skryptowalny agent przeglądarkowy; tylko sandbox i allowlist |

## GPU, inferencja i optymalizacja

| Priorytet | Repozytorium | Zastosowanie |
| --- | --- | --- |
| P0 | [skypilot-org/skypilot](https://github.com/skypilot-org/skypilot) | Orkiestracja wynajętych GPU; wybór operatora, przerywanie i koszty |
| P1 | [dstackai/dstack](https://github.com/dstackai/dstack) | Zadania GPU i usługi modeli na różnych chmurach |
| R&D | [OpenBMB/ForgeKernel](https://github.com/OpenBMB/ForgeKernel) | Agent profiluje i ewolucyjnie poprawia jądra GPU |
| P1 | [Dao-AILab/flash-attention](https://github.com/Dao-AILab/flash-attention) | Optymalizowane implementacje attention |
| R&D | [deepseek-ai/DeepGEMM](https://github.com/deepseek-ai/DeepGEMM) | GPU kernels, zwłaszcza GEMM i MoE |
| P1 | [flashinfer-ai/flashinfer](https://github.com/flashinfer-ai/flashinfer) | Jądra do inferencji i zarządzania KV cache |
| P2 | [linkedin/Liger-Kernel](https://github.com/linkedin/Liger-Kernel) | Oszczędniejsze operatory dla treningu/post-treningu |
| R&D | [kvcache-ai/Mooncake](https://github.com/kvcache-ai/Mooncake) | Rozproszone serwowanie, rozdzielenie prefill/decode i cache |
| R&D | [fthrvi/nakshatra](https://github.com/fthrvi/nakshatra) | Heterogeniczna inferencja modelu rozłożona na wiele maszyn |

## Ewaluacja, pamięć, tracing

| Priorytet | Repozytorium | Zastosowanie |
| --- | --- | --- |
| P0 | [stanfordnlp/dspy](https://github.com/stanfordnlp/dspy) | Programatyczna optymalizacja promptów i pipeline'ów LLM |
| P0 | [gepa-ai/gepa](https://github.com/gepa-ai/gepa) | Feedback-driven ewolucyjna optymalizacja instrukcji |
| P1 | [getzep/graphiti](https://github.com/getzep/graphiti) | Pamięć wiedzy i relacji z komponentem czasowym |
| P1 | [letta-ai/frontiermemory](https://github.com/letta-ai/frontiermemory) | Ewaluacja czy pamięć poprawia późniejsze wykonywanie zadań |
| P2 | [hamza-dev-tech/agent-memory-bench](https://github.com/hamza-dev-tech/agent-memory-bench) | Benchmark pamięci, odporności i kosztów |
| P0 | [langfuse/langfuse](https://github.com/langfuse/langfuse) | Ślady agentów, metryki, ewaluacje i koszt |
| P0 | [promptfoo/promptfoo](https://github.com/promptfoo/promptfoo) | Testy regresji, prompt injection i bezpieczeństwa agentów |

## Interpretowalność i łączenie modeli

| Priorytet | Repozytorium | Zastosowanie |
| --- | --- | --- |
| R&D | [TransformerLensOrg/TransformerLens](https://github.com/TransformerLensOrg/TransformerLens) | Interpretowalność i interwencje w aktywacjach transformerów |
| R&D | [ndif-team/nnsight](https://github.com/ndif-team/nnsight) | Inspekcja i eksperymentalna edycja aktywacji modelu |
| R&D | [arcee-ai/mergekit](https://github.com/arcee-ai/mergekit) | Scalanie wag kompatybilnych modeli i ewaluacja kombinacji |

## Licencje i pochodzenie

- HyperAgents: oznaczenie CC BY-NC-SA 4.0 w README — **NIE zakładać komercyjnego prawa użycia**.
- ShinkaEvolve, Data Designer i ForgeKernel: README deklarują Apache-2.0 dla repozytorium; inne licencje mogą obowiązywać modele, wagi i datasety.
- Agent-World: README odsyła do MIT; dane treningowe i benchmarkowe analizować osobno.
- LTX i Video-Coder: nie mylić licencji kodu z licencjami wag, modelami bazowymi, datasetami i wynikami generowania.
- CUDA/FlashAttention/DeepGEMM/ForgeKernel: zależność od konkretnej generacji GPU; testować na wynajmowanej konfiguracji, bez przenoszenia benchmarku 1:1.
- Wiele projektów badawczych wymaga 32–80+ GB VRAM lub większych klastrów do pełnego treningu. Konkretne wymagania potwierdzić dla commit SHA i konfiguracji.

## Co weryfikować przed wdrożeniem

1. Commit SHA/tag, data i status projektu, CI, otwarte luki, autorzy i signed releases.
2. Licencje: kod + wagi + dane + checkpointy + modele bazowe + ograniczenia komercyjne.
3. Dependency lockfiles, obrazy kontenerów/digest, możliwość wykonania arbitralnego kodu.
4. Sprzęt/VRAM, czas, realna cena GPU z narzutami, region i retencja.
5. Weryfikowalne benchmarki, rozdzielenie danych treningowych od testowych, zaufane funkcje nagrody.
6. Czy projekt rzeczywiście integruje się przez API/CLI/MCP czy wymaga przepisywania.
7. Privacy: tylko dane syntetyczne; żadnych aktów, PESEL, KW, tokenów i screenshotów NotarAI.
8. Bezpośrednia instalacja z HEAD jest zabroniona w środowisku posiadającym dostęp do produkcji.

Maszynowo odczytywalny odpowiednik: [catalog.json](catalog.json). Wpisy P0 są priorytetami badawczymi, **nie** zatwierdzonymi zależnościami produkcyjnymi.
