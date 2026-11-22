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
