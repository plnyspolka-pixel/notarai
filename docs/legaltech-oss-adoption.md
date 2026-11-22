# NotarAI — kontrolowane wykorzystanie publicznego kodu LegalTech

**Stan R&D: 22.11.2026.** Nie jest to dowód zgodności z RODO ani audyt bezpieczeństwa produkcyjnego.

## Zakres PR

Gałąź zawiera niezależny, **offline** benchmark anonimizacji z 22 fikcyjnymi przykładami: polskie odmiany nazwisk, PESEL/NIP/REGON/KRS/KW, IBAN, telefony, e-maile, adresy, sygnatury i frazy, których nie wolno usuwać. Tester nie instaluje ani nie uruchamia kodu zewnętrznych dostawców.

Nie zmienia app.py, bedrock.py, pomocnik/, AWS ani RejNET, nie wysyła danych przez sieć i nie używa rzeczywistych aktów. Nawet idealny wynik daje status REVIEW_REQUIRED, a flaga production_approved jest zawsze false.

## Przebieg porównania

Na izolowanym, pozbawionym dostępu do sieci środowisku testowym:

```bash
python -m tools.legaltech_oss.benchmark export --dir /tmp/notarai-pii-inputs
# Anonimizuj powstałe fikcyjne pliki w osobnych sandboxach,
# zapisując rezultaty UTF-8 jako <case-id>.txt w katalogach wyjściowych.
python -m tools.legaltech_oss.benchmark score --dir /tmp/engine-a-output --report /tmp/report-a.json
python -m tools.legaltech_oss.benchmark score --dir /tmp/engine-b-output --report /tmp/report-b.json
python -m pytest -q test_legaltech_oss_benchmark.py
```

Raport zawiera wyłącznie liczby oraz identyfikatory syntetycznych przypadków, nie treść dokumentów. Kod wyjścia 2 oznacza wyciek, brak wyniku, stratę wymaganej treści albo błąd formatu. Kod 0 nie upoważnia do wysyłania danych do LLM. Korpus zawiera przykłady o formalnie wiarygodnych numerach, lecz osoby i scenariusze są fikcyjne. Nie dodawać rzeczywistych danych do repo ani do CI.

## Weryfikacja upublicznionych repozytoriów

| Repo | Użyteczność | Decyzja |
|---|---|---|
| [matematic-anonimizacja-pl](https://github.com/matematicsolutions/matematic-anonimizacja-pl) | Lokalny silnik Node.js, Apache-2.0, stabilne tokeny w wielu dokumentach | Testować; autor w README raportuje 52,5% fragmentów z pozostawionym PII w ślepym teście 80 przykładów |
| [anon-legal-pl](https://github.com/apiotrowski-afk/anon-legal-pl) | Presidio, spaCy, polskie wzorce, OCR, Apache-2.0 | Testować; autor ostrzega przed niepełnym recall |
| [Stemma](https://github.com/stemma-sh/stemma) | Edycja DOCX ze zmianami śledzonymi, MIT OR Apache-2.0 | Osobny pilotaż Worda, bez automatycznej publikacji aktów |
| [FlaUI-MCP](https://github.com/shanselman/FlaUI-MCP) | Prawdziwa automatyzacja interfejsu Windows przez UIA, MIT | Osobny pilot RejNET VM z allowlist, autoryzacją i audytem |
| [prawo-pl-mcp](https://github.com/matematicsolutions/prawo-pl-mcp) | Konektory źródeł prawa | Osobny test weryfikacji tekstu i daty przepisu u źródła urzędowego |
| [edoreczenia-php](https://github.com/b44x/edoreczenia-php) | SDK e-Doręczeń i mock | Wymagane testy na oficjalnym INT i poprawne EPO |
| [PATRON](https://github.com/matematicsolutions/patron) | Pełna aplikacja desktopowa, AGPL-3.0 | Nie kopiować do SaaS bez analizy obowiązków licencyjnych |
| [Microsoft winappCli](https://github.com/microsoft/winappCli) | Build, packaging, signing Windows | **Nie** jest narzędziem automatyzacji RejNET — nie stosować do tego celu |

Sprawdzone SHA upstream i statusy licencji znajdują się w tools/legaltech_oss/upstreams.json. Nie zawierają one pobranego cudzego kodu. Deklaracja licencji w README nie zastępuje sprawdzenia pełnych LICENSE/NOTICE, zależności i składu konkretnego commita.

## Kryteria przyjęcia (otwarte)

1. Niezależnie uruchomić dwa silniki na tych samych, wyłącznie fikcyjnych wejściach — w odciętym od sieci, nieuprzywilejowanym środowisku.
2. Rozszerzyć ślepy korpus do co najmniej 100 trudnych przypadków, w tym OCR, DOCX tracked changes, polskie odmiany, relacje między dokumentami.
3. Uzyskać zero ujawnionych **znanych** znaczników oraz brak usunięcia wymaganych fraz — nadal bez twierdzenia, że wszystkie dane są anonimowe.
4. Przeprowadzić kontrolę licencji, repozytorium, zależności i map pseudonimizacji; mapy nadal są danymi osobowymi.
5. Włączenie do ścieżki danych kancelarii tylko w osobnym PR po testach negatywnych, granicy izolacji, kontroli dostępu i akceptacji notariusza.

**Kluczowa zasada:** pseudonimizacja nie jest równoznaczna z Zero Knowledge i nie wyklucza identyfikacji strony przez kontekst. Ani ten test, ani żadna biblioteka nie wydaje automatycznej zgody na wysyłkę dokumentu poza zaufaną granicę.
