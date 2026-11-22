# SEC-09 — [SEC-09] Cross-tenant isolation: dwóch fikcyjnych klientów, odmowy IAM/KMS/S3/SQS/ECS

**Status: PLANNED (NOT IMPLEMENTED).** P0; zależności: SEC-05, SEC-06, SEC-07

## Zakres
1. Oddziel tenant identity wyłącznie przez zaufane serwerowe role i sesje; uniemożliwiaj wybór obcego tenant przez REST, message queue, document ID, task ARN, iam:PassRole i ECS overrides.
2. Przygotuj pełne testy cross-tenant pilot01 ↔ pilot02 dla S3 versioned object, KMS RSA/Recipient attestation, SQS FIFO, DynamoDB lease/jobs i wyników przetwarzania.
3. Sprawdź izolację w jednym wspólnym ECS Nitro cluster, capacity provider, VPC i obrazie przeglądarki; zweryfikuj brak podatności na confused deputy oraz eskalację przez task execution/instance profile.
4. Zbierz zanonimizowane dowody z autoryzowanego live AWS, nie ujawniając kluczy, dokumentów i innych tenantów.

## Kryteria odbioru
- [ ] Zadanie fikcyjnego tenant A nie odszyfrowuje, nie pobiera i nie nadpisuje danych tenant B.
- [ ] Odmowy potwierdzone z rzeczywistych IAM/KMS/S3/SQS i code-path; błąd ≠ sukces, jeśli test nie został wykonany.
- [ ] Raport wiąże shared VPC z odrębnymi zasobami i rolami klientów.

## Instrukcja dla osobnej konwersacji
To **wyłącznie PR planistyczny**. Zrealizuj zadanie na istniejącej gałęzi tego PR, uzupełnij kod, testy, instrukcje i dowody w tym samym PR. Czytaj poprzednie #57, #60, #61, #62, #65 i odpowiednie SEC-nn; sprawdź aktualne SHA. Wszystkie SEC-nn bazują na #65 i nie wymagają edycji gałęzi pozostałych zadań. Jeśli potrzebna zmiana w pliku współdzielonym, udokumentuj integracyjne uzgodnienie i konflikt.
Zakres danych: wyłącznie syntetyczne pilot01/pilot02, EU eu-central-1, produkcja OFF, no-submit/no-sign. Nie dotykaj prawdziwych spraw, nie wynoś plaintext ani sekretów do CloudWatch/GitHub/proxy. Nie wykonuj AWS write bez autoryzowanych tożsamości i zgody kustosza. Wyniki CI != real hardware evidence. Kryteria: kod + testy odmowy + dokumentacja, niezależny dowód i jawne FAIL/BLOCKED. Bez automatycznej deklaracji 'Verified Zero Knowledge/Zero Operator Access'.
