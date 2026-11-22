# NotarAI 3 × ZERO on AWS — jedna ścieżka produkcyjna

**Data:** 2026-11-22. **Decyzja architektoniczna właściciela:** ufamy zobowiązaniom oraz udokumentowanym mechanizmom AWS i na nich opieramy usługę cywilną. To nie jest projekt mający udowadniać, że AWS jest wrogiem. Chronimy poufność wobec operatorów **NotarAI**, nie wobec zaufanego dostawcy AWS. Twierdzenia marketingowe muszą mieć określony zakres i dowody.

## 0. Co już istniało na master (sprawdzono w repo)

- `infra/notarai-confidential-task.yaml`: **AWS ECS `CONFIDENTIAL_SANDBOX`**, nie nowe odkrycie i nie planowana migracja.
- `infra/notarai-confidential-capacity-base.yaml`, `scripts/render_confidential_taskdef.py`: ECS Managed Instances, digest ECR, PCR17, AWS region.
- `confidential/worker.py`: fail-closed `/dev/nsm`, SQS → S3 → attested KMS → Playwright demo, **preview-only**.
- `confidential/nsm_recipient.py`: przykład MIT-0 z AWS, NSM + recipient KMS; kopiowanie go ponownie jest zbędne.
- `test_confidential_infra.py`, `test_confidential_worker.py`: istniejące testy syntetyczne.
- UWAGA: `infra/notarai-confidential-demo-kms.yaml` wyraźnie określa klucz jako **AWS-account-administered, synthetic only**; nie jest to dowód niezależnej kontroli klucza kancelarii.

## 1. Co właśnie przejęto, zamiast napisać ponownie

Z archiwalnego #86/#87 **selektywnie** przeniesiono do czystego master (bez łączenia całego starego custody):
- `confidential/customer_release.py` — AES-GCM i RSA-3072 kancelarii (envelope v3), jednorazowy grant.
- `confidential/customer_origin.py` — podpis pochodzenia i niezmienna wersja S3.
- `confidential/customer_nitro_attestation.py` i `customer_attested_release.py` — COSE/X.509, AWS Nitro root, PCR8/17, nonce i recipient.
- `confidential/customer_guest_v3.py` i zmodyfikowany `nsm_recipient.py` — jeden guest/jeden podgląd.
- Testy, CLI klienta i dedykowany CI; ten kod jest **prototypem offline** i nie jest jeszcze połączony z istniejącym AWS S3/SQS workerem.

Nowy moduł `confidential/three_zero_gate.py` jest **małą kontrolą konfiguracji** ECS/Bedrock, nie zamiennikiem AWS Nitro, KMS, czy atestacji. Read-only CLI `scripts/audit_three_zero_aws.py` nigdy nie ogłasza automatycznie GO.

## 2. Minimalne 3 × ZERO — granice, które dają się sprawdzić

| Hasło | Zakres produktu | Odbiór |
|---|---|---|
| Zero Trust | Autoryzacja tenant/job i brak automatycznego zaufania do operatorowego żądania, konfiguracji, API lub certyfikatu | Odmowa dla obcego klienta, niepodpisanego żądania, replay, innego obrazu/PCR |
| Zero Operator Access | Operator NotarAI nie może jednostronnie odzyskać plaintextu ani DEK z S3/KMS ani podmienić kodu i wydać klucza bez zgody kancelarii | Prawdziwa atestacja + klientowskie wydanie klucza, negatywna próba z uprawnieniami operatora |
| Zero Knowledge (zakresowe) | NotarAI jako operator nie dostaje treści. AWS Nitro + Bedrock są **zaufanymi podprocesorami**. To nie jest matematyczny ZKP ani obietnica braku przetwarzania przez AWS | Brak plaintext w operator API/logach/storage; udokumentowane kontrakty AWS i model/region/retencja Bedrock |

**Nigdy nie przenosić automatycznie tego twierdzenia na Windows VM/RejNET, portale zewnętrzne i model Bedrock w trybie niezweryfikowanym.**

## 3. Co redukujemy trwale

- **Nie wdrażamy:** niezależnego kustosza, obcego konta custody KMS, Shamir/MPC/FHE, blockchain/WORM u trzeciego podmiotu, trzech podpisów każdego zlecenia, drugiego frameworka atestacji, własnego serwera OpenFGA/OPA bez potrzeby.
- **Nie przebudowujemy:** ECS Nitro Sandbox, task definition, shared VPC/ECR, istniejącego workera i ledger; adaptujemy bieżący kod.
- **Zachowujemy koniecznie:** customer-owned DEK i lokalny podpisany weryfikator, PCR-policy/release manifest, operator/admin key-policy mutation boundary, brak logowania plaintextu, tenant isolation, niepowtarzalny grant, read-only audyt dostawcy.
- **W szczególności:** fakt, że AWS Nitro chroni pamięć przed parent/operatorem AWS, nie powstrzymuje naszego *własnego* workera przed świadomym wysłaniem danych. Dlatego blokujemy zmiany kodu i nieautoryzowane egress.

## 4. Jedna ścieżka wdrożenia i mierzalne bramki (bez kolejnej serii 15 PR-ów)

### A. W kodzie — branch obecny
- [x] Archiwizacja 41 PR-ów: `archive/three-zero-legacy-complete-20261122`; wszystkie osobne snapshoty odzyskiwalne z historii archiwalnej.
- [x] Czysta ekstrakcja biblioteki customer-owned v3 z #86/#87.
- [x] Statyczny skaner task-definition, logów Bedrock i stanu ECS — zawsze oznacza hardware i ZOA jako **niezweryfikowane**.
- [ ] Zielony GitHub CI na aktualnym SHA (sprawdzić po utworzeniu PR).
- [ ] Połączenie v3 z istniejącym workerem SQS/S3 i atomowym anty-replay, podpisanym pochodzeniem oraz rzeczywistym odczytem VersionId.
- [ ] Prosty i niezależnie dystrybuowany **klient przeglądarkowy**, który weryfikuje attestation AWS zanim wyda klucz.
- [ ] Kopia/restore klucza kancelarii.

### B. W AWS — wymaga autoryzowanego konta i pilota, bez danych prawdziwych
- [ ] Zatwierdzone `image@sha256`, wygenerowana polityka `ecs-nitro-sandbox-genpolicy`, PCR8/PCR17.
- [ ] Realny ECS confidential sandbox + prawdziwa atestacja NSM, **pozytywny i negatywny** test wydania klucza.
- [ ] Operator/admin: próby podmiany obrazu, polityki KMS, roli/IAM i klienta — żadna nie może doprowadzić do nieautoryzowanego odczytu.
- [ ] Dwie fikcyjne kancelarie, próby cross-tenant, restart, SQS replay i potwierdzony brak plaintext w logach.
- [ ] Odczyt AWS `bedrock:GetModelInvocationLoggingConfiguration` oraz dowód blokady ponownego włączenia logów dla operatora NotarAI.
- [ ] Jeden zatwierdzony model Claude, endpoint, EU profile/region i polityka retencji z [AWS Bedrock data retention](https://docs.aws.amazon.com/bedrock/latest/userguide/data-retention.html).
- [ ] DPA/warunki AWS, poufność notarialna, ewentualny niezależny przegląd konkretnych claims i prosty raport dowodów.

**Status do czasu spełnienia B:** `NO_GO` dla marketingowego pełnego 3 × ZERO. Zielony CI ≠ prawdziwy dowód AWS.

## 5. CLI: read-only preflight

```bash
# Bez AWS: czytelny NO_GO, gdy brak dowodów
python scripts/audit_three_zero_aws.py

# Jawny audyt AWS: STS + ECS + Bedrock GET; zero mutacji, bez pobierania dokumentów
python scripts/audit_three_zero_aws.py --check-aws \
  --profile <autoryzowany-profil> --account <12-cyfr> \
  --task-definition <zarejestrowany-task-definition> \
  --cluster <ecs-cluster> --task-arn <ecs-task-arn>
```

**CLI nigdy nie aktywuje produkcji ani nie zwraca GO**; nawet wszystkie `PASS_STATIC` wymagają niezależnych dowodów sprzętowych i kontraktowych. Rola audytora wymaga wyłącznie `sts:GetCallerIdentity`, `ecs:DescribeTaskDefinition`, `ecs:DescribeTasks`, `bedrock:GetModelInvocationLoggingConfiguration`.

## 6. AWS źródła — nie zastępuj deklaracji dostawcy własnymi mitami

- [ECS Confidential Sandboxes – security model](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/ict-security-model.html): weryfikacja PCR musi być egzekwowana przez KMS lub niezależny klient; sam pomiar to nie odmowa.
- [ECS attestation policy](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/ict-confidential-policy-configuration.html): PCR8, PCR17, policy generator.
- [AWS Bedrock logging](https://docs.aws.amazon.com/bedrock/latest/userguide/model-invocation-logging.html): wyłączone domyślnie, ale operator konta może je włączyć; porównać realne ustawienia.
- [AWS Bedrock data retention](https://docs.aws.amazon.com/bedrock/latest/userguide/data-retention.html): model-specyficzne tryby i wyjątki.
- [AWS Bedrock data protection](https://docs.aws.amazon.com/bedrock/latest/userguide/data-protection.html): dostawcy modeli nie widzą promptów klienta; AWS pozostaje zaufanym dostawcą.

## 7. Archiwum i zasada utrzymania

[Pełny indeks backupu 41 PR-ów](https://github.com/plnyspolka-pixel/notarai/blob/archive/three-zero-legacy-complete-20261122/archive/THREE_ZERO_LEGACY_SNAPSHOTS.md). **Nie mergować gałęzi archiwalnej.** Oryginalne PR-y mogą pozostać czytelne jako referencje, a po zastąpieniu mogą być zamykane z linkiem do głównego implementacyjnego PR. Klient Windows/RejNET to osobny produkt i osobny model zagrożeń.
