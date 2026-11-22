# SEC-02 — mapa eskalacji, zasady operatora i tryb awaryjny

Stan: IMPLEMENTACJA PILOTOWEJ ROLI OBSERWACYJNEJ, ale NIEZWERYFIKOWANA NA AWS. Żadnego wdrożenia ani testu na kontach klienta. Wszystkie próby dotyczą wyłącznie pilot01/pilot02 oraz eu-central-1.

## Rejestr principal -> action -> resource -> account

| Principal | Wrażliwe działanie / ryzyko | Resource | Konto / właściciel | Status |
|---|---|---|---|---|
| NOWY synthetic observer | ecs:ListTasks; ecr:DescribeImages; sqs:GetQueueAttributes, żadne modyfikacje | jeden cluster, shared ECR, kolejka testowego tenanta | workload | IaC + statyczny walidator; brak live |
| GitHub OIDC publisher | ecr:PutImage, upload warstw, ecr:GetAuthorizationToken | ECR pilot, w innym szablonie | workload | statycznie przypięty aud/sub, rzeczywista postać tokenu GitHub nieudokumentowana |
| GitHub OIDC deployer notarai-github-wdrozenie | CloudFormation, iam:PassRole / możliwa eskalacja przez stack roles | zasoby usługi i role egzekucyjne stacków | workload | potencjalnie uprzywilejowany, wymaga inwentaryzacji na AWS |
| ECS confidential guest task | attested kms:Decrypt, wyłącznie tenant S3/SQS/DynamoDB | Nitro / zewnętrzny KMS | workload -> custody | IAM z repo, efektywne uprawnienia do sprawdzenia |
| ECS task execution role | pobranie ECR, runtime ECS | guest execution | workload | zależność od AWS-managed policy |
| Shared ECS infrastructure / instance roles | iam:PassRole instance role, uprawnienia infrastrukturalne ECS | Managed Instances/EC2 | workload | kontrola zakresu i wersji AWS-managed policies wymagana |
| Dispatcher Lambda | ecs:RunTask, iam:PassRole tylko predefiniowane role ECS | wskazany task definition, shared ECS | workload | ograniczone w IaC, ale możliwe przejęcie przez administratora funkcji |
| CloudFormation stack execution role | wykonanie zasobów z template, w tym IAM, KMS, ECS | stack role | workload | BLOCKED — brak kompletnej listy rzeczywistych stacków i ról |
| Custody KMS administrator | kms:PutKeyPolicy, zarządzanie key lifecycle, bez normalnego odszyfrowywania przez operatora | klucz RSA Nitro | custody | policy w repo nie potwierdza własności konta |
| Custody release signer | kms:Sign dla konkretnego digest/PCR17/key policy | podpisowa key ECC | custody | wymagane niezależne zatwierdzenie i jego dowody |
| root / IAM Identity Center / AWS Organizations | zmiana SSO, organizacji, SCP, delegated admin, root recovery | oba konta i organizacje | nieustalony kontroler | BLOCKED — konieczna niezależna atestacja |

To jest rejestr wynikający z kodu, a NIE pełny rejestr rzeczywistych principal. K1 pozostaje BLOCKED. Deterministyczny manifest wszystkich znanych ról, trust statements, policy Action/Resource/Account i braków można wygenerować bez sieci przez `python -m scripts.confidential_operator_iam_source_inventory --output sec02-source-inventory.json --summary`. Workflow SEC-02 zapisuje ten plik jako recenzowalny artefakt — output maskuje numery AWS account ID; to statyczna analiza źródeł, a nie stan AWS.

## Ograniczona rola operatora

Szablon: infra/notarai-confidential-operator-iam.yaml. Jest opt-in; nowa rola OBSERVER nie przejmuje prawa deployowania. Wymaga istniejącej SourceRoleName na koncie workload; Trusted role przypięta do jednego same-account ARN, a sesja trwa do 3600 s (AWS IAM minimum). PermissionsBoundary plus inline allowlist ograniczają tylko tę nową rolę. Dodatkowo szablon wymusza explicit Deny dla wszystkich operacji poza trzema dozwolonymi odczytami (`DenyEverythingExceptObserverActions`) oraz `NotResource` Deny dla odczytów innych zasobów; zabezpiecza to także przed bezpośrednimi grantami w resource policies do assumed-role session, które według AWS mogą ominąć samo implicit Deny granicy uprawnień. Patrz [AWS: IAM permissions boundaries](https://docs.aws.amazon.com/IAM/latest/UserGuide/access_policies_boundaries.html) i [policy evaluation](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_evaluation-logic_policy-eval-denyallow.html). Ścieżki ECR image replacement, iam:PassRole, CloudFormation execution role, kms:PutKeyPolicy/CreateGrant, OIDC trust mutation i sts:AssumeRole do custody mają explicit Deny. Inne tożsamości, pierwotna SourceRoleName, root i administratorzy AWS Organizations NIE są zabezpieczani przez tę rolę.

Istniejący OIDC publisher ma prawo wypchnąć kod; jeśli operator przejmie kod GitHub lub ścieżkę wydawniczą, podpis zgody niezależnego custody i przypięcie obrazu do digest/PCR17 muszą nadal uniemożliwić odszyfrowanie. Sama niezmienność tagów ECR nie jest dowodem. Weryfikacja zmiennych aud/sub GitHub OIDC i ich dostosowanej składni jest obowiązkowa w realnym AWS.

## Sześć prób negatywnych

1. ECR: PutImage / BatchDeleteImage — DENY na nowej roli; osobno musi być zweryfikowana ścieżka image publisher / account admin.
2. iam:PassRole do roli admin — DENY na nowej roli; osobno sprawdzić dispatcher i role deployment.
3. CloudFormation: CreateStack/ExecuteChangeSet i przejęcie execution role — DENY na nowej roli; przejrzeć istniejące stack roles.
4. KMS: PutKeyPolicy/CreateGrant — DENY na nowej roli; REALNE decyzje zależą od custody account i jego organizacji.
5. OIDC: UpdateAssumeRolePolicy/zmiana dostawcy oraz spoof tokenu — mutation DENY, aud/sub sprawdzone statycznie, ale rzeczywiste spoof tokenu NIE zostało wykonane.
6. sts:AssumeRole / AWS Organizations — DENY na nowej roli; ścieżka przez management/root wymaga niezależnego dowodu.

Odczyt IAM wymaga osobnej autoryzacji obu właścicieli kont: `python -m scripts.confidential_operator_iam_evidence --operator-profile OPS --custody-profile CUSTODY --tenant pilot01 --authorized-read-only`. Skrypt porównuje istniejącą rolę, ARN permission boundary i aktywną wersję policy z dokładnie wyrenderowanym IaC; drift i niepełna odpowiedź to BLOCKED. Symuluje wszystkie konkretne pod-operacje sześciu ścieżek, ale NIE wywołuje mutujących API ani realnych prób ataku. Test statyczny NIE oznacza wyniku odmowy API na AWS. IAM policy simulation nie zastępuje sprawdzenia permission boundary, SCP, session policies, resource policies, SSO i rzeczywistej odmowy.

## Organizations / root / SSO

Nie wolno uznawać odrębności custody na podstawie dwóch Account IDs. Wymagane są niezależnie podpisane dowody zarządcy AWS Organizations management account, Control Tower, delegated admin, SSO/Identity Center assigner, konta rozliczeniowego, ścieżki root password/MFA/recovery oraz możliwości AssumeRoot; należy weryfikować w obu kontach i wskazać, kto ma prawo zmienić każdy element. Jeżeli operator zarządza custody przez Organizations albo może przejąć jego root/SSO, warunek FAIL. Brak autoryzowanych danych = BLOCKED.

SCP nie tworzymy i nie dołączamy w PR. SCP mogłoby ograniczać tylko konta/OU, którymi zarządza uprawniony właściciel AWS Organizations; SCP nie dowodzi niezależności konta custody od management account.

## Break-glass: procedura, bez prawa do danych

1. Incydent zgłoszony do niezależnego, nieusuwalnego dziennika; bez PII i plaintext. Incydent określa konto, podmiot i zakres metadata-only.
2. Wymagane dwie różne, niezależnie uwierzytelnione osoby: custody owner oraz independent security reviewer. Każda zgoda podpisana i zweryfikowana w oddzielnym systemie, niedostępnym dla operatora.
3. Czas uprawnienia najwyżej 15 minut, MFA/security key, UTC start/expiry i ślad wystawienia/revocation; nie wolno przyznać kms:Decrypt, kms:PutKeyPolicy, CreateGrant, dostępu do plaintext, root reset ani SSO superadmin.
4. Po każdym użyciu natychmiastowe cofnięcie i kontrola CloudTrail / Identity Center przez dwie osoby. Odzyskiwanie root lub klucza nie jest tym trybem — osobna niezależna procedura i audyt.
5. Automatyczny walidator sprawdza format fikcyjnych dwóch zgód, zakres i TTL, ale NIE uwierzytelnia tych osób ani nie wystawia żadnych dostępów.

## Pobranie dowodów AWS — tylko po autoryzacji

Uprawniony auditor w eu-central-1 wykonuje read-only STS GetCallerIdentity; IAM GetRole/ListAttachedRolePolicies/GetRolePolicy/GetPolicyVersion; ECS DescribeTaskDefinition; ECR DescribeRepositories; KMS DescribeKey/GetKeyPolicy/ListGrants; CloudFormation DescribeStacks (RoleARN); Organizations DescribeOrganization/ListDelegatedAdministrators; oddzielnie sprawdza adminów Identity Center, root i środki odzyskania dostępu. Osoba niezależna wykonuje i zapisuje bezpieczne rzeczywiste negatywne próby dla sześciu ścieżek. Każdy zapis: alias principal/resource, operacja, decyzja, UTC timestamp, SHA256 polityk, podpis audytora, identyfikator CloudTrail — bez tokenów, DEK, PII, treści dokumentów. Nie tworzyć uprawnień w celu uruchomienia testów.

Kryteria K1–K6 z PR pozostają BLOCKED do czasu rzeczywistej weryfikacji. Żadnych twierdzeń Zero Trust / Zero Operator Access / Zero Knowledge verified, bez zatwierdzonych i niepodważalnych dowodów infrastruktury. Brak AUTO submit/sign.
