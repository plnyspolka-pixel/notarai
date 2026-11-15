# Agent Forge — offline job scheduler v1

Moduły: tools/agent_factory/forge_scheduler.py i forge_scheduler_cli.py.

Zadania są trwałe w SQLite, posiadają idempotency ID i hash manifestu, atomową dzierżawę lease, maksymalnie 3 próby, anulowanie, status dead-letter po przekroczonym czasie i pause/resume (operator kill switch dla nowych claimów i zatwierdzenia zakończenia aktywnych jobów).

Działa wyłącznie adapter deterministic-fixture. Nie uruchamia modeli, przeglądarek, kontenerów, chmury ani skryptów; żaden worker nie działa w tle. CLI wykona jeden tick na polecenie.

Demonstracja bez płatnych usług:

python -m tools.agent_factory.forge_scheduler_cli submit --job-id synthetic-001

python -m tools.agent_factory.forge_scheduler_cli tick

python -m tools.agent_factory.forge_scheduler_cli list

python -m tools.agent_factory.forge_scheduler_cli pause

Użycie zewnętrznych workerów wymaga separacji uprawnień i izolacji VM/container, budżetów poza bazą, whitelisted egress, pomiaru rachunku dostawcy i operator approval. Pause nie jest sygnałem do zabicia już wykonywanego procesu; obecny tick jest krótki i offline. SQLite jest przeznaczone do prototypu jednego hosta, nie do wielowęzłowego klastra. Wyniki zadania weryfikuje dotychczasowy forge_core.py.

Testy: test_agent_forge_scheduler.py.
