# Agent Forge - local model + benchmark (v2)

Status: kod adaptera istnieje, testy protokołu na lokalnym sztucznym serwerze. Żaden rzeczywisty model, GPU ani sesja produkcyjna nie są używane w CI.

## Mechanika

- tools/agent_factory/forge_llm.py: klient OpenAI Chat Completions do lokalnego 127.0.0.1, bez przekierowań, z limitami czasu/odpowiedzi i ścisłym walidatorem JSON.
- tools/agent_factory/forge_llm_cli.py: ręczny adapter wyłącznie do zadań syntetycznych. Dwa jawne warunki opt-in.
- tools/agent_factory/forge_benchmark.py: trzy niezależnie oceniane zadania (sum/count/max), idempotencja i raport agregujący.
- test_agent_forge_llm.py: testy deny-by-default, SSRF, protokołu HTTP na mock-serwerze, replay i błędnych odpowiedzi.

## Bezpłatne testy

python -m tools.agent_factory.forge_benchmark --prefix manual-baseline

python -m tools.agent_factory.forge_benchmark --compare

python -m pytest -q test_agent_forge_llm.py test_agent_forge.py

## Ręczne połączenie z już uruchomionym modelem

Dopiero po odrębnym zatwierdzeniu kosztów, regionu i serwera operator może ręcznie ustawić zmienną środowiskową AGENT_FORGE_ALLOW_LOCAL_MODEL na I_APPROVE_SYNTHETIC_LOOPBACK_ONLY i uruchomić:

python -m tools.agent_factory.forge_llm_cli --run-id manual-001 --model local-model --endpoint http://127.0.0.1:8000/v1 --allow-local-model

Nie uruchamiać tego w CI. Tunel loopback nie dowodzi, w jakiej jurysdykcji działa GPU. Żaden kod nie potrafi obecnie egzekwować limitu pieniężnego GPU po stronie dostawcy. Kosty tych wywołań mają wartość null (niezmierzone), nie zero.

Adapter nie wykonuje narzędzi, kodu ani zewnętrznego pluginu. To pierwszy prawdziwy protokół wymiany wiadomości z modelem, nie pełny agent programistyczny. Niezmienność logów SQLite nie jest kryptograficznie dowiedziona wobec administratora hosta. Zasady NotarAI/RODO i nadrzędny CLAUDE.md pozostają wiążące.
