# OPUS — Open Source Reuse Atlas (customer-owned v3, 2026-11-22)

**Status: instrukcja dla kodowania, nie implementacja.** To jest **jedno źródło prawdy** dla #88–#91, #66, #69, #72–#78 i #63–#64. Opus ma przeczytać je **przed pisaniem kodu**. Celem jest odzyskanie istniejących modułów NotarAI, wykorzystanie OSS i uniknięcie 15 różnych implementacji tego samego protokołu.

## Instrukcja startowa do wklejenia w osobnej sesji Opusa

> Otwórz PR wskazany w tej sesji. Przeczytaj cały opis wraz z kryteriami odbioru oraz ten atlas. Najpierw zidentyfikuj wszystkie istniejące implementacje w `master`, #68, #86, #87 i pozostałych zależnościach; przygotuj tabelę `reuse / adapt / missing` z konkretnymi ścieżkami. Otwórz wskazane upstream OSS, zweryfikuj licencję, aktualny kod i API. Nie implementuj drugi raz tych samych mechanizmów. Utwórz minimalny działający kod i testy odmowy. Uruchom testy oraz CI na konkretnym SHA; zaktualizuj PR: zmienione pliki, realne wyniki, osobny status mock i live, lista ograniczeń. Nie merguj całej starej gałęzi z kustoszem i nie wdrażaj produkcyjnie bez akceptacji.

## Co już istnieje — nigdy nie tworzyć na nowo bez dowodu potrzeby

**Na `master` (potwierdzone w aktualnym drzewie repozytorium):**
- `confidential/nsm_recipient.py` — NSM; **rozbuduj**, nie tworzyć drugiego klienta NSM.
- `confidential/nitro_unwrapper.py` — istniejąca baza Nitro unwrap; v3 nie może milcząco przejść do operatorowego KMS.
- `confidential/router.py`, `confidential/worker.py` — wejście API i worker: **adaptuj**.
- `infra/notarai-confidential-task.yaml`, `infra/notarai-confidential-ecr.yaml`, `infra/notarai-confidential-capacity-base.yaml`, `scripts/render_confidential_taskdef.py`, `scripts/confidential_pilot_run.py` — istniejące IaC/uruchamianie, bez duplikowania ECS/VPC.

**Na gałęzi #87 (weryfikacja drzewka, NIE jest to jeden gotowy merge):**
- `confidential/customer_nitro_attestation.py` — weryfikator NSM/COSE/PCR.
- `confidential/customer_attested_release.py` — challenge i wydanie jednego grantu.
- `confidential/customer_guest_v3.py` — ephemeral guest RSA, NSM i sesja podglądu.
- `confidential/customer_release.py`, `confidential/customer_origin.py` — envelope, klucz kancelarii i podpis pochodzenia.
- `confidential/dispatch.py`, `confidential/document_registry.py`, `confidential/job_ledger.py`, `confidential/worker.py` — transport i ledger do adaptacji.
- `infra/notarai-confidential-shared-fabric.yaml`, `infra/notarai-confidential-job-ledger.yaml` — shared fabric i DynamoDB do ponownego wykorzystania, po selektywnym review.

**Zasada:** gałąź #87 dziedziczy stare eksperymenty custody. Przenieś pojedyncze potrzebne pliki/commity na czysty `master` i przetestuj; NIE wciskaj całości do produkcji.

## Zewnętrzne źródła — zweryfikowane repozytoria i konkretne pliki

| Upstream | Licencja | Plik/interfejs | Po co | Ważne ostrzeżenie |
|---|---|---|---|---|
| [AWS browser attestation](https://github.com/aws-samples/sample-nitro-enclaves-attestation-webapp) | MIT-0 | [`frontend/src/lib/attestationVerifier.js`](https://github.com/aws-samples/sample-nitro-enclaves-attestation-webapp/blob/main/frontend/src/lib/attestationVerifier.js), [`x509Parser.js`](https://github.com/aws-samples/sample-nitro-enclaves-attestation-webapp/blob/main/frontend/src/lib/x509Parser.js) | Parsowanie CBOR/COSE i WebCrypto w przeglądarce | **Przykład, nie audytowany zamiennik walidatora pełnego chain/trust policy**; sprawdź kompletność |
| [AWS educational verifier](https://github.com/aws-samples/sample-nitro-enclaves-attestation) | MIT-0 | [`client/attestation_verifier.py`](https://github.com/aws-samples/sample-nitro-enclaves-attestation/blob/main/client/attestation_verifier.py) | Wzorce certyfikatów/COSE w Pythonie | Dokument źródłowy deklaruje wersję edukacyjną; nie kopiuj jako produkcyjnego bezpieczeństwa |
| [AWS Nitro NSM samples](https://github.com/aws/aws-nitro-enclaves-samples) | Apache-2.0 | [`att_doc_retriever_sample/py/att_doc_retriever_sample.py`](https://github.com/aws/aws-nitro-enclaves-samples/blob/main/att_doc_retriever_sample/py/att_doc_retriever_sample.py) | Prawdziwy `/dev/nsm`, odbiór atestacji | Wzorzec syscalls, nie pełna polityka aplikacyjna |
| [AWS LLM enclave](https://github.com/aws-samples/aws-nitro-enclaves-llm) | MIT-0 | [`src/enclave/server.py`](https://github.com/aws-samples/aws-nitro-enclaves-llm/blob/main/src/enclave/server.py), [`src/vsock-proxy.yaml`](https://github.com/aws-samples/aws-nitro-enclaves-llm/blob/main/src/vsock-proxy.yaml) | Layout uruchomienia modelu i komunikacji | Przykład wywołuje KMS i loguje credentials; **tego nie kopiować** |
| [noble-hashes](https://github.com/paulmillr/noble-hashes) | MIT | [`src/argon2.ts`](https://github.com/paulmillr/noble-hashes/blob/main/src/argon2.ts) | Argon2id do backupu klucza | Kalibracja parametrów i testy interoperacyjności; nie pisać własnego KDF |
| [Sigstore cosign](https://github.com/sigstore/cosign) | Apache-2.0 | [`cmd/cosign/cli/sign/sign_blob.go`](https://github.com/sigstore/cosign/blob/main/cmd/cosign/cli/sign/sign_blob.go) | Podpis artefaktu release/dowodów | Nie budować własnej infrastruktury transparency log, jeśli nie potrzebna |
| [OPA](https://github.com/open-policy-agent/opa) | Apache-2.0 | [`rego/rego.go`](https://github.com/open-policy-agent/opa/blob/main/rego/rego.go) | Wzór policy-as-code | **Opcjonalne**: istniejąca allowlista i kontrola IAM zwykle wystarczą |
| [OpenFGA](https://github.com/openfga/openfga) | Apache-2.0 | [`docs/check/README.md`](https://github.com/openfga/openfga/blob/main/docs/check/README.md) | Model zasad dostępu do tenant/job | Dokumentacja/wzorzec; **nie uruchamiaj osobnego serwera** w MVP |
| [Microsoft Presidio](https://github.com/data-privacy-stack/presidio) | MIT | [`analyzer_engine.py`](https://github.com/data-privacy-stack/presidio/blob/main/presidio-analyzer/presidio_analyzer/analyzer_engine.py), [`anonymizer_engine.py`](https://github.com/data-privacy-stack/presidio/blob/main/presidio-anonymizer/presidio_anonymizer/anonymizer_engine.py) | Rozpoznawanie i redakcja PII w testach | Redakcja nie zastępuje kryptografii i nie zapewnia pełnej poufności |
| [Microsoft Agent Governance](https://github.com/microsoft/agent-governance-toolkit) | MIT | [`policy-engine/sdk/python/README.md`](https://github.com/microsoft/agent-governance-toolkit/blob/main/policy-engine/sdk/python/README.md) | Wzorce `allow/deny/transform`, aprobata działań agenta | Nie instaluj całego frameworka tylko dla małej allowlisty |
| [FlaUI](https://github.com/FlaUI/FlaUI) | MIT | [`README.md`](https://github.com/FlaUI/FlaUI/blob/main/README.md), NuGet `FlaUI.UIA3`/`FlaUI.Core` | UI Automation Windows | Testuj tylko na syntetycznym Notepad/VM; nie wymuszaj UIA3 gdy aplikacja wymaga UIA2 |

Przed vendoringiem: pin dokładnego tagu/commita, zanotuj licencję i jej tekst, autora/źródło, własne zmiany, znane luki oraz metodę aktualizacji. Preferuj bibliotekę i adapter zamiast kopiowania całego źródła.

## Miniwzorce integracyjne — NASZE pseudokody (nie kopiowane z OSS, nie gotowy kod)

### A. #89: grant wydany wyłącznie po weryfikacji klienta

```ts
const nonce = secureRandomBytes(32);
const challenge = bind({jobId, envelopeSha256, nonce});
const attestation = await requestNitroAttestation(challenge);
// Verify cryptographically ON CLIENT: AWS root+chain+COSE, freshness,
// signed release policy, PCR8/PCR17, nonce/user_data, recipient SPKI.
const recipient = await verifyNitroOrThrow(attestation, challenge, trustedRelease);
const wrappedDek = await wrapDekForRecipient(dek, recipient.rsaSpki, challenge);
// No fallback to server's "verified" flag or operator-provided pubkey.
```

### B. #90: atomowe zużycie grantu przed odszyfrowaniem

```python
def execute_once(job, grant):
    validate_signed_document_origin(job)
    validate_exact_s3_version_and_hash(job)
    validate_grant_scope_and_expiry(job, grant)
    # Conditional update: pending -> consumed; fail on replay or concurrent worker.
    ledger.consume_once(job.id, grant.id, expected_state="pending")
    return guest.decrypt_and_preview_only(job, grant)
```

### C. #91: kopia klucza bez recovery operatora

```ts
// The encrypted backup must be generated locally by the trusted client.
const key = argon2id(passphrase, randomSalt, calibratedParameters);
const encryptedKey = aeadEncrypt(key, exportedPrivateKey, backupMetadata);
downloadOfflineBackup({version: 1, salt, params: calibratedParameters, encryptedKey});
// Verify restoration on a second device/profile before real documents.
```

### D. #63/#64: Windows only with deterministic policy

```python
decision = check_action_policy(tenant, signed_skill, proposed_action, current_screen)
if decision != "allow":
    return needs_human_approval_or_deny()
# UIA via FlaUI, readback of current state, no auto-submit/sign.
result = execute_allowlisted_uia_action(proposed_action)
return verify_ui_state_after_action(result)
```

**Każdy blok powyżej to niekompletna ilustracja granicy modułów.** Nie uruchamiać ani nie traktować jako bezpiecznej implementacji. Opus musi skleić go z faktycznymi typami, podpisami, stanami DDB i testami w repozytorium.

## Mapa dla KAŻDEGO PR — konkretna instrukcja dla Opusa

| PR | Najpierw otwórz w NotarAI | OSS do adaptacji | Czego nie rób ponownie |
|---|---|---|---|
| **#88** | `customer_release.py`, `customer_origin.py`, `customer_nitro_attestation.py`, `customer_guest_v3.py` na #87; `nsm_recipient.py` na master | AWS browser verifier + Python educational verifier | Własny parser COSE i nowy customer key protocol; przenieś testy |
| **#89** | `customer_attested_release.py`, `scripts/customer_attested_release.py`; klient HTML z #68 | AWS JS `attestationVerifier.js`/`x509Parser.js`; cosign dla podpisanych wydań | Dynamiczna „zaufana” strona bez przypięcia klucza, duplikowanie WebCrypto |
| **#90** | `worker.py`, `router.py` na master; `dispatch.py`, `document_registry.py`, `job_ledger.py`, `customer_guest_v3.py` na #87 | NSM retriever; AWS enclave/vsock layout | Drugi worker/ECS/kolejka, nowy ledger, operator KMS decrypt |
| **#91** | `customer_release.py`, client UI z #89 | noble-hashes Argon2id; WebCrypto AEAD | Własny KDF, helpdesk key escrow, Shamir |
| **#66** | `docs/security-workstreams` na #87; program bazowy `#88` | AWS attestation threat boundary | Military threat model, kustosz |
| **#69** | `confidential/worker.py`, #40 EU gateway | Nitro LLM server/vsock, Presidio analyzer | Nowy MLOps stack lub twierdzenie, że zwykły Bedrock jest ZK |
| **#72** | `customer_nitro_attestation.py`, `nsm_recipient.py`, #87 tests | AWS NSM retriever + browser verifier | Nowy atestation parser; mylenie synthetic PASS z AWS hardware PASS |
| **#73** | `router.py`, `worker.py`, #56 egress, #90 | Governance Toolkit/OPA policy patterns (opcjonalne) | Własny rozproszony firewall lub nowe konto custody |
| **#74** | `job_ledger.py`, `document_registry.py`, `dispatch.py`; #60 shared fabric | OpenFGA check semantics (jako wzorzec), IAM | Oddzielny serwer OpenFGA lub VPC per tenant |
| **#75** | `worker.py`, `job_ledger.py`, #90 data flow | Presidio analyzer/anonymizer dla testów/redakcji | Nowy storage i 3 zewnętrzne podpisy do każdej operacji |
| **#76** | `customer_attested_release.py`, #87 reports, #85 | cosign verify/sign | Blockchain lub osobny kustosz transparency |
| **#77** | `scripts/confidential_pilot_run.py`, `scripts/render_confidential_taskdef.py`; #90 workflow | AWS Nitro NSM sample | Osobna platforma pilotowa; powtórne całe E2E |
| **#78** | #66 claims, #72 hardware reports, #76 evidence | cosign verify | Własny certyfikator, uniwersalna obietnica Zero Knowledge |
| **#63** | existing `computer_use/` code na gałęzi #63 | FlaUI, Agent Governance Toolkit | Własny UIA stack i autonomiczne submit/sign |
| **#64** | pilot VM, signed-job code w #64 | FlaUI.UIA3 and UIA2 fallback | Instalacja NotarAI na PC notariusza, nowy protokół bez testów |

## Minimalna forma raportu Opusa w KAŻDYM PR

```text
REUSE INVENTORY
- existing modules reused: ...
- OSS actually imported/ported: URL + pinned SHA/tag + SPDX license + changed symbols
- functionality deliberately not rebuilt: ...

DIFF
- paths changed: ...
- contract version changes: ...

TEST EVIDENCE
- command / exact HEAD SHA / passed / failed / skipped / URL
- synthetic: PASS | FAIL
- authorized AWS live: PASS | BLOCKED | FAIL
- no plaintext, no submit, cross-tenant denials: PASS | FAIL | NOT TESTED

HANDOFF
- acceptance checklist: each criterion PASS/BLOCKED/FAIL
- blockers and single next PR
```

**Fail closed on missing evidence.** Żaden PR z tekstem „wygląda bezpiecznie” bez linku do kodu/testów nie jest ukończony.
