# Agent Forge — executable offline foundation

**Status:** działający szkielet badawczy, bez połączeń z modelami/GPU/produkcyjnym NotarAI.

Zawiera:
- tools/agent_factory/forge_core.py — polityka deny-by-default, jawny adapter fixture, kontrola danych syntetycznych, niezależny evaluator i SQLite registry z idempotencją i hash-linked event log.
- tools/agent_factory/forge_cli.py — CLI doctor/demo/report.
- docs/agent-factory-research/fixtures/ — syntetyczne zadanie i osobna rubryka z SHA-256 zadania.
- test_agent_forge.py — regresje bezpieczeństwa, zakaz wywołań zewnętrznych, trwałość i test pełnej ścieżki.
- docs/agent-factory-research/catalog.json — 55 zweryfikowanych linków repozytoriów do osobnych badań.

Szybkie lokalne sprawdzenie (Python 3.11+, bez dodatkowych zależności):

    python -m tools.agent_factory.forge_cli doctor
    python -m tools.agent_factory.forge_cli demo --run-id sum-demo-001
    python -m tools.agent_factory.forge_cli report
    python -m pytest -q test_agent_forge.py

Runtime zapisuje lokalny plik .agent-forge/runs.sqlite3 (zignorowany przez git). Nie loguje pełnej zawartości datasetu i nie zapisuje kodu generowanego przez model. Wynik demonstracji liczy sumę listy liczb w zaufanym, wbudowanym adapterze. To test control plane, **nie działający jeszcze agent programistyczny**.

Granice obecnej wersji:
1. Nie wykonuje kodu niezaufanego — wbudowany adapter nie jest sandboxem.
2. Zewnętrzne modele, ComfyUI, SkyPilot, chmury i płatne GPU są celowo zablokowane.
3. Lokalny hash-chain pozwala wykryć proste manipulacje historią, lecz nie chroni przed administratorem, który zmieni całą bazę.
4. Rubryka ma ograniczony język operacji, aby nie dopuścić eval/exec dostarczonych przez model.
5. Do modeli zewnętrznych potrzebne są prawdziwa izolacja, brama uprawnień, budżety, audyt i testy z niezależnym weryfikatorem.
6. Nie ma benchmarków potwierdzających przewagę nad modelami komercyjnymi; wyniki wymagają rzeczywistych pomiarów.

Bezpieczeństwo i ograniczenia danych obowiązują zgodnie z CLAUDE.md i docs/agent-factory.md. Brak dostępu do danych klientów, AWS, produkcji, browser sessions, płatności i wdrożeń.
