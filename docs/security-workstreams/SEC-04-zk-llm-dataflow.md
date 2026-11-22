# SEC-04 — [SEC-04] Zero Knowledge: izolacja AI/LLM, inference i wyników

**Status: PLANNED, not implemented.** Priorytet: P0
**Zależności:** SEC-01, SEC-03, #65

## Zakres
1. Zinwentaryzuj wszystkie ścieżki model inference (AWS Bedrock, zewnętrzne API, embeddings, OCR, logging, traces, support, cache). Sporządź precyzyjną mapę kto i kiedy może zobaczyć plaintext.
2. Domyślnie zabroń wysyłania decrypted plaintext poza atestowany Nitro. Jeśli model poza Nitro ma przetworzyć treść, to jawnie zdefiniuj osobny trust boundary i ustaw wynik ZK=UNVERIFIED; nie ukrywaj go w definicjach.
3. Wprowadź gateway polityki AI: pinned model/provider, region UE, allowlist operacji, data minimization, zerowy logging treści, osobne zgody gdy wymagane. Nie dopuszczaj fallbacku do publicznego API.
4. Przetestuj negatywne scenariusze prompt injection, ukryte URL/requests, egress do niezatwierdzonego dostawcy, retencję w logs/traces, eksfiltrację poprzez odpowiedzi modelu.

## Mierzalne kryteria zakończenia — SEC-04

**TWARDY WARUNEK `DONE`:** komplet **K1–K6 = PASS**, każde poparte linkiem do wyniku testu lub niezależnego dowodu, **0 FAIL, 0 BLOCKED, 0 UNVERIFIED**, istniejący test docelowy z **0 failed i 0 pominiętych scenariuszy krytycznych** oraz zielony CI dla aktualnego HEAD SHA. Wymagany rzeczywisty dowód z AWS lub zewnętrznego audytora jest niezbędny tam, gdzie wskazano go w K1–K6; test mock nie zastępuje live. Przy choć jednej niespełnionej pozycji PR pozostaje OTWARTY/DRAFT. Zamknięcie implementacyjnego PR nie oznacza automatycznego pozwolenia na marketing ZK/ZOA.

- [ ] **K1.** **Mapa 100% tras AI:** spisane wszystkie miejsca wywołania Bedrock, zewnętrznego LLM, embedding, OCR, cache, log/tracing; każda trasa ma region, klasę danych, providera, retencję i właściciela.
- [ ] **K2.** **Domyślna odmowa:** 0 wywołań modelu z plaintext poza zatwierdzoną granicą; test przechwytuje klienta AI i blokuje brak polityki. Bedrock poza Nitro jest osobnym trust boundary, nie ścisłym ZK.
- [ ] **K3.** **6 testów negatywnych:** zmiana modelu, region poza UE, publiczny endpoint, prompt-injection URL, output zawierający fikcyjne dane sprawy i trace/log z PII — odmowa albo jawne `UNVERIFIED` ZK.
- [ ] **K4.** **AI fallback:** timeout lub błąd Bedrock nie przełącza modelu na publiczne API; wymagane 2 negatywne testy.
- [ ] **K5.** **Retencja i telemetry:** dla każdej ścieżki określona retencja/podprocesorzy i brak dokumentów w logach/traces; brak dowodu retencji = `BLOCKED`.
- [ ] **K6.** **Granica ZK:** test odmawia strict Zero Knowledge, jeśli inference ujawnia plaintext usłudze nieatestowanej; wskazany wariant confidential inference wymagający odrębnego dowodu.

**Docelowy test do dodania:** `python -m pytest -q test_confidential_zk_ai_boundary.py` — 0 failed i 0 pominiętych testów krytycznych.

### Wspólny warunek zamknięcia
- [ ] Zielone CI dla aktualnego HEAD SHA; komenda, liczba `passed/failed/skipped`, dowód w `docs/security-evidence/SEC-04.md` (lub artefakcie CI).
- [ ] Każdy K1–K6 ma link do testu lub dowodu, datę, właściciela i `PASS/FAIL/BLOCKED`. Brak prawdziwego AWS = `BLOCKED`, nie `PASS`.
- [ ] Zero PII/plaintext/DEK w artefaktach, zero zmiany AUTO no-submit. CI nie ustanawia `Zero Knowledge verified`.

## Zasady pracy w nowej konwersacji
To jest **PR planistyczny**. Na tym etapie nie ma implementacji ani działającego dowodu. Nowa konwersacja ma zrealizować zadanie na **tej konkretnej gałęzi PR**, nie zakładać kolejnego zbędnego PR. Najpierw przeczytaj kod i aktualny stan #57, #60, #61, #62, #65 oraz sprawdź ich SHA. Nie edytuj cudzych gałęzi i nie scalać bez integracyjnego przeglądu.

Reguły: test wyłącznie pilot01/pilot02 i fikcyjne dane; AWS eu-central-1; produkcja wyłączona; AUTO preview nie wysyła, nie podpisuje i nie składa wniosków. Nie podnoś operatorowi uprawnień custody, nie loguj PII/plaintext/sekretów i nie wprowadzaj sieciowego 0.0.0.0/0 dla guest. Każdą własność security potwierdź testami pozytywnymi i **negatywnymi**; brak konta/narzędzi oznacz BLOCKED, a nie PASS. Sama dokumentacja lub CI nie stanowi dowodu sprzętowego. Zapisz kod + testy + wyniki + wymaganą niezależną atestację w PR.

**Definition of done:** zmiana możliwa do niezależnego review, testy CI zielone, brak funkcji submit, wszystkie pozostałe ograniczenia podane jawnie, bez twierdzenia 'Zero Operator Access / Zero Knowledge verified' przed dowodami.
