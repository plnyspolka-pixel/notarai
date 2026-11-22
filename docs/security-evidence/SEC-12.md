# SEC-12 — Adversarial E2E and commercial release gate

**22.11.2026 — IMPLEMENTED OFFLINE; REAL AWS / NITRO E2E BLOCKED. PR #77 DRAFT.**

## Co wykonano w tej gałęzi
- `confidential/adversarial_gate.py`: deterministyczna macierz 19 prób na fikcyjnych `pilot01` i `pilot02`. Dwa scenariusze pozytywne, 13 prób obejścia i cztery awarie. Przetwarza wyłącznie metadane fikcyjne.
- `test_confidential_adversarial_e2e.py`: testy 13 odmów, czterech awarii, oddzielnych tożsamości KMS/IAM, kompletności raportu i zakazu automatycznego GO.
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
