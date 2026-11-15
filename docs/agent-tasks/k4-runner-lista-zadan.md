# K4 - runner: lista zadań

Zakres: tools/agent_factory/runner.py i test_agent_factory.py.

Dodaj podpolecenie `tasks`, które wypisuje posortowane nazwy plików *.md z docs/agent-tasks
(po jednej w wierszu, ścieżka względem repo z ukośnikami /), pomijając dowiązania symboliczne i pliki
większe niż MAX_TASK_BYTES. Wydziel logikę do funkcji list_tasks(repo: Path) -> list[str] i dodaj dla niej
test na tmp_path (plik poprawny, plik za duży, plik z innym rozszerzeniem). Istniejące testy mają przechodzić.

Sprawdzenie: python -m pytest -q test_agent_factory.py

Zasady: tylko dane syntetyczne; nie czytaj dane/, .env ani żadnych kluczy; bez sieci i bez instalowania paczek. Zmieniaj wyłącznie wymienione pliki. Na koniec podaj: zmienione pliki, wynik testów, ograniczenia.
