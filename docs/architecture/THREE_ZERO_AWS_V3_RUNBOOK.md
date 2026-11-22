# NotarAI 3×ZERO AWS v3 — runbook pilota (2026-11-22)

Status: KOD + CI SYNTETYCZNE, NIE AWS LIVE. Nigdy nie utożsamiać tego z produkcyjnym GO.

## Co jest połączone w głównym PR #94
- Wykorzystujemy istniejący ECS CONFIDENTIAL_SANDBOX/Nitro, S3, SQS i DynamoDB bez nowego kustosza, konta KMS ani innej infrastruktury TEE.
- confidential/customer_v3_transport.py: szyfrogram kancelarii, rezerwacja dokumentu, rzeczywisty VersionId, podpis pochodzenia i metadane FIFO.
- confidential/customer_v3_worker.py: SQS -> S3 (konkretna wersja) -> challenge -> NSM attestation -> grant -> jeden podgląd.
- confidential/customer_v3_execution.py: ponowna weryfikacja signed-origin wewnątrz guest, atomowe spalenie grantu, brak ponownego decrypt, brak submit.
- confidential/Dockerfile + confidential/bake_trust.py: podczas budowania wymagają jawnie podanego ED25519 PUBLIC KEY kancelarii. Klucza prywatnego nie wbudowujemy ani nie zapisujemy w serwerze.
- infra/notarai-confidential-task.yaml: tylko customer-v3, IAM bez kms:Decrypt.
- infra/notarai-confidential-staging.yaml: S3 Versioning=Enabled.
- scripts/confidential_pilot_bootstrap.py: nie tworzy domyślnego demonstracyjnego KMS.
- Archiwum historyczne: archive/three-zero-legacy-complete-20261122. Nie mergować archiwum.

## Kontrolna ścieżka jednego fikcyjnego zlecenia
1. Przygotuj tenant, wersjonowany bucket i kolejkę FIFO; wdroż istniejący staging/ledger/capacity.
2. Klient LOKALNIE szyfruje dokument przez `python scripts/customer_attested_release.py seal --plaintext local-demo.json --owner-public-key owner-public.pem --tenant-id pilot01 --case-id case01 --object-id object01 --document-version <32 hex> --output ciphertext.json`, zachowując owner RSA-3072 private key wyłącznie lokalnie. Operator otrzymuje tylko kopertę ciphertext. CustomerCiphertextTransport.admit_ciphertext zwraca VersionId.
3. Klient LOKALNIE podpisuje wskazany S3 VersionId w scripts/customer_attested_release.py (subcommand origin) kluczem Ed25519. Publiczny klucz tej pary musi być wbudowany w obraz Nitro.
4. Przed wrzuceniem do SQS klient tworzy świeży challenge subcommand challenge i zapisuje challenge.json w S3 dokładnie raz.
5. Operator wykonuje enqueue_signed_preview z weryfikacją oryginalnego podpisu. Worker Nitro sprawdza SQS, DDB, S3 VersionId i customer challenge.
6. Worker tworzy ephemeral RSA recipient w /dev/nsm i wystawia niezmienny attestation.cbor w S3. Klient LOKALNIE weryfikuje AWS COSE/X.509, nonce, hash zlecenia, PCR8/PCR17 i niezależnie podpisany manifest obrazu. Dopiero wtedy subcommand release wyda grant.json: DEK RSA-OAEP zaszyfrowany wyłącznie do zweryfikowanego recipient.
7. Worker czyta tylko encrypted grant, atomowo konsumuje release w istniejącym DynamoDB, robi fikcyjny podgląd bez submit i zapisuje wynik bez plaintext. Jeden proces/jedna praca/jeden grant.
8. Zweryfikuj na realnym AWS poprawną ścieżkę, odmowę przy zmianie PCR, zamianie obrazu, braku zgody klienta, cross-tenant, replay i wszelkich operator/admin IAM oraz brak ujawnienia canary w S3/SQS/logach.

## Położenie untrusted transport w S3
- kancelarie/<tenant>/confidential-control/<job>/challenge.json
- kancelarie/<tenant>/confidential-control/<job>/attestation.cbor
- kancelarie/<tenant>/confidential-control/<job>/grant.json

Ważne: klient musi mieć oddzielne, najmniejsze możliwe uprawnienia S3, żeby przesyłać challenge/grant oraz odbierać attestation. Nie przyznawać dostępu do owner private key ani lokalnego PCR signing trust operatorowemu frontendowi.

## Jak przygotować obraz
Buduj tylko z jawnie zweryfikowanymi parametrami Docker build:
- TRUSTED_ORIGIN_ISSUER_ID: identyfikator kancelarii
- TRUSTED_ORIGIN_PUBLIC_B64: publiczny Ed25519 Raw (32 bajty, Base64)

Obraz bez tych argumentów musi odmówić zbudowania. Przypnij ECR image@sha256; wygeneruj politykę ecs-nitro-sandbox-genpolicy i PCR8/PCR17; zatwierdź niezależnym klientem przed wydaniem DEK. Bez takiej procedury nie ma dowodu Zero Operator Access.

## Pozostałe blokady (NO_GO)
- Brak uruchomienia hardware Nitro na autoryzowanym koncie AWS i niezależnych dowodów pozytywnych/negatywnych, w tym prawdziwych uprawnień operatora.
- Brak produkcyjnego, niezależnie dystrybuowanego klienta kluczy z backup/restore oraz rotacją. Lokalny CLI to pilot, nie docelowy frontend.
- Brak testowanego end-to-end ograniczenia egress; aktualny security group AWS pilota nadal dopuszcza TCP 443 w świat i musi zostać ograniczony.
- Brak testów live Bedrock/modelu i podpisanych ustaleń o regionie, retencji, logach i przetwarzaniu. Na razie worker tylko podgląda lokalny fikcyjny formularz, bez AI.
- Brak potwierdzonego DPA/oceny prawnej i testów administracyjnych IAM, S3, ECR, task-definition/policy mutation.

Ocena: kod offline możliwy do dalszego testowania, live 3×ZERO i sprzedaż = NO_GO. Wszystkie nowe prace na PR #94; archiwalne pomysły poza ścieżką wdrożeniową.

## Uzupełnienie po testach GitHub: oczekiwanie na grant S3

AWS S3 przy braku `s3:ListBucket` zwraca HTTP 403, a nie 404, gdy `GetObject` dotyczy brakującego grantu. Bez naprawy worker kończyłby zadanie przed przesłaniem klucza przez kancelarię. Teraz worker wykonuje `ListObjectsV2` z **dokładnym** `Prefix=<job>/grant.json` i `MaxKeys=1`; IAM dopuszcza listowanie tylko nazw grantów w bieżącym tenancie. Pusty wynik oznacza jeszcze oczekujący grant. Inne błędy lub zwrócenie obcego klucza powodują odmowę. Jest negatywny test 403/prefix-confusion i weryfikacja zakresu IAM.

Lokalny CLI `seal` zapisuje wyłącznie kopertę AES-GCM/RSA klienta, wymaga jawnego klucza publicznego i odmawia nadpisania istniejącego wyjścia. Bez AWS call. To prototyp, nie zastępuje podpisanego dystrybuowanego klienta, bezpiecznej kopii klucza i prób sprzętowych.
