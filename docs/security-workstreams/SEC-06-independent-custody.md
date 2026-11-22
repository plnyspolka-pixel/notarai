# SEC-06 — [SEC-06] Niezależny kustosz kluczy KMS: konto, onboarding, rotacja, odebranie uprawnień

**Status: PLANNED (BRAK IMPLEMENTACJI).** P0; zależności: SEC-01, SEC-02, #61, #62

## Zakres
1. Zdefiniuj i zweryfikuj niezależność AWS account kustosza: Organization management, root, SSO, IAM, billing delegation, key admin oraz CloudFormation execution roles nie mogą być kontrolowane przez NotarAI.
2. Zautomatyzuj proces dołączania fikcyjnej kancelarii z odrębnym KMS RSA/permissions, mechanizm revocation i rotation bez cichego przejścia na operator key; oraz awaryjną odmowę release.
3. Zaimplementuj minimalne polityki custody, brak wildcard grants, izolacja principals, samodzielny niezależny change-control i read-only weryfikację zmian.
4. Zaprojektuj klientowi możliwość wyboru prawdziwie niezależnego kustosza (jego konto lub niezależny podmiot) oraz formalną akceptację nowej wersji obrazu/PCR.

## Kryteria odbioru
- [ ] Dowód braku jednostronnego operator access do custodian IAM, key policy, grants i signing key (nie tylko 2 różne numery kont).
- [ ] Negatywne testy: attacker-controlled operator AWS / root / CI / organizations nie zmienia custody bez niezależnej zgody.
- [ ] Udokumentowane bezpieczne key revocation, release freeze, rotation, recovery; real AWS proof BLOCKED jeśli nie ma niezależnego konta.

## Polecenie dla nowej konwersacji
**Ten draft PR zawiera wyłącznie plan.** Pracuj na gałęzi aktualnego PR, rozwijaj ten PR (nie twórz nowego). Najpierw przeczytaj bazowe #57, #60, #61, #62, #65 oraz aktywne PR-y SEC-01..SEC-12. Nie modyfikuj gałęzi innych zadań. Osobne PR-y mają wspólny bazowy commit #65, ale są niezależne i nie mogą być scalane bez przeglądu konfliktów.
**Ograniczenia:** tylko fikcyjne pilot01/pilot02; eu-central-1; produkcja OFF; żadnych podpisów, wysyłek, składania wniosków ani dostępu do prawdziwych dokumentów. AWS only w autoryzowanej sesji, niezależna zgoda kustosza obowiązkowa. Bez plaintext/PII w logs, debug, CI, proxy. Testy offline ≠ real hardware proof. Skuteczność sprawdź regresją + fail-closed negatywnymi testami; nie polegaj tylko na „documentation review”.
**Dostarcz:** kod/IaC + testy + zanonimizowane dowody + checklistę niezależnego audytu + status PASS/BLOCKED/UNVERIFIED; nie obiecuj produkcji ani Zero Knowledge/ZERO Operator Access bez dowodu.
