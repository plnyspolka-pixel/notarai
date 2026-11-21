# CLAUDE CODE — wykonaj pilotaż AWS Confidential Browser (NotarAI)

**Zlecenie użytkownika z 21.11.2026:** wolno Ci utworzyć i skonfigurować
niezbędne **odrębne zasoby testowe AWS** dla NotarAI. Jeśli masz działający
AWS MCP, użyj go; w przeciwnym razie użyj lokalnego, autoryzowanego
AWS CLI/SSO. Nie deklaruj wdrożenia bez dowodów AWS. Wykonaj tyle etapów,
ile realnie pozwalają uprawnienia i limity konta. Nie pytaj o decyzje,
które wynikają już z tego polecenia. Zgłaszaj jedynie faktyczne blokery.

## 0. Zakres nienaruszalny

- Region **WYŁĄCZNIE eu-central-1 (Frankfurt)**, fikcyjny tenant `pilot01`.
- **ŻADNYCH** dokumentów klientów, PESEL, aktów, sesji, podpisów ani
  sekretów w ChatGPT, PR, GitHub Actions, CloudWatch, CloudTrail czy fixture.
- Zero zmian produkcyjnego Fargate, domen, DNS notarialnych, ról SaaS
  bez osobnej oceny. Zostaw `PIECZAPP_CONFIDENTIAL_ENABLED` wyłączony.
- **AUTO** = domyślnie przygotowanie/preview; nigdy nie wysyła, nie podpisuje,
  nie wykonuje przelewów, nie składa oświadczeń. Żaden test urzędowy live.
- Nie uruchamiaj `scripts/confidential_pilot_bootstrap.py --apply` w
  obecnej postaci: łączy capacity provider ze stagingowym SG
  dopuszczającym wychodzący HTTPS do 0.0.0.0/0.
  Zamiast tego **złóż zasoby z osobnych stacków i capacity provider
  wskazujący TYLKO SG z prywatnego stosu egress**.
- Każde `run-task` ma mieć `CONFIDENTIAL_SANDBOX`, finalny obraz
  `@sha256`, PCR17 i KMS policy oraz `assignPublicIp=DISABLED`.
  Nie używaj `containerOverrides`, nie luzuj Cedar attestation
  ani złożonej bariery no-submit.
- CloudFormation + IaC w repo. Nie zapisuj access keys ani wartości
  z AWS Secrets Manager; przestrzegaj `CLAUDE.md`.
- Koszty: EC2 Managed Instances, ECS i zwłaszcza **interfejsowe VPCE**
  naliczają opłaty. Przed wykonaniem pokaż szacowane koszty, ogranicz się
  do jednej maszyny i jednej AZ, po teście zatrzymaj wszystkie taski,
  zostaw harmonogram wyłączony, zgłoś stale kosztujące endpointy.
  Nie zostawiaj uruchomionego EC2/Managed Instance bez celu.

## 1. Najpierw kod i zależności PR

Kolejność roboczych PR: **#52 -> #53 -> #54 -> #55 -> #56 -> #57**.
Pracuj na gałęzi tego PR:
`feature/confidential-job-ledger-aws-handoff-20261121`.

Przeczytaj: `CLAUDE.md`,
`docs/confidential-deployment.md`,
`docs/confidential-dispatcher.md`,
`docs/confidential-signed-approval.md`,
`docs/confidential-auto-mode.md`,
`docs/confidential-private-egress.md` oraz ten plik.

Uruchom:
```sh
python -m pytest -q test_confidential.py test_confidential_worker.py \
  test_confidential_interop.py test_confidential_infra.py \
  test_confidential_preflight.py test_confidential_dispatch.py \
  test_confidential_approval.py test_confidential_auto.py \
  test_confidential_egress.py test_confidential_job_ledger.py \
  test_confidential_audit.py
node test_confidential_auto_js.js
python -m confidential.demo_browser
python scripts/confidential_pilot_run.py --help
python scripts/verify_confidential_private_network.py --help
```
Sprawdź GitHub Actions. Jeśli którykolwiek test nie przechodzi, napraw
źródło, a nie test poprzez pominięcie zabezpieczeń. Dla CloudFormation
użyj `cfn-lint --regions eu-central-1 --template infra/notarai-confidential-*.yaml`
(z wyjątkiem znanego, ściśle ograniczonego wyjątku E3002 wyłącznie dla
pola TrustedExecutionConfiguration w task definition).

## 2. Tożsamość AWS — rozpoznanie read-only

```sh
export AWS_PROFILE=notarai-admin
export AWS_REGION=eu-central-1 AWS_DEFAULT_REGION=eu-central-1
export TENANT=pilot01
aws sts get-caller-identity --profile "$AWS_PROFILE"
aws ec2 describe-availability-zones --filters Name=state,Values=available \
  --region "$AWS_REGION" --profile "$AWS_PROFILE"
aws ec2 describe-managed-prefix-lists \
  --filters Name=prefix-list-name,Values=com.amazonaws.eu-central-1.s3 \
  --region "$AWS_REGION" --profile "$AWS_PROFILE"
aws ec2 describe-managed-prefix-lists \
  --filters Name=prefix-list-name,Values=com.amazonaws.eu-central-1.dynamodb \
  --region "$AWS_REGION" --profile "$AWS_PROFILE"
```

Ustal `ACCOUNT` wyłącznie ze STS i porównuj w całym procesie.
`notarai-admin` to przykładowa nazwa profilu, znajdź autoryzowany
profil/SSO istniejący na tej maszynie, jeśli inny. **Nie wstawiaj
identyfikatorów dostępu ani tokenów do PR**. Zweryfikuj AWS CLI v2 i
oficjalne ECS Nitro generator `ecs-nitro-sandbox-genpolicy` (pochodzenie,
wersja, checksum). Sprawdź kontowe limity, AZ i obsługę
`nitroEnclavesEnabled` w modelu ECS. Przerwij przy braku uprawnień
zamiast korzystać z roli produkcyjnej o szerszych prawach.

## 3. Prywatna VPC i endpointy (CloudFormation)

Utwórz niezależne testowe zasoby, nie korzystaj z podsieci produkcyjnej:

1. `infra/notarai-confidential-network-base.yaml`:
   stack `notarai-confidential-network-base`,
   parametry `TenantId=pilot01`, `AvailabilityZone=<AZ m6i.xlarge>`.
   Odczytaj output `PilotVpcId`, `PrivateSubnetId`,
   `PrivateRouteTableId`.
2. `infra/notarai-confidential-private-egress.yaml`:
   stack `notarai-confidential-private-egress`.
   Wymagane parametry: `TenantId=pilot01`,
   `PilotAcknowledgement=dedicated-pilot-route-table`,
   `VpcId`, `PrivateSubnetId`, `PilotRouteTableId`,
   `S3GatewayPrefixListId`, `DynamoDbGatewayPrefixListId`.
   Prefix listy MUSZĄ być zweryfikowane jako AWS-managed S3 i DynamoDB
   z regionu eu-central-1, nie dowolne `pl-...`.
   Odczytaj outputy `PilotGuestSecurityGroupId` i
   `PilotEndpointSecurityGroupId`.
3. Zweryfikuj z `scripts/verify_confidential_private_network.py --check`
   z `--account`, `--profile`, `--vpc`, `--subnet`, `--route-table`,
   `--guest-sg`, `--endpoint-sg`, `--s3-prefix`,
   `--dynamodb-prefix`.
   Sam `--check` niczego nie zmienia.
4. Sprawdź faktyczne połączenia z ECS Managed Instances (ECS agent,
   STS, ECR API/DKR, S3 layers, KMS, SQS, DynamoDB).
   Jeżeli brak wymaganej usługi VPCE, dopisz ją do szablonu i testów.
   **Nie dodawaj NAT/IGW, nie otwieraj 0/0.**
5. Weryfikuj Security Groups na rzeczywistym task ENI oraz host ENI,
   a nie tylko w definicji sieci. Zweryfikuj DNS resolver i
   ewentualny dodatkowy kanał exfiltracji. Uwaga: to wciąż nie jest
   produkcyjna izolacja portali rządowych.

## 4. Magazyn syntetyczny, role, klucze (CloudFormation)

Deploy osobnych, istniejących szablonów z `TenantId=pilot01`:
```
infra/notarai-confidential-staging.yaml
infra/notarai-confidential-job-ledger.yaml
infra/notarai-confidential-ecr.yaml
infra/notarai-confidential-demo-kms.yaml
infra/notarai-confidential-capacity-base.yaml
infra/notarai-confidential-artifacts.yaml
```
Użyj nazw stacków odpowiednio
`notarai-confidential-staging`, `-job-ledger`, `-ecr`,
`-demo-kms`, `-capacity-base`, `-artifacts` z prefiksem
`notarai-confidential`. Dla capacity-base podaj VPC ID
oraz `CAPABILITY_NAMED_IAM`.
KMS `ExpectedPCR17` ma pozostać początkowo **96 zerami** (deny-all).
DynamoDB job table musi mieć `Retain`, PITR, SSE; worker tylko
`GetItem/UpdateItem`, a stagingowy API/fixture tylko
`PutItem/GetItem/UpdateItem` na **konkretnym** tabelowym ARN.
Nie dopinaj w ciemno tych uprawnień do roli produkcyjnej.
Nie mieszaj dokumentów klienta z artefaktami wykonywalnymi.

Wymagane nowe zasoby są teraz opisane w szablonach; ich utworzenie jest
autoryzowane dla syntetycznego pilota. Jeśli CloudFormation wymaga
poprawki API/schematu, popraw IaC i dołóż test, zanim ponowisz deploy.

## 5. ECR, atestacja, KMS

1. Zbuduj izolowany obraz:
   `docker build -f confidential/Dockerfile -t notarai-confidential:pilot .`
   i wykonaj offline Chromium smoke. **Nie dokładaj** danych/kluczy do
   obrazu; sprawdź `.dockerignore`.
2. Zaloguj się do prywatnego ECR przez `aws ecr get-login-password`
   i `docker login --password-stdin`. Wypchnij do własnego repo
   `notarai-confidential-pilot01` pod **nowym** immutable tagiem;
   pobierz digest `sha256:...` z `ecr describe-images`.
3. `python scripts/render_confidential_taskdef.py --account ... \
   --tenant pilot01 --image <ECR_URI@sha256:...> --kms-key-arn ... \
   --bucket ... --queue ... --output /tmp/confidential-taskdef.json`.
4. Z finalnej definicji i oficjalnego generatora AWS pozyskaj
   bazowe `attestationPolicy` oraz **niezerowy PCR17**.
   Sprawdź politykę Cedar i pin obrazu/środowiska. Nie zgaduj formatu
   wyjścia generatora: dopasuj renderer/parsowanie do rzeczywistego
   wyjścia AWS i dołóż test. Każda zmiana image/entrypoint/env
   wymaga regeneracji policy i PCR17.
5. Dopiero wtedy uaktualnij `ExpectedPCR17` w stacku
   `notarai-confidential-demo-kms` i utwórz
   `notarai-confidential-task` z finalnym obrazem,
   base64 attestation policy, PCR, KMS ARN, bucket, SQS URL/ARN.
   `CAPABILITY_NAMED_IAM`.
6. Sprawdź `ecs-nitro-sandbox-genpolicy --check
   --task-definition <ZAREJESTROWANY_TASK_ARN>`; przejrzyj
   `ecs describe-task-definition`, `kms get-key-policy`,
   role i wszystkie `Allow kms:Decrypt`.
   Wymagana para: PCR17 + PCR8:ServiceName `ecs.amazonaws.com`.
7. Sprawdź AWS CloudTrail z atestowanym `KMS Decrypt`, w tym PCR17,
   i kontrolowany negatywny przypadek odmowy po zmianie obrazu/PCR.

## 6. ECS capacity provider — TYLKO prywatne SG

Po deploy `notarai-confidential-capacity-base`, **nie uruchamiaj**
`confidential_pilot_bootstrap.py --apply`.

Zamiast tego:
```sh
python scripts/render_confidential_capacity.py \
  --tenant pilot01 --account "$ACCOUNT" \
  --subnet "$PRIVATE_SUBNET" \
  --instance-sg "$PILOT_GUEST_SG" \
  --instance-type m6i.xlarge \
  --output /tmp/notarai-capacity.json
aws ecs create-capacity-provider \
  --cli-input-json file:///tmp/notarai-capacity.json \
  --region eu-central-1 --profile "$AWS_PROFILE"
aws ecs put-cluster-capacity-providers \
  --cluster notarai-confidential-pilot01 \
  --capacity-providers notarai-confidential-pilot01 \
  --default-capacity-provider-strategy \
    capacityProvider=notarai-confidential-pilot01,weight=1 \
  --region eu-central-1 --profile "$AWS_PROFILE"
```
Przed deploy sprawdź, czy provider o tej nazwie już istnieje;
nie nadpisuj niezweryfikowanego providera ani nie twórz duplikatu.
Z `ecs describe-capacity-providers` potwierdź **jednocześnie**
`nitroEnclavesEnabled=true`, image pinned task,
`networkConfiguration.securityGroups=[PILOT_GUEST_SG]`
i odpowiednie prywatne subnets.

## 7. End-to-end z fikcyjnymi danymi

- `scripts/confidential_pilot_fixture.py --apply` tworzy **jedno**
  szyfrowane, hardcoded fikcyjne zlecenie, **najpierw zapisując**
  stan `queued` do tabeli `notarai-confidential-jobs-pilot01`,
  potem publikując ID do SQS FIFO.
- Zapisz wygenerowane `job_id`; nie twórz wielu kopii.
- `scripts/confidential_pilot_run.py` z `--apply` wymaga teraz
  `--vpc`, `--route-table`, `--subnet`, `--guest-sg`,
  `--endpoint-sg`, `--s3-prefix`, `--dynamodb-prefix`,
  `--account`, `--profile`, `--tenant pilot01`, `--job-id`.
  Najpierw **read-only preflight**, dopiero potem RunTask.
- Sprawdź `trustedExecutionSummary`, policy `CONFIGURED`,
  stop code 0, tylko `preview_completed`, `submitted=false`,
  S3 marker i DynamoDB status; SQS powinien zostać usunięty po
  potwierdzeniu sukcesu.
- Uruchom `python scripts/audit_confidential_pilot.py --profile "$AWS_PROFILE"
  --account "$ACCOUNT" --tenant pilot01 --job-id "$JOB_ID" --check`.
  Porównaj metadane DDB, SQS visible/inflight/DLQ, ECS active i istnienie
  S3 result marker bez pobierania treści dokumentów.
- Uruchom testy awarii: obca kancelaria, brak rejestru job, podrobiona
  wiadomość SQS, podmiana KMS PCR/digest, brak VPCE, konkurencyjny
  job claim, duplikat SQS, brak zgody na wysłanie. W przypadku awarii
  nie powinna powstać operacja urzędowa.
- Jeśli napotkasz rzeczywiste błędy ECS/API, dokumentuj zanonimizowane
  kody i weryfikuj oficjalne API przed modyfikacją IaC.

## 8. Automatyczny scheduler po zielonym pilocie

- Spakuj `scripts/package_confidential_dispatch.py` do ZIP, oblicz
  SHA256 i umieść tylko w dedykowanym bucket `-artifacts` pod
  immutable key z digest.
- Deploy `infra/notarai-confidential-dispatch.yaml` z
  `DispatchEnabled=false`, `CodeBucket`, `CodeKey`,
  `TaskDefinitionArn`, `TaskRoleArn`, `TaskExecutionRoleArn`,
  `WorkQueueArn/Url`, `PrivateSubnetId`,
  `GuestSecurityGroupId`.
- Zrób osobne testy wywołania Lambda, SQS depth, DDB lease,
  ochrony przed podwójnym ECS RunTask; zweryfikuj billing.
- Możesz włączyć **wyłącznie pilotażowy** `DispatchEnabled=true`
  po kompletnym, pozytywnym E2E i kosztowym safety check,
  ale na końcu zostaw `false`, jeśli test już się zakończył.
  Nigdy nie włączaj produkcyjnego `PIECZAPP_CONFIDENTIAL_ENABLED`.

## 9. Raport w PR, bez sekretów

Dodaj komentarz z:
- faktycznym AWS account alias (nie kluczami), region, utworzonymi
  stackami, statusami CloudFormation i niesekretnymi ARN;
- digest obrazu ECR, PIN PCR17 (hash nie jest sekretem),
  wersją binariów generatora i rezultatem `--check`;
- pozytywnymi/negatywnymi wynikami KMS, Nitro, sieci, SQS/DynamoDB,
  statusem i ilością kosztujących zasobów;
- wynikiem testów/CI, linkami do PR poprawek i
  `docs/czeka-na-dostep.md` dla każdego niezakończonego blokeru.

Jeśli nie masz połączenia AWS/SSO — zatrzymaj się na wykonanych
testach i preflight, a w komentarzu wskaż konkretnie brakujący
profil/uprawnienie. **Nigdy nie wpisuj fikcyjnych wartości jako
rzeczywistych wyników AWS.**

## 10. Rollback i koszty

Niezwłocznie wyłącz pilotażowy harmonogram, zatrzymaj pilotażowe taski
i sprawdź, czy nie pozostały Managed Instances. Tabele, kolejki, KMS
i niektóre buckety są z `Retain` i wymagają ręcznego procesu
usunięcia; nie usuwaj automatycznie materiału dowodowego ani klucza,
który mógłby zawierać dane klienta. Endpointy Interface pobierają
opłaty godzinowe nawet bez ruchu: pokaż ich stan i koszt, a po
zakończonym pilocie zaproponuj bezpieczne usunięcie testowej sieci.

## Dokumentacja oficjalna

- ECS Nitro: https://docs.aws.amazon.com/AmazonECS/latest/developerguide/ict-getting-started.html
- ECS Cedar/PCR17: https://docs.aws.amazon.com/AmazonECS/latest/developerguide/ict-confidential-policy-configuration.html
- ECS private endpoints: https://docs.aws.amazon.com/AmazonECS/latest/developerguide/vpc-endpoints.html
- DynamoDB gateway endpoint: https://docs.aws.amazon.com/vpc/latest/privatelink/vpc-endpoints-ddb.html
- KMS attestation keys: https://docs.aws.amazon.com/kms/latest/developerguide/conditions-nitro-enclave.html
- ECS instance networking: https://docs.aws.amazon.com/AmazonECS/latest/developerguide/managed-instances-awsvpc-mode.html


### Dodatkowy warunek produkcyjny (nie dotyczy fikcyjnego testu)

Dalsze wdrożenie wymaga **przypięcia konkretnej wersji obiektu S3 do jobu**:
obecny envelope pod kluczem case/object można nadpisać po zakolejkowaniu.
Claude ma dodać Versioning + immutability binding (`VersionId` i/lub
SHA-256 ciphertext) do zamówienia oraz weryfikację przed decrypt, zanim
kiedykolwiek dopuści się prawdziwe dokumenty albo podpisane oświadczenia.
Opis problemu: `docs/confidential-job-lifecycle.md`.
