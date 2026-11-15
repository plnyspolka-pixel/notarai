# Agent Factory Research Pack (NotarAI)

**Gałąź:** feature/secure-agent-factory-20261115  
**Data przeglądu:** 2026-11-15  
**Status:** dokumentacja badawcza; badania i lokalne testy; bez płatnego GPU, zadań produkcyjnych i wdrożeń.

Ten katalog zbiera odkrycia z rozmów o agentach programistycznych, przeglądarkowych, głosowych, filmowych, autonomicznym R&D, ewolucji agentów, danych syntetycznych, RL i optymalizacji GPU. Stanowi uzupełnienie [Secure Agent Factory MVP](../agent-factory.md), a nie osobną autoryzację do działań.

## Pliki

- [catalog.md](catalog.md): pierwotny katalog 55 repozytoriów; aktualny kompletny katalog maszynowy w catalog.json.
- [ACADEMIC_REVIEW_2026-11-15.md](ACADEMIC_REVIEW_2026-11-15.md): krytyczny przegląd badań, ablacje i metodologia.
- [academic-evidence.json](academic-evidence.json): rekordy 24 publikacji i benchmarków, siła dowodów oraz ograniczenia.
- [catalog.json](catalog.json): katalog maszynowy do filtrowania i automatycznej walidacji.
- [experiments.md](experiments.md): kolejka eksperymentów z metrykami i granicami ryzyka.
- [architecture.md](architecture.md): docelowe moduły i przepływ danych.
- [CLAUDE_CODE_TASK.md](CLAUDE_CODE_TASK.md): instrukcja dla Claude Code: audyt, wybór, testy i prototypy.
- [.claude/skills/agent-research-lab/SKILL.md](../../.claude/skills/agent-research-lab/SKILL.md): lokalna procedura badań.

## Priorytet startowy

1. **P0 bezpieczeństwo:** izolacja workerów, kontrola egress, limity GPU, redakcja logów, niezależny benchmark i kontrola dostępu do narzędzi — zgodnie z nadrzędnym CLAUDE.md.
2. **Agent runtime:** Prime Agent/Deep Agents/OpenHands jako **alternatywy**, nie trzy frameworki naraz.
3. **Research loop:** autoresearch + ShinkaEvolve lub DSPy/GEPA dla weryfikowalnych zmian.
4. **Dataset/Gym:** Agent-World + NeMo Data Designer + Verifiers; syntetyczne przypadki, żadnych danych klientów.
5. **Video:** Comfy MCP + LTX; równoległa ścieżka badań Video-Coder/Blender i VBench; finalizacja przez Remotion.
6. **GPU:** SkyPilot; mierz koszt zaakceptowanego zadania, a nie samą cenę GPU-h.
7. **Self-modification:** HyperAgents/SkillOS/ForgeKernel wyłącznie jako eksperymenty w odłączonym środowisku, bez dostępu do repozytoriów produkcyjnych i sekretów.

## Metodologia

Przed jakimkolwiek treningiem zbierz bazowe wyniki agentów na wspólnych, odtwarzalnych zadaniach. Wyniki winny uwzględniać: success@1, human review minutes, regresje, PLN na zaakceptowany task, GPU-seconds, tokeny, P50/P95 latency, stabilność po awarii i naruszenia polityk. Każda próba ma zapisać commit, konfigurację, model, dataset hash, seed, metryki i kryteria akceptacji.

Projekt NotarAI ma publiczne repozytorium. Nigdy nie umieszczaj w nim danych osobowych, prawdziwych zrzutów ekranu, sekretów ani surowych sesji. Zasady RODO, eu-central-1 i dostępność modelu w zatwierdzonej trasie Bedrock mają nadrzędność.

**Brak automatycznego merge, deploy, płatności GPU i instalowania niezweryfikowanych repozytoriów.**
