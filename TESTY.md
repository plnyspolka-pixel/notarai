# Testy pieczapp

Testy automatyczne dla walidatorów, wykrywania pól i przepływu z Bedrock.

## Uruchomienie

### Windows

Dwuklik w `uruchom_testy.bat` lub w konsoli:

```cmd
uruchom_testy.bat
```

### Ręcznie (po skonfigurowaniu środowiska)

```bash
# Aktywuj środowisko wirtualne
.venv\Scripts\activate

# Uruchom wszystkie testy
pytest

# Uruchom konkretny plik testów
pytest test_walidacja.py

# Uruchom z większą szczegółowością
pytest -v

# Uruchom konkretny test
pytest test_walidacja.py::TestPesel::test_pesel_poprawny_xx_wiek

# Pokaż print'y nawet gdy test przechodzi
pytest -s
```

## Struktura testów

```
test_walidacja.py    - Testy walidatorów (PESEL, NIP, KW, kwoty)
test_dokumenty.py    - Testy wykrywania pól ze wzoru i konwersji dokumentów
test_bedrock.py      - Testy przepływu z atrapą Bedrock (bez prawdziwego modelu)
test_ekw.py          - Księga wieczysta z EKW przez dostawcę: atrapa klienta HTTP, zapis do sprawy, ślad audytowy, endpointy
pytest.ini           - Konfiguracja pytest
generuj_testowe.py   - Pomocniczy skrypt do generowania poprawnych numerów testowych
```

## Pokrycie testów

### test_walidacja.py

- ✅ PESEL: poprawne numery (XIX, XX, XXI, XXII wiek)
- ✅ PESEL: niepoprawne sumy kontrolne
- ✅ PESEL: niepoprawne daty (błędne miesiące, dni)
- ✅ PESEL: daty w przyszłości
- ✅ PESEL: płeć (mężczyzna/kobieta)
- ✅ PESEL: formatowanie (myślniki, spacje)
- ✅ NIP: poprawne numery i sumy kontrolne
- ✅ NIP: przypadek suma % 11 == 10
- ✅ KW: poprawne numery z cyfrą kontrolną
- ✅ KW: różne formaty, wielkość liter, spacje
- ✅ Kwoty: różne formaty, separatory, waluty
- ✅ Automatyczne dobieranie walidatora po nazwie pola

### test_dokumenty.py

- ✅ Wykrywanie placeholder'ów {{nazwa}} i [NAZWA]
- ✅ Mieszane formaty, spacje, duplikaty
- ✅ Zachowanie kolejności pól
- ✅ Polskie znaki w nazwach
- ✅ Wieloliniowe wzory
- ✅ Odczyt wzoru z .txt i .docx
- ✅ Eksport projektu do .docx

### test_bedrock.py

- ✅ Przepływ ekstrakcji danych ze skanów (atrapa)
- ✅ Odczyt z brakami i rozbieżnościami
- ✅ Parsowanie JSON z markdown (```json...```)
- ✅ Przepływ generowania projektu dokumentu
- ✅ Obsługa wielu stron
- ✅ Struktura wywołania API

## Zasady pisania testów

1. **Nie wywołuj prawdziwego modelu** - używaj mocków (pytest-mock)
2. **Nie loguj danych osobowych** - w testach używaj tylko przykładowych danych
3. **Testy muszą być deterministyczne** - zawsze ten sam wynik
4. **Nazwy testów opisują co testują** - `test_pesel_xix_wiek`, nie `test_1`
5. **Grupuj testy w klasy** - `TestPesel`, `TestNip`, itp.
6. **Jeden test = jedna asercja (tam gdzie to możliwe)**
7. **Używaj poprawnych numerów kontrolnych** - sprawdź `generuj_testowe.py`

## Dodawanie nowych testów

Gdy dodajesz nową funkcjonalność do aplikacji:

1. Napisz test PRZED implementacją (TDD)
2. Sprawdź czy test nie przechodzi (czerwony)
3. Zaimplementuj funkcjonalność
4. Sprawdź czy test przechodzi (zielony)
5. Refaktoryzuj jeśli potrzeba

## Debugowanie testów

```bash
# Zatrzymaj się na pierwszym błędzie
pytest -x

# Pokaż lokalne zmienne przy błędzie
pytest -l

# Uruchom tylko testy, które nie przeszły ostatnim razem
pytest --lf

# Uruchom pdb przy błędzie
pytest --pdb
```

## Continuous Integration

Testy są uruchamiane automatycznie przed każdym:
- Commitem (pre-commit hook - do skonfigurowania)
- Pull requestem (GitHub Actions - do skonfigurowania)
- Deploymentem (do skonfigurowania)

## Problemy

**Import Error przy pytest**
```
Rozwiązanie: Upewnij się, że jesteś w środowisku wirtualnym:
.venv\Scripts\activate
```

**Testy nie znajdują modułów**
```
Rozwiązanie: pytest uruchamiaj z głównego katalogu projektu,
nie z podkataloga
```

**Mock nie działa**
```
Rozwiązanie: Sprawdź ścieżkę do mockowanej funkcji:
@patch("bedrock._klient")  # ✅ poprawnie
@patch("boto3.client")      # ❌ za wysoko
```

## TODO

- [ ] Dodać testy integracyjne z prawdziwym Bedrock (tylko środowisko dev)
- [ ] Testy wydajności (ile czasu zajmuje przetworzenie 40 stron)
- [ ] Testy bezpieczeństwa (czy dane osobowe nie wyciekają do logów)
- [ ] Coverage report (pytest-cov)
- [ ] Testy dla przyszłych funkcji: rejestry, formularze, audit log
