# SEC-03 — [SEC-03] Zero Knowledge: szyfrowanie klienta, niezależne klucze i bezpieczne odzyskiwanie

**Status: PLANNED, not implemented.** Priorytet: P0
**Zależności:** SEC-01, #61, #62, #65

## Zakres
1. Zaudytuj przepływ danych klienta przed browser upload: gdzie powstaje DEK, jakie JS/script/CDN może podmienić operator, jak zabezpieczony jest key wrapping i AAD tenant/case/object/version.
2. Zaprojektuj i wdroż brak plaintext na serwerze aplikacyjnym NotarAI: client-side AEAD, ciasna izolacja tenantów, KMS external custody, walidacja integralności i mechanizm key binding.
3. Wprost rozstrzygnij ryzyko operatora kontrolującego kod frontendu: niezależnie zatwierdzany klient, weryfikowalny hash/release lub inny wiarygodny model dystrybucji. Bez tego NIE można reklamować pełnego Zero Knowledge.
4. Rozstrzygnij utratę i odzyskanie klucza, revocation/rotation, zmianę właściciela kancelarii i zgodne z tajemnicą notarialną usunięcie danych; testy odszyfrowania wyłącznie przez autoryzowany Nitro.

## Mierzalne kryteria zakończenia — SEC-03

- [ ] **K1.** **0 plaintext w backendzie:** test dwóch fikcyjnych dokumentów przechwytuje upload HTTP, logs i persistence; 0 wystąpień plaintext oraz DEK; backend otrzymuje ciphertext.
- [ ] **K2.** **5 odmów AEAD/AAD:** fałszywy tenant, object ID, VersionId, zły tag oraz replay zawsze odrzucane; AAD obejmuje tenant+object+version i szyfrowanie używa unikalnego nonce.
- [ ] **K3.** **Zarządzanie kluczami:** jawny przepływ utworzenia DEK, wrap, unwrap, rotation i revoke; serwer operatora nigdy nie otrzymuje niezaszyfrowanego DEK.
- [ ] **K4.** **Podmiana JS:** test nieautoryzowanego JS/SDK/release wykrywa manipulację przez niezależnie zaufanego klienta albo ustawia `BLOCKED`. Nie uznajemy własnego hostowanego JS za niezależny trust root.
- [ ] **K5.** **Recovery:** 3 testy: utrata klucza, nieuprawniona kancelaria i autoryzowany recovery. Brak ukrytego support/admin decrypt path.
- [ ] **K6.** **Odmowa operatora:** normalny backend nie może odszyfrować fikcyjnego dokumentu; prawdziwy dowód hardware Nitro pozostaje `BLOCKED` do SEC-07.

**Docelowy test, który należy dodać:** `python -m pytest -q test_confidential_zk_client_encryption.py` — 0 failed, 0 skipped krytycznych scenariuszy.

### Wspólny warunek zamknięcia
- [ ] Link do **zielonego CI dla aktualnego SHA**, wynik komendy testowej (passed/failed/skipped), zanonimizowany raport w `docs/security-evidence/SEC-03.md` (lub artefakcie CI), oraz linki do testów każdego K1–K6. Nazwę planowanego testu trzeba dopiero wdrożyć; sam opis nie zalicza kryterium.
- [ ] Dla każdego kryterium jawny status `PASS`, `FAIL` lub `BLOCKED` z dowodem, datą i wykonawcą. Brak realnego dostępu AWS = `BLOCKED`, nie `PASS`. Zero plaintext, danych osobowych, sekretów i DEK w artefaktach.
- [ ] W żadnym kodzie dodanym przez PR nie ma możliwości wysyłania ani podpisywania formularzy w AUTO. Testy CI i wykonany PR NIE oznaczają potwierdzenia komercyjnych twierdzeń Zero Trust / Zero Operator Access / Zero Knowledge.

## Zasady pracy w nowej konwersacji
To jest **PR planistyczny**. Na tym etapie nie ma implementacji ani działającego dowodu. Nowa konwersacja ma zrealizować zadanie na **tej konkretnej gałęzi PR**, nie zakładać kolejnego zbędnego PR. Najpierw przeczytaj kod i aktualny stan #57, #60, #61, #62, #65 oraz sprawdź ich SHA. Nie edytuj cudzych gałęzi i nie scalać bez integracyjnego przeglądu.

Reguły: test wyłącznie pilot01/pilot02 i fikcyjne dane; AWS eu-central-1; produkcja wyłączona; AUTO preview nie wysyła, nie podpisuje i nie składa wniosków. Nie podnoś operatorowi uprawnień custody, nie loguj PII/plaintext/sekretów i nie wprowadzaj sieciowego 0.0.0.0/0 dla guest. Każdą własność security potwierdź testami pozytywnymi i **negatywnymi**; brak konta/narzędzi oznacz BLOCKED, a nie PASS. Sama dokumentacja lub CI nie stanowi dowodu sprzętowego. Zapisz kod + testy + wyniki + wymaganą niezależną atestację w PR.

**Definition of done:** zmiana możliwa do niezależnego review, testy CI zielone, brak funkcji submit, wszystkie pozostałe ograniczenia podane jawnie, bez twierdzenia 'Zero Operator Access / Zero Knowledge verified' przed dowodami.
