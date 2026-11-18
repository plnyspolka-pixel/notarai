# Pakiet koncepcyjny V4 — „Komputerku…”

„Kancelaria pod Siódemką”, sezon 1: 8 odcinków. Oś: chaos kancelarii → uporządkowane materiały i praca zespołu → projekt aktu na wzorze kancelarii, do oceny notariusza. Bez finalnych dialogów i scenariuszy.

**Przed użyciem produkcyjnym przeczytaj [notę integracyjną](INTEGRACJA_PR20.md).** W szczególności aktualne głosy v2 i Text to Dialogue z `../glosy.md` mają pierwszeństwo przed historycznymi identyfikatorami w zamrożonym pakiecie.

## Materiały

- [Kompletny ZIP — 22 pliki](NotarAI_V4_Komputerku_Kancelaria_pod_Siodemka.zip)
- Biblia sezonu, 25 stron: [PDF](pakiet/BIBLIA_SEZONU_V4.pdf) · [DOCX](pakiet/BIBLIA_SEZONU_V4.docx) · [źródło Markdown](pakiet/BIBLIA_SEZONU_V4.md)
- Brand/production bible, 8 stron: [PDF](pakiet/BRAND_PRODUCTION_V4.pdf) · [DOCX](pakiet/BRAND_PRODUCTION_V4.docx) · [Markdown](pakiet/BRAND_PRODUCTION_V4.md)
- Autoryzacja prawna i produktu, 6 stron: [PDF](pakiet/AUTORYZACJA_V4.pdf) · [DOCX](pakiet/AUTORYZACJA_V4.docx) · [Markdown](pakiet/AUTORYZACJA_V4.md)
- [Matryca 8 odcinków i mailingu](pakiet/MATRYCA_8_ODCINKOW_V4.csv)
- [Mapa statusów 13 funkcji](pakiet/MAPA_FUNKCJI_V4.csv)
- [72 kontrole autoryzacji](pakiet/CHECKLISTY_AUTORYZACJI_V4.csv)
- [Rejestr zgód](pakiet/REJESTR_AUTORYZACJI_V4.json) · [walidator publikacji](pakiet/waliduj_publikacje.py)
- [Instrukcja pakietu](pakiet/README.md) · [weryfikacja](pakiet/WERYFIKACJA_PLIKOW.json) · [sumy SHA-256](pakiet/MANIFEST_SHA256.json)

## Status i kontrola

39 stron PDF sprawdzono wizualnie, DOCX sprawdzono strukturalnie i pod kątem zgodności treści. Natywnego renderu DOCX nie wykonano — brak LibreOffice; układ w Wordzie wymaga sprawdzenia. CSV: UTF-8 z BOM, średnik. ZIP: CRC i zgodność manifestu PASS.

Publikacja i mailing pozostają **BLOCK**. Brak potwierdzenia produkcyjnego wdrożenia nie staje się obietnicą dostępnej funkcji. Poczta przychodząca, porównywanie KW i pełna zdalna orkiestracja są planowane lub wymagają osobnej weryfikacji. Walidator nie jest jeszcze podłączony do zewnętrznej kolejki publikacji.

Archiwum zachowano bez zmian względem przekazanej wersji: SHA-256 `cec72b5b94ff3de37af8536124de506988d7ff8b9d1fc68e648dda3416490189`. Jego baseline to `5e58dd03b79ba1228657ec858b3116e84e5f659d`; zgodność z nowszym stanem PR opisuje nota integracyjna. Stare scenariusze pozostają osobnym archiwum i nie przyjmują numeracji E01–E08 V4.
