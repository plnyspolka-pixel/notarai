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

### ElevenLabs: tylko silnik v3 lub nowszy (twarda reguła, 16.11.2026)
- Każda generacja głosu w ElevenLabs (lektor TTS, dialog, agenci rozmowni,
  projektowanie głosu, zamiana mowy) używa modelu v3 lub nowszego:
  `eleven_v4`, `eleven_v4_turbo`, `eleven_v3`, `eleven_v3_conversational`
  (projektowanie głosu: `eleven_ttv_v3`). NIGDY `eleven_multilingual_v2`,
  `eleven_flash_v2_5`, `eleven_turbo_v2_5` ani innych v1/v2 - także przy
  pracy przez konektor ElevenLabs, narzędzia MCP `fu` i skrypty.
- Gdy narzędzie albo model nie daje wyboru v3+, przerwij i zgłoś to,
  zamiast schodzić na niższy silnik. Domyślnie: lektor `eleven_v4`,
  agenci `eleven_v4_turbo`.

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

### Publikacja (bez FTP z ręki)
- Zmiany w `strona/` (notarai.pl) i `seo/` publikuje sam GitHub:
  `.github/workflows/strona.yml` po zielonych testach na `master` generuje
  katalog, blog i sitemap i wysyła na az.pl przez FTPS tylko zmienione pliki.
  Aplikację (`static/`, kod Pythona) wdraża `.github/workflows/wdrozenie.yml`.
- Gdy użytkownik prosi o zmianę strony lub frontendu: zrób zmianę, puść
  testy, commit, push i pull request do `master`; po scaleniu wszystko idzie
  na stronę samo. Nie uruchamiaj `infra\strona.ps1` ani FTP ręcznie, chyba
  że workflow nie działa (wtedy to wysyłka awaryjna).

## Secure Agent Factory (prototyp, bez wdrożenia produkcyjnego)

- Architektura i zasady: docs/agent-factory.md.
- **Polecenie dla Claude Code:** docs/claude-code-handoff-agent-factory.md. Przy pracach agentowych przeczytaj je w całości, realizuj kolejne etapy i testuj rezultaty.
- Nie korzystaj z danych klientów, sesji produkcyjnych ani sekretów. Nie omijaj zasad UE z tego pliku. Żadnych automatycznych wdrożeń na produkcję.
