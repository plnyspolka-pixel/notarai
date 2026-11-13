# AWS Guidance

- Prefer the AWS MCP Server for AWS interactions — it provides sandboxed
  execution, observability, and audit logging. If unavailable, use the
  AWS CLI directly.
- Before starting a task, check whether a relevant AWS skill is available.
  Load the skill with `retrieve_skill` and prefer its guidance over
  general knowledge.
- When uncertain about specific AWS details (API parameters, permissions,
  limits, error codes), verify against documentation rather than guessing.
  State uncertainty explicitly if you cannot confirm.
- When creating infrastructure, prefer infrastructure-as-code (AWS CDK or
  CloudFormation) over direct CLI commands.
- When working with infrastructure, follow AWS Well-Architected Framework
  principles.
- Do not use em dashes in AWS resource names or descriptions. Use
  hyphens instead.

## Secret Safety

- MUST load the `aws-secrets-manager` skill first for any secret,
  credential, API key, token, or password task. MUST NOT call
  `secretsmanager get-secret-value` or `batch-get-secret-value`, and MUST
  NOT hit the Secrets Manager Agent daemon directly. MUST use
  `{{resolve:secretsmanager:secret-id:SecretString:json-key}}` with
  `asm-exec` so the secret resolves at runtime without entering context.

## Projekt: notarai (notarai.pl)

Wersja SaaS asystenta kancelarii notarialnej. Wywodzi się z projektu
pieczapp (stanowisko lokalne); identyfikatory w kodzie (moduły, zmienne
`PIECZAPP_*`) celowo pozostawiono, żeby nie rozjechać się z testami.

### Ograniczenia (RODO)
- Domyślny region: eu-central-1 (Frankfurt). NIE twórz zasobów poza UE.
- Dane osobowe klientów (PESEL, imiona, adresy) NIE mogą trafiać do logów
  CloudWatch, CloudTrail ani do komunikatów debugowania.
- Sekrety wyłącznie przez AWS Secrets Manager. Nigdy w kodzie ani w .env
  commitowanym do repozytorium. Token admina (`PIECZAPP_ADMIN_TOKEN`) w
  chmurze podpinaj jako referencję do sekretu, nie jako wartość w env.
- Modele Claude wywołuj przez Bedrock w eu-central-1, nie przez publiczne API.
- Przed utworzeniem zasobu przechowującego dane osobowe (bucket spraw,
  baza kancelarii) zapytaj o potwierdzenie.
- Obraz Dockera nie może zawierać `dane/` ani `.env` (pilnuje tego
  `.dockerignore`; nie usuwaj z niego tych wpisów).

### Konwencje
- Zasoby nazywaj z prefiksem: notarai-
- Infrastrukturę definiuj jako kod (CloudFormation w `infra/`), nie przez
  konsolę i nie w Terraform.
- Tryb domyślny aplikacji to lokalny; tryb SaaS włączają zmienne opisane
  w `SAAS.md` i `.env.example`.

### Zadania czekające na dostęp (testy na żywo)
- Rejestr: `docs/czeka-na-dostep.md` (pozycje `NA-n`). Gdy użytkownik mówi,
  że jest dostęp (konto notariusza, środowisko testowe GIIF, portal MS itp.),
  zacznij od tej listy i prowadź test na żywo według kroków z pozycji.
- Każde nowe zadanie, którego nie da się skończyć bez dostępu z zewnątrz,
  dopisz tam jako kolejną pozycję; po zrobieniu oznacz `zrobione` z datą
  i commitem (nie usuwaj).

### Dostęp do AWS w sesji chmurowej Claude
- Gdy w środowisku są zmienne `NOTARAI_AWS_ACCESS_KEY_ID` i
  `NOTARAI_AWS_SECRET_ACCESS_KEY`, zacznij od `source infra/aws-z-env.sh`:
  instaluje AWS CLI, zapisuje profil `notarai-admin` i wyłącza atrapy
  `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` ustawiane przez chmurę. Potem
  AWS CLI działa bez `aws login` i bez konektora AWS.
- Gdy tych zmiennych nie ma, nie proś o logowanie w czacie: wskaż
  `infra\USTAW_DOSTEP_CLAUDE.bat` i sekcję „Claude w chmurze” w README.md.
