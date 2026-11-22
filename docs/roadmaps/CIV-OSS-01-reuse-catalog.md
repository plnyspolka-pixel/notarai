# CIV-OSS-01 — zweryfikowany katalog gotowych komponentów do NotarAI Confidential

**Sprawdzono GitHub 22.11.2026.** Wpis oznacza sprawdzony adres repo i deklarację licencji, nie niezależny audyt jakości ani gwarancję kompatybilności. Opus ma przed importem sprawdzić wybrany *tag/commit SHA*, licencję pliku, zależności, obecne API i testy; do raportu wkleić dokładne `source@SHA` i `destination path`. Nie kopiować losowych fragmentów z internetowych gistów. **Preferencja: kod, który już istnieje w NotarAI, > mała biblioteka > cały nowy framework.**

## A. Wykorzystaj NAJPIERW istniejący kod NotarAI

| Własny kod / źródło | Zastosowanie i zadania | NIE przepisywać |
|---|---|---|
| [#86 `confidential/customer_release.py`](https://github.com/plnyspolka-pixel/notarai/blob/feature/confidential-customer-keys-minimal-20261122/confidential/customer_release.py) | AES-256-GCM envelope v3, RSA-3072 owner, OAEP SHA-256, `issue_job_release` i `open_preview_in_guest` | Envelope serializer, wrap/unwrap DEK i walidacji tenant/job |
| [#86 `confidential/customer_origin.py`](https://github.com/plnyspolka-pixel/notarai/blob/feature/confidential-customer-keys-minimal-20261122/confidential/customer_origin.py) | Podpis Ed25519 pochodzenia dokumentu i receipt przed otwarciem | Własnego schematu podpisów ani rozróżnienia nadawcy w guest |
| [#87 `confidential/customer_nitro_attestation.py`](https://github.com/plnyspolka-pixel/notarai/blob/feature/sec86-customer-attested-release-20261122/confidential/customer_nitro_attestation.py) | Offline COSE_Sign1/ES384, X.509 chain, root pin, PCR, nonce, RSA SPKI | Własnego dekodera „verified: true” z API, nowego łańcucha certyfikatów |
| [#87 `confidential/customer_attested_release.py`](https://github.com/plnyspolka-pixel/notarai/blob/feature/sec86-customer-attested-release-20261122/confidential/customer_attested_release.py) | `challenge_user_data`, `issue_attested_job_release`; wiązanie hash koperty z job/nonce | Osobnego serwera wydawania kluczy i zaufania do klucza operatora |
| [#87 `confidential/customer_guest_v3.py`](https://github.com/plnyspolka-pixel/notarai/blob/feature/sec86-customer-attested-release-20261122/confidential/customer_guest_v3.py) | NSM guest, efemeryczny RSA, pojedyncza sesja | Innego guest receiver, drugiego protokołu od zera |
| [#87 `confidential/nsm_recipient.py`](https://github.com/plnyspolka-pixel/notarai/blob/feature/sec86-customer-attested-release-20261122/confidential/nsm_recipient.py) | NSM request nonce/user_data | Nowego wrappera /dev/nsm |
| [#68 `docs/security-workstreams/SEC-03-...`](https://github.com/plnyspolka-pixel/notarai/pull/68) | Niezależny podpisany klient offline i document registry (zob. zmienione pliki PR przed importem) | Nie przenosić starych KMS ARN/kustosza z v2 |
| [#50](https://github.com/plnyspolka-pixel/notarai/pull/50), [#51](https://github.com/plnyspolka-pixel/notarai/pull/51) | Obecne Nitro, AWS, Chromium, system pilota na master | Nowego stacku chmurowego |
| [#57](https://github.com/plnyspolka-pixel/notarai/pull/57), [#60](https://github.com/plnyspolka-pixel/notarai/pull/60), [#74](https://github.com/plnyspolka-pixel/notarai/pull/74) | Job ledger, shared VPC/ECS/ECR, separacja tenant — adaptować *selektywnie* | Duplikatu SQS/registries, osobnej VPC na każdy tenant |
| [#63](https://github.com/plnyspolka-pixel/notarai/pull/63), [#64](https://github.com/plnyspolka-pixel/notarai/pull/64) | Computer Use, Windows VM, UIA, testy, odrębna granica ochrony | Drugiego systemu agentów i VM |

**Przykładowy wycinek kontraktu już napisanego w #87** (orientacyjny interfejs integracyjny, nie nowy kod):
```python
from confidential.customer_attested_release import (
    challenge_user_data, issue_attested_job_release,
)
# nonce powstaje w niezależnym kliencie kancelarii;
# user_data wiąże SHA-256 koperty, job_id i nonce.
# issue_attested_job_release weryfikuje pełną atestację
# PRZED dopuszczeniem do RSA rewrap klucza dokumentu.
```

## B. Sprawdzone OSS (repo, dokładne pliki i licencja)

| Komponent / licencja | Weryfikowany link | Po co i kiedy | Uwaga wdrożeniowa |
|---|---|---|---|
| AWS Nitro browser verifier — **MIT-0** | [`attestationVerifier.js`](https://github.com/aws-samples/sample-nitro-enclaves-attestation-webapp/blob/main/frontend/src/lib/attestationVerifier.js), [`x509Parser.js`](https://github.com/aws-samples/sample-nitro-enclaves-attestation-webapp/blob/main/frontend/src/lib/x509Parser.js) | #89: startowy wzorzec browser COSE/X.509 | **Wzorzec, nie gotowy bezwarunkowy weryfikator produkcyjny.** Dodać testy całego chain, ES384, alg confusion, prawdziwe PCR8/17, fresh nonce/job, debug, exp i podpisu klienta. Własny Python #87 jest źródłem reguł, nie wolno go zastąpić samą walidacją pól |
| AWS Nitro attestation demo — **MIT-0** | [`client/attestation_verifier.py`](https://github.com/aws-samples/sample-nitro-enclaves-attestation/blob/main/client/attestation_verifier.py) | #88/#72: przykładowe dekodowanie i polityka raportu | Uwaga: plik deklaruje „simplified for educational purposes”; **nie kopiować samego testu checksum CA jako pełnego certificate path validation** |
| AWS Nitro NSM API — **Apache-2.0** | [`aws-nitro-enclaves-nsm-api`](https://github.com/aws/aws-nitro-enclaves-nsm-api) | #90/#72: oryginalny kontrakt dokumentu atestacji i NSM | Najpierw użyj wrappera `nsm_recipient.py` z #87 |
| AWS Nitro C SDK — **Apache-2.0** | [`aws-nitro-enclaves-sdk-c`](https://github.com/aws/aws-nitro-enclaves-sdk-c) | #72: przykłady native integrations tylko jeśli Python NSM niewystarczający | Nie dodawaj C SDK do Pythona bez konkretnej potrzeby |
| AWS attestation retriever + vsock — **Apache-2.0** | [`att_doc_retriever_sample/py/att_doc_retriever_sample.py`](https://github.com/aws/aws-nitro-enclaves-samples/blob/main/att_doc_retriever_sample/py/att_doc_retriever_sample.py), [`vsock_sample/py`](https://github.com/aws/aws-nitro-enclaves-samples/tree/main/vsock_sample/py) | #90/#72: request do /dev/nsm i komunikacja vsock | Zmapuj do istniejącego protokołu, nie implementuj równolegle trzech kanałów IPC |
| `cbor-x` — **MIT** | [repo](https://github.com/kriszyp/cbor-x) | #89: dekoder CBOR/COSE w przeglądarce, jeśli obecny dekoder jest niewystarczający | `cbor-x` to dekoder CBOR, **nie** weryfikator certyfikatów/COSE; jawnie testuj tagi i kanoniczność |
| `jose` — **MIT** | [repo](https://github.com/panva/jose) | #89/#76: podpisy release JWS tylko **jeśli** zgodne z istniejącym formatem | Nie przepisywać istniejącego Ed25519 binarnego receipt na JWS bez zysku |
| `@noble/hashes` Argon2id — **MIT** | [`src/argon2.ts`](https://github.com/paulmillr/noble-hashes/blob/main/src/argon2.ts) | #91: KDF do bezpiecznego offline backupu klucza | Sprawdź wsparcie przeglądarek, koszt KDF i pamięć; AEAD użyć z WebCrypto, nie pisz go sam |
| Sigstore `cosign` — **Apache-2.0** | [repo](https://github.com/sigstore/cosign), [`sign_blob.go`](https://github.com/sigstore/cosign/blob/main/cmd/cosign/cli/sign/sign_blob.go) | #89/#76: podpis artefaktów i manifestów image@digest | Narzędzie wydania **nie zastępuje zaufanego kanału publikacji klucza/pinu** |
| OPA — **Apache-2.0** | [repo](https://github.com/open-policy-agent/opa), [`rego/rego.go`](https://github.com/open-policy-agent/opa/blob/main/rego/rego.go) | #66/#73: reguły policy-as-code, ale tylko gdy obecne if/allowlist są niewystarczające | Nie wprowadzać nowego policy servera w MVP bez uzasadnienia |
| OpenFGA — **Apache-2.0** | [repo](https://github.com/openfga/openfga), [`docs/check/README.md`](https://github.com/openfga/openfga/blob/main/docs/check/README.md) | #74: model permissions tenant/case/notary, **do inspiracji** | Nie wdrażać osobnego auth serwisu przy małej, statycznej macierzy ról |
| Microsoft Agent Governance Toolkit — **MIT** | [`policy-engine/sdk/python/README.md`](https://github.com/microsoft/agent-governance-toolkit/blob/main/policy-engine/sdk/python/README.md) | #63/#69: allow/deny/transform i rozdział autoryzacji LLM od wykonania | API host SDK różni się od standalone `agent-control-spec`; preferuj adaptację testów/polityki bez nowego silnika |
| Microsoft Presidio — **MIT** | [`analyzer_engine.py`](https://github.com/data-privacy-stack/presidio/blob/main/presidio-analyzer/presidio_analyzer/analyzer_engine.py), [`anonymizer_engine.py`](https://github.com/data-privacy-stack/presidio/blob/main/presidio-anonymizer/presidio_anonymizer/anonymizer_engine.py) | #69/#75: redakcja danych przed opcjonalnym zewnętrznym AI/logowaniem | **Nie gwarantuje** usunięcia wszystkich danych osobowych z polskich aktów; testuj na fikcyjnych PESEL/KW/adresach |
| AWS Nitro LLM POC — **MIT-0** | [`src/enclave/server.py`](https://github.com/aws-samples/aws-nitro-enclaves-llm/blob/main/src/enclave/server.py), [Dockerfile](https://github.com/aws-samples/aws-nitro-enclaves-llm/blob/main/src/enclave/Dockerfile) | #69: inspiracja inference w Nitro | Demo zawiera jawne `print(credentials)` i integrację KMS, **NIE KOPIOWAĆ GO DO PRODUKCJI**, nie jest gotowym backendem ZOA |
| Playwright — **Apache-2.0** | [repo](https://github.com/microsoft/playwright) | #73/#77/#63: testy przeglądarki, już używane w obecnym kodzie | Nie pisać nowego browser automation engine |
| FlaUI — **MIT** | [repo](https://github.com/FlaUI/FlaUI) | #63/#64: Windows UIA3, już w pilocie Windows | Użyj istniejącego adaptera z #64, nie wywołuj arbitralnych akcji OS |

## C. Zakaz powtarzania już wykonanej pracy
- **Nie buduj nowego cryptographic release flow:** #86 + #87 jest punktem wyjścia.
- **Nie buduj drugiego S3/SQS/ECS:** #50/#51/#57/#60.
- **Nie buduj nowego login/permission engine:** wykorzystaj aktualną sesję/role, OPA/FGA to opcja z kosztem, nie wymaganie.
- **Nie buduj „idealnego secure AI”**: najpierw jeden realny, testowalny backend i uczciwy unavailable w #69.
- **Nie buduj własnego narzędzia do obsługi Chromium i Windows**: Playwright, istniejące adapters #63/#64, FlaUI.
- **Nie buduj zewnętrznego kustosza kluczy**: jawna decyzja architektoniczna.
- **Nie kopiuj cudzych kawałków kodu bez licencji i commit SHA:** w PR zapisz listę przejętych plików i wymagane attribution; przechowaj odpowiedni NOTICE/licencję tam, gdzie konieczne.

## D. Szablon raportu Opusa — obowiązkowy we wszystkich PR
1. `EXISTING REUSE`: źródłowy PR/plik/SHA → docelowy plik/funkcja.
2. `OSS REUSE`: nazwa/repo/file/commit/license → użycie/odrzucenie, wraz z powodem.
3. `DO NOT REIMPLEMENT`: lista funkcji istniejących, z których korzystasz.
4. `DELIVERABLES`: rzeczywiste commity/patches/tests/docs, brak pustej implementacji.
5. `ACCEPTANCE`: tabelka kryterium → dokładny test/CI run URL/sha → PASS/FAIL/BLOCKED.
6. `SAFETY`: synthetic only, brak deploymentu lub jawnie autoryzowany staging, ograniczenia claims.

**Dyrektywa:** jeśli ten sam komponent jest potrzebny kilku PR-om, powinien mieć jednego właściciela (najczęściej #88 API, #89 browser, #90 guest), a pozostałe go importują. Nie duplikuj po 15 razy własnych dekoderów, formatów koperty, tenant-policy ani client-signature.
