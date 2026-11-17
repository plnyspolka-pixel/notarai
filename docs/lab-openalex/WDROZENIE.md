# Wdrożenie wniosków laboratorium — projekt (17.11.2026)

Źródła: KIERUNKI.md (W/K), GENEROWANIE-WIDEO.md (G + wnioski A–C), ZBIORY-DANYCH.md,
gałęzie frontier-engineering-lab, secure-agent-factory, agent-factory-learning-loop,
coding-agents-100-foundation, koder-salad oraz własne dane z transkryptów Claude Code.

## Zasady egzekwowania

1. **Mechanizm zamiast dokumentu.** Reguła, którą da się sprawdzić automatem, idzie do kodu,
   CI albo hooka. Dokument tylko tam, gdzie automatu nie ma (decyzje biznesowe).
2. **Twarda blokada tylko dla rzeczy nieodwracalnych lub sekretów.** Reszta: ostrzeżenie
   i wpis w dzienniku. Powód: zmęczenie zatwierdzaniem (S059) i wprost wyrażona niechęć
   właściciela do „bezsensownych blokad”. Każda blokada ma w komunikacie „dlaczego”
   (P025–P029) i drogę wyjścia.
3. **Każda bramka zapisuje decyzję** (JSONL: kiedy, bramka, wynik, powód, bez treści
   i bez PII). To jest pomiar „przed/po”, którego wymagają KIERUNKI, i dane do T067
   (uczenie z CI i przeglądu — luka w literaturze).
4. **Nasze pomiary mają pierwszeństwo przed literaturą.** Przykład: na 100 parach
   zwykłe polecenie 27/100, „ustrukturyzowany kontrakt” 13/100 (learning-loop, 16.11).
   Dlatego szablon karty (W7) zostaje zwięzły; nie dokładamy sekcji bez pomiaru A/B.
5. **Fail-closed tam, gdzie chodzi o pieniądze i wysyłki** (wzór: GLOBAL OUTBOUND STOP
   w finyou main). Fail-open z wpisem do dziennika tam, gdzie chodzi o wygodę pracy.
6. **Bez scalania badań w całości.** Gałęzie badawcze mają dużo kodu; przenosimy wąsko
   to, co ma test i jest potrzebne teraz. Web-factory z frontier jest starsze niż master —
   nie scalać.
7. **Zgody zbiorczo.** Wszystko odwracalne robimy na gałęziach; scalenia, push, płatne GPU
   i obszary zastrzeżone trafiają do jednej paczki zgód w osobnej sesji.

## Dane własne użyte do W8 (które reguły są łamane)

52 lokalne transkrypty, 629 wiadomości użytkownika (do 17.11). Słownych poprawek mało (8).
Klasyfikator trybu auto zablokował agentom ≥ 50 akcji; najczęstsze kategorie:
zapis do magazynów sekretów (11), obejście trybu auto (10), dostęp bez uprawnień (6),
wyciąganie credentiali (5), nadawanie uprawnień (4), osłabianie zabezpieczeń / wycieki (6).
Sesje w trybie bypass nie mają klasyfikatora, więc **hook to jedyna bramka** — W8 zaczyna
od sekretów, nie od reguł stylu.

## Paczki wdrożenia

| Paczka | Zawartość | Repo / gałąź | Zgoda? |
|---|---|---|---|
| A. Koder | W6 ukryte testy + test sabotażu; zamrożone pliki testów (skrót); W3 bramka nowych importów/zależności (K5); W7 zwięzła karta (kryteria, „zmiana niepotrzebna”, zakaz kart otwartych); manifest przebiegu (silnik, dtype, kontekst — „Silent Hyperparameter”); dziennik JSONL; zapis wyniku 27/100 vs 13/100 | notarai, od feature/koder-salad | scalenie |
| B. ai-clip | skróty sha256 i rewizje modeli; `fakty` w ujęciu; `freezedetect`/`mpdecimate` w bramce; pole `wada` w przeglądzie; zapis pełnego promptu przy werdykcie; eksport par DPO; VLM tylko w parach (METODYKA); licencje FLUX | finyou, od feature/ai-clip-runner | scalenie |
| C. Wysyłki MCP (W2) | bramka na każde wywołanie: odbiorca musi istnieć w CRM lub zespole, twardy limit odbiorców, idempotencja 24 h, dziennik decyzji, fail-closed | finyou, od origin/main | **obszar zastrzeżony** |
| D. Sekrety i łańcuch dostaw | hook PreToolUse (odczyt/wypisanie sekretów, sekret w pliku repo, force-push na gałąź główną, `--no-verify`); gitleaks + audyt zależności w CI; W5 radar co tydzień; usunięcie wygasłego tokenu z settings.local.json | oba repo | scalenie / włączenie hooka globalnie |
| E. Protokół (W4) | powtórzenia kart, przedziały dokładne/bayesowskie, korekta sędziego LLM, porównanie z pojedynczym agentem przy równym budżecie (L050–L052), krzywa straty to nie miara (T046), trening przy podwojeniu danych (T045) | lab | — |

## Czego nie da się zrobić bez Ciebie (trafia do paczki zgód)

- Ocena ślepych par T1 (warunek G1 i kalibracji bramki ai-clip).
- Płatna paczka GPU K1+K2+K3 (ok. 10–15 USD), z dopisanym ramieniem „wczesne przerwanie” (L046).
- Scalenia/push gałęzi A–E; włączenie hooka sekretów na poziomie użytkownika.
- Bramka W2 — obszar zastrzeżony.
- Wiadomość do OPI PIB o zbiór klauzul (ZBIORY-DANYCH, krok 2).
- Decyzja A5: czy wrażliwy kod może iść na Salad (dzielenie GPU między najemców).
