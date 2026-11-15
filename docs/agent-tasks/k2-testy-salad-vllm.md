# K2 - testy jednostkowe salad_vllm

Zakres: nowy plik test_salad_vllm.py (w katalogu głównym repo). Nie zmieniaj tools/agent_factory/salad_vllm.py.

Napisz testy pytest dla tools/agent_factory/salad_vllm.py bez żadnych połączeń sieciowych:
1. group_path odrzuca nazwę bez przedrostka notarai-koder i nazwę z niedozwolonymi znakami, przyjmuje poprawną.
2. create_body: polecenie zawiera --host :: , port 8000, --served-model-name koder i wybrany parser;
   networking ma auth True i oba limity czasu 100000; zmienna KODER_DEADLINE jest w formacie ISO.
3. load_keys: brak klucza daje SaladError; wartości z pliku wskazanego przez NOTARAI_SALAD_ENV są czytane,
   a zmienne środowiskowe mają pierwszeństwo (użyj monkeypatch i tmp_path, kluczy zmyślonych).
4. gpu_classes z podmienioną funkcją api: czyta VRAM z nazw "RTX 5090 (32 GB)" i "AMD RX 7900 XTX (24GB)",
   pomija klasy bez ceny dla danego priorytetu, sortuje malejąco po VRAM.

Sprawdzenie: python -m pytest -q test_salad_vllm.py

Zasady: tylko dane syntetyczne; nie czytaj dane/, .env ani żadnych kluczy; bez sieci i bez instalowania paczek. Zmieniaj wyłącznie wymienione pliki. Na koniec podaj: zmienione pliki, wynik testów, ograniczenia.
