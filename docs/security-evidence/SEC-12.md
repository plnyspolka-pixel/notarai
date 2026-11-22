# SEC-12 — Adversarial E2E and commercial release gate

**22.11.2026 — IMPLEMENTED OFFLINE; REAL AWS / NITRO E2E BLOCKED. PR #77 DRAFT.**

## Co wykonano w tej gałęzi
- `confidential/adversarial_gate.py`: deterministyczna macierz 19 prób na fikcyjnych `pilot01` i `pilot02`. Dwa scenariusze pozytywne, 13 prób obejścia i cztery awarie. Dla obu fikcyjnych tenantów dodatkowo realny AES-256-GCM Envelope + realny `fill_form` na mockowanej przeglądarce; brak realnego KMS/NSM. Przetwarza wyłącznie metadane fikcyjne.
- `test_confidential_adversarial_e2e.py`: testy 13 odmów, czterech awarii, oddzielnych tożsamości KMS/IAM, kompletności raportu i zakazu automatycznego GO. Dodatkowe testy **rzeczywistych funkcji aplikacji**: `worker._parse_message`, `auto_mode.validate_preview_options`, `form_engine.fill_form`, `release_approval.verify_release`; nadal bez AWS.
- `scripts/run_confidential_adversarial_e2e.py --offline`: offline, exit 0 przy wszystkich testach kontraktowych. `--check`: exit 2 / BLOCKED, gdy brak dowodów live. Nie ma przełącznika obchodzącego to zachowanie.
- CI uruchamia test oraz weryfikuje `--check` zwracający odmowę.

**To test *modelu reguł* — NIE rzeczywisty atak na konto AWS, nie dowód, że Nitro/KMS/egress rzeczywiście zachowają się identycznie.** W szczególności macierz nie ma prawa wystawić pozytywnej decyzji commercial GO.

| Kryterium | Status 22.11.2026 | Dowód / brakująca praca |
|---|---|---|
| K1 — 2 tenanty | **BLOCKED (live)** | 2 próby pozytywne w mock; brak uruchomienia osobnych AWS IAM/KMS/task |
| K2 — 12+ odmów | **BLOCKED (live)** | 13 kontrprzykładów offline; każdą odmowę musi potwierdzić IAM/KMS/ECS/S3/egress |
| K3 — real AWS NSM | **BLOCKED** | brak dowodów EC2 Nitro attestation, osoby i daty |
| K4 — 4 awarie | **BLOCKED (live)** | 4 symulacje w mock, bez prawdziwego crash/retry |
| K5 — egress + canary | **BLOCKED** | brak niezależnego zbieracza logów/CloudWatch i skanu ciphertext/noncurrent versions |
| K6 — podpisany raport | **BLOCKED** | wymaga SEC-11, niezależnego kustosza, niezmiennego archiwum i podpisu |

## Wymagane do finalnego audytu

Zbieracz dowodów musi być pod kontrolą innego podmiotu niż operator NotarAI. Dla **każdego** 19 przypadków trzeba wykazać timestamp UTC, tenant, zakres AWS regionu eu-central-1, image@sha256, PCR17, KMS policy hash, CloudTrail event hashes, ARN zadania, wynik i podpis. Bez ujawniania wartości dokumentów, zrzutów, tajnych kluczy, imion, PESEL i tokenów.

Sekwencja live: podpisany release → zaaprobowana wersja obrazu → atestacja Nitro/NSM → KMS Decrypt do recipienta → preview-only → audyt metadanych i canary → negatywne próby operatora na rolach, release i key-policy → awarie/retry. Wymaga dwóch realnie niezależnych tożsamości (operator + kustosz) i uprawnionego audytora. CI/syntetyk nie dowodzą niezależności.

**GO/NO-GO:** jakiekolwiek FAIL/BLOCKED/UNVERIFIED/EXPIRED w K1–K6 ⇒ NO_GO. Po dopisaniu w przyszłości live-verifier należy weryfikować podpis kryptograficzny i fresh evidence poza kontem operatora; nie przyjmować boolowskich `verified=true` w JSON jako dowodu. Dane produkcyjne i wysyłki urzędowe poza zakresem.


## Pilot-only admission added

SEC-12 additionally rejects every tenant other than `pilot01` and `pilot02`
with HTTP 503 even if an operator configures it in the tenant allowlist.
This is an offline safety gate and a deliberate limitation: it prevents
unverified confidential pilot endpoints from processing a real office.
The tests use invented tenant IDs only. Commercial admission remains NO_GO.

The production transition must implement and audit a separate signed
hardware/custody admission flow. Merely changing environment variables
must never authorize that transition.


## 22.11.2026 — dodatkowy hard stop przed produkcją

Trzy różne entrypointy egzekwują listę `pilot01`/`pilot02`:
`confidential.router._scope`, `confidential.worker._config` (oraz
`_process_one` dla wywołań bezpośrednich), i
`confidential.dispatch.DispatcherConfig.validate`. Próby użycia innych
tenantów kończą się odmową przed jakimkolwiek wywołaniem SQS/ECS/KMS
w tych punktach wejścia. Testy są syntetyczne, nie poświadczają uprawnień AWS.

Workflow `confidential-browser.yml` publikuje artefakt
`sec12-offline-matrix` zawierający 19 wierszy z typem, wynikiem,
`source=MOCK`, `run_type=SYNTHETIC_ONLY`,
`real_aws_calls=0` i `commercial_go=false`. Retencja: 30 dni.
Ten artefakt ma ułatwić kontrolę regresji, NIE pełni funkcji
niezależnie podpisanego dowodu ani audytu hardware.

Ograniczenie: sama nazwa `pilot01`/`pilot02` NIE poświadcza,
że w przesłanym szyfrogramie nie ma rzeczywistych danych osobowych.
W pilocie wolno przekazywać **wyłącznie fikcyjne dane testowe**;
bez niezależnego zatwierdzenia oraz dodatkowego dowodu dopuszczenia
rzeczywistych danych weryfikacja K1–K6 pozostaje BLOCKED.


### Dowód regresji dla krytycznych scenariuszy

CI wykonuje `pytest` dla `test_confidential_adversarial_e2e.py`
osobno, wytwarza `notarai-sec12-tests.xml` w formacie JUnit,
a bramka wymaga co najmniej **65 zebranych testów** oraz dokładnie
`failures=0`, `errors=0`, `skipped=0`. Plik JUnit i raport
`notarai-sec12-gate.json` trafiają razem do artefaktu
`sec12-offline-matrix` (retencja 30 dni). To mierzalny dowód działania
regresji w CI, lecz nadal **nie** dowód realnego hardware AWS.
