# NotarAI V4 — kompletny pakiet koncepcyjny

Data: 12.11.2026. Kampania „Komputerku…”, serial „Kancelaria pod Siódemką”, sezon 1: 8 odcinków. Bez finalnych dialogów i scenariuszy.

## Zawartość
- BIBLIA_SEZONU_V4.docx / .pdf / .md — strategia, dramaturgia, bohaterowie, osiem kart i 40 koncepcji scen, mailing i przekazanie do produkcji.
- BRAND_PRODUCTION_V4.docx / .pdf / .md — identyfikacja, scenografia, obsada, produkcja i odbiór.
- AUTORYZACJA_V4.docx / .pdf / .md — prawne i produktowe bramki blokujące publikację.
- MATRYCA_8_ODCINKOW_V4.csv — film i mailing w jednym rekordzie odcinka; 8 wierszy.
- MAPA_FUNKCJI_V4.csv — wdrożenie, dowody kodu, plany, ograniczenia, źródła i testy.
- CHECKLISTY_AUTORYZACJI_V4.csv — rejestr warunków do podpisania.
- REJESTR_AUTORYZACJI_V4.json i waliduj_publikacje.py — domyślnie zablokowane zgody; walidator kończy się błędem, gdy brak dowodów lub podpisów.
- ZGODNOSC_PR20_V4.md — zgodność z zamrożonym head PR i zasady migracji.
- assets/ — oryginalne logo i sygnet, pomocniczy lockup kampanii, tokeny i pochodzenie.
- WERYFIKACJA_PLIKOW.json i MANIFEST_SHA256.json — wynik kontroli plików i sumy kontrolne.

## Jak otwierać
PDF otwórz w dowolnej przeglądarce PDF; jest wersją o stałym układzie. DOCX jest edytowalny. Używa Montserrat; przy braku fontu na komputerze odbiorcy Word może go zastąpić. PDF ma font osadzony. CSV ma UTF-8 z BOM i separator średnik. W Excelu użyj importu „Z tekstu/CSV”, kodowanie UTF-8, separator średnik; nie dziel tekstów po przecinku. W razie potrzeby poszerz kolumny i włącz zawijanie. Harmonogram jest względny wobec T0 ustalonego po autoryzacji.

## Ważne rozróżnienie
Istnienie kodu i dokumentacji nie potwierdza wdrożenia. Żadnej funkcji nie oznaczono jako zweryfikowanej produkcyjnie. Poczta, porównywanie KW i pełna zdalna orkiestracja mają warianty przyszłościowe albo zastępcze. Ekrany działających funkcji wymagają nagrania docelowej wersji. Wszystkie publikacje i wysyłki mają status BLOCK.

## Zgodność z PR #20
Punkt odniesienia: https://github.com/plnyspolka-pixel/notarai/pull/20, head 5e58dd03b79ba1228657ec858b3116e84e5f659d, odczyt 12.11.2026. PR był otwarty. V4 zachowuje postacie, scenografię v2, kamery, markę i tor produkcji. Rozwija koncepcję do 8 odcinków, nie nadpisuje historycznych 6 scenariuszy. Nie zmieniono repozytorium ani PR. Po zmianie head należy wykonać przegląd różnic.

## Kontrola i ograniczenia plików
PDF utworzono ze wspólnej treści z DOCX i sprawdzono tekstowo oraz wizualnie. DOCX sprawdzono strukturalnie i pod kątem zgodności tekstu. Natywny render DOCX przez wymagany renderer nie był możliwy z powodu braku LibreOffice w środowisku; nie jest to potwierdzenie wyglądu DOCX w Wordzie. Przed dalszą edycją i drukiem sprawdzić podziały stron w Wordzie. Szczegóły są w WERYFIKACJA_PLIKOW.json. Nie wykonano testów aplikacji, opinii prawnej, produkcji filmu ani wysyłki mailingu. Wcześniejsze pliki V2/V3 z rozmowy nie były dostępne; wykorzystano odczyt ustaleń, nie ich archiwa.

## Walidator publikacji
Uruchom Python 3.10+ z plikiem rejestru jako argumentem. W stanie początkowym oczekiwany jest komunikat BLOCK i kod wyjścia 2. Dopiero kompletny rejestr z istniejącymi dowodami, zamkniętymi 72 kontrolami dla każdego odcinka, zgodnymi hashami finalnych materiałów i ważnymi podpisami może przejść. Status NA wymaga wskazania osoby i uzasadnienia, dlaczego kontrola nie dotyczy danego wariantu. Narzędzie nie poświadcza tożsamości podpisujących ani poprawności prawnej. Włączenie go jako obowiązkowej bramki w kolejce publikacji jest zadaniem wdrożeniowym; samo ZIP nie blokuje zewnętrznych usług.

## Integralność
MANIFEST_SHA256.json obejmuje wszystkie pliki pakietu poza samym manifestem. ZIP należy rozpakować jako całość. Sumy kontrolne, odczyt formatów i test CRC archiwum służą weryfikacji technicznej plików; nie są autoryzacją publikacji. Manifest używa ścieżek względnych i działa po przeniesieniu folderu.
