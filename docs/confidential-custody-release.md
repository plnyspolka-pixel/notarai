# NotarAI: niezależna podpisana autoryzacja każdej wersji Nitro

**Status:** przygotowany kod, nie ma podpisanej wersji produkcyjnej ani
dowodu sprzętowego Nitro. Tylko fikcyjne testy i szablony.

Problem do rozwiązania: zwykły `GitHub Actions: success` nie mówi klientowi,
czy osoba kontrolująca NotarAI nie podmieniła kodu lub polityki atestacji.
Rozwiązaniem jest **oddzielna decyzja kustosza kluczy, kryptograficznie
podpisana poza kontem operatora**. Dotyczy to wyłącznie zatwierdzonej
wersji kodu, obrazu `@sha256`, wersji task definition, KMS key policy
(SHA-256) i PCR17.

## Model zaufania

1. Niezależny kustosz (własne konto AWS poza kontrolą operatora NotarAI)
   ma dwie osobne role: *audit-readonly* i *release signer*. Osoba
   kontrolująca konto NotarAI nie może `AssumeRole` do żadnej z nich,
   zmieniać ich trust policy ani zarządzać Organizations/SSO kustosza.
2. W koncie kustosza oddzielny klucz KMS `ECC_NIST_P256`
   `SIGN_VERIFY` podpisuje skrót wydania. Nie jest to klucz deszyfrujący.
   Klucz prywatny nie trafia do GitHub, dysku lub procesu NotarAI.
3. Kustosz odczytuje **rzeczywisty stan obu kont AWS** tuż przed podpisem,
   z `scripts/verify_confidential_operator_boundary.py`, odrzuca
   niezatwierdzone polityki, granty, role i obrazy.
4. Kustosz podpisuje kanoniczny JSON protokołem `ECDSA_SHA_256`
   z domeną `NotarAI:confidential:custody-release:v1\0`.
   Oświadczenie jest ważne najwyżej 48 h (domyślnie 24 h) i jest
   związane z jedną kancelarią i jedną konkretną konfiguracją.
5. Niezależny audytor ma **własną kopię** klucza publicznego i jego
   odcisk SHA-256 dostarczony poza infrastrukturą NotarAI.
   Kontroluje bieżący stan AWS, porównuje go z podpisem i odrzuca
   każdą zmianę image/task/PCR/key policy.
6. Podpisany manifest NIE jest dowodem faktycznego uruchomienia Nitro
   ani dowodem niepodległości organizacyjnej kont. To jedna z warstw
   dozwolonego procesu release.

## Wprowadzone pliki

- `infra/notarai-confidential-custody-signing.yaml` — niezależny
  klucz podpisujący P-256, z polityką wyłącznie dla oddzielnej roli
  kustosza, bez `kms:Decrypt` i `CreateGrant`, z `Retain`.
- `confidential/release_approval.py` — kanoniczne, domenowo oddzielone
  dane i walidacja podpisu ECDSA P-256, czasu, tożsamości kancelarii,
  account IDs, task ARN, key policy SHA256 i PCR17.
- `scripts/custodian_sign_confidential_release.py` — domyślnie
  **dry-run**, podpis tylko po `--approve-release`, pobiera live AWS
  z 2 kont, używa `kms:Sign` na trzeciej tożsamości custody.
- `scripts/verify_confidential_release.py` — niezależny audytor
  weryfikuje podpis wobec live stanu AWS i klucza publicznego
  uzyskanego **poza NotarAI**.
- `test_confidential_release_approval.py` — testy negatywne
  zmiany każdego pola, certyfikatu, fingerprintu, czasu, podpisu.

## Bezpieczna procedura

Preconditions: najpierw wykonaj
`docs/confidential-independent-custody.md` i realne testy
`KMS Decrypt`/Nitro. Użytkownik i zewnętrzny kustosz niezależnie
sprawdzają status konta. Osoba operatora nie uruchamia procedury
podpisywania w imieniu kustosza.

### 1. Utwórz klucz podpisujący w EXTERNAL custody account

```sh
aws cloudformation deploy \
  --stack-name notarai-confidential-custody-signing \
  --template-file infra/notarai-confidential-custody-signing.yaml \
  --parameter-overrides \
      WorkloadAccountId=<NOTARAI_WORKLOAD_ACCOUNT_ID> \
      CustodianSignerRoleArn=<CUSTODY_RELEASE_SIGNER_ROLE_ARN> \
      CustodyAcknowledgement=independent-release-approval \
  --region eu-central-1 --profile <INDEPENDENT_CUSTODIAN_DEPLOY_PROFILE>
```

Nie używaj roli `claude-admin` z produkcyjnego konta NotarAI
do tej czynności. Role `CustodianSignerRoleArn` tworzy i kontroluje
wyłącznie kustosz, niezależnie od NotarAI.

### 2. W koncie kustosza zatwierdź dokładny release

```sh
python scripts/custodian_sign_confidential_release.py \
  --operator-audit-profile <WORKLOAD_AUDITOR> \
  --custody-audit-profile <CUSTODY_AUDITOR> \
  --custody-signer-profile <CUSTODY_RELEASE_SIGNER> \
  --tenant pilot01 \
  --task-definition-arn <EXACT_PINNED_TASK_ARN> \
  --kms-key-arn <CUSTODIAN_DECRYPT_KEY_ARN> \
  --pcr17 <APPROVED_96_HEX> \
  --image-sha256 <ECR_IMAGE_DIGEST_64_HEX> \
  --signing-key-arn <EXTERNAL_RELEASE_SIGNING_KEY_ARN> \
  --output /tmp/notarai-release-pilot01.json \
  --approve-release
```

**To działanie zatwierdzające** — wymaga wyraźnego działania kustosza,
nie można go zautomatyzować przez PR operatora, jego CI ani
samodzielny deploy Claude. Bez flagi `--approve-release` dry-run
nie wykonuje żadnych wywołań AWS.

Kustosz udostępnia klientowi osobnym, zaufanym kanałem:
`GetPublicKey` => public PEM i odcisk
`SHA256(SubjectPublicKeyInfo DER)`; nigdy nie wysyła private key.
Odcisk podany w pliku z NotarAI nie jest samodzielnym dowodem zaufania.

### 3. Niezależny audytor potwierdza release

```sh
python scripts/verify_confidential_release.py \
  --operator-profile <WORKLOAD_READONLY_AUDITOR> \
  --custody-profile <CUSTODY_READONLY_AUDITOR> \
  --tenant pilot01 \
  --task-definition-arn <EXACT_PINNED_TASK_ARN> \
  --kms-key-arn <CUSTODIAN_DECRYPT_KEY_ARN> \
  --pcr17 <APPROVED_96_HEX> \
  --image-sha256 <ECR_IMAGE_DIGEST_64_HEX> \
  --receipt-file /tmp/notarai-release-pilot01.json \
  --trusted-custodian-public-key /secure/auditor/custody-public.pem \
  --trusted-custodian-public-key-sha256 <OUT_OF_BAND_PINNED_SHA256> \
  --check
```

Zwrot `independent_release_signature_verified=true` potwierdza
podpis **konkretnej konfiguracji z zewnętrznego trust root**.
Niezależnie od wyniku pozostaje
`hardware_nitro_attestation_verified=false` i
`zero_operator_access_proven=false` do czasu testu sprzętowego i
audytu rzeczywistego ruchu.

## Ważne ograniczenia

- Administrator **zewnętrznego** konta kustosza nadal może zmienić
  KMS key policy: musi być niezależnym i rozliczalnym powiernikiem.
  Sam podpis nie tworzy technicznego zakazu `kms:PutKeyPolicy`;
  należy również chronić ten proces IAM/SCP, rejestrować i nadzorować
  zmiany w zewnętrznym CloudTrail.
- Nie wolno automatycznie wymieniać `ExpectedPCR17` w KMS po push
  do GitHub. To wymaga aktualnego podpisu i akceptacji kustosza.
- Nie wolno ustawiać `Zero Operator Access` w produkcie, jeśli
  kustosz jest faktycznie zarządzany przez NotarAI, wspólny SSO
  lub to samo AWS Organizations.
- Do certyfikowalnego działania trzeba jeszcze dowodów prawdziwych
  `RecipientAttestation`, odmowy na złym PCR, niezależnego zapisu
  CloudTrail, testów przepływów plaintext i audytu.
