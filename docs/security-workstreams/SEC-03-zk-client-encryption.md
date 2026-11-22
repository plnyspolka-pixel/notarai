# SEC-03 — [SEC-03] Zero Knowledge: szyfrowanie klienta, niezależne klucze i bezpieczne odzyskiwanie

**Status: IMPLEMENTATION IN PROGRESS — external proofs BLOCKED.** Priorytet: P0
**Zależności:** SEC-01, #61, #62, #65

## Zakres
1. Zaudytuj przepływ danych klienta przed browser upload: gdzie powstaje DEK, jakie JS/script/CDN może podmienić operator, jak zabezpieczony jest key wrapping i AAD tenant/case/object/version.
2. Zaprojektuj i wdroż brak plaintext na serwerze aplikacyjnym NotarAI: client-side AEAD, ciasna izolacja tenantów, KMS external custody, walidacja integralności i mechanizm key binding.
3. Wprost rozstrzygnij ryzyko operatora kontrolującego kod frontendu: niezależnie zatwierdzany klient, weryfikowalny hash/release lub inny wiarygodny model dystrybucji. Bez tego NIE można reklamować pełnego Zero Knowledge.
4. Rozstrzygnij utratę i odzyskanie klucza, revocation/rotation, zmianę właściciela kancelarii i zgodne z tajemnicą notarialną usunięcie danych; testy odszyfrowania wyłącznie przez autoryzowany Nitro.

## Mierzalne kryteria zakończenia — SEC-03

**TWARDY WARUNEK `DONE`:** komplet **K1–K6 = PASS**, każde poparte linkiem do wyniku testu lub niezależnego dowodu, **0 FAIL, 0 BLOCKED, 0 UNVERIFIED**, istniejący test docelowy z **0 failed i 0 pominiętych scenariuszy krytycznych** oraz zielony CI dla aktualnego HEAD SHA. Wymagany rzeczywisty dowód z AWS lub zewnętrznego audytora jest niezbędny tam, gdzie wskazano go w K1–K6; test mock nie zastępuje live. Przy choć jednej niespełnionej pozycji PR pozostaje OTWARTY/DRAFT. Zamknięcie implementacyjnego PR nie oznacza automatycznego pozwolenia na marketing ZK/ZOA.

- [ ] **K1.** **0 plaintext w backendzie:** test dwóch fikcyjnych dokumentów przechwytuje upload HTTP, logs i persistence; 0 wystąpień plaintext oraz DEK; backend otrzymuje ciphertext.
- [ ] **K2.** **5 odmów AEAD/AAD:** fałszywy tenant, object ID, VersionId, zły tag oraz replay zawsze odrzucane; AAD obejmuje tenant+object+version i szyfrowanie używa unikalnego nonce.
- [ ] **K3.** **Zarządzanie kluczami:** jawny przepływ utworzenia DEK, wrap, unwrap, rotation i revoke; serwer operatora nigdy nie otrzymuje niezaszyfrowanego DEK.
- [ ] **K4.** **Podmiana JS:** test nieautoryzowanego JS/SDK/release wykrywa manipulację przez niezależnie zaufanego klienta albo ustawia `BLOCKED`. Nie uznajemy własnego hostowanego JS za niezależny trust root.
- [ ] **K5.** **Recovery:** 3 testy: utrata klucza, nieuprawniona kancelaria i autoryzowany recovery. Brak ukrytego support/admin decrypt path.
- [ ] **K6.** **Odmowa operatora:** normalny backend nie może odszyfrować fikcyjnego dokumentu; prawdziwy dowód hardware Nitro pozostaje `BLOCKED` do SEC-07.

**Docelowy test, który należy dodać:** `python -m pytest -q test_confidential_zk_client_encryption.py` — 0 failed, 0 skipped krytycznych scenariuszy.

### Wspólny warunek zamknięcia
- [ ] Link do **zielonego CI dla aktualnego SHA**, wynik komendy testowej (passed/failed/skipped), zanonimizowany raport w `docs/security-evidence/SEC-03.md` (lub artefakcie CI), oraz linki do testów każdego K1–K6. Testy zostały dodane, ale wynik aktualnego SHA i niezależne dowody nadal muszą być osobno zweryfikowane.
- [ ] Dla każdego kryterium jawny status `PASS`, `FAIL` lub `BLOCKED` z dowodem, datą i wykonawcą. Brak realnego dostępu AWS = `BLOCKED`, nie `PASS`. Zero plaintext, danych osobowych, sekretów i DEK w artefaktach.
- [ ] W żadnym kodzie dodanym przez PR nie ma możliwości wysyłania ani podpisywania formularzy w AUTO. Testy CI i wykonany PR NIE oznaczają potwierdzenia komercyjnych twierdzeń Zero Trust / Zero Operator Access / Zero Knowledge.

## Zasady pracy w nowej konwersacji
To jest **PR implementacyjny, nadal DRAFT**. Kod i testy syntetyczne są w repozytorium; dowody z rzeczywistych kont AWS, odrębnego kustosza i sprzętowego Nitro są nadal BLOCKED. Nowa konwersacja ma zrealizować zadanie na **tej konkretnej gałęzi PR**, nie zakładać kolejnego zbędnego PR. Najpierw przeczytaj kod i aktualny stan #57, #60, #61, #62, #65 oraz sprawdź ich SHA. Nie edytuj cudzych gałęzi i nie scalać bez integracyjnego przeglądu.

Reguły: test wyłącznie pilot01/pilot02 i fikcyjne dane; AWS eu-central-1; produkcja wyłączona; AUTO preview nie wysyła, nie podpisuje i nie składa wniosków. Nie podnoś operatorowi uprawnień custody, nie loguj PII/plaintext/sekretów i nie wprowadzaj sieciowego 0.0.0.0/0 dla guest. Każdą własność security potwierdź testami pozytywnymi i **negatywnymi**; brak konta/narzędzi oznacz BLOCKED, a nie PASS. Sama dokumentacja lub CI nie stanowi dowodu sprzętowego. Zapisz kod + testy + wyniki + wymaganą niezależną atestację w PR.

**Definition of done:** zmiana możliwa do niezależnego review, testy CI zielone, brak funkcji submit, wszystkie pozostałe ograniczenia podane jawnie, bez twierdzenia 'Zero Operator Access / Zero Knowledge verified' przed dowodami.


## Implementacja rozpoczęta 2026-11-22

Kod został zapisany bezpośrednio na gałęzi tego PR. Moduły: `static/confidential-crypto.js`, `confidential/envelope.py`, `confidential/router.py`, `confidential/worker.py`, `confidential/client_release.py`, `confidential/zk_recovery.py`. Test obowiązkowy: `test_confidential_zk_client_encryption.py` (CI).

**Statusy K1–K6 i ograniczenia:** `docs/security-evidence/SEC-03.md`. Żadnego K1–K6 nie oznaczamy PASS na podstawie samych testów offline. W szczególności niezależna dystrybucja klienta, custody account i realna atestacja Nitro nadal są `BLOCKED`. To nadal PR draft, nie dowód komercyjnego ZK/ZOA.


## Aktualizacja SEC-03: odrębne klucze approverów i dowód źródła

- Migracja akceptuje tylko notarai.recovery.v2, wiążące dokładny SHA-256 oryginalnego ciphertextu, S3 VersionId, stary KMS pin oraz nowy cel/klucz.
- Oba klucze Ed25519 dla autoryzacji są pobierane z niezależnego, obrazo-pinanego trusted-recovery-root.json. Nigdy od wywołującego (mitigacja fałszywych dwóch podpisów operatora).
- Rejestr nonce sprawdza STS konta kustosza i używa jego sesji DynamoDB. Produkcyjny kanał dostępu do odrębnego kustosza nadal wymaga zatwierdzonej atestowanej integracji; żadnych poświadczeń kustosza w NotarAI.
- Skrypt package_confidential_recovery_root.py przyjmuje dwa niezależnie pozyskane fingerprinty SPKI i generuje publiczny root do osobnego measured image build.
- Testy negatywne test_confidential_recovery_trust.py i test_confidential_zk_client_encryption.py obejmują rogue signers, wrong SHA/S3, wrong pin, expired clock, replay i brak root.
- K5 pozostaje BLOCKED, bo odzyskiwanie nie jest jeszcze połączone z rzeczywistym KMS/legitymacją prawną i nie ma bezpiecznego key-wide revoke. Współdzielonego klucza KMS nie można wyłączać jako odpowiednika revocation jednego dokumentu.
