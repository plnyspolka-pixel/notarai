# SEC-03 — [SEC-03] Zero Knowledge: szyfrowanie klienta, niezależne klucze i bezpieczne odzyskiwanie

**Status: PLANNED, not implemented.** Priorytet: P0
**Zależności:** SEC-01, #61, #62, #65

## Zakres
1. Zaudytuj przepływ danych klienta przed browser upload: gdzie powstaje DEK, jakie JS/script/CDN może podmienić operator, jak zabezpieczony jest key wrapping i AAD tenant/case/object/version.
2. Zaprojektuj i wdroż brak plaintext na serwerze aplikacyjnym NotarAI: client-side AEAD, ciasna izolacja tenantów, KMS external custody, walidacja integralności i mechanizm key binding.
3. Wprost rozstrzygnij ryzyko operatora kontrolującego kod frontendu: niezależnie zatwierdzany klient, weryfikowalny hash/release lub inny wiarygodny model dystrybucji. Bez tego NIE można reklamować pełnego Zero Knowledge.
4. Rozstrzygnij utratę i odzyskanie klucza, revocation/rotation, zmianę właściciela kancelarii i zgodne z tajemnicą notarialną usunięcie danych; testy odszyfrowania wyłącznie przez autoryzowany Nitro.

## Kryteria odbioru
- [ ] Żaden nieszyfrowany dokument ani DEK nie przechodzi przez aplikacyjny backend/telemetrię operatora.
- [ ] Testy tamper, cross-tenant, wrong AAD, key rotation/revocation oraz regresja crypto.
- [ ] Opis nieusuwalnych wyjątków od ścisłego ZK, jeśli Nitro przetwarza plaintext w ramach zadania.

## Zasady pracy w nowej konwersacji
To jest **PR planistyczny**. Na tym etapie nie ma implementacji ani działającego dowodu. Nowa konwersacja ma zrealizować zadanie na **tej konkretnej gałęzi PR**, nie zakładać kolejnego zbędnego PR. Najpierw przeczytaj kod i aktualny stan #57, #60, #61, #62, #65 oraz sprawdź ich SHA. Nie edytuj cudzych gałęzi i nie scalać bez integracyjnego przeglądu.

Reguły: test wyłącznie pilot01/pilot02 i fikcyjne dane; AWS eu-central-1; produkcja wyłączona; AUTO preview nie wysyła, nie podpisuje i nie składa wniosków. Nie podnoś operatorowi uprawnień custody, nie loguj PII/plaintext/sekretów i nie wprowadzaj sieciowego 0.0.0.0/0 dla guest. Każdą własność security potwierdź testami pozytywnymi i **negatywnymi**; brak konta/narzędzi oznacz BLOCKED, a nie PASS. Sama dokumentacja lub CI nie stanowi dowodu sprzętowego. Zapisz kod + testy + wyniki + wymaganą niezależną atestację w PR.

**Definition of done:** zmiana możliwa do niezależnego review, testy CI zielone, brak funkcji submit, wszystkie pozostałe ograniczenia podane jawnie, bez twierdzenia 'Zero Operator Access / Zero Knowledge verified' przed dowodami.
