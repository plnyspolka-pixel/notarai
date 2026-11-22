# SEC-01 — [SEC-01] Threat model oraz kryteria twierdzeń Zero Trust / Zero Operator / Zero Knowledge

**Status: PLANNED, not implemented.** Priorytet: P0
**Zależności:** Początek: #57, #60, #61, #62, #65

## Zakres
1. Przygotuj realistyczny model zagrożeń: operator AWS z AdministratorAccess, GitHub administrator, host/guest, KMS custodian, AWS Organizations, klient, API, DNS/proxy, modele AI i logi.
2. Rozdziel precyzyjnie: Zero Trust (NIST 800-207), Zero Operator Access, Confidential Computing oraz *ograniczone produktowe* Zero Knowledge. Wskaż, czego nie można zagwarantować na obecnym stosie.
3. Stwórz maszynowo czytelną macierz claim → wymagany dowód → właściciel dowodu → test odmowy → expiry → status UNVERIFIED / PASS / FAIL / BLOCKED. Domyślnie wszystko UNVERIFIED.
4. Oceń transakcyjne i prawne operacje: bez autoryzowanego podpisania/wysłania formularza. Ustal nieprzekraczalne granice zakresu produktu.

## Kryteria odbioru
- [ ] Threat model i testowalna macierz wszystkich twierdzeń, bez fikcyjnych certyfikatów.
- [ ] Negatywne scenariusze admin IAM, key-policy mutation, malicious release, cross-tenant i exfiltration.
- [ ] Test schematu claims zapewnia: brak marketingowego PASS z samym CI albo statycznym raportem.

## Zasady pracy w nowej konwersacji
To jest **PR planistyczny**. Na tym etapie nie ma implementacji ani działającego dowodu. Nowa konwersacja ma zrealizować zadanie na **tej konkretnej gałęzi PR**, nie zakładać kolejnego zbędnego PR. Najpierw przeczytaj kod i aktualny stan #57, #60, #61, #62, #65 oraz sprawdź ich SHA. Nie edytuj cudzych gałęzi i nie scalać bez integracyjnego przeglądu.

Reguły: test wyłącznie pilot01/pilot02 i fikcyjne dane; AWS eu-central-1; produkcja wyłączona; AUTO preview nie wysyła, nie podpisuje i nie składa wniosków. Nie podnoś operatorowi uprawnień custody, nie loguj PII/plaintext/sekretów i nie wprowadzaj sieciowego 0.0.0.0/0 dla guest. Każdą własność security potwierdź testami pozytywnymi i **negatywnymi**; brak konta/narzędzi oznacz BLOCKED, a nie PASS. Sama dokumentacja lub CI nie stanowi dowodu sprzętowego. Zapisz kod + testy + wyniki + wymaganą niezależną atestację w PR.

**Definition of done:** zmiana możliwa do niezależnego review, testy CI zielone, brak funkcji submit, wszystkie pozostałe ograniczenia podane jawnie, bez twierdzenia 'Zero Operator Access / Zero Knowledge verified' przed dowodami.
