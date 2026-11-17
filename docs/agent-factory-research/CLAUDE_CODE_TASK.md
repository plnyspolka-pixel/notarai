# Claude Code — research handoff: Agent Factory / Mad Scientist Lab

**READ FIRST:** repo CLAUDE.md, docs/agent-factory.md, docs/claude-code-handoff-agent-factory.md, then this directory. Branch feature/secure-agent-factory-20261115. Nie zmieniaj aplikacji NotarAI w ramach tego polecenia bez osobnego scope.

Cel: przekształcić katalog badań w minimalny, bezpieczny, porównywalny system eksperymentów, nie w przypadkową instalację 50 repozytoriów.

## Phase A — due diligence (wykonaj od razu, bez GPU i API)

1. Zweryfikuj ponownie catalog.json: API GitHub, latest tag/commit, aktualność, README, license SPDX, licencje wag/danych, podstawowe CI, znane archiwizacje.
2. Zweryfikuj prawdziwą obecność kodu/artefaktów — istnienie repo nie oznacza dostępnych wag ani reprodukowalnego treningu.
3. Wybierz po jednym projekcie reprezentującym: harness (OpenHands LUB Prime Agent), evolution (ShinkaEvolve LUB DSPy/GEPA), synthetic gym (Agent-World/Verifiers), video (Video-Coder + Comfy MCP, jeśli zgodne).
4. Przygotuj ADR z alternatywami, macierzą kosztów i licencji. Oznacz każde twierdzenie: verified, author-claimed, proposed, tested.
5. Nie uruchamiaj instalatorów z internetu bez pinned commit SHA, przeglądu dependencies i izolacji.

## Phase B — reproducible evaluation harness (CPU only by default)

- Zaimplementuj wersjonowany manifest eksperymentu, walidację schematu, scoring obiektywny, parser kosztów i raport porównawczy.
- Zadania syntetyczne; testy poza workspace agenta, z blokadą edycji.
- Zautomatyzuj testy negatywne: prompt injection, dostęp do .env, path traversal, exfiltration, modyfikowanie testów i polityk, nieautoryzowana akcja.
- Jedna próba przechodzi cykl task -> sandbox -> independent evaluator -> report -> human review. Wszystkie narzędzia wychodzą fail-closed.

## Phase C — eksperymenty, ale tylko po zgodzie

- EXP-01 najpierw; następnie EXP-02 i EXP-03. Media/GPU według kolejki experiments.md.
- Płatne GPU, nowe chmury, transfer danych i komercyjne wykorzystanie wag wymagają operator approval, cap PLN, określonego regionu, stop-time i teardown.
- Zero domyślnych kosztów. Nie używaj kont AWS produkcyjnych. Nie odsłaniaj vLLM publicznie.
- PR z raportem: faktyczne testy, licencje, luki, koszt, benchmark w kilku losowaniach, rekomendacje dalszych badań.
- Zero samowolnego wdrożenia, merge, uruchamiania autoryzowanych kontaktów czy publikacji.

## P0 deliverable

W pełni działające **lokalne** demo z syntetycznym zadaniem, manifestem, niezależnym evaluator'em i zero-cost mode. Jeśli brakuje narzędzia, udokumentuj blocker zamiast symulować sukces.

Zawsze odróżniaj: research docs delivered / code implemented / tests passed / cloud provisioned / production deployed.
