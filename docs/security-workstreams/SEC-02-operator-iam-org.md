# SEC-02 — [SEC-02] Kontrola uprawnień operatora AWS, SCP i trybu awaryjnego

**Status: PLANNED, not implemented.** Priorytet: P0
**Zależności:** SEC-01 i #61–#65

## Zakres
1. Zmapuj całą eskalację uprawnień: workload IAM, ECS RunTask/PassRole, ECR image, CloudFormation stack roles, GitHub OIDC, root/SSO i AWS Organizations.
2. Wprowadź w IaC IAM least privilege i weryfikator odmowy: operator nie może przejąć custody account ani zmienić klucza, root lub SCP. SCP wyłącznie dla organizacji kontrolowanych przez uprawniony podmiot i po weryfikacji realnych uprawnień.
3. Przygotuj niezależny break-glass i procedurę odzyskiwania dostępu z dwoma zatwierdzeniami; zeruj jakąkolwiek możliwość serwisowego odczytu plaintext.
4. Przeprowadź testy negatywne symulujące przejęte konto operatora oraz rzeczywiste read-only AWS evidence, o ile dostęp jest autoryzowany.

## Kryteria odbioru
- [ ] Zasady IAM/SCP w przeglądalnym IaC i uruchamialne testy deny.
- [ ] Dokument uprawnień szczególnych/wyjątków i ścieżki AWS Organizations/SSO.
- [ ] Raport o brakach realnego cross-account ownership; nie myl dwóch numerów kont z niezależnością.

## Zasady pracy w nowej konwersacji
To jest **PR planistyczny**. Na tym etapie nie ma implementacji ani działającego dowodu. Nowa konwersacja ma zrealizować zadanie na **tej konkretnej gałęzi PR**, nie zakładać kolejnego zbędnego PR. Najpierw przeczytaj kod i aktualny stan #57, #60, #61, #62, #65 oraz sprawdź ich SHA. Nie edytuj cudzych gałęzi i nie scalać bez integracyjnego przeglądu.

Reguły: test wyłącznie pilot01/pilot02 i fikcyjne dane; AWS eu-central-1; produkcja wyłączona; AUTO preview nie wysyła, nie podpisuje i nie składa wniosków. Nie podnoś operatorowi uprawnień custody, nie loguj PII/plaintext/sekretów i nie wprowadzaj sieciowego 0.0.0.0/0 dla guest. Każdą własność security potwierdź testami pozytywnymi i **negatywnymi**; brak konta/narzędzi oznacz BLOCKED, a nie PASS. Sama dokumentacja lub CI nie stanowi dowodu sprzętowego. Zapisz kod + testy + wyniki + wymaganą niezależną atestację w PR.

**Definition of done:** zmiana możliwa do niezależnego review, testy CI zielone, brak funkcji submit, wszystkie pozostałe ograniczenia podane jawnie, bez twierdzenia 'Zero Operator Access / Zero Knowledge verified' przed dowodami.
