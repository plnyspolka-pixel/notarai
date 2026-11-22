# CIV-02 — prosty klient kancelarii: klucz i weryfikacja Nitro bez instalacji

**Status:** PLAN ONLY. Osobna sesja kodowania po CIV-01 (#88), praca nad nowym klientem v3. Bazowanie kodu na aktualnym master po włączeniu CIV-01; nie scalać #68 jako całości.

## Cel użytkownika
Notariusz wchodzi do zaufanego klienta webowego, szyfruje dokument, widzi odbiorcę i wyraża zgodę na jeden podgląd. **Bez Pythona, konsoli, kwalifikowanego podpisu i aplikacji NotarAI instalowanej na Windows.** Wrażliwe klucze nie pojawiają się na serwerze operatora.

## Implementacja
1. Wykorzystaj istniejący samodzielny HTML z #68 i RSA/OAEP AES-GCM envelope v3 z #86. Przenieś kryptografię do sprawdzonego WebCrypto; nie pisz własnych prymitywów.
2. Zaadaptuj pełną weryfikację NSM/COSE z #87 (albo dopasowany weryfikator z przykładu AWS MIT-0) w niezależnie wydawanym, przypiętym podpisem/hashem kliencie. Zatwierdzony klucz wydawcy i manifest PCR muszą być zaufane niezależnie od serwera NotarAI.
3. Zrób interfejs: **Zaszyfruj dokument → Zweryfikuj środowisko → Zezwól na jeden podgląd**. Pokazuj czytelny komunikat w razie odmowy lub braku połączenia; nie oferuj awaryjnego „kontynuuj bez atestacji”.
4. Integruj challenge: klient tworzy nonce >=32 bytes, wiąże job/dokument i sprawdza podpis AWS, łańcuch, cert time, PCR8/17, brak debug oraz exact RSA-3072 SPKI; dopiero wtedy szyfruje DEK.
5. Zadbaj o dystrybucję: jednorazowe przypięcie wydania w procesie onboardingu (podpis/odcisk dostarczony poza dynamicznym JS operatora); kolejne wydania z podpisanym manifestem i czytelnym potwierdzeniem aktualizacji. Nie wymagaj osobnego kustosza treści. Zwykły serwer NotarAI może transportować tylko ciphertext/challenge/raport.
6. Wydawanie klucza klienta i procedurę odtworzenia obsługuje CIV-04, nie duplikuj ich.

## Kryteria odbioru
- [ ] Kompletny test end-to-end w **dwóch aktualnych przeglądarkach** (Chrome i Edge) na fikcyjnym 1 MB dokumencie, bez instalacji oraz bez Pythona/CLI na urządzeniu użytkownika.
- [ ] Po początkowym onboardingu wykonanie jednego zadania zajmuje **maks. 3 świadome czynności użytkownika** (szyfrowanie, sprawdzenie, zgoda; bez specjalistycznej wiedzy).
- [ ] Wszystkie testy negatywne **fail-closed**: podmieniony JS/manifest, nieważny podpis release, nieprawidłowy łańcuch AWS, debug, PCR8/PCR17, stary nonce, zły tenant/job/envelope, klucz EC zamiast RSA, brak/niepoprawne dane atestacji.
- [ ] Automatyczny test network: przy danych wejściowych `CANARY-PII-FAKE` w HTTP/S3/API/telemetrii nie ma plaintext, DEK ani prywatnego klucza.
- [ ] Podmiana klucza odbiorcy lub wartości PCR w API nie wydaje grantu; aplikacja nie ufa flagom `verified: true` od operatora.
- [ ] Każdy wydany grant ma dokładny jobId, hash koperty i max 900s; UI wyświetla status `odmówiono` bez szczegółów sekretów.
- [ ] Test podpisanego release obejmuje aktualizację w przód, podmianę wersji i rollback do starszej niż zatwierdzona.
- [ ] Weryfikator, jego zależności i sposób podpisania paczki są odtwarzalne z udokumentowanego SHA; odrębna instrukcja dla pilota kancelarii.
- [ ] Przed realnym AWS wszystkie testy tylko synthetic; żadnego claimu produkcyjnego Zero Operator Access.

## Granice
Nie włączaj zewnętrznego modelu AI, automatycznego wysyłania aktów, RejNET, WebAuthn/QES jako wymogu, nowych kont AWS ani zaawansowanego recovery. Wszystko poza testami na fikcyjnych dokumentach zostaje wyłączone.

## Konflikty ze starymi PR
Nie przenosić do v3 klienta kustosza i KMS ARN z #68. #87 dostarcza punkt wyjścia do weryfikatora; #88 dostarcza wspólną bazę, #90 dostarczy prawdziwy guest i protokół transportu.


## INSTRUKCJA DLA CLAUDE OPUS — SESJA PR #89

Jesteś wykonawcą *tego* PR. **Wykonaj kod + testy**, nie kończ na kolejnym planie. Twoim celem jest zrealizowanie kryteriów odbioru powyżej. Nie modyfikuj obszarów innych sesji. Zanim zapiszesz kod, otwórz [katalog OSS](https://github.com/plnyspolka-pixel/notarai/blob/plan/civil-confidential-civ01-clean-base-20261122/docs/roadmaps/CIV-OSS-reuse-map.md)] i sprawdź bazową gałąź oraz aktualny stan projektu.

1. Zbadaj niezależny HTML z #68, `static/confidential-crypto.js`, Python verifier v3 z #87 oraz WebCrypto możliwości Chrome/Edge.
2. Zaimplementuj jedno podpisane, spójne wydanie klienta browser offline-first, zweryfikowane lokalnie; wykorzystaj AWS JS verifier jako punkt wyjścia, ale napraw fail-closed dla debug/PCR/RSA.
3. Podłącz nonce/job/ciphertext -> NSM proof -> RSA DEK grant; operator-hosted JS nie może decydować o zaufanym kluczu ani certyfikacie.
4. Dodaj Chrome+Edge E2E, test podmiany podpisu oraz brak plaintext/DEK na sieci; CI i dowód w PR.

**Kod do obejrzenia, nie do kopiowania bez analizy:**

- [AWS Nitro JS verifier MIT-0](https://github.com/aws-samples/sample-nitro-enclaves-attestation-webapp/blob/main/frontend/src/lib/attestationVerifier.js)
- [AWS HPKE/browser sample MIT-0](https://github.com/aws-samples/sample-nitro-enclaves-attestation-webapp/blob/main/frontend/src/lib/hpkeEncryption.js)
- [Tinfoil verify-before-send Apache-2.0 — wzorzec tylko](https://github.com/tinfoilsh/tinfoil-js/blob/main/packages/tinfoil/src/internal/verified.ts)

Przed skopiowaniem wybierz SHA/tag, przeczytaj licencję i zapisz notice. Przetestuj regresję i negatywne przypadki z definicji odbioru. Raport końcowy: zmienione pliki, ponownie użyte komponenty, testy PASS/FAIL/BLOCKED, dokładny SHA i link CI, blokady sprzętowe. Brak AWS deploy/realnych aktów bez oddzielnej zgody. **PR planistyczny pozostaje Draft do wykonania.**
