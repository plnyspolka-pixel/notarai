# SEC-01 — [SEC-01] Threat model oraz kryteria twierdzeń Zero Trust / Zero Operator / Zero Knowledge

**Status: PLANNED, not implemented.** Priorytet: P0
**Zależności:** Początek: #57, #60, #61, #62, #65

## Zakres
1. Przygotuj realistyczny model zagrożeń: operator AWS z AdministratorAccess, GitHub administrator, host/guest, KMS custodian, AWS Organizations, klient, API, DNS/proxy, modele AI i logi.
2. Rozdziel precyzyjnie: Zero Trust (NIST 800-207), Zero Operator Access, Confidential Computing oraz *ograniczone produktowe* Zero Knowledge. Wskaż, czego nie można zagwarantować na obecnym stosie.
3. Stwórz maszynowo czytelną macierz claim → wymagany dowód → właściciel dowodu → test odmowy → expiry → status UNVERIFIED / PASS / FAIL / BLOCKED. Domyślnie wszystko UNVERIFIED.
4. Oceń transakcyjne i prawne operacje: bez autoryzowanego podpisania/wysłania formularza. Ustal nieprzekraczalne granice zakresu produktu.

## Mierzalne kryteria zakończenia — SEC-01

- [ ] **K1.** **4 twierdzenia:** maszynowa macierz JSON/YAML zawiera `zero_trust`, `zero_operator_access`, `confidential_computing`, `scoped_zero_knowledge`; każdy wpis ma `scope`, `trust_boundary`, `required_evidence`, `evidence_owner`, `negative_test`, `expires_at`, `status`. Brak pola → walidator odmawia.
- [ ] **K2.** **Brak automatycznego PASS:** dla 4 twierdzeń bez dowodów status 4/4 = `UNVERIFIED`; samo zielone CI, opis PR lub test mock nigdy nie zmieniają statusu na `PASS`.
- [ ] **K3.** **Minimum 10 ataków:** macierz obejmuje IAM/root, GitHub release, `kms:PutKeyPolicy`, custody Organizations/SSO, PCR/digest, cross-tenant, DNS/proxy, logi, AI i frontend; każdy ma test odmowy i właściciela.
- [ ] **K4.** **Minimum 5 negatywnych testów:** brak, przeterminowanie, błędny podpis, inny tenant i zły digest/obraz → `FAIL/BLOCKED`, nigdy `PASS`.
- [ ] **K5.** **Definicja ZK:** dokument wyraźnie rozróżnia ścisłe Zero Knowledge od ograniczonego confidential processing; plaintext w Bedrock/innym modelu poza Nitro jawnie wyklucza bezwarunkową deklarację ZK.
- [ ] **K6.** **Czynności prawne:** model zagrożeń i test walidatora potwierdzają, że AUTO nie może podpisywać, wysyłać ani finalnie składać formularzy.

**Docelowy test, który należy dodać:** `python -m pytest -q test_confidential_security_claims.py` — 0 failed, 0 skipped krytycznych scenariuszy.

### Wspólny warunek zamknięcia
- [ ] Link do **zielonego CI dla aktualnego SHA**, wynik komendy testowej (passed/failed/skipped), zanonimizowany raport w `docs/security-evidence/SEC-01.md` (lub artefakcie CI), oraz linki do testów każdego K1–K6. Nazwę planowanego testu trzeba dopiero wdrożyć; sam opis nie zalicza kryterium.
- [ ] Dla każdego kryterium jawny status `PASS`, `FAIL` lub `BLOCKED` z dowodem, datą i wykonawcą. Brak realnego dostępu AWS = `BLOCKED`, nie `PASS`. Zero plaintext, danych osobowych, sekretów i DEK w artefaktach.
- [ ] W żadnym kodzie dodanym przez PR nie ma możliwości wysyłania ani podpisywania formularzy w AUTO. Testy CI i wykonany PR NIE oznaczają potwierdzenia komercyjnych twierdzeń Zero Trust / Zero Operator Access / Zero Knowledge.

## Zasady pracy w nowej konwersacji
To jest **PR planistyczny**. Na tym etapie nie ma implementacji ani działającego dowodu. Nowa konwersacja ma zrealizować zadanie na **tej konkretnej gałęzi PR**, nie zakładać kolejnego zbędnego PR. Najpierw przeczytaj kod i aktualny stan #57, #60, #61, #62, #65 oraz sprawdź ich SHA. Nie edytuj cudzych gałęzi i nie scalać bez integracyjnego przeglądu.

Reguły: test wyłącznie pilot01/pilot02 i fikcyjne dane; AWS eu-central-1; produkcja wyłączona; AUTO preview nie wysyła, nie podpisuje i nie składa wniosków. Nie podnoś operatorowi uprawnień custody, nie loguj PII/plaintext/sekretów i nie wprowadzaj sieciowego 0.0.0.0/0 dla guest. Każdą własność security potwierdź testami pozytywnymi i **negatywnymi**; brak konta/narzędzi oznacz BLOCKED, a nie PASS. Sama dokumentacja lub CI nie stanowi dowodu sprzętowego. Zapisz kod + testy + wyniki + wymaganą niezależną atestację w PR.

**Definition of done:** zmiana możliwa do niezależnego review, testy CI zielone, brak funkcji submit, wszystkie pozostałe ograniczenia podane jawnie, bez twierdzenia 'Zero Operator Access / Zero Knowledge verified' przed dowodami.
