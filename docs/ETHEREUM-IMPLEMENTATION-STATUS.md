# NotarAI Secrecy Proof + Ethereum — wykonanie 2026-11-13

**Branch:** `wdrazamy-ethereum`. **Status:** kryptograficzny prototyp i kontrolowany pilotaż, NIE gotowość produkcyjna, NIE kwalifikowana usługa zaufania.

## Implementowane (DONE)
- `proof_engine.py`: prywatne salted commitments + Merkle v1 + read-only Ethereum RPC verifier; wspólny protokół z Finance You.
- `dowody_ethereum.py`: kancelaryjny dziennik dowodowy, zakotwiczenie w przygotowanych partiach oraz weryfikacja wskazanej transakcji Ethereum.
- `autoryzacja.py`, `stanowiska.py`: blokada uprawnień sekretariatu/aplikanta i dostępu serwisowego do `/api/dowody` oraz `/api/sealed`.
- `static/sealed-client.mjs`: AES-256-GCM po stronie klienta, PBKDF2-SHA256 600 tys. iteracji, losowy nonce i salt, binding kancelarii oraz UUID dokumentu do AAD.
- `notarai_sealed_cli.py`: samodzielny lokalny klient Python/Windows do szyfrowania/odszyfrowania bez połączenia z backendem; bez przesyłania hasła.
- `sealed_vault.py`: oddzielne API przechowujące wyłącznie zatwierdzone składniowo szyfrogramy z wersjonowanym formatem JSON; strict-schema, brak pól na plaintext, tenant isolation, kontrola idempotencji. POC do 4 MiB i 50 dokumentów/kancelaria.
- `tests/fixtures/sealed-envelope-v1.json`: wspólny test vector AES-GCM; Python generuje format, JS niezależnie odszyfrowuje.
- Testy: `test_proof_engine.py`, `test_dowody_policy.py`, `test_sealed_vault.py`, `test_sealed_api.py`, `test_sealed_cli.py`, `test_sealed_client.mjs`; Github Actions.

## Prawdziwy zakres gwarancji (CLAIMS)
| Twierdzenie | Dowód w POC | Status |
|---|---|---|
| Lokalny CLI nie łączy się z Bedrock ani NotarAI | Kod CLI + lokalny test bez sieci | weryfikowalne w zdefiniowanym buildzie |
| Endpoint `/api/sealed` nie oczekuje i nie przechowuje plaintextu | Pydantic extra=forbid + testy API | weryfikowalne dla tego endpointu |
| Payload receipt nie zmienił się po opublikowaniu rootu | Merkle witness + zweryfikowany RPC receipt | możliwe dopiero po prawdziwym anchor |
| Operator nie ma możliwości odszyfrowania ŻADNYCH aktów w całym systemie | nie istnieje jeszcze pełna E2E atestacja | **NOT VERIFIED** |
| Żadna osoba fizyczna nigdy nie widziała danych | nie jest możliwe do wywnioskowania z samego blockchaina | **NOT PROVABLE** |
| Wdrożona kwalifikowana usługa eIDAS/QTSP | brak audytu i kwalifikacji | **NOT QUALIFIED** |

## P0 — blokery przed premierą Sealed
1. Obecne `app.py` + `bedrock.py` nadal przetwarzają jawne akty w normalnym trybie. **Nie reklamować obecnej całości jako zero-knowledge**.
2. Operator może podmienić JS serwowany przez WWW. Potrzebna odrębna podpisana, reprodukowalna dystrybucja klienta, a najlepiej natywny klient z weryfikowaną aktualizacją.
3. PBKDF2 z hasłem nie wystarcza dla wszystkich modeli zagrożeń. Docelowo losowe per-file DEK i hardware-backed office KEK, rotacja, odzyskiwanie przez kancelarię, multi-recipient share i revocation.
4. Obecny magazyn JSON jest ograniczonym prototypem; potrzebne obiektowe szyfrogramy, WORM/Object Lock, odporność na awarie, retencja i sprawdzona izolacja kancelarii.
5. Brak podpisanych, niezależnie atestowanych raportów poufności i podpisu/kwalifikowanego znacznika czasu.
6. Brak bezpiecznej integracji signer/RPC/automatycznej publikacji rootów do Mainnet. **Nie dokonano transakcji ETH.**
7. Testy CI są offline i nie stanowią audytu wszystkich endpointów, IAM, CloudWatch, cache, backupów ani integracji z Bedrock.

## Następne zadania dla Claude Code
`/wdrazamy-ethereum` → szczegółowy plan w `CLAUDE_ETHEREUM_MISSION.md`.
Najpierw: signed installer, pełna mapa ścieżek plaintext, AEAD per-file DEK i key custody, niezależna weryfikacja builda oraz sealed flow testy end-to-end na fikcyjnych danych.

**Nie merge'ować i nie deployować automatycznie.** Licencja/kwalifikacja, bezpieczeństwo prawdziwych aktów i kontrola dostępu wymagają osobnego przeglądu.

## Aktualizacja implementacji — Sealed v2 i KMS (13.11.2026)

**DONE na gałęzi:**
- `notarai_sealed_v2.py`: lokalny klient CLI, losowy DEK AES-256-GCM na dokument, X25519/HKDF/AES-GCM opakowanie dla wielu uprawnionych osób, klucze prywatne w zaszyfrowanym PKCS8 na urządzeniu kancelarii, bez przesyłania plaintextu do operatora;
- `rotate_recipients`: tworzy nowy dokument z nowym DEK i nowym UUID; odwołany klucz nie odszyfruje nowej wersji. Stare skopiowane wersje pozostają poza zakresem technicznego cofnięcia;
- `sealed_vault_v2.py` + FastAPI: wyłącznie zaszyfrowane v2, strict schema, brak pól na plaintext, isolation po kancelarii, blokady dostępu operatora serwisowego;
- `sealed_release.py`: weryfikator Ed25519 podpisu release i SHA-256 każdego pliku, klucz wydawcy poza GitHub;
- `.github/workflows/sealed-local-client.yml`: proces **ręcznego** budowania lokalnego pliku wykonywalnego dla Windows i Linux z poświadczeniem pochodzenia GitHub OIDC. Workflow nie został uruchomiony w tym zadaniu, nie ma jeszcze Authenticode/certyfikatu wydawcy;
- `kms_anchor.py`: EIP-1559 + AWS KMS ECC_SECG_P256K1, testy offline; sealer NotarAI domyślnie przygotowuje Sepolia, nie Mainnet; potwierdza transakcję oddzielnym RPC.

**BLOCKED (nie przedstawiać jako wdrożone):** podpis wydania kluczem rzeczywistego wydawcy, Authenticode Windows i podpisany aktualizator; TPM/HSM dla prywatnych kluczy kancelarii; migracja całego istniejącego obiegu aktów do Sealed; audyt wszystkich logów i kanałów AI; faktyczny KMS/IAM/RPC z kluczem testowym; automatyczny sealer/publisher; eIDAS/QTSP.

Praca pozostaje w `wdrazamy-ethereum`, bez Mainnet, wdrożenia produkcyjnego i bez transmisji prawdziwych aktów. Runbook: `docs/ETHEREUM-PUBLISHER-RUNBOOK.md`, instrukcja lokalna: `docs/SEALED-LOCAL-CLIENT.md`.
