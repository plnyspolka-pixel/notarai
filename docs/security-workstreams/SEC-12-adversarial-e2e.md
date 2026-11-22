# SEC-12 — [SEC-12] Zintegrowany test atakującego operatora i dwóch kancelarii (release gate)

**Status: PLANNED (NOT IMPLEMENTED).** P0; zależności: SEC-02 do SEC-11

## Zakres
1. Przygotuj powtarzalną sekwencję E2E na fikcyjnych tenantach: upload zaszyfrowanego dokumentu → signed image/release → Nitro attestation → KMS attested unwrap → preview-only → wynik i dowody.
2. Zasymuluj przeciwnika operator AWS/CI/host/sieć: zmiana kodu, PCR, KMS policy, role grants, task overrides, replay, podmiana dokumentu VersionId, traffic exfil, cross-tenant access.
3. Użyj realnych kontrprzykładów, testów fault injection/awaria sieci i retry, sprawdź brak podpisu/wysyłki niezależnie od Playwright. Nie używaj prawdziwych usług urzędowych bez odrębnego legalnego test environment.
4. Zdefiniuj twardą blokadę commercial flag: FAIL/BLOCKED jeśli którykolwiek security gate niedowiedziony lub niezależny key custodian jest pod kontrolą NotarAI.

## Kryteria odbioru
- [ ] E2E wraz z negatywnymi atakami ma zanonimizowane, reproducible evidence z rzeczywistego sprzętu.
- [ ] Brak możliwości obejścia key/custody gate przez operatora bez zmiany niezależnie zatwierdzonego kodu i polityki.
- [ ] Raport końcowy odróżnia testy unit/mock, live AWS, certyfikaty i zakres Zero Knowledge.

## Instrukcja dla osobnej konwersacji
To **wyłącznie PR planistyczny**. Zrealizuj zadanie na istniejącej gałęzi tego PR, uzupełnij kod, testy, instrukcje i dowody w tym samym PR. Czytaj poprzednie #57, #60, #61, #62, #65 i odpowiednie SEC-nn; sprawdź aktualne SHA. Wszystkie SEC-nn bazują na #65 i nie wymagają edycji gałęzi pozostałych zadań. Jeśli potrzebna zmiana w pliku współdzielonym, udokumentuj integracyjne uzgodnienie i konflikt.
Zakres danych: wyłącznie syntetyczne pilot01/pilot02, EU eu-central-1, produkcja OFF, no-submit/no-sign. Nie dotykaj prawdziwych spraw, nie wynoś plaintext ani sekretów do CloudWatch/GitHub/proxy. Nie wykonuj AWS write bez autoryzowanych tożsamości i zgody kustosza. Wyniki CI != real hardware evidence. Kryteria: kod + testy odmowy + dokumentacja, niezależny dowód i jawne FAIL/BLOCKED. Bez automatycznej deklaracji 'Verified Zero Knowledge/Zero Operator Access'.
