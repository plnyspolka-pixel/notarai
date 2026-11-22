# SEC-11 — niezależny rejestr dowodów bezpieczeństwa

Stan: **PARTIAL IMPLEMENTATION / DRAFT / NOT VERIFIED** (2026-11-22).
Dane wyłącznie fikcyjne pilot01/pilot02, eu-central-1. Zero AWS write.

## Dostarczone artefakty

- confidential/signed_evidence.py — ścisły manifest, Ed25519, hash chain,
  walidacja terminów, offline verification, jawna odmowa deklaracji ZOA.
- scripts/verify_confidential_evidence.py — verifier offline bez AWS/NotarAI API.
- test_confidential_signed_evidence.py — negatywne przypadki: tenant, image
  digest, PCR17, KMS policy hash, UTC, brak deny testu, expiry, podpis,
  fingerprint, chain rollback/replay oraz brak hardware proof.
- infra/notarai-confidential-independent-evidence.yaml — NIEWDROŻONY szablon
  oddzielnego konta kustosza: Object Lock COMPLIANCE, versioning, public
  access block, S3 Retain, TLS i DENY dla całego konta operatora.
- .github/workflows/confidential-browser.yml — testy i linter szablonu.

## Granica twierdzeń

Podpis poświadcza tylko oświadczenie osoby podpisującej. Sam podpis nie
dowodzi, że AWS wykonał test, ani że fizyczne Nitro rzeczywiście działało.
Dlatego poprawne integrity_status=PASS nadal daje assurance_status=BLOCKED
oraz zero_operator_access_proven=false. Wpis provenance=AWS_LIVE lub
syntetyczne testy CI nie zastępują CloudTrail, sprawdzenia atestacji i
niezależnej kontroli dostępu do storage.

Fingerprint publicznego klucza i ostatni hash łańcucha muszą zostać
przekazane audytorowi NIEZALEŻNYM kanałem poza operatorem. Klucz prywatny
nigdy nie trafia do NotarAI, GitHub ani API. Manifest zawiera wyłącznie
identyfikatory techniczne i hashe; nie zawiera aktów, PESEL, ciphertext,
DEK, screenshotów ani dumpów.

Object Lock COMPLIANCE chroni istniejące wersje do końca retencji,
ale PUT tego samego key może utworzyć nową wersję, zatem sam Object Lock
nie blokuje podmienienia widoku latest. Potrzebne są również IAM DENY i
zewnętrznie zapisany chain head. RetentionDays=365 jest wyłącznie
przykładem dla pilota, nie ustaleniem prawnym.

## Użycie przez zewnętrznego audytora

Audytor otrzymuje niezależnie: bundle.json (lub chain.json), plik RAW
z 32-bajtowym publicznym Ed25519, pin SHA-256 i zatwierdzony HEAD SHA-256.

~~~bash
python -m pytest -q test_confidential_signed_evidence.py
python scripts/verify_confidential_evidence.py \
  --bundle bundle.json --trusted-public-key custodian-ed25519-pub.raw \
  --pinned-fingerprint "$PIN_SHA256" \
  --trusted-head-sha256 "$HEAD_SHA256"
python scripts/verify_confidential_evidence.py \
  --chain chain.json --trusted-public-key custodian-ed25519-pub.raw \
  --pinned-fingerprint "$PIN_SHA256" \
  --trusted-head-sha256 "$HEAD_SHA256"
~~~

Exit status 2: FAIL; 3: EXPIRED; 4: signature/integrity verified,
lecz live AWS/storage nie są niezależnie zweryfikowane. Kodu 4 nie wolno
używać do aktywacji produkcji ani stwierdzenia ZK/ZOA.

## Plan niezależnego testu AWS — jeszcze niewykonany

1. Kustosz uzyskuje STS GetCallerIdentity, sprawdza AWS Organizations/SCP,
   prawa, oddzielny account ID oraz brak trust do operatora.
2. Kustosz autoryzuje retention i wdraża szablon WORM wyłącznie na swoim
   odrębnym koncie, na syntetycznych identyfikatorach.
3. Kustosz przechowuje podpisane manifesty, wersje i niezależny HEAD SHA.
4. Operator na własnych credentials próbuje PutObject i
   DeleteObjectVersion dla syntetycznych wpisów. Oba testy muszą
   zakończyć się AccessDenied; zachowuje się request ID, UTC, Principal,
   bez zapisywania danych źródłowych.
5. Audytor niezależnie sprawdza realną atestację Nitro, KMS deny,
   zatwierdzoną wersję image, CloudTrail oraz ECS task i signed release.
6. Audytor dowodzi, że operator nie może zmienić bucket policy,
   Object Lock, kluczy, konta kustosza ani wcześniejszych wersji.
   Brak live dowodów to BLOCKED. Żadnych rzeczywistych spraw.

## Matryca K1–K6

| Kryterium | Status | Właściciel | Dowód lub brak |
| --- | --- | --- | --- |
| K1 format | UNVERIFIED | kod | manifest i testy, CI dla HEAD oczekiwany |
| K2 podpis niezależny | BLOCKED | kustosz | podpis syntetyczny ≠ realny podpis kustosza |
| K3 7 testów odmowy | UNVERIFIED | kod | testy jednostkowe, CI dla HEAD oczekiwany |
| K4 brak sprzętu/mock | UNVERIFIED | kod | fail-closed w verifier, potrzebny zielony CI |
| K5 WORM + 2 AccessDenied | BLOCKED | kustosz | szablon niewdrożony i brak live testu |
| K6 offline + live | BLOCKED | audytor | CLI gotowe, brak niezależnego sprawdzenia AWS |

Warunek DONE: 0 FAIL, 0 BLOCKED, 0 UNVERIFIED; dla K5/K6 prawdziwy dowód
zewnętrzny, nie mock. Merge PR nie uprawnia do marketingu Zero Knowledge
ani Zero Operator Access.


## Narzędzia przygotowane do niezależnego testu K5 (NIEWYKONANE)

- confidential/custody_storage.py / test_confidential_custody_storage.py:
  read-only STS/S3. Audytują Object Lock COMPLIANCE, versioning, public
  access block, szyfrowanie, bucket ownership, region i explicit deny.
- scripts/audit_confidential_evidence_storage.py: audyt wyłącznie read-only
  po podaniu --run-read-only i profilu SSO niezależnego kustosza.
- confidential/custody_denial_probe.py / test_confidential_custody_denials.py:
  dwie kontrolowane próby PutObject i DeleteObject (z VersionId) wyłącznie
  w syntetycznej przestrzeni S3.
- scripts/probe_confidential_evidence_operator_denials.py: nie należy
  do CI i NIE BYŁ URUCHAMIANY przeciwko AWS. Wymaga flagi
  --authorize-synthetic-write-probes oraz pisemnej zgody kustosza,
  osobnego profilu operatora i istniejącego fikcyjnego VersionId.

### Read-only w niezależnym koncie kustosza

~~~bash
python scripts/audit_confidential_evidence_storage.py \
  --custody-account "$CUSTODY_ACCOUNT" \
  --operator-account "$OPERATOR_ACCOUNT" \
  --bucket "$INDEPENDENT_WORM_BUCKET" \
  --profile "$CUSTODY_AUDITOR_SSO_PROFILE" \
  --run-read-only
~~~

Configuration_status PASS oznacza jedynie poprawny odczyt konfiguracji,
ale assurance_status pozostaje BLOCKED. Exit 4 nie pozwala deklarować
gotowości Zero Operator.

### Operator: dwie kontrolowane próby odmowy

Uruchamiać wyłącznie po pozytywnej kontroli read-only i pisemnej zgodzie
kustosza. Kustosz przygotowuje compliance-locked obiekt syntetyczny
i jego VersionId. Wykonawca korzysta tylko z profilu konta operatora.

~~~bash
python scripts/probe_confidential_evidence_operator_denials.py \
  --operator-account "$OPERATOR_ACCOUNT" \
  --custody-account "$CUSTODY_ACCOUNT" \
  --bucket "$INDEPENDENT_WORM_BUCKET" \
  --fixture-key sec11-fixture/independent-test-20261122 \
  --fixture-version "$CUSTODIAN_SYNTHETIC_VERSION_ID" \
  --operator-profile "$OPERATOR_AUDIT_SSO_PROFILE" \
  --authorize-synthetic-write-probes
~~~

UWAGA: S3 AccessDenied może pochodzić również z niezgodnego
ExpectedBucketOwner, a nie tylko z poprawnie wymuszonej granicy IAM.
Dlatego skrypt raportuje zaobserwowane odmowy, a nie potwierdzenie
niezależnego właściciela. Audytor musi związać wynik z osobnym odczytem
kustosza, STS, CloudTrail i kontrolą cross-account AssumeRole/trust.
Bez tego K5 pozostaje BLOCKED. Skrypt nie usuwa śladów po
nieoczekiwanym sukcesie.

K1–K4 nadal wymagają zielonego CI dla najnowszego commita;
K5–K6 dodatkowo rzeczywistych testów infrastruktury.


## Niezależne podpisywanie manifestu (kod offline, testy syntetyczne)

Nowe pliki: scripts/custodian_sign_confidential_evidence.py i
test_confidential_custody_signer.py. Audytor/kustosz uruchamia signer
wyłącznie na własnej stacji, nie na koncie/VM operatora NotarAI.

Wymagania: zaszyfrowany PKCS#8 PEM Ed25519 jako plik owner-only 0600;
hasło tylko przez dedykowany deskryptor pliku (FD > 2) z lokalnego
sejfowego kanału, NIE przez argument CLI, zmienną środowiskową, mail
ani GitHub. Manifest wejściowy zawiera tylko dozwolone techniczne dane.
Wyjście: nowy plik podpisanej paczki 0600, O_EXCL (bez nadpisania).
Publiczny fingerprint dystrybuować NIEZALEŻNIE poza NotarAI.

~~~bash
# FD 3 musi dostarczać hasło z niezależnego kanału kustosza,
# zakończone LF; nigdy nie umieszczać hasła w shell history.
python scripts/custodian_sign_confidential_evidence.py \
  --manifest reviewed-manifest.json \
  --encrypted-key custodian-encrypted-ed25519.pem \
  --output signed-bundle.json \
  --password-fd 3
~~~

Następnie custody archive zapisuje kopię, SHA manifestu, numer
wersji/łańcucha i niezależny HEAD SHA; audytor offline wykonuje
scripts/verify_confidential_evidence.py. Sam poprawny podpis wciąż
nie dowodzi realnej konfiguracji IAM/Nitro/WORM. Bez aktualnego CI i
niezależnego live audytu K2, K5 i K6 pozostają BLOCKED.


## Wiązanie odmowy z prawdziwą syntetyczną wersją

Przed próbami operatora niezależny kustosz musi wykonać dodatkowo
read-only audyt tego samego *fikcyjnego* VersionId. Używa opcji
--fixture-key i --fixture-version w
scripts/audit_confidential_evidence_storage.py:

~~~bash
python scripts/audit_confidential_evidence_storage.py \
  --custody-account "$CUSTODY_ACCOUNT" \
  --operator-account "$OPERATOR_ACCOUNT" \
  --bucket "$INDEPENDENT_WORM_BUCKET" \
  --profile "$CUSTODY_AUDITOR_SSO_PROFILE" \
  --fixture-key sec11-fixture/independent-test-20261122 \
  --fixture-version "$CUSTODIAN_SYNTHETIC_VERSION_ID" \
  --run-read-only
~~~

Wykorzystuje wyłącznie HeadObject i GetObjectRetention na wskazanej
wersji (bez GetObject/treści). Kontrola uznaje aktywny lock tylko gdy
Mode=COMPLIANCE, RetainUntilDate jest późniejszy niż bieżący czas UTC,
a identyfikator jest w wydzielonej przestrzeni sec11-fixture/.
Niezależny audytor koreluje wyniki konta kustosza z operatorem poprzez
SHA manifestu, ten sam bucket/version, UTC i CloudTrail; sam skrypt
celowo nie podnosi zero_operator_access_proven do true.
