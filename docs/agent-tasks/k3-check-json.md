# K3 - check --json

Zakres: tools/agent_factory/salad_vllm.py oraz test_salad_vllm_check.py (nowy).

Dodaj do polecenia `check` flagę `--json`. Z flagą polecenie wypisuje jeden obiekt JSON:
{"gpu": [{"name": ..., "vram": ..., "usd_h": ...}, ...], "groups": ["nazwa", ...]} i nic poza nim.
Bez flagi wynik ma pozostać taki jak dotąd. Dodaj test, który podmienia gpu_classes i our_groups
(monkeypatch), wywołuje cmd_check i sprawdza oba tryby przez capsys. Bez połączeń sieciowych.

Sprawdzenie: python -m pytest -q test_salad_vllm_check.py

Zasady: tylko dane syntetyczne; nie czytaj dane/, .env ani żadnych kluczy; bez sieci i bez instalowania paczek. Zmieniaj wyłącznie wymienione pliki. Na koniec podaj: zmienione pliki, wynik testów, ograniczenia.
