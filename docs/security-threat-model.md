# NotarAI SEC-01 — Model zagrożeń i granice gwarancji

**Zakres:** Confidential Browser / Nitro, wyłącznie dane fikcyjne pilot01 i pilot02, AWS `eu-central-1`.
**Status rzeczywisty:** ocena gwarancji = **UNVERIFIED**. Kod walidatora i testy jednostkowe **nie** potwierdzają sprzętowego Nitro, stanu prawdziwych kont, braku wycieków ani prawa do sprzedaży pod hasłem „Zero Knowledge / Zero Operator Access verified”.

## Chronione zasoby i granice zaufania

1. Dokument notarialny, PESEL, treść sprawy, dane w formularzu, DEK i session state. Wrogi operator nie może pozyskać ich przez host, debug, logi, backup ani integrację LLM.
2. Klient/przeglądarka: potencjalnie zaufane urządzenie, ale JavaScript dystrybuowany przez NotarAI może być zmieniony przez operatora. Sama kryptografia w JS nie daje bezwarunkowego Zero Knowledge.
3. Serwer API: uwierzytelnia tożsamość, przypisuje tenant i zleca tylko pracę z użyciem ciphertext. Operator kontroluje zwykły backend, nie powinien poznawać DEK.
4. AWS workload account: ECS Nitro Sandbox, ECR, SQS, S3, DDB. Załóż przejęcie roli z `AdministratorAccess`, ECS RunTask, IAM PassRole, CloudFormation i GitHub Actions.
5. Nitro guest: plaintext może wystąpić w RAM podczas przetwarzania. Sprzętowa atestacja i KMS `Recipient` ograniczają wydanie DEK, **nie ograniczają automatycznie treści wysyłanej przez zatwierdzony program**.
6. Kustosz KMS i release signer: osobne zaufane konto AWS **nieadministrujące się** z Organizations/SSO/root NotarAI, a nie tylko osobny numer konta. Sam kustosz pozostaje osobnym podmiotem zaufania.
7. Brama egress, DNS, proxy, CloudWatch, support, backup i AI/LLM: odrębne drogi wypływu plaintext wymagające testów. Model Bedrock poza Nitro przetwarzający odszyfrowany tekst jest osobną granicą zaufania.
8. Niezależny audytor: kontroluje odrębny klucz podpisujący dowody i ich repozytorium. NotarAI nie powinien móc podmieniać jego klucza/polityki; fingerprint podawany przez NotarAI nie wystarczy jako kotwica.

## Definicje — cztery różne twierdzenia

| Twierdzenie | Oczekiwana właściwość | Czego samo w sobie nie dowodzi |
|---|---|---|
| **Zero Trust** | Identyfikacja/autoryzacja każdego żądania, polityki najmniejszych uprawnień, ciągłe weryfikacje bez zaufania do położenia w VPC | Poufność zawartości RAM i brak nieautoryzowanego eksportu |
| **Zero Operator Access** | Personel NotarAI nie posiada **jednostronnej** drogi do odszyfrowania dokumentów: niezależny kustosz, hardware/KMS, podpisany release, brak eksfiltracji | Brak dostępu kustosza lub innych uprawnionych podmiotów do danych w każdej możliwej konfiguracji |
| **Confidential Computing** | Aktywny kod w atestowanym Nitro; odszyfrowanie kluczy tylko w powiązanym guest | Sposób wykorzystania plaintext przez dozwolony kod; bezpieczeństwo portali/LLM |
| **Scoped Zero Knowledge** | W zdefiniowanym przebiegu: szyfrowanie przed uploadem, brak dostępu zwykłego operatora do plaintext, przetwarzanie wewnątrz zatwierdzonego guest, kontrola eksportu | **Ścisłe zero knowledge**: Nitro musi odszyfrować dokument w swoim RAM; nieuczciwy frontend albo zwykłe AI poza Nitro również może otrzymać dane |

Twierdzenia muszą być oceniane osobno i wiązane z konkretną wersją kodu/obrazu, tenantem, kluczem i czasem. Nie należy oznaczać NotarAI jako „certyfikowany Zero Trust”; NIST SP 800-207 definiuje architekturę, a nie certyfikuje tej instalacji.

## Macierz ataków i wymagane testy negatywne

Źródło maszynowe: [`docs/security-claims/policy.json`](../security-claims/policy.json).
Każdy TH-xx w JSON zawiera aktora/atak, granicę zaufania, kontrolę, nazwanego niezależnego właściciela i scenariusz odmowy.

| ID | Przeciwnik i technika | Minimalny dowód odmowy |
|---|---|---|
| TH-01 | Klient/API podaje obcy tenant | Uwierzytelnienie i server-side tenant isolation |
| TH-02 | Administrator AWS podszywa się przez PassRole/RunTask | KMS nie wydaje DEK dla niezatwierdzonego obrazu/roli |
| TH-03 | Administrator próbuje `kms:PutKeyPolicy` | Odmowa na niezależnym koncie custody |
| TH-04 | GitHub maintainer podmienia obraz OCI | Odmowa brak zatwierdzonego digest/release |
| TH-05 | Host zastępuje PCR17 lub brak Nitro | Rzeczywista odmowa KMS RecipientAttestation |
| TH-06 | NotarAI kontroluje Organisations/SSO kustosza | Dokumentacyjny i live dowód niezależności, brak jednostronnego admina |
| TH-07 | Tenant A atakuje tenant B przez S3, SQS, DDB, KMS | Dwukierunkowe odmowy uprawnień |
| TH-08 | Playwright/guest wyprowadza dane HTTP/DNS/proxy/log | Fikcyjny marker nie dochodzi do nieautoryzowanego kolektora |
| TH-09 | Model AI otrzymuje niezatwierdzony plaintext | Gateway model/provider blokuje ten przepływ |
| TH-10 | Złośliwy JS po stronie klienta wysyła DEK | Niezależnie zatwierdzony klient wykrywa podmianę |
| TH-11 | Crash/backup/log utrwala dokument | Test braku syntetycznego markera w dostępnych operatorowi artefaktach |
| TH-12 | Prompt injection naciska finalne POST/podpis/wysłanie | AUTO pozostaje preview-only; odmowa submit/sign/register/file |

Nie istnieje „bezpieczny wyjątek” dla samodzielnego podpisywania, składania wniosków ani czynności prawnych wymagających udziału uprawnionej osoby. Testy i realizacja tych działań to inne projekty, nie element SEC-01.

## Jak działa maszyna dowodowa

`confidential/security_claims.py` czyta twardą politykę, która **w repo zawsze ma 4/4 UNVERIFIED**. Przed oceną nowych dowodów wymusza co najmniej 10 ataków, obowiązkowe pola i wszystkie `auto_actions=false`.

Receipt niezależnego audytora lub kustosza:
- ma domenowo oddzielony podpis `ECDSA P-256 / SHA-256`;
- jest wiązany z tenantem, regionem, dokładnym `image_sha256`, typem dowodu i **raportem z własnym SHA256**;
- ma datę wystawienia i wygaśnięcia (najwyżej 7 dni) oraz potwierdzenie przejścia niezależnego testu negatywnego;
- jest weryfikowany wobec publicznego klucza oraz jego odcisku `SHA256(SPKI DER)`, który audytor **musi dostarczyć poza NotarAI**;
- nie może być syntetycznym testem lub samym zielonym CI, jeżeli wymagany jest real AWS / independent audit.

**Interpretacja statusów:** `UNVERIFIED` = nie ma dowodów; `BLOCKED` = dowody niekompletne; `FAIL` = dostarczono dowód nieważny, sfałszowany, przeterminowany lub niepasujący; `PASS` = **tylko poprawność kryptograficzna i strukturalna dostarczonych receiptów**, nie niezależne potwierdzenie, że opisane testy faktycznie wykonano.

**Zabezpieczenie przed fałszywym marketingiem:** nawet gdy 4/4 receipts osiągają `PASS`, wynik zawiera `security_claims_commercially_verified=false`. Formalną ocenę autentyczności źródeł, rzeczywistą niezależność organizacji, sprzętowe testy Nitro i zgodę na deklaracje komercyjne może w przyszłości potwierdzić dopiero SEC-13 z zewnętrznym audytorem.

## Jak zweryfikować szybko (bez AWS)

```sh
python -m pytest -q test_confidential_security_claims.py
python scripts/audit_confidential_claims.py
python scripts/audit_confidential_claims.py --require-all-pass
```

Pierwsza komenda testuje bramkę i ataki, druga wyświetla 4/4 UNVERIFIED, trzecia **musi zwrócić exit code 2** bez niezależnych dowodów. Nie umieszczaj kluczy prywatnych audytora/kustosza w repozytorium.

**Wciąż brak:** rzeczywistych dowodów Nitro/CloudTrail, niezależnego AWS Organizations, audytu exfil oraz podpisanej opinii zewnętrznej. Prace są w #67–#78. Bez nich nie ma wiarygodnej deklaracji handlowej.
