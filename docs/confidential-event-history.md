# NotarAI AUTO — historia zdarzeń bez danych klienta (pilot)

Stan: **kod i IaC przygotowane, trigger DynamoDB Stream domyślnie OFF**.
Nie uruchamiać na produkcyjnych kancelariach ani na dokumentach klientów.

## Dlaczego osobny journal?

Control Room PR #58 pokazuje aktualny stan z ostatnich zadań, ale sama
tabela jobs nie jest niezmienną historią. PR #59 dodaje osobny tor:

1. DynamoDB `notarai-confidential-jobs-pilot01` emituje
   `NEW_AND_OLD_IMAGES` do DynamoDB Streams.
2. Lambda `confidential.event_journal.lambda_handler` czyta z jednego
   autoryzowanego, dokładnie zadanego stream ARN; waliduje tenant,
   job_id, `submitted=false`, stan i liczbę prób.
3. Jeśli stan/próba się zmieniły, Lambda zapisuje do odrębnej tabeli
   `notarai-confidential-events-pilot01` wyłącznie job ID, poprzedni i
   następny stan, licznik prób, przybliżony czas i SHA-256 eventID.
4. Warunkowy `PutItem` uniemożliwia nadpisanie istniejącego wpisu
   przez rolę Lambdy. Powtórne wykonanie Lambda nie dubluje zgodnych
   rekordów; kolizja z inną treścią skutkuje odmową.
5. `GET /api/confidential/control/jobs/{job_id}/history` — właściciel
   lub notariusz — zwraca maksymalnie 20 najnowszych wpisów, bez treści
   dokumentu. Zwykły pracownik kancelarii nie może go wywołać.
6. Sidebar AUTO oferuje ręczny przycisk „Historia”. Nie ma kontrolek
   podpisu, wysyłki, retry lub wykonywania innych operacji.

Dane case_id, object_id, s3_version, nonce, DEK, podpisy i treść
formularzy **nie są przekazywane do tabeli audit** ani do UI.
Należy dodatkowo zweryfikować polityki CloudWatch/CloudTrail w AWS.

## CloudFormation i IAM

Nowy `StreamSpecification NEW_AND_OLD_IMAGES` +
`JobStreamArn` output w `infra/notarai-confidential-job-ledger.yaml`.

`infra/notarai-confidential-audit.yaml` tworzy:
- oddzielną tabelę z kluczami `pk, sk`, PITR/SSE/Retain;
- Lambdę Python 3.12, kod z osobnego bucketu artefaktów;
- rolę ograniczoną do ReadStream z konkretnego ARN,
  `PutItem/GetItem` na tabeli audytu oraz wysłania nieobsłużonych
  rekordów do własnej DLQ;
- kolejkę DLQ z szyfrowaniem SQS-managed i 14-dniową retencją;
- `EventSourceMapping` z `StartingPosition=TRIM_HORIZON`,
  batch size 10, bisekcją błędów i maksymalnie 3 retry,
  **`AuditTriggerEnabled=false` domyślnie**.

Stare, produkcyjne IAM nie jest ruszane. Do read-only endpointu
potrzebne jest później `dynamodb:Query` na dokładnym ARN tabeli
audit, przydzielone wyłącznie uprawnionej roli SaaS pilota.

## Instrukcja dla Claude po ukończeniu PR #57/#58

1. Najpierw sprawdź, czy Claude nie zmienił już schematu job table
   lub workflow PR #57; jeśli tak, przenieś poprawki w kolejności.
2. Zweryfikuj `cfn-lint`, testy, odpowiedni region, IAM i koszty.
3. Zmiana istniejącego stacka jobs aktywuje DynamoDB Streams:
   osobno zweryfikuj nowy `JobStreamArn`, `StreamStatus=ENABLED`.
4. `python scripts/package_confidential_audit.py --output /tmp/notarai-audit.zip`
   generuje deterministyczny digest `sha256`. Wyślij ZIP do
   dedykowanego bucketu `ntr-cf-code-pilot01-...-eu-central-1`
   pod kluczem `confidential-audit/<sha256>.zip`, nie do
   magazynu dokumentów.
5. Deploy audytu z `AuditTriggerEnabled=false`. Zweryfikuj
   role, outputy, DLQ i uprawnienia API. Dopiero po akceptacji
   wszystkich testów fikcyjnych włącz na **syntetycznym tenancie**
   `AuditTriggerEnabled=true`.
6. Wykonaj scenariusz INSERT -> running -> retryable -> preview_completed
   na fikcyjnym jobie. Sprawdź idempotencję Lambda, odmowę obcej
   kancelarii, historię przez API, DLQ przy celowym niepowodzeniu.
7. Po zakończeniu pilota ustaw trigger `false`, sprawdź koszty
   i zostaw `PIECZAPP_CONFIDENTIAL_ENABLED` wyłączone.

## Ograniczenia dowodowe

**To jest operacyjna historia, NIE prawnie wiarygodny, kompletny rejestr
wszystkich czynności.** DynamoDB Streams przechowuje zdarzenia przez
ograniczony czas; jeśli trigger został uruchomiony późno albo wszystkie
próby zakończą się niepowodzeniem, mogą wystąpić luki. DLQ wymaga
monitoringu, a `TRIM_HORIZON` nie odtwarza wydarzeń sprzed
włączenia streamu ani starszych niż okres retencji.

Zdarzenia są uporządkowane przybliżonym czasem ze Stream; przy
wspólnym timestampie kolejność może być niejednoznaczna. Wpis w
DynamoDB nie dowodzi, że notariusz przeczytał dokument albo że
portal urzędowy przyjął wniosek. Do skutków prawnych potrzebne są
odrębne potwierdzenia odbioru, integralność dokumentu, podpis
kwalifikowany tam gdzie wymagany i sprawdzone prawa dostępu.

Oficjalna dokumentacja AWS:
- https://docs.aws.amazon.com/lambda/latest/dg/services-dynamodb-eventsourcemapping.html
- https://docs.aws.amazon.com/lambda/latest/dg/services-dynamodb-errors.html
- https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-resource-lambda-eventsourcemapping.html
