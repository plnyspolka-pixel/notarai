# SEC-02 — rejestr dowodów / evidence ledger

Data: 2026-11-22 UTC. Wykonawca kodu: ChatGPT. Repo PR: https://github.com/plnyspolka-pixel/notarai/pull/67

Ograniczenia: pilotażowe wyłącznie pilot01/pilot02, eu-central-1, dane syntetyczne. Brak AWS credentials, AWS write, rzeczywistych testów IAM/STS, niezależnego audytora, wglądu do root/SSO/Organizations. Brak plaintext/PII/DEK.

| Kryterium | Status | Dowód w repo | Brakujący dowód do PASS |
|---|---|---|---|
| K1 Pełny rejestr | BLOCKED | docs/security-workstreams/SEC-02-implementation.md oraz `scripts/confidential_operator_iam_source_inventory.py` (źródłowy redacted principal→action→resource→account; artefakt CI tylko po sukcesie run) | live enumeracja IAM, ECS, ECR, CloudFormation RoleARN, GitHub OIDC, SCP, SSO, root |
| K2 Least privilege | BLOCKED | infra/notarai-confidential-operator-iam.yaml (jawny Deny NotAction + NotResource przeciw grantom bezpośrednio do role session); confidential/operator_iam_controls.py | AWS deploy w autoryzowanym pilocie, realne uprawnienia wszystkich operatorów i ich role source/admin |
| K3 Sześć odmów | BLOCKED | test_confidential_operator_iam_controls.py: sześć scenariuszy, mutacje Deny/NotResource, kontrola kompletności wyniku `SimulatePrincipalPolicy`; skrypt `scripts/confidential_operator_iam_evidence.py` porównuje live read-only policy z dokładnym IaC | autoryzowane live denial IAM/STS/ECR/OIDC/Cfn/KMS oraz kontrola transitive role |
| K4 Niezależność custody | BLOCKED | assess_custody_ownership w confidential/operator_iam_controls.py | niezależna atestacja AWS org management, root/recovery, delegated SSO/admin obu kont |
| K5 Break-glass | BLOCKED | runbook dwuosobowej zgody, TTL 15 min, metadata-only i testy | podpisana próba ćwiczebna, niezależny immutable audit i dowód revocation |
| K6 Real evidence | BLOCKED | szablon raportu i zakres API w SEC-02-implementation.md | redacted live IAM/STS denial, SHA256 polityk KMS/IAM, podpis zewnętrznego audytora |

Uruchamialny test: python -m pytest -q test_confidential_operator_iam_controls.py

Wynik kontrolny z wcześniejszego commit SHA `7256b9039cb3f9b2e70f546c923ab84a91ca8f0e`: **48 passed, 0 failed, 0 skipped** — [GitHub Actions #44981564902](https://github.com/plnyspolka-pixel/notarai/actions/runs/44981564902). Po tym commicie wprowadzono dalsze zmiany w kodzie i testach; **dla aktualnego HEAD trzeba niezależnie potwierdzić zielony CI**. Nie przenosić wyników starszego SHA na nowe. Dopuszczalne wyniki statyczne nie oznaczają PASS dla wymaganych dowodów live. Końcowy stan PR: OPEN/DRAFT, NOT DONE. Żadnych marketingowych twierdzeń ZT/ZOA/ZK verified.
