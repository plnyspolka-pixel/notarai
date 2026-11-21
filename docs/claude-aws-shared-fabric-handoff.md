# Claude Code — ZMIANA ARCHITEKTURY: wdrażaj jeden SHARED FABRIC

**Nowsza decyzja właściciela, 22.11.2026: nie tworzyć oddzielnych płatnych
VPCE na kancelarię ani jednorazowej tenant-specific VPC. Budować od razu
docelową sieć współdzieloną przez wszystkie kancelarie.**
Ten dokument **zastępuje kroki sieci/capacity/ECR** starego
`docs/claude-aws-confidential-handoff.md` w PR #57.
Nie scalać równolegle z aktywnymi zmianami PR #57 bez uzgodnienia i
rebase; prace na `feature/confidential-shared-fabric-20261122` są
osobną, reviewowalną gałęzią.

Upoważnienie użytkownika obejmuje stworzenie odrębnych syntetycznych
zasobów testowych AWS w eu-central-1; **nie obejmuje obchodzenia
zabezpieczeń sesji Claude ani uruchamiania produkcji**. Jeśli środowisko
odmawia Create/Deploy, potrzebna jest wyraźna interakcja właściciela
z Claude Code w sesji o odpowiednich uprawnieniach. Nie obchodź odmowy,
nie przejmuj aktywnych ról produkcyjnych.

## Cel (jednorazowo na region)

- ONE VPC `notarai-confidential-shared-fabric`, z jednym zestawem VPCE
  na każdy potrzebny AWS service i aktywną AZ;
- ONE `notarai-confidential-shared` ECS cluster/capacity provider;
- ONE ECR repo `notarai-confidential-shared`, immutable image @sha256;
- osobne dla każdej kancelarii: task definition, task IAM,
  klucz KMS i PCR17 policy, SQS FIFO, DDB job/lease, prefixy/bucket
  ciphertext, prawa dostępu. Brak kopiowania endpointów i hostów.
- AUTO = automatyczne przygotowanie podglądu, bez podpisu/wysyłki.

## I. Preconditions, read-only

```sh
export AWS_REGION=eu-central-1
export AWS_DEFAULT_REGION=eu-central-1
export AWS_PROFILE=<UPRAWNIONY_PROFIL>
aws sts get-caller-identity --profile "$AWS_PROFILE" --region eu-central-1
aws ec2 describe-availability-zones --region eu-central-1 --profile "$AWS_PROFILE"
aws ec2 describe-managed-prefix-lists \
  --filters Name=prefix-list-name,Values=com.amazonaws.eu-central-1.s3 \
  --region eu-central-1 --profile "$AWS_PROFILE"
aws ec2 describe-managed-prefix-lists \
  --filters Name=prefix-list-name,Values=com.amazonaws.eu-central-1.dynamodb \
  --region eu-central-1 --profile "$AWS_PROFILE"
aws ec2 describe-vpc-endpoint-services \
  --region eu-central-1 --profile "$AWS_PROFILE"
```

Odczytaj `ACCOUNT` ze STS. Potwierdź listy prefixów są AWS-owned,
prawdziwe usługi ECS/ECR/KMS/SQS, dostępną AZ, limit VPC i budżet.
W raporcie CloudFormation w PR #57 Claude wcześniej wskazał
`eu-central-1a`, ale przeprowadź aktualną weryfikację.

## II. Testy offline

```sh
python -m pytest -q test_confidential_shared_fabric.py \
  test_confidential_dispatch.py test_confidential_preflight.py \
  test_confidential_egress.py
python scripts/render_confidential_shared_capacity.py --help
python scripts/verify_confidential_shared_fabric.py --help
python scripts/confidential_pilot_run.py --help
cfn-lint --regions eu-central-1 --template \
  infra/notarai-confidential-shared-fabric.yaml \
  infra/notarai-confidential-shared-capacity.yaml \
  infra/notarai-confidential-shared-ecr.yaml
```

Nie osłabiaj testów przy błędach. Najpierw sprawdź i napraw IaC/CLI.

## III. Jeden zestaw endpointów i wspólna pula

Po potwierdzeniu preconditions i wyraźnie autoryzowanym zapisie:

```sh
aws cloudformation deploy \
  --stack-name notarai-confidential-shared-fabric \
  --template-file infra/notarai-confidential-shared-fabric.yaml \
  --parameter-overrides SharedNetworkName=notarai \
    AvailabilityZone=eu-central-1a \
    S3PrefixListId=<AWS_MANAGED_S3_PREFIX_ID> \
    DynamoDbPrefixListId=<AWS_MANAGED_DDB_PREFIX_ID> \
    EnableStsEndpoint=false EnableLogsEndpoint=false EnableSignerEndpoint=false \
  --region eu-central-1 --profile "$AWS_PROFILE"
python scripts/verify_confidential_shared_fabric.py \
  --profile "$AWS_PROFILE" --account "$ACCOUNT" --check
aws cloudformation deploy \
  --stack-name notarai-confidential-shared-capacity \
  --template-file infra/notarai-confidential-shared-capacity.yaml \
  --capabilities CAPABILITY_NAMED_IAM \
  --region eu-central-1 --profile "$AWS_PROFILE"
aws cloudformation deploy \
  --stack-name notarai-confidential-shared-ecr \
  --template-file infra/notarai-confidential-shared-ecr.yaml \
  --region eu-central-1 --profile "$AWS_PROFILE"
```

Nie twórz `notarai-confidential-network-base` /
`notarai-confidential-private-egress` /
`notarai-confidential-capacity-base` jako alternatywnego zestawu.
Nie łącz istniejących produkcyjnych subnets, VPC ani SG.

CloudFormation outputs shared fabric:
`SharedVpcId`, `SharedPrivateSubnetId`,
`SharedRuntimeSecurityGroupId`, `SharedEndpointSecurityGroupId`,
`SharedRouteTableId`. Dopilnuj, by endpointy i SG należały do
TEJ JEDNEJ VPC, a nie przypadkowo do produkcyjnej default VPC.

7 bazowych płatnych interface endpoints to KMS, SQS, ECR API,
ECR DKR, ECS, ECS-Agent i ECS-Telemetry.
STS, Logs i Signer są opcjonalne; włącz tylko na podstawie
rzeczywistych wymagań/diagnostyki. W przypadku signer-based image
trust potrzebujesz także ścieżki do AWS Signer; przy samym
pinned digest ten endpoint nie powinien być potrzebny.
S3 i DynamoDB to osobne gateway endpointy bez opłaty godzinowej
za sam endpoint. Nie przywracaj NAT, żeby "naprawić" brakujący serwis.

## IV. Jeden capacity provider (bez tenant name)

```sh
python scripts/render_confidential_shared_capacity.py \
  --account "$ACCOUNT" \
  --subnet <SHARED_PRIVATE_SUBNET_ID> \
  --security-group <SHARED_RUNTIME_SG_ID> \
  --instance-type m6i.xlarge \
  --output /tmp/notarai-confidential-shared-capacity.json
aws ecs create-capacity-provider \
  --cli-input-json file:///tmp/notarai-confidential-shared-capacity.json \
  --region eu-central-1 --profile "$AWS_PROFILE"
aws ecs put-cluster-capacity-providers \
  --cluster notarai-confidential-shared \
  --capacity-providers notarai-confidential-shared \
  --default-capacity-provider-strategy \
    capacityProvider=notarai-confidential-shared,weight=1 \
  --region eu-central-1 --profile "$AWS_PROFILE"
```

Przed `create-capacity-provider` sprawdź `describe-capacity-providers`;
nie duplikuj istniejącej nazwy, jeśli zaufany provider już istnieje.
Sprawdź `nitroEnclavesEnabled=true`, SG i subnet z outputs SHARED.
Szablon ECS Managed Instances provider wymaga weryfikacji wersji
rzeczywistego AWS CLI/API; nie zgaduj pól API.
Nie zostawiaj EC2 uruchomionych bez aktywnego testu.

## V. Dwa fikcyjne tenanty, jeden obraz

1. Wypchnij obraz Chromium z GitHub Actions przez ograniczoną rolę
   OIDC do `notarai-confidential-shared`. Klon/zbudowanie obrazu
   w sesji Claude może nie działać przez proxy; nie dodawaj
   niezweryfikowanego CA do attested guest image.
2. Pobierz image digest z ECR, używaj wyłącznie `@sha256:...`.
3. Utwórz osobne syntetyczne tenanty `pilot01` i `pilot02`
   z osobnymi S3 prefixami/kluczami KMS/SQS FIFO/DDB job ledger,
   task IAM i attestation policy. Nie zakładaj, że obecne
   jednokancelaryjne szablony wspierają onboarding drugiego tenanta
   bez aktualizacji nazw stacków; popraw parametryzację IaC.
4. Dla obu zleceń wygeneruj definicje:
   ```sh
   python scripts/render_confidential_taskdef.py --shared-image \
      --account "$ACCOUNT" --tenant pilot01 \
      --image "<SHARED_ECR_URI@sha256:...>" \
      --kms-key-arn "<TENANT1_KMS_ARN>" \
      --bucket "<TENANT1_CIPHERTEXT_BUCKET>" \
      --queue "<TENANT1_QUEUE_URL>" --output /tmp/tenant1.json
   ```
   Analogicznie `pilot02`. Digest obrazu ma być IDENTYCZNY,
   ale role, KMS, SQS i attested environment są oddzielne.
5. Wygeneruj Cedar policy/PCR17 osobno dla definicji tenantów,
   dostosuj KMS decrypt do exact task role/valid PCR17. Zadbaj o
   negatywny test dostępu tenant1 do dokumentu/klucza tenant2.
6. Worker testowy uruchamiaj przez
   `scripts/confidential_pilot_run.py --shared-compute --apply`
   z dokładnymi parametrami VPC/subnet/SG i weryfikacją read-only
   z `scripts/verify_confidential_shared_fabric.py --check`.
7. Wspólny scheduler:
   `infra/notarai-confidential-dispatch.yaml`
   z `SharedCompute=true`, `DispatchEnabled=false` do czasu testów.
   Tenant-specific Lambda może planować tylko własną task definition,
   FIFO queue i lease, ale wszystkie korzystają z jednego shared ECS.
8. Sprawdź, że drugi tenant NIE tworzy nowego VPC Endpoint,
   Nitro EC2 hosta, klastra ECS, capacity providera ani ECR repo.

**Stop warunek:** nie uruchamiaj produkcyjnego AUTO ani ruchu do portali,
dopóki nie przejdą rzeczywiste KMS/NSM/PCR17, sieć i no-submit.
Publiczne portale nie będą dostępne z AWS-only endpoint fabric; do
prawdziwego przeglądania trzeba osobnego audytowanego egress proxy,
nie dodawać NAT+0/0.

## VI. Zakończenie i koszty

- Wyłącz pilotowe schedulery, zatrzymaj wszystkie syntetyczne taski,
  zweryfikuj skalowanie liczby płatnych Managed Instances do zera.
- Osobno przedstaw koszt 7 / 9 / 10 endpointów w 1 AZ i scenariusz
  2 AZ. Wspólny koszt nie mnoży się przez liczbę kancelarii.
- S3, KMS i DynamoDB zachowują polityki Retain i backup:
  usuń tylko prawdziwe syntetyczne zasoby po bezpiecznym zatwierdzeniu;
  nie usuwaj dowodów ani danych klienta.
- Dodaj do dyskusji PR tenanta-neutralne statusy i zanonimizowane
  dowody AWS, listę stacków, ECR digest, negatywne KMS cross-tenant,
  wynik no-submit, koszty i wszelkie blokery.
- **Nigdy nie nazywaj zielonego cfn-lint ani offline mocków
  potwierdzeniem sprzętowego wdrożenia.**
