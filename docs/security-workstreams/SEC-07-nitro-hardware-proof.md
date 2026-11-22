# SEC-07 — [SEC-07] Dowód sprzętowy Nitro/KMS: pozytywne i negatywne testy atestacji

**Status: PLANNED (BRAK IMPLEMENTACJI).** P0; zależności: SEC-05, SEC-06, #65; konto AWS i niezależny custody

## Zakres
1. Przygotuj uruchamialny E2E w eu-central-1 na dwóch syntetycznych tenantach; wykorzystaj tylko zatwierdzony digest OCI i rzeczywisty ECS Nitro Confidential Sandbox.
2. Pozytywnie sprawdź KMS Recipient Attestation ze sprzętowym NSM, klucz wydany tylko jako CiphertextForRecipient i odszyfrowanie wewnątrz zatwierdzonego guest.
3. Negatywnie zweryfikuj zwykłe EC2/host, zły PCR, zmieniony obraz, odmowę bez podpisu kustosza, zły tenant/klucz/rola i próbę policy tamper; zbierz niezależne CloudTrail read-only dowody z obu kont.
4. Oddziel w artefaktach dowód sprzętowy od statycznego preflight/CI. Zadbaj o fail-closed i rollback bez utraty śladów bezpieczeństwa.

## Mierzalne kryteria zakończenia — SEC-07

**TWARDY WARUNEK `DONE`:** komplet **K1–K6 = PASS**, każde poparte linkiem do wyniku testu lub niezależnego dowodu, **0 FAIL, 0 BLOCKED, 0 UNVERIFIED**, istniejący test docelowy z **0 failed i 0 pominiętych scenariuszy krytycznych** oraz zielony CI dla aktualnego HEAD SHA. Wymagany rzeczywisty dowód z AWS lub zewnętrznego audytora jest niezbędny tam, gdzie wskazano go w K1–K6; test mock nie zastępuje live. Przy choć jednej niespełnionej pozycji PR pozostaje OTWARTY/DRAFT. Zamknięcie implementacyjnego PR nie oznacza automatycznego pozwolenia na marketing ZK/ZOA.

- [ ] **K1.** **Prawdziwy pozytywny test:** na ECS Nitro Confidential Sandbox w eu-central-1 fikcyjny pilot01 odszyfrowuje tylko `CiphertextForRecipient` z KMS przez `/dev/nsm`; raport zawiera task revision, image@sha256, PCR17, KMS key ARN (redacted), czas i exit=0.
- [ ] **K2.** **Minimum 6 odmów na AWS:** zwykłe EC2/host, zły PCR17, inny digest, cudzy tenant/role, niezależnie niezatwierdzony release i błędny key ARN — każda próba kończy się odmową decrypt/DEK. Test bez wykonania oznacz `BLOCKED`.
- [ ] **K3.** **Brak jawnego KMS DEK:** test sprawdza, że rezultat nigdy nie zawiera `Plaintext` i nie loguje kluczy; tylko CMS przeznaczony dla efemerycznego guest.
- [ ] **K4.** **Dwa konta:** audytor pobiera read-only z custody i workload aktualne hash key policy, task definition, podpis release, Grant inventory i zapis CloudTrail KMS; brak wglądu do któregoś konta => `BLOCKED`.
- [ ] **K5.** **Reprodukcja:** zapisz skrypt E2E, komendy, timestamp UTC, identyfikator fikcyjnego job, status każdej próby i kryptograficzny hash raportu; dowód podpisuje niezależny kustosz/audytor.
- [ ] **K6.** **Brama twarda:** żaden scenariusz mock/CI nie daje `hardware_attestation_verified=true`; ten atrybut tylko po realnym teście 1+6 odmów z dwiema niezależnymi tożsamościami.

**Test offline do napisania:** `python -m pytest -q test_confidential_nitro_hardware_plan.py` — 0 failed i 0 skipped krytycznych.

**Test realny do napisania (wymaga niezależnie autoryzowanego AWS):** `python scripts/run_nitro_attestation_e2e.py --check` — bez realnego PASS punkt K6 pozostaje BLOCKED.

### Wspólny warunek zamknięcia
- [ ] Link do **zielonego CI dla aktualnego SHA**, dokładna komenda, liczba passed/failed/skipped i zanonimizowany raport w `docs/security-evidence/SEC-07.md` (lub równoważnym artefakcie). Testy opisane niżej należy dopiero wdrożyć; nazwa testu nie wystarcza.
- [ ] Każdy K1–K6 ma `PASS/FAIL/BLOCKED`, datę, wykonawcę, link do dowodu. Brak realnej sesji AWS = `BLOCKED` dla punktów sprzętowych. Zero PII, plaintext, DEK, tokenów i sekretów w dowodach.
- [ ] Pozostaje AUTO preview-only / no-submit / no-sign i produkcja OFF. Ukończony PR lub zielony CI nie oznaczają komercyjnego `Zero Operator Access verified`.

## Polecenie dla nowej konwersacji
**Ten draft PR zawiera wyłącznie plan.** Pracuj na gałęzi aktualnego PR, rozwijaj ten PR (nie twórz nowego). Najpierw przeczytaj bazowe #57, #60, #61, #62, #65 oraz aktywne PR-y SEC-01..SEC-12. Nie modyfikuj gałęzi innych zadań. Osobne PR-y mają wspólny bazowy commit #65, ale są niezależne i nie mogą być scalane bez przeglądu konfliktów.
**Ograniczenia:** tylko fikcyjne pilot01/pilot02; eu-central-1; produkcja OFF; żadnych podpisów, wysyłek, składania wniosków ani dostępu do prawdziwych dokumentów. AWS only w autoryzowanej sesji, niezależna zgoda kustosza obowiązkowa. Bez plaintext/PII w logs, debug, CI, proxy. Testy offline ≠ real hardware proof. Skuteczność sprawdź regresją + fail-closed negatywnymi testami; nie polegaj tylko na „documentation review”.
**Dostarcz:** kod/IaC + testy + zanonimizowane dowody + checklistę niezależnego audytu + status PASS/BLOCKED/UNVERIFIED; nie obiecuj produkcji ani Zero Knowledge/ZERO Operator Access bez dowodu.
