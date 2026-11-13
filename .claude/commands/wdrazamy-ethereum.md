# Wdrażamy Ethereum — samodzielna misja implementacyjna

**Najważniejsza zasada:** W tym repozytorium priorytetem jest tajemnicę notarialną.

Otwórz w całości `CLAUDE_ETHEREUM_MISSION.md`, następnie `CLAUDE.md` i odpowiedni dokument techniczny pod `docs/`. Postępuj według misji, wykonując jak najwięcej rzeczywistych zmian w kodzie i testach, bez zatrzymywania się na analizie.

Przebieg:
1. Sprawdź bieżącą gałąź — pracuj wyłącznie na `wdrazamy-ethereum`. Jeżeli jesteś na innej gałęzi, przełącz bez nadpisywania cudzych zmian.
2. Sklasyfikuj stan modułów: działa / częściowe / niezaimplementowane / ryzyko. Zapisz krytyczne braki do `docs/ETHEREUM-IMPLEMENTATION-STATUS.md`.
3. Zrealizuj bezpiecznie P0 i kolejne priorytety z pliku misji, twórz testy negatywne i integracyjne, popraw wykryte błędy, wykonuj commity partiami.
4. Uruchom testy i odpowiednie GitHub Actions. Napraw regresje, a niemożliwe do wykonania testy opisz ze wskazaniem konkretnej przyczyny.
5. Zakończ wymiernym raportem: commity, zmienione pliki, wynik CI, weryfikowalne gwarancje i ograniczenia oraz wyraźnie oddzielone blokery wymagające zgody właściciela.

Nie wysyłaj danych osobowych, sekretów, transakcji Ethereum Mainnet ani nie wykonuj deployu produkcyjnego bez zgody. **Nie myl kryptograficznego dowodu integralności z dowodem, że żadna osoba fizyczna nie widziała danych.** Nie przedstawiaj etapu POC jako posiadania kwalifikacji eIDAS/QTSP lub licencji ECSPR.

Jeżeli szczegóły implementacyjne są niejednoznaczne, wykonaj najlepszą bezpieczną wersję i opisz wybór. Dąż do możliwie dużego postępu, zamiast kończyć na liście sugestii.
