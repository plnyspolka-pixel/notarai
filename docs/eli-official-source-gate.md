# NotarAI — bramka oficjalnych źródeł ELI (wersja badawcza)

Status: **R&D, tylko do odczytu, bez wpięcia w produkcyjny generator aktów**. 22 listopada 2026.

## Problem

API ELI Sejmu podaje dla wielu aktów wyłącznie PDF. Metadane `textHTML=false` i `textPDF=true` **nie oznaczają braku aktu**. W szczególności urzędowe metadane `DU/2026/1243` wskazują `textHTML=false, textPDF=true`; dokument jest dostępny pod `/text.pdf`.

Źródła: [oficjalna dokumentacja ELI](https://api.sejm.gov.pl/eli_pl.html), [metadane DU/2026/1243](https://api.sejm.gov.pl/eli/acts/DU/2026/1243), [urzędowy PDF](https://api.sejm.gov.pl/eli/acts/DU/2026/1243/text.pdf).

## Zakres wdrożonego komponentu

- `tools/eli_source/eli_gate.py`: identyfikatory `DU/rok/poz` lub `MP/rok/poz`, walidacja metadanych ELI, wybór HTML/PDF, pobieranie z jedynego dopuszczonego hosta `api.sejm.gov.pl`, kontrola MIME i rozmiaru, SHA-256 pobranych bajtów, blokada przekierowań.
- `tools/eli_source/quote_gate.py`: sprawdzenie, czy **dosłowny** fragment tekstu znajduje się w pobranym urzędowym HTML (ignoruje treść skryptów i nagłówków). Brak dopasowania to odmowa. Zgodność oznacza tylko występowanie w konkretnym opublikowanym dokumencie — **nie** potwierdza obowiązywania na określony dzień.
- `tools/eli_source/__main__.py`: CLI drukujące wyłącznie metadane i sumy SHA-256, nigdy tekst całego aktu ani cytatu.
- `test_eli_source_gate.py`: testy bez sieci, m.in. odrzucenie zmienionego identyfikatora, redirectu na inny host, niezgodnego MIME, nieprawidłowych PDF-ów, prób pobierania niezadeklarowanego formatu i fałszywych cytatów.

## Uruchomienie ręczne (publiczne źródła, bez dokumentów kancelarii)

```bash
python -m tools.eli_source DU/2026/1243
# Wynik: PDF_EXTRACTION_REQUIRED, dokument urzędowy do pobrania /text.pdf.

python -m tools.eli_source DU/2026/1243 --fetch-format pdf
# Pobiera urzędowy plik do RAM, sprawdza %PDF-, drukuje sumę SHA-256.

# Dla aktu udostępniającego HTML (przykład historyczny):
python -m tools.eli_source DU/2020/1 --fetch-format html
# Jeżeli sprawdzasz konkretny cytat, zapisz go w pliku UTF-8:
python -m tools.eli_source DU/2020/1 --fetch-format html --quote-file fragment.txt
```

Testy offline:

```bash
PYTHONPATH=. python -m pytest -q test_eli_source_gate.py
```

## Inwarianty bezpieczeństwa

1. **Zero danych spraw klientów**. Wyłącznie publiczne przepisy prawa; bez sekretów, tokenów, wewnętrznych aktów i wyszukiwania dowolnych URL.
2. Brak `eval`, przeglądarki, JavaScript, OCR lub wywołań modelu. Parser HTML jedynie odczytuje tekst.
3. Adresy są konstruowane z kontrolowanego identyfikatora, tylko `https://api.sejm.gov.pl/eli/acts/...`, przekierowania HTTP zablokowane **przed ich wykonaniem**.
4. Maksimum 256 KiB metadanych, 8 MiB HTML, 24 MiB PDF; timeout 8 s.
5. Zapis dowodu pochodzenia: URL urzędowy i SHA-256 bajtów; brak danych dokumentu w logach. Podsumowanie nie zawiera tekstu aktu ani cytatu.
6. Bramka nie sprawdza nowelizacji, przepisów przejściowych, obowiązywania, utraty mocy, orzeczeń TK ani rozbieżności między tekstami jednolitymi; pole `legal_validity_on_selected_date_verified=false` jest zawsze fałszywe.
7. Nie wolno na podstawie samego `FOUND_IN_OFFICIAL_HTML` oznaczać podstawy prawnej jako aktualnej.

## Następne PR-y (jeszcze nie wykonane)

- **PDF → tekst**: adapter `eli2md` lub własny konwerter w osobnej izolacji; do każdej jednostki redakcyjnej przechowywać SHA urzędowego PDF, oznaczenie wyodrębnionej strony i status jakości. OCR bez pełnej walidacji nie może przejść jako źródło pierwotne.
- **Prawo na dzień X**: chronologia zmian, teksty jednolite, wejście w życie poszczególnych jednostek oraz wyraźne oznaczenie przypadków wymagających kontroli prawnika.
- **Kontekst aktu**: ustalenie, czy `DU/rok/poz` jest pierwotną ustawą, obwieszczeniem tekstu jednolitego czy nowelizacją — różne konsekwencje prawne.
- **Integracja z generatorem**: dopiero po testach na fikcyjnych wzorach dokumentów, review bezpieczeństwa i akceptacji notariusza.

## Kryteria odbioru PR

- Testy źródeł przechodzą offline; istniejąca aplikacja pozostaje nietknięta.
- Dla `DU/2026/1243` wybór PDF zamiast nieistniejącego HTML.
- Dla `DU/2020/1` możliwość pobrania HTML i sprawdzenia dosłownego cytatu.
- Zły URL, błędny MIME, przekierowanie, nadmiar bajtów, brak cytatu: fail-closed.
- Każdy raport jawnie mówi, że nie zweryfikowano stanu prawnego na datę.
- Uruchomienie na produkcji dopiero przez oddzielny PR i audyt.