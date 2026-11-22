# SEC-02 — rejestr dowodów / evidence ledger

Data: 2026-11-22 UTC. Wykonawca kodu: ChatGPT. Repo PR: https://github.com/plnyspolka-pixel/notarai/pull/67

Ograniczenia: pilotażowe wyłącznie pilot01/pilot02, eu-central-1, dane syntetyczne. Brak AWS credentials, AWS write, rzeczywistych testów IAM/STS, niezależnego audytora, wglądu do root/SSO/Organizations. Brak plaintext/PII/DEK.

| Kryterium | Status | Dowód w repo | Brakujący dowód do PASS |
|---|---|---|---|
| K1 Pełny rejestr | BLOCKED | docs/security-workstreams/SEC-02-implementation.md oraz istniejące szablony IAM | live enumeracja IAM, ECS, ECR, CloudFormation RoleARN, GitHub OIDC, SCP, SSO, root |
| K2 Least privilege | BLOCKED | infra/notarai-confidential-operator-iam.yaml; confidential/operator_iam_controls.py | AWS deploy w autoryzowanym pilocie, realne uprawnienia wszystkich operatorów i ich role source/admin |
| K3 Sześć odmów | BLOCKED | test_confidential_operator_iam_controls.py: sześć scenariuszy + mutacje | autoryzowane live denial IAM/STS/ECR/OIDC/Cfn/KMS oraz kontrola transitive role |
| K4 Niezależność custody | BLOCKED | assess_custody_ownership w confidential/operator_iam_controls.py | niezależna atestacja AWS org management, root/recovery, delegated SSO/admin obu kont |
| K5 Break-glass | BLOCKED | runbook dwuosobowej zgody, TTL 15 min, metadata-only i testy | podpisana próba ćwiczebna, niezależny immutable audit i dowód revocation |
| K6 Real evidence | BLOCKED | szablon raportu i zakres API w SEC-02-implementation.md | redacted live IAM/STS denial, SHA256 polityk KMS/IAM, podpis zewnętrznego audytora |

Uruchamialny test: python -m pytest -q test_confidential_operator_iam_controls.py

Wynik testu: do osobnej weryfikacji w GitHub Actions dla aktualnego HEAD; nie jest tu deklarowany PASS. Dopuszczalne wyniki statyczne nie oznaczają PASS dla wymaganych dowodów live. Końcowy stan PR: OPEN/DRAFT, NOT DONE. Żadnych marketingowych twierdzeń ZT/ZOA/ZK verified.
