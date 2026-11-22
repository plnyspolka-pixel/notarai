# SEC-12 — [SEC-12] Zintegrowany test atakującego operatora i dwóch kancelarii (release gate)

**Status: PLANNED (NOT IMPLEMENTED).** P0; zależności: SEC-02 do SEC-11

## Zakres
1. Przygotuj powtarzalną sekwencję E2E na fikcyjnych tenantach: upload zaszyfrowanego dokumentu → signed image/release → Nitro attestation → KMS attested unwrap → preview-only → wynik i dowody.
2. Zasymuluj przeciwnika operator AWS/CI/host/sieć: zmiana kodu, PCR, KMS policy, role grants, task overrides, replay, podmiana dokumentu VersionId, traffic exfil, cross-tenant access.
3. Użyj realnych kontrprzykładów, testów fault injection/awaria sieci i retry, sprawdź brak podpisu/wysyłki niezależnie od Playwright. Nie używaj prawdziwych usług urzędowych bez odrębnego legalnego test environment.
4. Zdefiniuj twardą blokadę commercial flag: FAIL/BLOCKED jeśli którykolwiek security gate niedowiedziony lub niezależny key custodian jest pod kontrolą NotarAI.

## Mierzalne kryteria zakończenia — SEC-12

- [ ] **K1.** **2 pozytywne scenariusze:** pilot01 i pilot02 kończą fikcyjne zaszyfrowane zadania jako `preview_completed` i `submitted=false`, z odrębnym KMS/task role, tą samą zatwierdzoną wersją Nitro.
- [ ] **K2.** **Min. 12 odmów:** IAM/PassRole, zmiana KMS key policy, CreateGrant, OCI digest swap, PCR tamper, release replay, expiry, S3 VersionId swap, wrong tenant, API scope, exfil GET/POST i próba wywołania submit — wszystkie zakończone odmową lub twardym FAIL.
- [ ] **K3.** **Rzeczywisty AWS:** te same scenariusze uruchamiane z autoryzowanych kont workload i custody, z hardware NSM; jeśli infrastruktura niedostępna, cały live gate pozostaje `BLOCKED`.
- [ ] **K4.** **Awarie:** co najmniej 4 scenariusze timeout, retry, duplicate SQS i crash guest; zero utraconych blokad i zero finalnego submit.
- [ ] **K5.** **Brak wypływu:** fikcyjny canary marker 0 razy na kolektorze egress, w stdout/stderr, CloudWatch i artefaktach operatora, zarówno przy sukcesie jak i negatywnych próbach.
- [ ] **K6.** **Raport podpisany:** wynik per case (2 pozytywne + 12 negatywnych + 4 awarie), run ID, timestamps, image digest, KMS/CloudTrail hashes, owner i niezależny podpis; którekolwiek FAIL/BLOCKED w P0 ⇒ commercial GO=NO.

**Test do dopisania:** `python -m pytest -q test_confidential_adversarial_e2e.py` — 0 failed / 0 pominiętych testów krytycznych.

**E2E AWS do dopisania:** `python scripts/run_confidential_adversarial_e2e.py --check` (brak realnego wykonania = BLOCKED).

### Wspólny warunek zamknięcia
- [ ] Link do **zielonego CI dla aktualnego SHA**, dokładna komenda, liczba passed/failed/skipped oraz zanonimizowany raport `docs/security-evidence/SEC-12.md` (lub odpowiedni artefakt CI). Testy opisane niżej muszą zostać zaimplementowane.
- [ ] Każdy K1–K6 ma status `PASS/FAIL/BLOCKED`, datę, właściciela i link do weryfikowalnego dowodu. Brak rzeczywistego AWS lub niezależnej kontroli = `BLOCKED`, nigdy domniemany `PASS`.
- [ ] Bez plaintext, PESEL, tokenów, materiałów kluczy lub danych osobowych w dowodach; AUTO nadal nie podpisuje i nie wysyła. Zakończenie PR to nie automatyczna deklaracja ZK/ZOA.

## Instrukcja dla osobnej konwersacji
To **wyłącznie PR planistyczny**. Zrealizuj zadanie na istniejącej gałęzi tego PR, uzupełnij kod, testy, instrukcje i dowody w tym samym PR. Czytaj poprzednie #57, #60, #61, #62, #65 i odpowiednie SEC-nn; sprawdź aktualne SHA. Wszystkie SEC-nn bazują na #65 i nie wymagają edycji gałęzi pozostałych zadań. Jeśli potrzebna zmiana w pliku współdzielonym, udokumentuj integracyjne uzgodnienie i konflikt.
Zakres danych: wyłącznie syntetyczne pilot01/pilot02, EU eu-central-1, produkcja OFF, no-submit/no-sign. Nie dotykaj prawdziwych spraw, nie wynoś plaintext ani sekretów do CloudWatch/GitHub/proxy. Nie wykonuj AWS write bez autoryzowanych tożsamości i zgody kustosza. Wyniki CI != real hardware evidence. Kryteria: kod + testy odmowy + dokumentacja, niezależny dowód i jawne FAIL/BLOCKED. Bez automatycznej deklaracji 'Verified Zero Knowledge/Zero Operator Access'.
