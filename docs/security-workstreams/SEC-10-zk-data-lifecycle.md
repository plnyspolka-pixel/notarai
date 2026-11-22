# SEC-10 — [SEC-10] Zero Knowledge: cykl życia plaintext, retencja, logi, kopie i usuwanie

**Status: PLANNED (NOT IMPLEMENTED).** P0; zależności: SEC-03, SEC-04, SEC-08

## Zakres
1. Zmapuj w jakich procesach dokument występuje jawnie: browser RAM, model context, PDF preview, exception, crashdump, screenshot, metrics, tmpfs, stdout/stderr, support, cache i backup.
2. Wymuś minimalny lifetime DEK/plaintext wewnątrz zatwierdzonego Nitro; brak core dump, persisted browser cache i metadanych ujawniających PII; na ile technicznie możliwe: bezpieczna likwidacja sesji i zera po zakończeniu.
3. Przetestuj retencję i usuwanie ciphertext, kluczy/wersji, backupów, danych z LLM i audytu zgodnie z wymaganiami notarialnymi/RODO; NIE obiecuj kasowania historii w S3 Retain/PITR bez osobnej procedury.
4. Przygotuj model recovery i legal hold: operator nie może mieć ukrytego klucza awaryjnego, a notariusz/kustosz muszą znać ograniczenia odtwarzania.

## Mierzalne kryteria zakończenia — SEC-10

**TWARDY WARUNEK `DONE`:** komplet **K1–K6 = PASS**, każde poparte linkiem do wyniku testu lub niezależnego dowodu, **0 FAIL, 0 BLOCKED, 0 UNVERIFIED**, istniejący test docelowy z **0 failed i 0 pominiętych scenariuszy krytycznych** oraz zielony CI dla aktualnego HEAD SHA. Wymagany rzeczywisty dowód z AWS lub zewnętrznego audytora jest niezbędny tam, gdzie wskazano go w K1–K6; test mock nie zastępuje live. Przy choć jednej niespełnionej pozycji PR pozostaje OTWARTY/DRAFT. Zamknięcie implementacyjnego PR nie oznacza automatycznego pozwolenia na marketing ZK/ZOA.

- [ ] **K1.** **Mapa pamięci i retencji:** lista wszystkich co najmniej 10 możliwych lokalizacji danych: RAM Nitro, /tmp/tmpfs, browser cache/profile, crash dump, screenshot, stdout, stderr, CloudWatch, proxy, LLM request/output, S3 version i PITR; dla każdej zapisane: możliwy plaintext?, dostęp operatora?, retention i właściciel.
- [ ] **K2.** **6 testów syntetycznego markera:** normalny sukces, wyjątek, restart/retry, browser crash, błąd network i timeout. Po każdym przechwycenie stdout/stderr/logów/artefaktów i wykazanie 0 utrwalonych wystąpień fikcyjnego plaintext/DEK.
- [ ] **K3.** **Brak trwałego plaintext:** konfiguracja guest ma readonly filesystem, szyfrowanie artefaktów oraz ulotny tmpfs; po zakończeniu nie zostaje żaden niezaszyfrowany plik w persistent S3, bazach i volume snapshots (test skanu syntetycznego).
- [ ] **K4.** **Retencja jednoznaczna:** tabela dla ciphertext/version, DDB PITR, SQS/DLQ, CloudTrail, LLM, logów i backupów zawiera dokładny okres, podstawę prawną i sposób usunięcia; nie obiecuj usunięcia z `Retain` bez procedury.
- [ ] **K5.** **Recovery bez backdoor:** testy utraty DEK, odwołania klucza i żądania administratora — administrator nie dostaje plaintext, a recovery wymaga jawnego autoryzowanego kustosza/klienta.
- [ ] **K6.** **Rzeczywista analiza:** testy crash/log w faktycznym Nitro + AWS storage/CloudTrail z fikcyjnym markerem i zanonimizowanym raportem. Fizyczne wymazanie RAM po wykonaniu kodu nie jest tu bezwzględną gwarancją; jeśli brak dowodu, `BLOCKED`.

**Test do dopisania:** `python -m pytest -q test_confidential_plaintext_lifecycle.py` — 0 failed / 0 pominiętych testów krytycznych.

### Wspólny warunek zamknięcia
- [ ] Link do **zielonego CI dla aktualnego SHA**, dokładna komenda, liczba passed/failed/skipped oraz zanonimizowany raport `docs/security-evidence/SEC-10.md` (lub odpowiedni artefakt CI). Testy opisane niżej muszą zostać zaimplementowane.
- [ ] Każdy K1–K6 ma status `PASS/FAIL/BLOCKED`, datę, właściciela i link do weryfikowalnego dowodu. Brak rzeczywistego AWS lub niezależnej kontroli = `BLOCKED`, nigdy domniemany `PASS`.
- [ ] Bez plaintext, PESEL, tokenów, materiałów kluczy lub danych osobowych w dowodach; AUTO nadal nie podpisuje i nie wysyła. Zakończenie PR to nie automatyczna deklaracja ZK/ZOA.

## Instrukcja dla osobnej konwersacji
To **wyłącznie PR planistyczny**. Zrealizuj zadanie na istniejącej gałęzi tego PR, uzupełnij kod, testy, instrukcje i dowody w tym samym PR. Czytaj poprzednie #57, #60, #61, #62, #65 i odpowiednie SEC-nn; sprawdź aktualne SHA. Wszystkie SEC-nn bazują na #65 i nie wymagają edycji gałęzi pozostałych zadań. Jeśli potrzebna zmiana w pliku współdzielonym, udokumentuj integracyjne uzgodnienie i konflikt.
Zakres danych: wyłącznie syntetyczne pilot01/pilot02, EU eu-central-1, produkcja OFF, no-submit/no-sign. Nie dotykaj prawdziwych spraw, nie wynoś plaintext ani sekretów do CloudWatch/GitHub/proxy. Nie wykonuj AWS write bez autoryzowanych tożsamości i zgody kustosza. Wyniki CI != real hardware evidence. Kryteria: kod + testy odmowy + dokumentacja, niezależny dowód i jawne FAIL/BLOCKED. Bez automatycznej deklaracji 'Verified Zero Knowledge/Zero Operator Access'.
