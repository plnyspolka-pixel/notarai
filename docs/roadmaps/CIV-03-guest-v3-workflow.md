# CIV-03 — kompletna ścieżka v3: S3 → SQS → Nitro → jeden podgląd

**Status:** PLAN ONLY. P0. Jedna sesja kodowania po CIV-01 (#88), współpraca z kontraktem CIV-02 (#89). Bez produkcyjnego deploymentu AWS w tym PR.

## Cel
Po weryfikacji atestacji w CIV-02 i wydaniu pojedynczego RSA-OAEP grantu rzeczywisty kod Nitro obsłuży **jeden** zaszyfrowany dokument, wykona syntetyczny podgląd i zakończy. Operator NotarAI ma prawo zarządzać kolejką oraz zadaniami, lecz nie dostaje DEK/plaintext.

## Komponenty do użycia, nie przepisywania
- `confidential/customer_guest_v3.py` z #87 (NSM nonce i jednorazowy guest RSA);
- `confidential/customer_release.py` i `customer_origin.py` z #86;
- istniejące `confidential/worker.py`, `router.py`, `dispatch.py`, `job_ledger.py`, `document_registry.py` z #50 i #57;
- S3 versioning, SQS FIFO, ECS Managed Instances/Nitro z #51/#60; S3/DDB/IAM izolacja z #74 jako referencja;
- do końca pozostaje **preview-only** i **local-demo**. Żadnego faktycznego portalu prawnego ani kliknięcia „wyślij”.

## Kontrakt v3
- Opaque `customer-envelope.v1` i `customer-release.v1` bez `kms_key_arn`, `tenant_id`/case/object/documentVersion/jobId i exact `s3_version` + hash.
- Enclave generuje RSA key **w Nitro**, tworzy NSM COSE z nonce i user_data związanymi z tą kopertą. Nie ufa kluczowi, który przysyła operator.
- Notariusz w CIV-02 sprawdza report i dostarcza grant. Guest weryfikuje podpisany origin receipt oraz immutable VersionId przed unwrap.
- `job_ledger` konsumuje autoryzację atomowo przed decrypt; po błędzie/restartcie nie powtarza skutków ubocznych. Przy niepewnym stanie: `needs_review`, bez automatycznego powtórzenia.
- Status API i logi zawierają tylko `job_id`, wynik, czas i liczbę wypełnionych pól. Nie zawierają dokumentu, podglądu, PESEL ani sekretów.

## Kryteria odbioru
- [ ] Przy syntetycznym dokumencie v3 pełny przebieg: `upload ciphertext → S3 VersionId → SQS job → real-code guest challenge → cryptographic grant → verify origin → decrypt → preview-only → terminal status`. Test lokalny uruchamia realne funkcje (bez mockowania samych walidatorów).
- [ ] Minimum **15 negatywnych scenariuszy** w CI: obcy tenant, inny job, case, documentVersion, S3 version, ciphertext SHA, origin signature, missing PCR/nonce, zły grant, wygaśnięcie, dwa consumery, replay, duplikat SQS, worker crash.
- [ ] Przy **dwóch równoległych workerach** i jednym jobie: dokładnie **jedna** udana rezerwacja z DDB, najwyżej **jeden** preview, druga próba odmówiona; oddzielny test po restarcie.
- [ ] Żadna ścieżka v3 nie wywołuje `kms:Decrypt` pod kluczem operatora. V2 pozostaje kompatybilne i niedostępne jako fallback v3.
- [ ] Nadpisanie obiektu w S3 nie wpływa na przypięty VersionId; niezgodność kończy się odmową **przed** DEK unwrap.
- [ ] Brak `submit`/sign/send i dowolnych LLM-generated instrukcji; nawet po retry `submitted` jest **false**.
- [ ] `NOTARAI_CONFIDENTIAL_REQUIRED=1`, obecność `/dev/nsm`, aktywna konfiguracja pilota i niezależnie przypięty issuer są obowiązkowe w guest. Bez nich **fail closed**.
- [ ] Worker zwalnia pamięć przez zakończenie pojedynczego procesu po zleceniu; dokumentacja jasno stwierdza brak gwarantowanego memory-wipe w Pythonie.
- [ ] CI security, regresja v2 i v3 green; brak sekretów i plaintext w logach oraz artefaktach.
- [ ] AWS nie jest uruchamiany z CI; realny hardware proof w #72.

## Granice i zakazy
Nie zmieniaj całego VPC, nie twórz drugiego workera ani custodial KMS, nie dołączaj RejNET/Windows, nie przejmuj automatycznie innych PR. Syntetyczny podgląd nie jest próbą realnego złożenia wniosku. Przed realnym AWS wymagana akceptacja kosztu i osobny runbook pilota.

## Kontrakt z #72/#73/#74
#72 potwierdza hardware live, #73 brak exfil w sieci, #74 izolację dwóch kancelarii. W tym PR trzeba zapewnić testowalne punkty kontrolne i wyłączenie funkcji do chwili tamtych dowodów.
