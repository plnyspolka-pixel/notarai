# K1 - test dowiązań na Windows

Zakres: tylko test_agent_factory.py.

Test `test_task_confined_to_committed_subtree` na Windows bez uprawnień do tworzenia dowiązań
symbolicznych kończy się błędem OSError (WinError 1314) zamiast sprawdzać logikę. Popraw test tak,
żeby część wymagająca dowiązania była pomijana (pytest.skip) tylko wtedy, gdy system odmawia
utworzenia dowiązania, a pozostałe asercje testu nadal się wykonywały. Nie zmieniaj runner.py.

Sprawdzenie: python -m pytest -q test_agent_factory.py - wszystko zielone albo pominięte.

Zasady: tylko dane syntetyczne; nie czytaj dane/, .env ani żadnych kluczy; bez sieci i bez instalowania paczek. Zmieniaj wyłącznie wymienione pliki. Na koniec podaj: zmienione pliki, wynik testów, ograniczenia.
