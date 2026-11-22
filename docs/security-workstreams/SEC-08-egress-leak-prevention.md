# SEC-08 — [SEC-08] Ochrona plaintext: izolowany egress, antyeksfiltracja i bezpieczna przeglądarka

**Status: PLANNED (BRAK IMPLEMENTACJI).** P0; zależności: SEC-01, SEC-04, SEC-07

## Zakres
1. Zmapuj wszystkie drogi exfil: HTTPS, DNS, metadata, EC2 host, proxy, S3 presigned URLs, log drivers, stdout/stderr, telemetry, screenshots, model AI i zewnętrzne formularze.
2. Zaprojektuj i wdroż niezależnie egzekwowany deny-by-default egress; nie można polegać tylko na Playwright/JS allowlist, ochronie SSRF czy blokowaniu POST w DOM.
3. Zewnętrzne portale w przyszłości przez allowlist host/URL/method i zatwierdzanie skutków ubocznych; na razie no-submit jest nieprzekraczalny i ma być testowany na nieufnych stronach.
4. Sprawdź, czy proxy nie potrafi ujawnić odszyfrowanego dokumentu operatorowi; wdroż sanitizację logów oraz twarde ograniczenia danych wychodzących.

## Mierzalne kryteria zakończenia — SEC-08

**TWARDY WARUNEK `DONE`:** komplet **K1–K6 = PASS**, każde poparte linkiem do wyniku testu lub niezależnego dowodu, **0 FAIL, 0 BLOCKED, 0 UNVERIFIED**, istniejący test docelowy z **0 failed i 0 pominiętych scenariuszy krytycznych** oraz zielony CI dla aktualnego HEAD SHA. Wymagany rzeczywisty dowód z AWS lub zewnętrznego audytora jest niezbędny tam, gdzie wskazano go w K1–K6; test mock nie zastępuje live. Przy choć jednej niespełnionej pozycji PR pozostaje OTWARTY/DRAFT. Zamknięcie implementacyjnego PR nie oznacza automatycznego pozwolenia na marketing ZK/ZOA.

- [ ] **K1.** **Inwentaryzacja ujść:** lista obejmuje HTTP GET query, POST body, headers, redirect, DNS, S3 presigned URL, logi/stdout/stderr, screenshot, LLM, AWS API i metadata; każde ujście ma fail-closed mechanizm kontroli niezależny od samego Playwright.
- [ ] **K2.** **Minimum 9 negatywnych testów:** po jednym dla GET query, POST, redirect, custom header, DNS tunneling, IPv6, S3 URL, model-output i log leakage; we wszystkich synthetic secret marker nie dociera do kolektora.
- [ ] **K3.** **Ruch z guest:** bez zatwierdzonego egress porty i hosty niezaufane zablokowane w sieci, nie tylko w kodzie; w teście nie występuje wildcard `0.0.0.0/0` ani dostęp publiczny omijający proxy.
- [ ] **K4.** **Legalna nawigacja:** przy poprawnej allowlist przechodzi fikcyjny GET do testowego portalu, a finalny POST/submit/sign nie przechodzi nawet przy HTML/JS prompt injection.
- [ ] **K5.** **Brak logowania:** grepowanie testowych logów, CloudWatch, traces, proxy i błędów na synthetic marker zwraca 0 wyników; nie zapisujemy PII w dowodach.
- [ ] **K6.** **Dowód realny:** z autoryzowanej Nitro task ENI i proxy logów (metadane) weryfikuj rzeczywistą odmowę exfil i brak alternatywnej trasy; bez live testu `BLOCKED` dla claimu braku egress.

**Test offline do napisania:** `python -m pytest -q test_confidential_egress_adversarial.py` — 0 failed i 0 skipped krytycznych.

**Test realny do napisania (wymaga niezależnie autoryzowanego AWS):** `python scripts/verify_confidential_egress_live.py --check` — bez realnego PASS punkt K6 pozostaje BLOCKED.

### Wspólny warunek zamknięcia
- [ ] Link do **zielonego CI dla aktualnego SHA**, dokładna komenda, liczba passed/failed/skipped i zanonimizowany raport w `docs/security-evidence/SEC-08.md` (lub równoważnym artefakcie). Testy opisane niżej należy dopiero wdrożyć; nazwa testu nie wystarcza.
- [ ] Każdy K1–K6 ma `PASS/FAIL/BLOCKED`, datę, wykonawcę, link do dowodu. Brak realnej sesji AWS = `BLOCKED` dla punktów sprzętowych. Zero PII, plaintext, DEK, tokenów i sekretów w dowodach.
- [ ] Pozostaje AUTO preview-only / no-submit / no-sign i produkcja OFF. Ukończony PR lub zielony CI nie oznaczają komercyjnego `Zero Operator Access verified`.

## Polecenie dla nowej konwersacji
**Ten draft PR zawiera wyłącznie plan.** Pracuj na gałęzi aktualnego PR, rozwijaj ten PR (nie twórz nowego). Najpierw przeczytaj bazowe #57, #60, #61, #62, #65 oraz aktywne PR-y SEC-01..SEC-12. Nie modyfikuj gałęzi innych zadań. Osobne PR-y mają wspólny bazowy commit #65, ale są niezależne i nie mogą być scalane bez przeglądu konfliktów.
**Ograniczenia:** tylko fikcyjne pilot01/pilot02; eu-central-1; produkcja OFF; żadnych podpisów, wysyłek, składania wniosków ani dostępu do prawdziwych dokumentów. AWS only w autoryzowanej sesji, niezależna zgoda kustosza obowiązkowa. Bez plaintext/PII w logs, debug, CI, proxy. Testy offline ≠ real hardware proof. Skuteczność sprawdź regresją + fail-closed negatywnymi testami; nie polegaj tylko na „documentation review”.
**Dostarcz:** kod/IaC + testy + zanonimizowane dowody + checklistę niezależnego audytu + status PASS/BLOCKED/UNVERIFIED; nie obiecuj produkcji ani Zero Knowledge/ZERO Operator Access bez dowodu.
