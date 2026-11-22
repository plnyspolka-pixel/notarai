# NotarAI — dowód Zero Operator Access: niezależny kustosz kluczy (Faza 1)

**Stan: kod + testy offline, nie ma potwierdzonego wdrożenia na AWS.**
Nie wolno publikować twierdzeń „Zero Operator Access verified”, „Zero Knowledge
verified” ani „operator nie może odczytać dokumentów” jako bezwarunkowych
faktów na podstawie samych testów jednostkowych/CloudFormation.

## Znalezione obejście w dotychczasowym projekcie

Stara konfiguracja `infra/notarai-confidential-demo-kms.yaml` przechowuje
klucz w **tym samym koncie AWS**, co aplikacja. Konto z uprawnieniami
`AdministratorAccess` może zmienić `kms:PutKeyPolicy`, dodać nieatestowany
`kms:Decrypt` i uzyskać dostęp do DEK dokumentu. Sama kontrola
`kms:RecipientAttestation:PCR17` nie powstrzymuje administratora klucza,
który może zmodyfikować warunek. W szczególności **nie wystarczy**
odebrać uprawnień pracownikowi przez dodatkową rolę IAM, jeżeli operator
nadal kontroluje root lub Organizations management account.

To konkretny powód, dla którego nie wolno z obecnego pilota
wywodzić twierdzenia „operator nie może odczytać danych”.

## Docelowy minimalny model zaufania

- `workload account` — AWS konto NotarAI, kontrolowane przez operatora
  aplikacji, uruchamia ECS Nitro Sandbox, przechowuje ciphertext, kolejki
  metadanych i publiczne artefakty.
- `custody account` — **osobne konto AWS zarządzane niezależnie od
  NotarAI i niepodlegające organizacji AWS Organizations ani SSO
  kontrolowanym przez NotarAI**. Jego administrator kontroluje wyłącznie
  klucz KMS i zatwierdzane pomiary PCR. To może być zewnętrzny podmiot
  powierniczy lub klient z własnym kontem AWS. Dwa konta z tym samym
  niekontrolowanym właścicielem NIE spełniają założenia.
- Role ECS zadania należą do workload, ale key policy w custody account
  daje im wyłącznie `kms:Decrypt` uwarunkowane rzeczywistym
  `RecipientAttestation:PCR17` i `PCR8:ServiceName=ecs.amazonaws.com`.
  Workload root ma jedynie `GetPublicKey` i `DescribeKey`. Nie ma
  `kms:PutKeyPolicy`, `CreateGrant` ani zwykłego `Decrypt`.
- Kustodian ma uprawnienie zmiany KMS policy; jest **niezależnym zaufanym
  podmiotem**, nie jest to ścisłe „zero knowledge względem wszystkich”.
  Zmiany pomiarów PCR17 nie mogą wynikać wyłącznie z dyspozycji operatora
  NotarAI — wymagają osobnej procedury akceptacji i dziennika u kustosza.
- Dokumenty i DEK istnieją w plaintext tylko w zaufanym guest, a
  `KMS Decrypt` wydaje jedynie `CiphertextForRecipient` powiązany z
  efemerycznym kluczem publicznym wygenerowanym wewnątrz Nitro.
- Host, proxy, CI, administratorzy chmury i operator portalu nie
  otrzymują plaintext, ale musimy to nadal **potwierdzić realnymi testami
  egress, logów, code review i atestacji sprzętowej**.

## Co dokładnie powstało

1. `infra/notarai-confidential-external-custody-kms.yaml` — osobny
   asymetryczny klucz KMS RSA_3072 w koncie kustosza, poza NotarAI.
   `CustodyAccountDifferent` nie tworzy klucza w koncie workload;
   `ExpectedPCR17` nie przyjmuje 96 zer. `DeletionPolicy: Retain`.
   Nie uruchamia niczego w AWS.
2. `confidential/operator_boundary.py` — fail-closed kontrola
   **dwóch różnych kont**, dokładnego key policy (3 wyłączne allow),
   braku grantów, metadanych klucza i pinned task definition
   (CONFIDENTIAL_SANDBOX, tylko wspólny immutable obraz Chromium,
   brak ECS Exec/volumes/log driver, osobny tenant/queue/KMS).
3. `scripts/verify_confidential_operator_boundary.py` — audytor z
   **dwoma niezależnymi profilami AWS tylko do odczytu** może weryfikować
   na żywo `sts:GetCallerIdentity`, `kms:DescribeKey`,
   `kms:GetKeyPolicy`, `kms:ListGrants`, `ecs:DescribeTaskDefinition`.
   Wymaga `--check` do jakiegokolwiek zapytania AWS; w przeciwnym
   razie dry-run. Fail-closed przy braku uprawnień/niepełnych wynikach.
   Opcjonalny redacted report tworzy nowy plik z 0600. Nigdy nie
   pobiera danych klienta, kluczy prywatnych ani nie wykonuje decrypt.
4. `test_confidential_operator_boundary.py` — kilkadziesiąt negatywnych
   przypadków: grant nieoczekiwany, admin `Decrypt`, `kms:*`,
   dziedziczenie uprawnień przez konto operatora, brak PCR8/17,
   błędny digest, obraz/rola/tenant, ten sam AWS account.

## Uruchomienie syntetyczne z niezależnym kustoszem

**Precondition 1:** niezależny podmiot dostarcza *nowe* konto i
tożsamości tylko dla audytora. Użytkownik i kustosz akceptują
rozgraniczenie odpowiedzialności. Nie twórz konta w tym samym
Organizations zarządzanym przez NotarAI. Nie wkładaj sekretów do PR.

**Precondition 2:** na koncie operatora istnieje już ograniczona rola
`notarai-confidential-pilot01` z dokładnym `TaskRoleArn`.
W przeciwnym razie CloudFormation kustosza odrzuci nieistniejący
principal. Region zawsze eu-central-1.

**Precondition 3:** obraz ECR jest immutable `@sha256`, a PCR17 i
policy base64 pochodzą z oficjalnego narzędzia
`ecs-nitro-sandbox-genpolicy`, po niezależnym przeglądzie kodu.
Nie zgaduj PCR17 i nie używaj wartości z dokumentacji jako produkcyjnej.

W **koncie kustosza**:

```sh
aws cloudformation deploy \
  --stack-name notarai-confidential-custody-kms-pilot01 \
  --template-file infra/notarai-confidential-external-custody-kms.yaml \
  --parameter-overrides \
      WorkloadAccountId=<WORKLOAD_ACCOUNT_12_DIGITS> \
      TenantId=pilot01 \
      ExpectedPCR17=<INDEPENDENTLY_APPROVED_96_HEX_PCR> \
      CustodyAcknowledgement=independent-operator-custody \
  --profile <EXTERNAL_CUSTODY_DEPLOY_PROFILE> --region eu-central-1
```

Nie uruchamiaj, jeśli występuje jakakolwiek niejasność co do
niezależności konta i administracji. Skopiuj `ExternalKeyArn` do
definicji zadania i IAM role w koncie NotarAI. `kms:GetPublicKey`
może dodatkowo wymagać IAM policy po stronie NotarAI, ponieważ
cross-account KMS potrzebuje uprawnień po obu stronach.

Na **obu kontach tylko odczyt**:

```sh
python scripts/verify_confidential_operator_boundary.py \
    --operator-profile <WORKLOAD_READONLY_AUDIT_PROFILE> \
    --custody-profile <EXTERNAL_CUSTODY_READONLY_AUDIT_PROFILE> \
    --tenant pilot01 \
    --task-definition-arn <EXACT_VERSIONED_ARN> \
    --kms-key-arn <EXTERNAL_KEY_ARN> \
    --pcr17 <96_HEX> \
    --image-sha256 <ECR_DIGEST_64_HEX_NO_PREFIX> \
    --check --output /tmp/notarai-boundary-pilot01.json
```

**Uwaga:** to sprawdza konfigurację w danej chwili.
`static_configuration_verified=true` oznacza tylko ten fakt.
Raport zawsze pozostawia `live_nitro_attestation_verified=false`,
`independent_custody_verified=false` i
`zero_operator_access_proven=false`, nawet gdy wszystkie testy przejdą.

## Kryteria dopuszczenia deklaracji komercyjnej

Nie zmieniaj stanu twierdzenia Zero Operator Access do czasu
gdy **niezależny audytor** ma następujące dowody:

1. Autentyczne niezależne konto custody, administracja/Organizations,
   MFA, reguły dostępu i monitoring `kms:PutKeyPolicy`, zewnętrzny
   proces zatwierdzania zmian PCR i obrazu (operator NotarAI
   nie może zmienić key policy ani tożsamości kustosza).
2. Raport realny z obu kont AWS, dokładne `iam:PassRole`,
   `kms:ListGrants`, IAM policy task role, ECR digest, KMS policy.
3. Pozytywny test sprzętowy `KMS Decrypt` z attested Nitro;
   **negatywny** test tego samego cipher/DEK z klasycznego EC2,
   hosta, złym PCR, złym task role i innym tenantem.
4. Potwierdzenie przez CloudTrail po stronie obu kont, że
   attestation PCR8/PCR17 była użyta do chronionych operacji KMS;
   żadne z zapisów nie zawiera plaintext.
5. Testy sieciowe E2E: próba eksfiltracji przez proxy, logowanie,
   stdout/stderr, błędy, debug, upload i zewnętrzne LLM; bramka
   no-submit. Samo Nitro tego nie blokuje.
6. Weryfikowalna zewnętrzna autoryzacja kolejnych wersji obrazu
   i pomiarów PCR, odrębne IAM signoff oraz niezależny zapis
   dowodów niekontrolowany przez operatora. GitHub CI nie wystarcza.
7. Niezależne badanie bezpieczeństwa i formalnie określony
   model zagrożeń — w szczególności ataki operatora i kustosza,
   błędy programu, ujawnienie przez dozwolone odpowiedzi,
   wymagania RODO i tajemnicy notarialnej.

**Uczciwa przyszła obietnica w odpowiednim zakresie:**
„Personel i administratorzy infrastruktury NotarAI nie posiadają
jednostronnej możliwości odszyfrowania dokumentów: klucze są
kontrolowane przez niezależnego kustosza i udostępniane wyłącznie
atestowanym środowiskom Nitro”. Dopiero po pozytywnym audycie.

**Nie twierdzić:** „nikt nie może odczytać danych”, „AWS zero
knowledge”, „pełne bezpieczeństwo danych”, „operatorzy nie mają
dostępu do wyników” ani „certyfikowany Zero Trust”, jeżeli brak
odrębnej certyfikacji i kontroli rzeczywistych przepływów.

## Dokumentacja AWS

- https://docs.aws.amazon.com/enclaves/latest/user/flow.html
- https://docs.aws.amazon.com/kms/latest/developerguide/key-policy-modifying-external-accounts.html
- https://docs.aws.amazon.com/AmazonECS/latest/developerguide/ict-security-model.html
- https://docs.aws.amazon.com/AmazonECS/latest/developerguide/ict-confidential-policy-configuration.html
- https://csrc.nist.gov/pubs/sp/800/207/final
