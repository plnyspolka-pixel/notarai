# SEC-09 — [SEC-09] Cross-tenant isolation: dwóch fikcyjnych klientów, odmowy IAM/KMS/S3/SQS/ECS

**Status: IMPLEMENTATION IN PROGRESS — NOT LIVE VERIFIED (2026-11-22).** P0; zależności: SEC-05, SEC-06, SEC-07

Wdrożono walidację przypisania per-tenant (`confidential/tenant_isolation.py`), blokadę błędnej konfiguracji workera, poprawne uprawnienie `s3:GetObjectVersion`, testy offline (`test_confidential_cross_tenant_isolation.py`), read-only AWS/IAM simulator (`scripts/verify_confidential_tenant_isolation.py`) oraz raport stanu `docs/security-evidence/SEC-09.md`. **Wszystkie K1–K6 pozostają BLOCKED do czasu rzeczywistych dowodów.** Skrypt `--check` zwraca 2 przy braku dowodów live; nie dokonuje AWS writes.

## Zakres
1. Oddziel tenant identity wyłącznie przez zaufane serwerowe role i sesje; uniemożliwiaj wybór obcego tenant przez REST, message queue, document ID, task ARN, iam:PassRole i ECS overrides.
2. Przygotuj pełne testy cross-tenant pilot01 ↔ pilot02 dla S3 versioned object, KMS RSA/Recipient attestation, SQS FIFO, DynamoDB lease/jobs i wyników przetwarzania.
3. Sprawdź izolację w jednym wspólnym ECS Nitro cluster, capacity provider, VPC i obrazie przeglądarki; zweryfikuj brak podatności na confused deputy oraz eskalację przez task execution/instance profile.
4. Zbierz zanonimizowane dowody z autoryzowanego live AWS, nie ujawniając kluczy, dokumentów i innych tenantów.

## Mierzalne kryteria zakończenia — SEC-09

**TWARDY WARUNEK `DONE`:** komplet **K1–K6 = PASS**, każde poparte linkiem do wyniku testu lub niezależnego dowodu, **0 FAIL, 0 BLOCKED, 0 UNVERIFIED**, istniejący test docelowy z **0 failed i 0 pominiętych scenariuszy krytycznych** oraz zielony CI dla aktualnego HEAD SHA. Wymagany rzeczywisty dowód z AWS lub zewnętrznego audytora jest niezbędny tam, gdzie wskazano go w K1–K6; test mock nie zastępuje live. Przy choć jednej niespełnionej pozycji PR pozostaje OTWARTY/DRAFT. Zamknięcie implementacyjnego PR nie oznacza automatycznego pozwolenia na marketing ZK/ZOA.

- [ ] **K1.** **Dwa niezależne piloty:** pilot01 i pilot02 mają osobne task roles, KMS keys, SQS FIFO, S3 namespace/version, job ledger i sesje API; używają tego samego ECS cluster/provider/VPC i tego samego zatwierdzonego digest.
- [ ] **K2.** **Minimum 10 rzeczywistych odmów:** pilot01→pilot02 i pilot02→pilot01, każda dla KMS Decrypt, S3 GetObjectVersion, SQS ReceiveMessage, DynamoDB Get/UpdateItem oraz ECS RunTask/PassRole; wszystkie z `AccessDenied` albo równoważnym dowodem.
- [ ] **K3.** **Tenant pod kontrolą serwera:** podmiana tenant ID, job ID, queue URL, task ARN, VersionId i body/query API nie może przełączyć wykonania na cudzą kancelarię; min. 6 testów input tampering.
- [ ] **K4.** **Race/confused deputy:** równoległe zadania i duplicate delivery nie umożliwiają odebrania wyniku ani lease drugiej kancelarii; 2 kontrolowane próby współbieżne.
- [ ] **K5.** **Pozytywne:** dla obu tenantów po jednym fikcyjnym zadaniu poprawnie kończącym preview, `submitted=false`, bez użycia wspólnej roli dostępu do obu danych.
- [ ] **K6.** **Ślad audytowy:** identyfikatory ról/policy, hash konfiguracji i 10 odmów w zanonimizowanym raporcie AWS; jeśli wykonano wyłącznie mock, live izolacja `BLOCKED`.

**Test offline zaimplementowany (wynik CI do potwierdzenia):** `python -m pytest -q test_confidential_cross_tenant_isolation.py` — 0 failed i 0 skipped krytycznych.

**Wstępny read-only verifier zaimplementowany (nie jest rzeczywistym testem odmów; wymagane niezależnie autoryzowane AWS i osobne testy live):** `python scripts/verify_confidential_tenant_isolation.py --check` — bez realnego PASS punkt K6 pozostaje BLOCKED.

### Wspólny warunek zamknięcia
- [ ] Link do **zielonego CI dla aktualnego SHA**, dokładna komenda, liczba passed/failed/skipped i zanonimizowany raport w `docs/security-evidence/SEC-09.md` (lub równoważnym artefakcie). Testy opisane niżej należy dopiero wdrożyć; nazwa testu nie wystarcza.
- [ ] Każdy K1–K6 ma `PASS/FAIL/BLOCKED`, datę, wykonawcę, link do dowodu. Brak realnej sesji AWS = `BLOCKED` dla punktów sprzętowych. Zero PII, plaintext, DEK, tokenów i sekretów w dowodach.
- [ ] Pozostaje AUTO preview-only / no-submit / no-sign i produkcja OFF. Ukończony PR lub zielony CI nie oznaczają komercyjnego `Zero Operator Access verified`.

## Instrukcja dla osobnej konwersacji
PR miał pierwotnie wyłącznie plan; aktualnie posiada częściową implementację. Dokończ zadanie na istniejącej gałęzi tego PR, uzupełnij kod, testy, instrukcje i dowody w tym samym PR. Czytaj poprzednie #57, #60, #61, #62, #65 i odpowiednie SEC-nn; sprawdź aktualne SHA. Wszystkie SEC-nn bazują na #65 i nie wymagają edycji gałęzi pozostałych zadań. Jeśli potrzebna zmiana w pliku współdzielonym, udokumentuj integracyjne uzgodnienie i konflikt.
Zakres danych: wyłącznie syntetyczne pilot01/pilot02, EU eu-central-1, produkcja OFF, no-submit/no-sign. Nie dotykaj prawdziwych spraw, nie wynoś plaintext ani sekretów do CloudWatch/GitHub/proxy. Nie wykonuj AWS write bez autoryzowanych tożsamości i zgody kustosza. Wyniki CI != real hardware evidence. Kryteria: kod + testy odmowy + dokumentacja, niezależny dowód i jawne FAIL/BLOCKED. Bez automatycznej deklaracji 'Verified Zero Knowledge/Zero Operator Access'.
