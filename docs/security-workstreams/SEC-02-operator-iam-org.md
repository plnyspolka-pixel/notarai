# SEC-02 — [SEC-02] Kontrola uprawnień operatora AWS, SCP i trybu awaryjnego

**Status: PLANNED, not implemented.** Priorytet: P0
**Zależności:** SEC-01 i #61–#65

## Zakres
1. Zmapuj całą eskalację uprawnień: workload IAM, ECS RunTask/PassRole, ECR image, CloudFormation stack roles, GitHub OIDC, root/SSO i AWS Organizations.
2. Wprowadź w IaC IAM least privilege i weryfikator odmowy: operator nie może przejąć custody account ani zmienić klucza, root lub SCP. SCP wyłącznie dla organizacji kontrolowanych przez uprawniony podmiot i po weryfikacji realnych uprawnień.
3. Przygotuj niezależny break-glass i procedurę odzyskiwania dostępu z dwoma zatwierdzeniami; zeruj jakąkolwiek możliwość serwisowego odczytu plaintext.
4. Przeprowadź testy negatywne symulujące przejęte konto operatora oraz rzeczywiste read-only AWS evidence, o ile dostęp jest autoryzowany.

## Mierzalne kryteria zakończenia — SEC-02

- [ ] **K1.** **Pełny rejestr uprawnień:** tabela `principal→action→resource→account` obejmuje ECS, `iam:PassRole`, ECR, KMS, CloudFormation, GitHub OIDC, AWS root, SSO i Organizations; brak nieopisanej roli z możliwością eskalacji.
- [ ] **K2.** **IaC least privilege:** w workload operator nie dostaje `kms:PutKeyPolicy`, `kms:CreateGrant` ani dostępu administratora custody; role runtime nie mają nieuzasadnionego `Action:*`/`Resource:*`.
- [ ] **K3.** **6 prób eskalacji = 6 odmów:** podmiana ECR, nadużycie PassRole, przejęcie CloudFormation execution role, `PutKeyPolicy`, OIDC spoof i `sts:AssumeRole` do custody.
- [ ] **K4.** **Dwie AWS account IDs nie wystarczą:** weryfikator wymaga dowodu niezależności custody Organizations/SSO/root; brak danych = `BLOCKED`.
- [ ] **K5.** **Break-glass:** udokumentowane dwie niezależne zgody, maksymalny czas podwyższonych uprawnień, log audytowy i brak ścieżki dostępu do plaintext.
- [ ] **K6.** **Dowód rzeczywisty:** jeżeli mamy autoryzowany dostęp, zanonimizowany wynik rzeczywistych odmów IAM/STS i SHA polityk. Bez live AWS brak statusu `PASS` dla kontroli infrastruktury.

**Docelowy test, który należy dodać:** `python -m pytest -q test_confidential_operator_iam_controls.py` — 0 failed, 0 skipped krytycznych scenariuszy.

### Wspólny warunek zamknięcia
- [ ] Link do **zielonego CI dla aktualnego SHA**, wynik komendy testowej (passed/failed/skipped), zanonimizowany raport w `docs/security-evidence/SEC-02.md` (lub artefakcie CI), oraz linki do testów każdego K1–K6. Nazwę planowanego testu trzeba dopiero wdrożyć; sam opis nie zalicza kryterium.
- [ ] Dla każdego kryterium jawny status `PASS`, `FAIL` lub `BLOCKED` z dowodem, datą i wykonawcą. Brak realnego dostępu AWS = `BLOCKED`, nie `PASS`. Zero plaintext, danych osobowych, sekretów i DEK w artefaktach.
- [ ] W żadnym kodzie dodanym przez PR nie ma możliwości wysyłania ani podpisywania formularzy w AUTO. Testy CI i wykonany PR NIE oznaczają potwierdzenia komercyjnych twierdzeń Zero Trust / Zero Operator Access / Zero Knowledge.

## Zasady pracy w nowej konwersacji
To jest **PR planistyczny**. Na tym etapie nie ma implementacji ani działającego dowodu. Nowa konwersacja ma zrealizować zadanie na **tej konkretnej gałęzi PR**, nie zakładać kolejnego zbędnego PR. Najpierw przeczytaj kod i aktualny stan #57, #60, #61, #62, #65 oraz sprawdź ich SHA. Nie edytuj cudzych gałęzi i nie scalać bez integracyjnego przeglądu.

Reguły: test wyłącznie pilot01/pilot02 i fikcyjne dane; AWS eu-central-1; produkcja wyłączona; AUTO preview nie wysyła, nie podpisuje i nie składa wniosków. Nie podnoś operatorowi uprawnień custody, nie loguj PII/plaintext/sekretów i nie wprowadzaj sieciowego 0.0.0.0/0 dla guest. Każdą własność security potwierdź testami pozytywnymi i **negatywnymi**; brak konta/narzędzi oznacz BLOCKED, a nie PASS. Sama dokumentacja lub CI nie stanowi dowodu sprzętowego. Zapisz kod + testy + wyniki + wymaganą niezależną atestację w PR.

**Definition of done:** zmiana możliwa do niezależnego review, testy CI zielone, brak funkcji submit, wszystkie pozostałe ograniczenia podane jawnie, bez twierdzenia 'Zero Operator Access / Zero Knowledge verified' przed dowodami.
