# SEC-11 — [SEC-11] Niezależny rejestr dowodów: atestacje, release, KMS, IAM i audyt zmian

**Status: PLANNED (NOT IMPLEMENTED).** P0; zależności: SEC-01, SEC-05, SEC-06, SEC-07

## Zakres
1. Zaprojektuj zewnętrzny, append-only repozytorium dowodowe pod kontrolą niezależnego audytora/kustosza (nie tylko logi aplikacji lub konto AWS operatora).
2. Dowody: AWS STS identity / Organizations scope, wersja image@sha256, task ARN, PCR17, policy hash, podpis kustosza, CloudTrail KMS, testy deny, ECS Nitro status, tenant, czas, zakres i expiry.
3. Implementuj podpisaną paczkę z kryptograficznym łańcuchem integralności i sprawdzaniem kompletności/replay; bez PESEL, aktów, ciphertext, sekretów ani surowych dumpów.
4. Zbuduj publiczny dla klienta/audytora weryfikator offline: wypisuje co potwierdzono, czego nie, oraz czy poświadczenia wygasły; nigdy nie konwertuj automatycznie PASS(unit tests) na PASS(hardware).

## Mierzalne kryteria zakończenia — SEC-11

- [ ] **K1.** **Format dowodu:** maszynowy manifest wiąże tenant, UTC timestamp, region, source SHA, ECR digest, task ARN, PCR17, KMS policy hash, custody account, release ID, wyniki testów, właściciela i expiry; każda wymagana pozycja ma jawny status.
- [ ] **K2.** **Podpis niezależny:** odrębny audytor/kustosz podpisuje hash kanonicznego manifestu. Offline verifier korzysta z klucza publicznego/fingerprint dostarczonych *poza* kontem operatora; modyfikacja dowodu, podpisu lub fingerprintu powoduje FAIL.
- [ ] **K3.** **7 negatywnych testów:** podmieniony tenant, digest, PCR, key policy, data, usunięty test odmowy i przeterminowany manifest; wszystkie unieważniają wynik.
- [ ] **K4.** **Odporność na braki:** niepełne dowody hardware albo status mock nigdy nie prowadzą do `zero_operator_access_proven=true`; brak rejestru niezależnego daje `BLOCKED`, bez sztucznego fallbacku.
- [ ] **K5.** **Append-only:** realne konto lub storage kustosza uniemożliwia operatorowi NotarAI modyfikowanie i usuwanie wcześniejszych podpisanych manifestów; test 2 prób operatora (overwrite/delete) kończy się odmową.
- [ ] **K6.** **Weryfikacja offline:** polecenie do niezależnej inspekcji paczki nie potrzebuje serwera NotarAI ani tokenu aplikacji. Wynik ma czytelne `PASS`, `FAIL`, `EXPIRED`, `BLOCKED` i hash manifestu. Live WORM/ownership bez dowodu = `BLOCKED`.

**Test do dopisania:** `python -m pytest -q test_confidential_signed_evidence.py` — 0 failed / 0 pominiętych testów krytycznych.

### Wspólny warunek zamknięcia
- [ ] Link do **zielonego CI dla aktualnego SHA**, dokładna komenda, liczba passed/failed/skipped oraz zanonimizowany raport `docs/security-evidence/SEC-11.md` (lub odpowiedni artefakt CI). Testy opisane niżej muszą zostać zaimplementowane.
- [ ] Każdy K1–K6 ma status `PASS/FAIL/BLOCKED`, datę, właściciela i link do weryfikowalnego dowodu. Brak rzeczywistego AWS lub niezależnej kontroli = `BLOCKED`, nigdy domniemany `PASS`.
- [ ] Bez plaintext, PESEL, tokenów, materiałów kluczy lub danych osobowych w dowodach; AUTO nadal nie podpisuje i nie wysyła. Zakończenie PR to nie automatyczna deklaracja ZK/ZOA.

## Instrukcja dla osobnej konwersacji
To **wyłącznie PR planistyczny**. Zrealizuj zadanie na istniejącej gałęzi tego PR, uzupełnij kod, testy, instrukcje i dowody w tym samym PR. Czytaj poprzednie #57, #60, #61, #62, #65 i odpowiednie SEC-nn; sprawdź aktualne SHA. Wszystkie SEC-nn bazują na #65 i nie wymagają edycji gałęzi pozostałych zadań. Jeśli potrzebna zmiana w pliku współdzielonym, udokumentuj integracyjne uzgodnienie i konflikt.
Zakres danych: wyłącznie syntetyczne pilot01/pilot02, EU eu-central-1, produkcja OFF, no-submit/no-sign. Nie dotykaj prawdziwych spraw, nie wynoś plaintext ani sekretów do CloudWatch/GitHub/proxy. Nie wykonuj AWS write bez autoryzowanych tożsamości i zgody kustosza. Wyniki CI != real hardware evidence. Kryteria: kod + testy odmowy + dokumentacja, niezależny dowód i jawne FAIL/BLOCKED. Bez automatycznej deklaracji 'Verified Zero Knowledge/Zero Operator Access'.
