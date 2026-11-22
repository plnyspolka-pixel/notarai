# CIV-OSS — katalog kodu do ponownego wykorzystania (NotarAI Confidential)

Stan sprawdzenia: **2026-11-22**. Katalog to mapa implementacji dla **Claude Opus** pracującego w oddzielnej sesji nad konkretnym PR-em. Nie jest listą technologii do instalowania. Najpierw odczytaj **nasz kod**, potem **wskazany plik w OSS**, przejmij tylko brakującą funkcję, zachowaj testy i wymagane informacje licencyjne.

## Zasady absolutne dla każdego Opusa

1. **READ FIRST:** właściwy PR + dokument CIV-XX / aneks, aktualny `master`, poprzednie PR #50/#51, źródłowe #68/#86/#87. Czytaj kod i testy, nie polegaj na opisie ze starego czatu.
2. **REUSE FIRST:** jeśli funkcja istnieje w NotarAI, zaadaptuj ją; nie stawiaj konkurencyjnego gateway, polityk, serwisu kluczy, kolejki, VPC ani frameworka. Zwróć w opisie tabelę `istnieje → adaptuję → nowy kod` dla każdego elementu.
3. **COPY LEGALLY:** nie kopiuj z przypadkowych repozytoriów; przed skopiowaniem sprawdź `LICENSE` także na poziomie podkatalogu, identyfikator konkretnego SHA i odpowiednie zależności. Zachowaj copyright/NOTICE/attribution w `THIRD_PARTY_NOTICES.md`; odnotuj pliki, zakres i ewentualne modyfikacje. Preferuj użycie biblioteki jako zależności zamiast kopiowania. NIE zakładaj, że każde publiczne repo = wolna licencja.
4. **SOURCE PINNING:** otwarte linki poniżej wskazują aktualny branch, aby łatwo znaleźć kod. Przed użyciem wybierz konkretny commit/tag i przypnij go w testach/lockfile/docs.
5. **SECURITY BOUNDARY:** klient kancelarii → Nitro (potwierdzony przez NSM) → AI/Windows jako osobne granice. Nie twórz marketingowej obietnicy Zero Operator Access bez dowodu live i testu negatywnego.
6. **DONE ≠ PLAN:** prawdziwa implementacja, testy pozytywne/odmowy, CI na dokładnym HEAD SHA, widoczny PASS/BLOCKED i pliki zmienione. Dokumentacyjny Draft nie jest gotowym PR-em.
7. **LIFECYCLE:** bez realnych aktów klienta, bez deploy AWS bez zgody na koszt, bez scalania innych PR-ów, bez zwalniania `NO_GO` bez dowodu.

## Nasze repozytorium ma pierwszeństwo

| Funkcja | Gotowe / przygotowane w NotarAI | Właściciel |
|---|---|---|
| Nitro KMS / NSM / sealed recipient | `confidential/nsm_recipient.py`, `nitro_unwrapper.py`, `attested_kms.py` w #50, rozszerzone w #87 | #88, #90, #72 |
| Envelope AES-GCM i szyfrowanie JS | `confidential/envelope.py`, `static/confidential-crypto.js`; v3 w #86 `confidential/customer_release.py` | #88, #89 |
| COSE verifier AWS + nonce/PCR | #87: `confidential/customer_nitro_attestation.py`, `customer_attested_release.py`, `test_customer_attestation.py` | #88/#89 |
| Podpisanie pochodzenia dokumentu | #86 `confidential/customer_origin.py`; w v2 #68 `origin_admission.py` | #88/#90 |
| Guest, worker i przepływ preview | #87 `customer_guest_v3.py`; #50 `worker.py`, #57 `job_ledger.py` | #90 |
| S3, SQS, ECS, IAM, Shared Fabric | istniejący `infra/`, #51/#57/#60/#74 | #90/#72/#74 |
| Ochrona egress / browser policy | #63/#69/#73 `computer_use/`, `confidential/` | #73/#63 |
| Log i kryptograficzne receipts | #76 `confidential/` oraz #85 `transparency_log.py` | #76 |
| Pilot Windows / UIA / signed jobs | #63 `computer_use/`, #64 `agent/NotarAI.VirtualEmployee.*` | #63/#64 |

**Nie kopiuj** #61/#62/#65/#70/#71 jako pełnej architektury: to stary *zewnętrzny kustosz KMS*. Nie budujemy Shamir, MPC, FHE, ZKP, obowiązkowych HSM ani wielu odrębnych custody accounts.

## Otwarte źródła: dokładne pliki i decyzja

### A. Nitro, klient i kryptografia — użyć jako pierwsze

| Źródło i konkretne pliki | Licencja (sprawdzona) | Dlaczego / dokładny reuse | PR |
|---|---|---|---|
| [AWS Nitro Browser Verifier](https://github.com/aws-samples/sample-nitro-enclaves-attestation-webapp/blob/main/frontend/src/lib/attestationVerifier.js) i [HPKE client](https://github.com/aws-samples/sample-nitro-enclaves-attestation-webapp/blob/main/frontend/src/lib/hpkeEncryption.js) | MIT-0 | COSE_Sign1, cert chain AWS, WebCrypto. **Nie kopiuj bez poprawek**: debug warning musi blokować, PCR musi być pinningiem, brak RSA guest = deny, przeliczyć binding klucza do v3 | #88, #89 |
| [AWS Nitro Python attestation sample](https://github.com/aws-samples/sample-nitro-enclaves-attestation/blob/main/client/attestation_verifier.py) | MIT-0 | Pomocniczy test kompatybilności/parsing; **kod edukacyjny**, nie samodzielny dowód bezpieczeństwa | #88, #72 |
| [AWS Nitro NSM API](https://github.com/aws/aws-nitro-enclaves-nsm-api/blob/main/docs/attestation_process.md) oraz [Rust NSM library](https://github.com/aws/aws-nitro-enclaves-nsm-api/tree/main/nsm-lib/src) | Apache-2.0 | Oficjalny protokół NSM i struktura atestacji. Dopasować istniejący adapter; bez pisania własnego drivera | #90, #72 |
| [AWS Nitro C SDK](https://github.com/aws/aws-nitro-enclaves-sdk-c) | Apache-2.0 | Gdy potrzebna zgodność Guest/KMS; istniejący Python adapter ma pierwszeństwo | #90, #72 |
| [Maple/OpenSecret Rust verifier](https://github.com/MaplePrivacyLabs/Maple/blob/master/sdk/rust/src/attestation.rs) oraz [testy i fixtures](https://github.com/MaplePrivacyLabs/Maple/tree/master/sdk/rust/tests) | MIT (repo; sprawdzić też `sdk/rust/LICENSE`) | Niezależny punkt porównania AWS-root chain/PCR/nonce i test fixtures; **nie wymieniaj całego runtime'u Maple** | #88, #72 |
| [libsodium.js: browser Argon2id test](https://github.com/jedisct1/libsodium.js/blob/master/browsers-test/pwhash_argon2id.js) oraz [README](https://github.com/jedisct1/libsodium.js) | permissive ISC-like (`LICENSE` root) | Wykorzystaj gotowe `crypto_pwhash`/Argon2id + AEAD do szyfrowanej kopii klucza; test WebAssembly/offline, spójność wydania CSP, bez autorskiego KDF | #91 |
| [age](https://github.com/FiloSottile/age) | BSD-3-Clause | Prostota kopii szyfrowanych; przydatny wzorzec formatu i odzyskiwania, **nie wymuszaj Go/CLI w webowej aplikacji** | #91 |

### B. AI, policy, narzędzia — używać tylko gdy są brakującą częścią

| Źródło i plik | Licencja | Decyzja | PR |
|---|---|---|---|
| [Private AI Gateway ACI](https://github.com/Dstack-TEE/private-ai-gateway/blob/main/spec/aci.md), [ACI verifier/protocol](https://github.com/Dstack-TEE/private-ai-gateway/tree/main/crates) | Apache-2.0 | Format attested inference, klucz kanału i receipts, OpenAI-compatible. **Developer preview; integracja dopiero po osobnym audycie endpointu** | #69 |
| [Tinfoil JS verifier](https://github.com/tinfoilsh/tinfoil-js/tree/main/packages/verifier/src), [verified transport](https://github.com/tinfoilsh/tinfoil-js/blob/main/packages/tinfoil/src/internal/verified.ts) | Apache-2.0 | Wzorzec verify-before-send i wiązania TLS; **TDX/SEV-SNP ≠ natywny AWS Nitro COSE**, nie zastępuje #87 | #69, #89 (wzorzec) |
| [Maple OpenSecret](https://github.com/MaplePrivacyLabs/Maple/tree/master/services/opensecret), [SDK](https://github.com/MaplePrivacyLabs/Maple/tree/master/sdk) | MIT | Wzorzec sesji i prywatnej pamięci czatu; analizować dopiero przy AI, nie portować całej aplikacji | #69 |
| [Microsoft MCP policy proxy](https://github.com/microsoft/agent-governance-toolkit/blob/main/agent-governance-python/agent-mesh/packages/mcp-proxy/src/policy.ts), [audit](https://github.com/microsoft/agent-governance-toolkit/blob/main/agent-governance-python/agent-mesh/packages/mcp-proxy/src/audit.ts) | MIT | Interceptor narzędzi, default-deny, log zredagowany, human approval; adaptuj do istniejących `computer_use/*` | #63, #73 |
| [cMCP allowlist](https://github.com/agentrust-io/cmcp/blob/main/examples/policy-templates/tool-allowlist.cedar), [sensitive egress guard](https://github.com/agentrust-io/cmcp/blob/main/examples/policy-templates/sensitive-egress-guard.cedar), [status/spec](https://github.com/agentrust-io/cmcp/tree/main/docs/spec) | MIT | Gotowe małe polityki; **preview**. Wziąć ideę reguł i testy, nie instalować całego cMCP równolegle z policy engine | #73, #63 |
| [OPA](https://github.com/open-policy-agent/opa) i [OpenFGA](https://github.com/openfga/openfga) | Apache-2.0 | Potencjalne osobne policy/authorization engine. **Nie instalować obu w MVP**; istniejące IAM i własne reguły mają pierwszeństwo | #74, #63 |

### C. Dowody, integracja, automatyzacja — selektywnie

| Źródło i plik | Licencja | Decyzja | PR |
|---|---|---|---|
| [EphemeralML receipt verify](https://github.com/cyntrisec/EphemeralML/blob/main/common/src/receipt_verify.rs), [format](https://github.com/cyntrisec/EphemeralML/blob/main/common/src/air_receipt.rs) | Apache-2.0 | Wzorzec podpisanej paczki dowodowej offline; nie instaluj całego inference runtime'u | #76, #77 |
| [Sigstore Python verification](https://github.com/sigstore/sigstore-python/tree/main/sigstore/verify), [in-toto verify](https://github.com/in-toto/in-toto/blob/develop/in_toto/verifylib.py) | Apache-2.0 (LICENSE w obu) | Wzorzec supply chain podpis/manifest. Jeśli obecny #76 działa — nie implementuj kolejnego frameworka | #76, #78 |
| [Moto](https://github.com/getmoto/moto) | Apache-2.0 | Lokalne fake AWS S3/SQS/DynamoDB dla testów; **nigdy** nie oznaczaj fake AWS jako realnego dowodu NSM/Nitro | #90, #74, #77 |
| [FlaUI](https://github.com/FlaUI/FlaUI/tree/main/src/FlaUI.UIA3), [Window API](https://github.com/FlaUI/FlaUI/blob/main/src/FlaUI.Core/AutomationElements/Window.cs) | MIT | UI Automation .NET 8 Windows; **już używany w #64**, nie pisać własnego silnika klików | #63, #64 |
| [Azure Windows confidential VM demo](https://github.com/Azure-Samples/confidential-computing/blob/main/vm-samples/WindowsAttest.ps1) | MIT | **Porównanie architektury**, nie bezpośrednie przeniesienie na AWS Windows; administrator Windows dalej osobna granica | #64 |
| [OWASP ASVS](https://github.com/OWASP/ASVS) | standard / sprawdzić licencję dokładnego materiału przed reprodukcją | Lista kontroli web app do audytu; nie kopiować całej normy do repo | #66, #78 |

## Nieprzydatne albo ryzykowne do kopiowania

- [NEAR Private ML SDK](https://github.com/nearai/private-ml-sdk): MIT, lecz **zarchiwizowany** (2026-10); brak uzasadnienia dla nowego zależnego runtime'u.
- [Dstack core](https://github.com/Dstack-TEE/dstack): może zastąpić orchestration/compute, ale **nie migrować** z istniejącego AWS Nitro/ECS bez wykazanego oszczędzania pracy i kosztów.
- [Edgeless PrivateMode](https://github.com/edgelesssys/privatemode-public): ograniczona licencja dla części folderów; nie zakładać możliwości kopiowania całości.
- [TEE Guardian](https://github.com/NethermindEth/tee-guardian): archiwum AGPL-3.0, threshold custody niepotrzebne w MVP.
- [tinfoil confidential-model-router](https://github.com/tinfoilsh/confidential-model-router): AGPL-3.0; nie kopiować fragmentów do zamkniętego SaaS bez odrębnej decyzji prawnej.
- [Contrast](https://github.com/edgelesssys/contrast): BSL, nie kod MIT.
- [NEAR cloud-api](https://github.com/nearai/cloud-api): PolyForm Strict, nie wolne do dowolnej komercyjnej kopii.
- Publiczny GitHub != automatyczne prawo do użycia kodu, nazw, logo i danych testowych.

## Zapis decyzji OSS wymagany w każdym PR

W opisie wynikowym dodaj tabelę:

| Co zrobiono | Kod NotarAI użyty ponownie | Źródło OSS (repo/plik/commit/licencja) | Wzięty zakres / odstępstwo | Dowód testowy |
|---|---|---|---|---|

Jeżeli nie skopiowano żadnego kodu, zapisz **„analiza OSS; reuse przez adapter / nie skopiowano kodu”**, zamiast pozorować integrację. Usuń dublujące funkcje tylko po zielonej regresji. Przyszli wykonawcy mają przeglądać ten plik przed nową implementacją.
