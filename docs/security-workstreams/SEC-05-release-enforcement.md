# SEC-05 — [SEC-05] Bezpieczne wydania: podpis kustosza obowiązkowy dla każdej uruchamianej wersji Nitro

**Status: PLANNED (BRAK IMPLEMENTACJI).** P0; zależności: SEC-01, #61, #62, #65

## Zakres
1. Przenieś niezależne ECDSA release-gate z pilota/CLI do docelowego serwerowego schedulera i kontroli uruchamiania; testowy flag/parametr operatora nie może wyłączyć wymaganej zgody.
2. Zweryfikuj digest obrazu, dokładny task ARN, PCR17, KMS key policy, tenant, rolę IAM, okres ważności i trust root z kanału poza operatorem; odrzuć dowolny downgrade, replay i race przy zmianie policy po zatwierdzeniu.
3. Uszczelnij build pipeline/SBOM, zależności, obraz OCI, OIDC i ECR; rozdziel builder/operator od kustosza i audytora; przypnij digest z supply-chain provenance.
4. Wyklucz mechanizmy boczne: ECS Exec, container overrides, niezaufane sidecars, log drivers, debug, alternative task families, direct ECS RunTask in operator-controlled account.

## Kryteria odbioru
- [ ] Niedopuszczony obraz/task/PCR17/policy nie może dostać KMS DEK; test negatywny z uprawnieniami operatora.
- [ ] Release sign-off jest wymagany w kodzie produkcyjnym, nie tylko w ręcznym narzędziu; sprawdzono wszystkie ścieżki launch.
- [ ] Weryfikacja pozostawia status unverified przy nieobecnej kontroli rzeczywistego KMS/Nitro.

## Polecenie dla nowej konwersacji
**Ten draft PR zawiera wyłącznie plan.** Pracuj na gałęzi aktualnego PR, rozwijaj ten PR (nie twórz nowego). Najpierw przeczytaj bazowe #57, #60, #61, #62, #65 oraz aktywne PR-y SEC-01..SEC-12. Nie modyfikuj gałęzi innych zadań. Osobne PR-y mają wspólny bazowy commit #65, ale są niezależne i nie mogą być scalane bez przeglądu konfliktów.
**Ograniczenia:** tylko fikcyjne pilot01/pilot02; eu-central-1; produkcja OFF; żadnych podpisów, wysyłek, składania wniosków ani dostępu do prawdziwych dokumentów. AWS only w autoryzowanej sesji, niezależna zgoda kustosza obowiązkowa. Bez plaintext/PII w logs, debug, CI, proxy. Testy offline ≠ real hardware proof. Skuteczność sprawdź regresją + fail-closed negatywnymi testami; nie polegaj tylko na „documentation review”.
**Dostarcz:** kod/IaC + testy + zanonimizowane dowody + checklistę niezależnego audytu + status PASS/BLOCKED/UNVERIFIED; nie obiecuj produkcji ani Zero Knowledge/ZERO Operator Access bez dowodu.
