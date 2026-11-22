# SEC-11 — [SEC-11] Niezależny rejestr dowodów: atestacje, release, KMS, IAM i audyt zmian

**Status: PLANNED (NOT IMPLEMENTED).** P0; zależności: SEC-01, SEC-05, SEC-06, SEC-07

## Zakres
1. Zaprojektuj zewnętrzny, append-only repozytorium dowodowe pod kontrolą niezależnego audytora/kustosza (nie tylko logi aplikacji lub konto AWS operatora).
2. Dowody: AWS STS identity / Organizations scope, wersja image@sha256, task ARN, PCR17, policy hash, podpis kustosza, CloudTrail KMS, testy deny, ECS Nitro status, tenant, czas, zakres i expiry.
3. Implementuj podpisaną paczkę z kryptograficznym łańcuchem integralności i sprawdzaniem kompletności/replay; bez PESEL, aktów, ciphertext, sekretów ani surowych dumpów.
4. Zbuduj publiczny dla klienta/audytora weryfikator offline: wypisuje co potwierdzono, czego nie, oraz czy poświadczenia wygasły; nigdy nie konwertuj automatycznie PASS(unit tests) na PASS(hardware).

## Kryteria odbioru
- [ ] Audytor weryfikuje podpis dowodu bez serwisu NotarAI i wykrywa zmianę manifestu.
- [ ] Raport ma faktyczny status UNVERIFIED/PASS/FAIL/EXPIRED z właścicielem dowodu.
- [ ] Niezależny storage ownership i immutability muszą być wykazane realnym uprawnieniem oraz testem odmowy operatorowi.

## Instrukcja dla osobnej konwersacji
To **wyłącznie PR planistyczny**. Zrealizuj zadanie na istniejącej gałęzi tego PR, uzupełnij kod, testy, instrukcje i dowody w tym samym PR. Czytaj poprzednie #57, #60, #61, #62, #65 i odpowiednie SEC-nn; sprawdź aktualne SHA. Wszystkie SEC-nn bazują na #65 i nie wymagają edycji gałęzi pozostałych zadań. Jeśli potrzebna zmiana w pliku współdzielonym, udokumentuj integracyjne uzgodnienie i konflikt.
Zakres danych: wyłącznie syntetyczne pilot01/pilot02, EU eu-central-1, produkcja OFF, no-submit/no-sign. Nie dotykaj prawdziwych spraw, nie wynoś plaintext ani sekretów do CloudWatch/GitHub/proxy. Nie wykonuj AWS write bez autoryzowanych tożsamości i zgody kustosza. Wyniki CI != real hardware evidence. Kryteria: kod + testy odmowy + dokumentacja, niezależny dowód i jawne FAIL/BLOCKED. Bez automatycznej deklaracji 'Verified Zero Knowledge/Zero Operator Access'.
