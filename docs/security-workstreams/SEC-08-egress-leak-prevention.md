# SEC-08 — [SEC-08] Ochrona plaintext: izolowany egress, antyeksfiltracja i bezpieczna przeglądarka

**Status: PLANNED (BRAK IMPLEMENTACJI).** P0; zależności: SEC-01, SEC-04, SEC-07

## Zakres
1. Zmapuj wszystkie drogi exfil: HTTPS, DNS, metadata, EC2 host, proxy, S3 presigned URLs, log drivers, stdout/stderr, telemetry, screenshots, model AI i zewnętrzne formularze.
2. Zaprojektuj i wdroż niezależnie egzekwowany deny-by-default egress; nie można polegać tylko na Playwright/JS allowlist, ochronie SSRF czy blokowaniu POST w DOM.
3. Zewnętrzne portale w przyszłości przez allowlist host/URL/method i zatwierdzanie skutków ubocznych; na razie no-submit jest nieprzekraczalny i ma być testowany na nieufnych stronach.
4. Sprawdź, czy proxy nie potrafi ujawnić odszyfrowanego dokumentu operatorowi; wdroż sanitizację logów oraz twarde ograniczenia danych wychodzących.

## Kryteria odbioru
- [ ] Scenariusze eksfiltracji (DNS, URL, GET query, POST, headers, body, S3, model output, logs) blokowane albo jawnie wyłączone z claim ZOA/ZK.
- [ ] Rzeczywisty egress test z pełnym Nitro fail-closed, nie tylko offline mock.
- [ ] Nie wyłączono ochrony przez przypadkowe uruchomienie NAT/public IP albo wildcard Security Group.

## Polecenie dla nowej konwersacji
**Ten draft PR zawiera wyłącznie plan.** Pracuj na gałęzi aktualnego PR, rozwijaj ten PR (nie twórz nowego). Najpierw przeczytaj bazowe #57, #60, #61, #62, #65 oraz aktywne PR-y SEC-01..SEC-12. Nie modyfikuj gałęzi innych zadań. Osobne PR-y mają wspólny bazowy commit #65, ale są niezależne i nie mogą być scalane bez przeglądu konfliktów.
**Ograniczenia:** tylko fikcyjne pilot01/pilot02; eu-central-1; produkcja OFF; żadnych podpisów, wysyłek, składania wniosków ani dostępu do prawdziwych dokumentów. AWS only w autoryzowanej sesji, niezależna zgoda kustosza obowiązkowa. Bez plaintext/PII w logs, debug, CI, proxy. Testy offline ≠ real hardware proof. Skuteczność sprawdź regresją + fail-closed negatywnymi testami; nie polegaj tylko na „documentation review”.
**Dostarcz:** kod/IaC + testy + zanonimizowane dowody + checklistę niezależnego audytu + status PASS/BLOCKED/UNVERIFIED; nie obiecuj produkcji ani Zero Knowledge/ZERO Operator Access bez dowodu.
