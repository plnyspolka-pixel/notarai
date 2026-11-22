# SEC-07 — [SEC-07] Dowód sprzętowy Nitro/KMS: pozytywne i negatywne testy atestacji

**Status: PLANNED (BRAK IMPLEMENTACJI).** P0; zależności: SEC-05, SEC-06, #65; konto AWS i niezależny custody

## Zakres
1. Przygotuj uruchamialny E2E w eu-central-1 na dwóch syntetycznych tenantach; wykorzystaj tylko zatwierdzony digest OCI i rzeczywisty ECS Nitro Confidential Sandbox.
2. Pozytywnie sprawdź KMS Recipient Attestation ze sprzętowym NSM, klucz wydany tylko jako CiphertextForRecipient i odszyfrowanie wewnątrz zatwierdzonego guest.
3. Negatywnie zweryfikuj zwykłe EC2/host, zły PCR, zmieniony obraz, odmowę bez podpisu kustosza, zły tenant/klucz/rola i próbę policy tamper; zbierz niezależne CloudTrail read-only dowody z obu kont.
4. Oddziel w artefaktach dowód sprzętowy od statycznego preflight/CI. Zadbaj o fail-closed i rollback bez utraty śladów bezpieczeństwa.

## Kryteria odbioru
- [ ] Testy rzeczywiste KMS/Nitro PASS tylko przy logach/artefaktach z autoryzowanej sesji obu kont; brak dowodów => BLOCKED.
- [ ] Klucz nie trafia do hosta/klasycznego workload ani do logów; skuteczność potwierdzona odmowami.
- [ ] Wynik wiąże konkretny tenant, exact image SHA, PCR17, key ARN, czas i podpis kustosza.

## Polecenie dla nowej konwersacji
**Ten draft PR zawiera wyłącznie plan.** Pracuj na gałęzi aktualnego PR, rozwijaj ten PR (nie twórz nowego). Najpierw przeczytaj bazowe #57, #60, #61, #62, #65 oraz aktywne PR-y SEC-01..SEC-12. Nie modyfikuj gałęzi innych zadań. Osobne PR-y mają wspólny bazowy commit #65, ale są niezależne i nie mogą być scalane bez przeglądu konfliktów.
**Ograniczenia:** tylko fikcyjne pilot01/pilot02; eu-central-1; produkcja OFF; żadnych podpisów, wysyłek, składania wniosków ani dostępu do prawdziwych dokumentów. AWS only w autoryzowanej sesji, niezależna zgoda kustosza obowiązkowa. Bez plaintext/PII w logs, debug, CI, proxy. Testy offline ≠ real hardware proof. Skuteczność sprawdź regresją + fail-closed negatywnymi testami; nie polegaj tylko na „documentation review”.
**Dostarcz:** kod/IaC + testy + zanonimizowane dowody + checklistę niezależnego audytu + status PASS/BLOCKED/UNVERIFIED; nie obiecuj produkcji ani Zero Knowledge/ZERO Operator Access bez dowodu.
