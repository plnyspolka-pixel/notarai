# SEC-06 — [SEC-06] Niezależny kustosz kluczy KMS: konto, onboarding, rotacja, odebranie uprawnień

**Status: IMPLEMENTACJA CZĘŚCIOWA / DRAFT — NIE ZAMYKAĆ.** P0; zależności: SEC-01, SEC-02, #61, #62. Wdrożenie i audyt AWS NIEPOTWIERDZONE.

## Zakres
1. Zdefiniuj i zweryfikuj niezależność AWS account kustosza: Organization management, root, SSO, IAM, billing delegation, key admin oraz CloudFormation execution roles nie mogą być kontrolowane przez NotarAI.
2. Zautomatyzuj proces dołączania fikcyjnej kancelarii z odrębnym KMS RSA/permissions, mechanizm revocation i rotation bez cichego przejścia na operator key; oraz awaryjną odmowę release.
3. Zaimplementuj minimalne polityki custody, brak wildcard grants, izolacja principals, samodzielny niezależny change-control i read-only weryfikację zmian.
4. Zaprojektuj klientowi możliwość wyboru prawdziwie niezależnego kustosza (jego konto lub niezależny podmiot) oraz formalną akceptację nowej wersji obrazu/PCR.

## Mierzalne kryteria zakończenia — SEC-06

**TWARDY WARUNEK `DONE`:** komplet **K1–K6 = PASS**, każde poparte linkiem do wyniku testu lub niezależnego dowodu, **0 FAIL, 0 BLOCKED, 0 UNVERIFIED**, istniejący test docelowy z **0 failed i 0 pominiętych scenariuszy krytycznych** oraz zielony CI dla aktualnego HEAD SHA. Wymagany rzeczywisty dowód z AWS lub zewnętrznego audytora jest niezbędny tam, gdzie wskazano go w K1–K6; test mock nie zastępuje live. Przy choć jednej niespełnionej pozycji PR pozostaje OTWARTY/DRAFT. Zamknięcie implementacyjnego PR nie oznacza automatycznego pozwolenia na marketing ZK/ZOA.

- [ ] **K1.** **Oddzielna administracja:** dowód od niezależnej osoby/podmiotu wykazuje, że workload root, NotarAI IAM/SSO, GitHub OIDC i Organizations management nie administrują custody account ani signing/decrypt KMS key.
- [ ] **K2.** **Przegląd polityk:** automatyczny walidator odrzuca `kms:PutKeyPolicy`, `kms:CreateGrant`, `kms:Decrypt`, wildcard grant lub assume-role dostępne operatorowi. 5 negatywnych przypadków i 0 niezatwierdzonych grantów.
- [ ] **K3.** **Onboarding 2 tenantów:** pilot01 i pilot02 mają dwa osobne KMS keys / policy / PCR binding / release approval i nie mogą przejąć kluczy drugiego tenanta; pozytywny fixture i cross-tenant deny.
- [ ] **K4.** **Revocation:** cofnięcie zgody kustosza lub policy freeze blokuje nowy decrypt; dodatkowy test wykazuje brak fallbacku do starej lub operatorskiej polityki.
- [ ] **K5.** **Rotacja i utrata klucza:** procedura i co najmniej 3 testy odnowienia, utraty dostępu oraz nieuprawnionego odzyskania; nie istnieje admin backdoor odzyskujący plaintext.
- [ ] **K6.** **Niezależna kontrola live:** read-only weryfikacja dwóch AWS accounts wraz z potwierdzeniem własności Org/SSO i podpisem kustosza. Bez autentycznie niezależnego konta ten punkt jest `BLOCKED`, bez zamykania jako zweryfikowane.

**Docelowy test uruchamiany w dedykowanym CI:** `python -m pytest -q --noconftest test_confidential_independent_custody_ops.py test_confidential_custody_kms_readonly.py test_confidential_operator_boundary.py` — wymagane 0 failed, 0 skipped scenariuszy krytycznych. Dodatkowo konieczne są testy z rzeczywistym KMS/Nitro i niezależny audyt, których CI nie wykonuje.

### Wspólny warunek zamknięcia
- [ ] Link do **zielonego CI dla aktualnego SHA**, wynik komendy testowej (passed/failed/skipped), zanonimizowany raport w `docs/security-evidence/SEC-06.md` (lub artefakcie CI), oraz linki do testów każdego K1–K6. Nazwę planowanego testu trzeba dopiero wdrożyć; sam opis nie zalicza kryterium.
- [ ] Dla każdego kryterium jawny status `PASS`, `FAIL` lub `BLOCKED` z dowodem, datą i wykonawcą. Brak realnego dostępu AWS = `BLOCKED`, nie `PASS`. Zero plaintext, danych osobowych, sekretów i DEK w artefaktach.
- [ ] W żadnym kodzie dodanym przez PR nie ma możliwości wysyłania ani podpisywania formularzy w AUTO. Testy CI i wykonany PR NIE oznaczają potwierdzenia komercyjnych twierdzeń Zero Trust / Zero Operator Access / Zero Knowledge.

## Polecenie dla nowej konwersacji
**Ten draft PR ma częściową implementację i testy synthetic.** Pracuj na gałęzi aktualnego PR, rozwijaj ten PR (nie twórz nowego). Najpierw przeczytaj bazowe #57, #60, #61, #62, #65 oraz aktywne PR-y SEC-01..SEC-12. Nie modyfikuj gałęzi innych zadań. Osobne PR-y mają wspólny bazowy commit #65, ale są niezależne i nie mogą być scalane bez przeglądu konfliktów.
**Ograniczenia:** tylko fikcyjne pilot01/pilot02; eu-central-1; produkcja OFF; żadnych podpisów, wysyłek, składania wniosków ani dostępu do prawdziwych dokumentów. AWS only w autoryzowanej sesji, niezależna zgoda kustosza obowiązkowa. Bez plaintext/PII w logs, debug, CI, proxy. Testy offline ≠ real hardware proof. Skuteczność sprawdź regresją + fail-closed negatywnymi testami; nie polegaj tylko na „documentation review”.
**Dostarcz:** kod/IaC + testy + zanonimizowane dowody + checklistę niezależnego audytu + status PASS/BLOCKED/UNVERIFIED; nie obiecuj produkcji ani Zero Knowledge/ZERO Operator Access bez dowodu.

## PR #71 — dostarczony kod i dowody (2026-11-22)

- `confidential/custody_ops.py`: signed ENROLL/FREEZE/REVOKE/ROTATE/UNFREEZE/MARK_LOST, fingerprint z zewnętrznego kanału, monotonically versioned state, deny dla starego KMS/tenanta, generator polityki deny-only i walidator snapshotu KMS.
- `scripts/verify_confidential_custody_independence.py`: domyślny dry-run (0 AWS calls), opcjonalny tylko-odczytowy audyt Organizations i IAM role trusts z oddzielnych profili; nie utożsamia dwóch kont z niezależnością.
- `test_confidential_independent_custody_ops.py`: fikcyjni pilot01/pilot02, co najmniej 5 mutacji KMS, 12 mutacji organizacyjnych, podpisy/replay, freeze/revocation/fallback, rotacja i utrata klucza.
- `docs/security-evidence/SEC-06.md`: K1–K6 ze statusem BLOCKED/UNVERIFIED, jawne warunki audytu i testów live. Testy CI nie zastępują odmów KMS.

**BLOKERY:** realnie niezależny custody AWS/Organizations/SSO i podpisany audyt; realna polityka KMS/CloudTrail i sprawdzenie jej skuteczności przez atak; dostarczone publiczne dowody CI dla finalnego HEAD. Implementacja nie jest wpięta w produkcyjny scheduler ani wypuszczona do użytkowników. Produkcja OFF, wyłącznie synthetic, AUTO bez podpisania/wysłania.

- `scripts/custodian_sign_confidential_operation.py`: odrębny signer działa wyłącznie przez niezależny profil AWS i pinned public-key fingerprint, domyślnie 0 wywołań AWS; zatwierdzenie wymaga `--approve-action`, a kod nigdy nie wykonuje `Decrypt` ani `PutKeyPolicy`.

### Kontynuacja PR #71: KMS read-only oraz obsługa starego klucza przy rotacji

- `scripts/verify_confidential_custody_kms.py`: odczyt metadanych KMS, kompletnego wykazu polityk i grantów (w tym paginacja). Każda brakująca strona, obcy klucz lub niezatwierdzony grant => BLOCKED; wynik pozytywnego statycznego audytu **nadal BLOCKED** do czasu prób KMS/Nitro i podpisu kustosza.
- `test_confidential_custody_kms_readonly.py`: regresja dla niepełnej paginacji, drugiej strony grantów, podwójnych kluczy JSON, dodatkowej polityki i błędnej tożsamości AWS.
- `infra/notarai-confidential-external-custody-kms.yaml` i `confidential/operator_boundary.py`: tylko kustosz zyskuje uprawnienia read-only `kms:ListGrants` i `kms:ListKeyPolicies`. Brak nowego dostępu operatora NotarAI.
- `scripts/plan_confidential_custody_operation.py`: ROTATE emituje dwa cele polityki KMS, osobno dla starego i nowego klucza, oba deny-only. Nadal wymagany jest niezależny kompletny rejestr historycznych kluczy, weryfikacja grantów i prawdziwy test odmowy deszyfrowania.
- Nowe testy są synthetic: żaden klucz AWS nie został zmieniony, usunięty, odszyfrowany ani zatwierdzony. Live K2/K4/K5/K6 pozostają niezakończone.
