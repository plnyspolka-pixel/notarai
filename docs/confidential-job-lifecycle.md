# Confidential Browser — trwały cykl życia zadania AUTO (pilot)

Stan: kod i testy offline, bez wdrożenia sprzętowego. Tylko syntetyczne
podglądy, bez czynności prawnych i wysyłania formularzy.

## Statusy

| Stan | Znaczenie |
| --- | --- |
| `queued` | API zarezerwowało rekord DDB, gotowy do SQS |
| `queue_uncertain` | Nieznany wynik publikacji SQS, **brak automatycznej retransmisji** |
| `running` | Worker uzyskał atomowy claim i 900 s lease |
| `retryable` | Niepowodzenie przygotowania fikcyjnego podglądu |
| `preview_completed` | Zapisano S3 marker i wynik DDB, można potwierdzić SQS |
| `needs_review` | Wyczerpane trzy próby albo stan wymagający operatora |

Tabela `notarai-confidential-jobs-pilot01`: warunkowe zapisy
`GetItem / PutItem / UpdateItem`, szyfrowanie SSE, PITR i Retain.

## Działanie

1. API weryfikuje kancelarię, sprawę i istnienie ciphertext.
2. Tworzy rekord `queued` (condition `attribute_not_exists(pk)`).
3. Publikuje tenant/case/object/job IDs do SQS FIFO. DynamoDB i SQS
   **nie** mają wspólnej transakcji. Niepewne SendMessage oznacza
   `queue_uncertain`, bez automatycznego retry.
4. Guest wymaga prawdziwej `/dev/nsm` i warunkowego DynamoDB claim
   **przed** pobraniem i odszyfrowaniem envelope z S3.
5. Claim jest unikatowy i związany z tenant/job/case/object. Drugi worker
   nie może wejść podczas aktywnego lease; maksymalnie 3 próby.
6. Worker wykonuje **wyłącznie** lokalny fikcyjny formularz w AUTO,
   zablokowanym submit i bez podpisu.
7. Wynik `submitted=false` zapisuje najpierw do S3, potem do DDB,
   a dopiero po potwierdzeniu kasuje wiadomość SQS.
8. Duplikat SQS po `preview_completed` może być potwierdzony bez
   drugiego odszyfrowania lub uruchomienia przeglądarki.

## IAM i dostęp

- Worker ma wyłącznie `dynamodb:GetItem` + `UpdateItem` do tabeli
  o nazwie `notarai-confidential-jobs-<tenant>` w `eu-central-1`.
- API staging wymaga `PutItem / GetItem / UpdateItem` tylko tej tabeli.
  Żadne uprawnienia nie zostały automatycznie dodane do produkcyjnej
  roli aplikacji; Claude musi je nadać w kontekście pilota.
- Sieć wykorzystuje dedykowany DynamoDB Gateway VPCE i SG
  z AWS-managed DynamoDB PrefixList.
- Read-only audyt:
  `python scripts/audit_confidential_pilot.py --account <ACCOUNT>
  --profile <SSO_PROFILE> --tenant pilot01 --job-id <JOB_ID> --check`.
  Bez `--check` zero połączeń AWS.

## Ograniczenia ważne przed realnym wdrożeniem

To **nie** jest exactly-once dla czynności zewnętrznych. Tylko
przygotowanie fikcyjnego podglądu może być ponowione, ponieważ
nie ma skutków prawnych. Żadnej automatycznej retry dla `send/sign`.

**Wersjonowanie S3 nie jest jeszcze zintegrowane z job ID.**
Obecny klucz case/object może być nadpisany między umieszczeniem
w kolejce a odczytem przez worker. Przed przetwarzaniem prawdziwych
danych trzeba włączyć S3 Versioning, przypinać VersionId lub
kryptograficzny digest do zlecenia i wymuszać jego zgodność w workerze.
Nie deklarować związania podpisanej zgody z treścią przed tym etapem.

Operator musi ręcznie wyjaśniać `queue_uncertain` i
`needs_review` bez zgadywania wyniku z portalu. Wszystkie testy AWS
należy wykonać wyłącznie z fikcyjną treścią i po potwierdzeniu
PCR17/KMS Nitro według `docs/claude-aws-confidential-handoff.md`.
Produkcja pozostaje OFF.
