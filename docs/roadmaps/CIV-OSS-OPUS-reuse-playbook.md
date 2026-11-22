# NotarAI Confidential — katalog ponownego użycia kodu i instrukcja dla Claude Opus
**Stan rozpoznania:** 2026-11-22. **Typ:** specyfikacja / nie wdrożenie. **Adresaci:** osobne sesje kodowania Opus, po jednej na PR.

## 0. Ważne
Budujemy **cywilny, ekonomiczny i zrozumiały** system. Wykorzystaj istniejącą implementację NotarAI, potem sprawdzony OSS, a nowy kod pisz dopiero dla brakującego połączenia. Jeśli nowy serwis/SDK/podpis nie wnosi uzasadnionej kontroli, **nie dodawaj go**. Nie przenoś custody/KMS operatora do nowego protokołu v3.

**Każdy wskazany fragment OSS to materiał do przeglądu, nie zweryfikowany produkcyjnie zamiennik!** Weryfikacja CPU/NSM, PCR, X.509, logów, egress, ABI i licencji jest obowiązkowa przed kopiowaniem. Gdy importujesz kod OSS, wpisz źródło (repo + plik + commit SHA), SPDX licencję i zakres zmian w `THIRD_PARTY_NOTICES.md` albo stosownym nagłówku; zachowaj wymagane noty. Linki do `main` są tylko nawigacją; przed wklejeniem przypnij konkretny commit SHA.

## 1. Najpierw własne repozytorium (prawdziwe, istniejące komponenty)

| Istniejący kod | Jak użyć | Czego nie przenosić |
|---|---|---|
| [PR #50](https://github.com/plnyspolka-pixel/notarai/pull/50), [master/confidential/worker.py](https://github.com/plnyspolka-pixel/notarai/blob/master/confidential/worker.py) | Nitro worker, S3/SQS, preview-only form engine, NSM, KMS v2 jako regresja | Nie traktuj v2 operator KMS jako gwarancji ZOA |
| [PR #51](https://github.com/plnyspolka-pixel/notarai/pull/51), [PR #60](https://github.com/plnyspolka-pixel/notarai/pull/60) | ECS Managed Instances, wspólna VPC, endpointy i wydajność | Nie buduj nowej VPC per kancelaria |
| [PR #68](https://github.com/plnyspolka-pixel/notarai/pull/68), [static/confidential-crypto.js](https://github.com/plnyspolka-pixel/notarai/blob/plan/confidential-sec-03-zk-client-encryption-20261122/static/confidential-crypto.js), [scripts/build_custodian_browser_client.py](https://github.com/plnyspolka-pixel/notarai/blob/plan/confidential-sec-03-zk-client-encryption-20261122/scripts/build_custodian_browser_client.py) | AES-GCM/WebCrypto, standalone signed HTML, testy origin, offline dystrybucja | KMS ARN, cudzy kustosz, legacy v2 i wielostronne recovery |
| [PR #86](https://github.com/plnyspolka-pixel/notarai/pull/86), [customer_release.py](https://github.com/plnyspolka-pixel/notarai/blob/feature/confidential-customer-keys-minimal-20261122/confidential/customer_release.py), [customer_origin.py](https://github.com/plnyspolka-pixel/notarai/blob/feature/confidential-customer-keys-minimal-20261122/confidential/customer_origin.py) | Klucz RSA-3072 kancelarii, koperta AES-GCM i jednorazowy grant | Nie omijaj atestacji przez przekazanie przez operatora „zweryfikowanego” klucza |
| [PR #87](https://github.com/plnyspolka-pixel/notarai/pull/87), [customer_nitro_attestation.py](https://github.com/plnyspolka-pixel/notarai/blob/feature/sec86-customer-attested-release-20261122/confidential/customer_nitro_attestation.py), [customer_attested_release.py](https://github.com/plnyspolka-pixel/notarai/blob/feature/sec86-customer-attested-release-20261122/confidential/customer_attested_release.py), [customer_guest_v3.py](https://github.com/plnyspolka-pixel/notarai/blob/feature/sec86-customer-attested-release-20261122/confidential/customer_guest_v3.py) | COSE/X509/PCR/nonce, RSA recipient i jedno zadanie; 54 syntetyczne testy zaliczone w CI | Nie reklamuj wyniku syntetycznego jako dowodu sprzętowego |
| [PR #57](https://github.com/plnyspolka-pixel/notarai/pull/57), [confidential/job_ledger.py](https://github.com/plnyspolka-pixel/notarai/blob/feature/confidential-job-ledger-aws-handoff-20261121/confidential/job_ledger.py) | Rezerwacja zadania DDB, lease, retry i deduplikacja | Nie dodawaj drugi raz job queue/ledger |
| [PR #69](https://github.com/plnyspolka-pixel/notarai/pull/69) i [#40](https://github.com/plnyspolka-pixel/notarai/pull/40) | Obecne ograniczenia granicy inferencji i EU gateway | Zwykły Bedrock nie staje się Nitro przez sam IAM |
| [PR #73](https://github.com/plnyspolka-pixel/notarai/pull/73), [#74](https://github.com/plnyspolka-pixel/notarai/pull/74), [#75](https://github.com/plnyspolka-pixel/notarai/pull/75) | Kontrola wycieków, izolacja tenantów, retencja | Nie łącz starych zagnieżdżonych gałęzi custody |
| [PR #76](https://github.com/plnyspolka-pixel/notarai/pull/76), [#85](https://github.com/plnyspolka-pixel/notarai/pull/85) | Weryfikator offline i opcjonalny transparency log | WORM/blockchain i trzy podpisy nie są warunkiem MVP |
| [PR #63](https://github.com/plnyspolka-pixel/notarai/pull/63), [#64](https://github.com/plnyspolka-pixel/notarai/pull/64) | Fallback UI, protokoły Windows i diagnostyka FlaUI | Windows VM nie odziedziczy attestation Nitro |

## 2. Zewnętrzne OSS — konkretne, zweryfikowane repozytoria

### AWS web attestation / MIT-0
- [aws-samples/sample-nitro-enclaves-attestation-webapp](https://github.com/aws-samples/sample-nitro-enclaves-attestation-webapp), **MIT-0**, szczególnie [frontend/src/lib/attestationVerifier.js](https://github.com/aws-samples/sample-nitro-enclaves-attestation-webapp/blob/main/frontend/src/lib/attestationVerifier.js), [frontend/src/lib/x509Parser.js](https://github.com/aws-samples/sample-nitro-enclaves-attestation-webapp/blob/main/frontend/src/lib/x509Parser.js), [LICENSE](https://github.com/aws-samples/sample-nitro-enclaves-attestation-webapp/blob/main/LICENSE).
- **Użycie**: format COSE_Sign1, AWS pinned root, weryfikacja lokalna i testy WebCrypto w CIV-02/#72. **Nie kopiować bez poprawek:** debug PCR0/1/2, egzekwowanie PCR allowlist, twarda odmowa brakującego klucza odbiorcy, dopasowanie P-256/HPKE z przykładu do RSA-3072/OAEP z #86. We wcześniejszej inspekcji te elementy wymagały korekty — testami negatywnymi potwierdź, czy nadal występują.
- [aws-samples/sample-nitro-enclaves-attestation/client/attestation_verifier.py](https://github.com/aws-samples/sample-nitro-enclaves-attestation/blob/main/client/attestation_verifier.py), **MIT-0**: poglądowa Python walidacja, **nie zamiennik** pełnej weryfikacji produkcyjnej, bo README nazywa ją demonstracyjną.

### AWS NSM/vsock / Apache-2.0
- [aws/aws-nitro-enclaves-samples](https://github.com/aws/aws-nitro-enclaves-samples), **Apache-2.0**;
  [att_doc_retriever_sample/py/att_doc_retriever_sample.py](https://github.com/aws/aws-nitro-enclaves-samples/blob/main/att_doc_retriever_sample/py/att_doc_retriever_sample.py);
  [vsock_sample/py](https://github.com/aws/aws-nitro-enclaves-samples/tree/main/vsock_sample/py).
- **Użycie:** sposób pobrania COSE z NSM i wzór vsock transportu wewnątrz Nitro. **Nie przebudowuj** istniejącego `confidential/nsm_recipient.py`, użyj tylko różnic potrzebnych dla nonce + user_data.

### Poufne LLM / MIT-0 — TYLKO WZORZEC
- [aws-samples/aws-nitro-enclaves-llm](https://github.com/aws-samples/aws-nitro-enclaves-llm), **MIT-0**, [src/enclave/server.py](https://github.com/aws-samples/aws-nitro-enclaves-llm/blob/main/src/enclave/server.py), [Dockerfile](https://github.com/aws-samples/aws-nitro-enclaves-llm/blob/main/src/enclave/Dockerfile).
- **Użycie**: wzór uruchomienia LLM wewnątrz Nitro i granica danych. **NIE kopiować dosłownie:** demonstracyjny `server.py` wypisuje dane credentials; korzysta z bezpośredniego klienta KMS. Trzeba usunąć wszystkie logi sekretów i dopasować do customer-owned v3. Brak pewności, czy wybrany model zmieści się w rzeczywistej enklawie i czy zapewni sensowną latencję; zmierz w #69 albo pozostaw opcję niedostępną.

### Backup klucza / MIT
- [paulmillr/noble-hashes](https://github.com/paulmillr/noble-hashes), **MIT**, [src/argon2.ts](https://github.com/paulmillr/noble-hashes/blob/main/src/argon2.ts), [README.md](https://github.com/paulmillr/noble-hashes/blob/main/README.md). **Użycie**: sprawdzona implementacja Argon2id/KDF dla zaszyfrowanego pliku backupu w CIV-04. AES-GCM wbudowane WebCrypto; nie pisz sam algorytmu. Zweryfikuj parametry RAM/CPU i kompatybilność z urządzeniami kancelarii.

### AI agent policies / MIT
- [microsoft/agent-governance-toolkit](https://github.com/microsoft/agent-governance-toolkit), **MIT**:
  [policy-engine/sdk/python/README.md](https://github.com/microsoft/agent-governance-toolkit/blob/main/policy-engine/sdk/python/README.md),
  [docs/quickstart.md](https://github.com/microsoft/agent-governance-toolkit/blob/main/docs/quickstart.md).
- **Użycie**: adaptuj deterministyczne `allow/deny`, interceptory tool call / agent action, kill switch i audyt bez plaintext. **Nie instaluj całej platformy**, jeśli obecny `computer_use` lub `confidential/ai_boundary.py` da się rozszerzyć kilkudziesięcioma liniami. To NIE zastępuje VPC egress, kontroli IAM ani Nitro.

### PII masking/test logs / MIT
- [data-privacy-stack/presidio](https://github.com/data-privacy-stack/presidio), **MIT**:
  [presidio-analyzer/presidio_analyzer/analyzer_engine.py](https://github.com/data-privacy-stack/presidio/blob/main/presidio-analyzer/presidio_analyzer/analyzer_engine.py) i
  [presidio-anonymizer/presidio_anonymizer/anonymizer_engine.py](https://github.com/data-privacy-stack/presidio/blob/main/presidio-anonymizer/presidio_anonymizer/anonymizer_engine.py).
- **Użycie:** opcjonalny test/sanitizer syntetycznych wyników i raportów dla #75/#77, gdy wystarczy. **Nie** polegać na regex/NER jako gwarancji 0 wycieków; lepiej nie emitować danych niż anonimizować je po wysłaniu do logu.

### Fine-grained auth / Apache-2.0 — referencja, nie zależność obowiązkowa
- [openfga/openfga](https://github.com/openfga/openfga), **Apache-2.0**, [docs/check/README.md](https://github.com/openfga/openfga/blob/main/docs/check/README.md).
- **Użycie:** wzorzec jawnego `principal + tenant + relation + object` i testów scope dla #74, #63. Najpierw wykorzystać istniejące IAM/DynamoDB, **nie stawiać nowego OpenFGA server** tylko po to, by sprawdzić dwa tenanty.
- [open-policy-agent/opa](https://github.com/open-policy-agent/opa), **Apache-2.0**, [rego/rego.go](https://github.com/open-policy-agent/opa/blob/main/rego/rego.go) i [integration docs](https://www.openpolicyagent.org/docs/integration). Opcjonalny referencyjny pomysł na polityki; **nie dodawaj sidecar/serwisu OPA do MVP** bez udowodnionej konieczności.

### Podpisy evidence / Apache-2.0 — opcjonalne
- [sigstore/cosign](https://github.com/sigstore/cosign), **Apache-2.0**, [cmd/cosign/cli/sign/sign_blob.go](https://github.com/sigstore/cosign/blob/main/cmd/cosign/cli/sign/sign_blob.go). Wzór podpisywania paczki / release manifestu dla #76. Już działający Ed25519 w NotarAI jest wystarczający dla lekkiego MVP, jeśli offline verifier zna zaufany klucz; **nie instaluj Rekor/TUF całej infrastruktury** bez potrzeby.

### Windows automation / MIT
- [FlaUI/FlaUI](https://github.com/FlaUI/FlaUI), **MIT**, [README.md](https://github.com/FlaUI/FlaUI/blob/main/README.md) oraz [src/FlaUI.UIA3](https://github.com/FlaUI/FlaUI/tree/main/src/FlaUI.UIA3). Użyj gotowych wrapperów Microsoft UI Automation i diagnostyki. **Nie** pisz własnego sterownika UIA ani nie zakładaj, że WinAppCLI jest potrzebny, skoro #64 ma już działający probe.

## 3. Mikrofragmenty do adaptacji — oryginalne szkice NotarAI (NIE kopiowane z OSS)

### A. Protokół grantu: kryptografia tylko po lokalnej weryfikacji (pseudokod, funkcje istnieją w #86/#87)
```python
# Wszystkie: notariusz uruchamia zaufanego klienta, NIE operatorowy backend.
nonce = os.urandom(32)
context = challenge_user_data(envelope, job_id=job_id, nonce=nonce)
report = receive_raw_nsm_report(job_id, nonce, context)  # nieufny transport
verified = verify_aws_nitro_attestation(
    report, expected_nonce=nonce,
    expected_user_data=context,
    expected_pcrs=trusted_customer_pcr_manifest,
)
grant = issue_job_release(
    envelope, owner_private_pem, verified.public_key_pem,
    job_id=job_id, issued_at=now, expires_at=now + 300,
)
# Brak report / zły PCR / zły klucz => błąd bez alternatywnego odbiorcy.
```

### B. Serwer obsługuje ciphertext + kontrolowany status, nigdy plaintext (kontrakt, nie kompletny worker)
```python
assert envelope["schema"] == "notarai.customer-envelope.v1"
assert hash_exact_envelope(envelope) == reserved_job.envelope_sha256
assert stored_object.version_id == reserved_job.s3_version
if not ledger.claim_once(tenant_id, job_id, release_id):
    raise JobDenied("job already consumed")
# Tylko Nitro guest może wywołać open_preview_in_guest(...)
# API/CloudWatch otrzymują status i job_id, nigdy fields/plaintext.
```
Nie dodawaj równolegle drugiego ledgera — adapter ma używać `confidential/job_ledger.py`. Interfejsy w tym fragmencie są **pseudokodem**.

### C. Gate narzędzia agenta (pseudokod)
```python
def authorize_tool(principal, tenant_id, tool, action):
    if principal.tenant_id != tenant_id:
        return "deny"
    if action in {"submit", "sign", "send", "delete"}:
        return "human_approval_required"
    return "allow" if tool in APPROVED_READ_ONLY_TOOLS else "deny"
```
To jest tylko przykład polityki. Zewnętrzny AGT / OpenFGA to opcje, nie wymagania nowych serwisów.

## 4. Standardowy kontrakt dla Opus — skopiuj przed wykonaniem KAŻDEGO PR

**Polecenie:** „Realizujesz **wyłącznie PR #N** repo `plnyspolka-pixel/notarai`. Odczytaj aktualny opis PR, aneks CIVILIAN/OPUS, ten katalog OSS, istniejący kod i testy. Sprawdź dokładny HEAD oraz base. Nie twórz nowego PR, chyba że gałąź jest wyłącznie planistyczna i potrzebujesz gałęzi kodowej (wtedy użyj osobnego brancha z numerem CIV; istniejący PR planistyczny pozostaw dokumentacją). Najpierw zrób tabelę REUSE / ADAPT / BUILD / SKIP, potem implementuj; nie przepisuj istniejących systemów. Nie instaluj nowej platformy, jeśli to nie jest konieczne. Testuj pozytywne i negatywne przypadki. Utrzymaj `preview-only`, brak automatycznego submit i 0 realnych danych. Zapisz kod, CI i status w przypisanym PR. Nie nazywaj symulacji dowodem AWS. Nie scalać, nie deployować płatnych zasobów bez wyraźnej autoryzacji. Na końcu podaj commit SHA, zielone/czerwone CI, licencje OSS, konkretne brakujące dowody AWS i link do PR.”

**Ważne w przypadku planistycznych #88–#91**: obecna gałąź zawiera wyłącznie dokumentację; sesja implementacyjna może na jej bazie dodać kod, jeśli zdoła utrzymać poprawny diff względem master. Jeśli nie, przygotuj dedykowaną gałąź kodową, zaktualizuj numer PR/odniesienie, bez niezamierzonego mergowania zależności. Nie przedstawiaj planu jako ukończonej funkcji.

## 5. Bramka odbioru powtarzana w każdym PR

- [ ] Kod reuse/adapt istniejących plików wskazany w opisie i review; 0 bezzasadnie nowych usług, kolejki, KMS kustosza, VPC.
- [ ] Dla każdego zewnętrznego komponentu zapisano wersję/commit SHA, SPDX oraz wymagane notices; brak bezrefleksyjnego kopiowania przykładów.
- [ ] Testy negatywne opisane w danym PR są automatyczne, deterministyczne i mają **0 failures/0 errors**.
- [ ] Link do CI dotyczy **dokładnego** commit SHA. Full regression w istniejącym master bez pogorszenia, chyba że status BLOCKED wraz z przyczyną.
- [ ] Wszelkie dane to fikcyjne canary. Wydanie klucza i plaintext nigdy na niezweryfikowany klucz operatora.
- [ ] Raport rozróżnia `software/synthetic PASS`, `hardware PASS`, `commercial GO`, `BLOCKED`.
- [ ] Brak automatycznych submitów, zmiany produkcji i płatnego AWS bez jawnej zgody.

## 6. Mapa PR i zamknięcia
Centralny plan kolejności: [CIV-00](./CIV-00-confidential-delivery-map.md).
Planowany łańcuch: #66 + #88 → #89/#90 → #91/#72 → #73/#74 → #75/#76 → #77 → #78; #69 osobno (AI), #63/#64 osobno (Windows). Otwarta gałąź custody #61/#62/#65/#70/#71 jest **LEGACY** dla customer-owned v3.



## 7. Dodatkowe zweryfikowane komponenty — nie powielaj kodu

Te repozytoria sprawdzono na GitHub 22.11.2026. Przed importem przypnij **konkretny commit SHA**, sprawdź licencję *pliku* i zgodność API; poniższe licencje są deklaracjami repozytoriów.

| Zadanie | Gotowy kod | Licencja | Wytyczne dla Opusa |
|---|---|---|---|
| #89 CBOR w przeglądarce | [`kriszyp/cbor-x`](https://github.com/kriszyp/cbor-x) | MIT | Parser CBOR, ale **nie weryfikator COSE/X.509**. Nie pisz kolejnego CBOR parsera, jeśli ten spełnia testy kanoniczności, tagów i formatów |
| #89/#76 opcjonalny standardowy JWS | [`panva/jose`](https://github.com/panva/jose) | MIT | Tylko jeśli wybrany kontrakt rzeczywiście używa JWS; nie zmieniaj bez powodu istniejącego Ed25519 receipt |
| #72/#90 AWS NSM protokół | [`aws/aws-nitro-enclaves-nsm-api`](https://github.com/aws/aws-nitro-enclaves-nsm-api) | Apache-2.0 | Traktuj jako referencję źródłową; w NotarAI już istnieje `nsm_recipient.py` |
| #72 dodatkowe API C | [`aws/aws-nitro-enclaves-sdk-c`](https://github.com/aws/aws-nitro-enclaves-sdk-c) | Apache-2.0 | Nie wnoś C SDK do Pythona, chyba że istniejący wrapper nie wystarcza |
| #63/#73/#77 sterowanie Chromium i testy E2E | [`microsoft/playwright`](https://github.com/microsoft/playwright) | Apache-2.0 | Już używany w NotarAI, **reuse**, nie twórz nowego browser-drivera |
| #87 cryptographic origin/API | [`confidential/nsm_recipient.py`](https://github.com/plnyspolka-pixel/notarai/blob/feature/sec86-customer-attested-release-20261122/confidential/nsm_recipient.py) | własny kod repo | Wystarcza NSM challenge z `nonce` i `user_data`; nie buduj nowego agenta w enklawie |

**Ważny kontrakt wewnętrzny, zamiast ponownej implementacji:**
```python
from confidential.customer_attested_release import (
    challenge_user_data, issue_attested_job_release,
)
# Decyzja o wydaniu DEK następuje dopiero po
# pełnej lokalnej weryfikacji NSM; operator nie wybiera klucza guest.
```

**Weryfikacja bezpieczeństwa przykładu AWS Nitro LLM:** [`src/enclave/server.py`](https://github.com/aws-samples/aws-nitro-enclaves-llm/blob/main/src/enclave/server.py) zawiera `print(credentials)` i wzorzec decrypt przez KMS. Użyj tylko jako dowodu wykonalności technicznej inferencji w Nitro. **Nie kopiuj logowania poświadczeń ani operatorowego KMS** do ścieżki v3.

**Jedyny katalog OSS:** ten plik. Każdy PR ma linkować do niego zamiast wklejać jego kopię; w opisie zadania zostaw tylko 2–5 najważniejszych *konkretnych linków*.
