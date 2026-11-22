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


## NotarAI Universal Computer Agent — zasady rozwoju (22.11.2026)
- **Cel:** możliwie uniwersalna obsługa autoryzowanego oprogramowania kancelaryjnego, bez oddzielnych pisanych od zera adapterów dla każdego producenta.
- **Najważniejszy dokument:** `docs/fallback-policy.md`; architektura: `docs/universal-computer-agent.md`. PR demonstratora: #63.
- **Dwa łańcuchy fallbacków:** (A) minimum wdrożenia: API -> browser worker -> hostowana Windows VM -> VM w sieci kancelarii -> wąski connector -> człowiek; (B) wykonanie: native API -> web DOM -> Windows UIA -> UIA+vision -> visual computer use -> pokazanie procedury -> handoff.
- Każda metoda ma `supports`, wykonanie oraz weryfikację. **Nie ponawiaj niepewnego zapisu**, nie próbuj innej metody po odmowie autoryzacji ani bez potwierdzenia braku efektów ubocznych.
- W kodzie: `computer_use/fallback_router.py` i `tests/test_computer_use_fallback_router.py` to czysty, provider-agnostic fundament, NIE działająca integracja z Windows/Playwright. Nie twierdź, że agent obsługuje aplikacje produkcyjne bez E2E.
- Przy integracji z dowolną aplikacją najpierw wykorzystaj istniejące wspólne backendi i profile GUI; osobne specjalne obejście dopiero po niepowodzeniu generycznych dróg, z testem regresji.
- Nie instaluj NotarAI na PC notariusza, jeśli jest możliwe legalne odizolowane środowisko wykonawcze. Nie obiecuj braku zmian w lokalnej infrastrukturze, jeżeli baza jest dostępna tylko lokalnie.

## Computer Use MVP — implementacja 22.11.2026
- Przeczytaj **`docs/computer-use-implementation.md`** oraz **`docs/fallback-policy.md`** przed dalszą rozbudową.
- Kod: `computer_use/fallback_router.py`, `deployment.py`, `profiles.py`, `profile_loader.py`, `browser.py`, `winapp.py`, `discovery.py`, `worker.py`. Żaden program kancelaryjny nie jest zależnością architektury.
- Testy: `python -m pytest -q tests/test_computer_use*` (w CI wymagane bieżące zielone testy; ostatnie lokalne: 61 testów, 3 subtesty).
- Windows diagnostyka: `python -m examples.computer_use_windows_probe --app notepad` na **testowej** Windows VM z WinApp CLI, bez danych klientów; wypisuje wyłącznie liczniki.
- Obecnie faktycznie zaimplementowano wybór środowiska, profile podpisane i tenant-bound, routing fallback, read-only oficjalne API/DOM/UIA, kontrolowane draft fill i read-only UIA discovery. **Nie ma jeszcze Windows VM, modelu vision, live end-to-end ani brokera produkcyjnego**.
- Nie odblokowywać zapisu repertorium, wysyłki, podpisów, CAPTCHA/2FA, bezpośredniej pracy na DB ani arbitralnych poleceń powłoki. Każdy kolejny backend musi przejść negatywne testy izolacji tenantów, braku PII i niepewnego zapisu.

- Testowa infrastruktura IaC: `infra/notarai-universal-worker-vm.yaml` (brak deployu, Windows/licencja/SSM endpoints wymagają potwierdzenia). Testy statyczne: `tests/test_computer_use_infra.py`.


## Universal Computer Use — stan implementacji 2026-11-22 (PR #63)

**Dokument nadrzędny: `docs/computer-use-production-readiness.md`.** Nie oznaczaj PR za production-ready bez potwierdzonych G1–G6. Dalsze implementacje muszą zmieniać kod / testy i utrzymywać te bramki, nie tylko dodawać plan.

Obecne moduły:
- `computer_use/vision.py`: aktywny po opt-in agent obrazu (in-memory screenshot, weryfikacja procesu Windows, EU Bedrock Converse, restrykcyjny wybór pól, no blind replay), **nieprzetestowany live na VM**.
- `computer_use/workflows.py`: podpisywane krótkie (do 12 kroków) procedury na różne programy, bez kodowania adaptera dla konkretnego producenta.
- `computer_use/session_lock.py`: mutex Windows dla sesji GUI (ponad procesami) + `worker.py`: tenant, allowlist, kolejność fallback.
- `computer_use/jobs.py`, `payloads.py`, `daemon.py`, `runtime.py`: tenantowe zlecenia i wykonywanie: SQS FIFO, DynamoDB conditional claim, S3 SSE-KMS, kill switch z osobnej tabeli, opisy i payload w rozdzielonych magazynach. `runtime.py` uruchamia proces tylko z podpisanym profilem i tożsamością tenantu z bezpiecznej konfiguracji VM.
- `computer_use/api.py`: konsola webowa `/virtual-employee` z `static/virtual_employee.*`, role z istniejącego Cognito, wgląd do zatwierdzanych danych, warunkowa akceptacja, stop/start, anulowanie i ręczne uzgodnienie niepewnych zadań.
- `infra/notarai-ve-control-plane.yaml` / `infra/notarai-ve-tenant.yaml`: odseparowane kolejki/IAM/tenant KMS/Windows VM. **Są szablonami, brak faktycznego deploymentu.**
- `tests/test_computer_use_*.py`, `.github/workflows/computer-use-ci.yml`: testy unitowe, bezpieczeństwa i szybki CI. Nie twierdzić, że testy live Windows przeszły.

**Blokery produkcyjne:** legalna instalacja programu i Windows VM w UE, dostęp do jego bazy, indywidualne konto robota, uruchomienie wszystkich kontrolowanych AWS zasobów, integracja z sekretami i podpisanym profilem, rzeczywiste testy UIA/vision i izolacji IAM/S3/KMS, audyt przepływu danych. Screenshot może zawierać dane osobowe; nigdy nie włączać wizji bez aprobaty kancelarii oraz prawidłowej konfiguracji EU Bedrock/egress. Unikać określenia 'zero knowledge' bez dowodu.
