# SEC-05 — [SEC-05] Bezpieczne wydania: podpis kustosza obowiązkowy dla każdej uruchamianej wersji Nitro

**Status: PLANNED (BRAK IMPLEMENTACJI).** P0; zależności: SEC-01, #61, #62, #65

## Zakres
1. Przenieś niezależne ECDSA release-gate z pilota/CLI do docelowego serwerowego schedulera i kontroli uruchamiania; testowy flag/parametr operatora nie może wyłączyć wymaganej zgody.
2. Zweryfikuj digest obrazu, dokładny task ARN, PCR17, KMS key policy, tenant, rolę IAM, okres ważności i trust root z kanału poza operatorem; odrzuć dowolny downgrade, replay i race przy zmianie policy po zatwierdzeniu.
3. Uszczelnij build pipeline/SBOM, zależności, obraz OCI, OIDC i ECR; rozdziel builder/operator od kustosza i audytora; przypnij digest z supply-chain provenance.
4. Wyklucz mechanizmy boczne: ECS Exec, container overrides, niezaufane sidecars, log drivers, debug, alternative task families, direct ECS RunTask in operator-controlled account.

## Mierzalne kryteria zakończenia — SEC-05

- [ ] **K1.** **100% ścieżek startu:** zmapowane wszystkie wywołania `ECS RunTask`, scheduler Lambda, CLI i API; każda produkcyjna ścieżka ma niezależną weryfikację release albo jest zablokowana przed decrypt.
- [ ] **K2.** **7 odmów:** brak podpisu, podpis błędny, wygasły, zły tenant, PCR17, image digest i KMS policy hash => brak efektywnego decrypt/uruchomienia autoryzowanego zadania.
- [ ] **K3.** **Bez downgrade:** nie ma przełączenia na operator-owned/demo KMS po błędzie custody; feature flag/parametr żądania klienta nie może wymusić starej ścieżki dla komercyjnego zadania.
- [ ] **K4.** **Direct RunTask:** test z pominięciem aplikacji wykazuje, że niezatwierdzona wersja nie otrzymuje DEK z KMS; bramka w schedulerze sama nie jest wystarczającym dowodem.
- [ ] **K5.** **Supply chain:** dla obrazu używany jest wyłącznie `@sha256`; w raporcie istnieją digest, source SHA, provenance/SBOM i podpis niezależnego kustosza, powiązane z exact task revision.
- [ ] **K6.** **Weryfikacja na AWS:** rzeczywisty KMS deny/allow i CloudTrail w obu kontach weryfikują binding; jeśli brak sprzętu lub kustosza, status *sprzętowego* dowodu = `BLOCKED`.

**Docelowy test, który należy dodać:** `python -m pytest -q test_confidential_release_gate.py` — 0 failed, 0 skipped krytycznych scenariuszy.

### Wspólny warunek zamknięcia
- [ ] Link do **zielonego CI dla aktualnego SHA**, wynik komendy testowej (passed/failed/skipped), zanonimizowany raport w `docs/security-evidence/SEC-05.md` (lub artefakcie CI), oraz linki do testów każdego K1–K6. Nazwę planowanego testu trzeba dopiero wdrożyć; sam opis nie zalicza kryterium.
- [ ] Dla każdego kryterium jawny status `PASS`, `FAIL` lub `BLOCKED` z dowodem, datą i wykonawcą. Brak realnego dostępu AWS = `BLOCKED`, nie `PASS`. Zero plaintext, danych osobowych, sekretów i DEK w artefaktach.
- [ ] W żadnym kodzie dodanym przez PR nie ma możliwości wysyłania ani podpisywania formularzy w AUTO. Testy CI i wykonany PR NIE oznaczają potwierdzenia komercyjnych twierdzeń Zero Trust / Zero Operator Access / Zero Knowledge.

## Polecenie dla nowej konwersacji
**Ten draft PR zawiera wyłącznie plan.** Pracuj na gałęzi aktualnego PR, rozwijaj ten PR (nie twórz nowego). Najpierw przeczytaj bazowe #57, #60, #61, #62, #65 oraz aktywne PR-y SEC-01..SEC-12. Nie modyfikuj gałęzi innych zadań. Osobne PR-y mają wspólny bazowy commit #65, ale są niezależne i nie mogą być scalane bez przeglądu konfliktów.
**Ograniczenia:** tylko fikcyjne pilot01/pilot02; eu-central-1; produkcja OFF; żadnych podpisów, wysyłek, składania wniosków ani dostępu do prawdziwych dokumentów. AWS only w autoryzowanej sesji, niezależna zgoda kustosza obowiązkowa. Bez plaintext/PII w logs, debug, CI, proxy. Testy offline ≠ real hardware proof. Skuteczność sprawdź regresją + fail-closed negatywnymi testami; nie polegaj tylko na „documentation review”.
**Dostarcz:** kod/IaC + testy + zanonimizowane dowody + checklistę niezależnego audytu + status PASS/BLOCKED/UNVERIFIED; nie obiecuj produkcji ani Zero Knowledge/ZERO Operator Access bez dowodu.
