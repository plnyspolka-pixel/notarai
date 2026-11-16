# Private AI Control Room — panel pochodzenia danych

**Wiodący cel produktowy:** sprzedaż B2B i wzbudzanie zaufania przez czytelny, sprawdzalny pokaz kontroli danych. Dziennik zdarzeń i zaawansowany audyt są warstwą dowodową, nie główną narracją pierwszego ekranu. Wymagania UX/marketingu i reguły prawdziwości twierdzeń: [`CONTROL_ROOM_SALES_BRIEF.md`](./CONTROL_ROOM_SALES_BRIEF.md).

Status 2026-11-16: **PROTOTYP OFFLINE, TYLKO DANE SYNTETYCZNE**.

## Gotowy kod

- private_ai_dashboard/index.html — lokalny HTML, nie jest serwowany na produkcji.
- private_ai_dashboard/dashboard.css — responsywny design, bez CDN.
- private_ai_dashboard/dashboard.js — 12 demonstracyjnych zdarzeń, bez sieci.
- private_ai/lineage.py — schemat zdarzeń i autoryzowana projekcja per tenant.
- private_ai_tests/test_lineage.py i test_dashboard_contract.py — testy.
- .claude/commands/private-ai-control-room.md — zadanie dla Claude Code.

## Widoki

Centrum dowodzenia: zdarzenia, blokady, braki dowodów, mapa drogi dokumentu.
Dziennik: czas, pseudonim użytkownika/dokumentu/agenta, źródło, cel,
operacja, wynik, jakość dowodu; pełne filtrowanie i wyszukiwanie.
Incydenty: odmowy wysyłania, błędy i operacje bez dowodu.
Szczegóły: kliknięcie zdarzenia aktualizuje diagram i metadane.
Raport JSON: wyłącznie syntetyczne, pseudonimowe dane, bez plików.

## Znaczenie dowodów

Zarejestrowane oznacza obserwację zapisaną w systemie — nie atestację.
Deklarowane oznacza samą konfigurację lub oświadczenie.
Brak dowodu oznacza niepewność, nie bezpieczeństwo.
Zweryfikowane niezależnie jest zastrzeżone dla dowodów z niezależnego
weryfikatora podpisanych checkpointów; obecnie nie występuje.

## Docelowa produkcyjna architektura

Zaufani producenci zdarzeń (API, AI Gateway, storage, polityki, agent MCP)
→ walidacja ścisłej allowlisty metadanych i usunięcie PII
→ kolejka/outbox z idempotencją
→ append-only magazyn i kryptograficzny checkpoint
→ niezależny świadek/weryfikator
→ tenant-scoped read model
→ uwierzytelnione API do odczytu
→ panel z filtrowaniem serwerowym.

Kontrole: SSO/OIDC i niezależne pryncypały workload; polityka OPA/OpenFGA;
pseudonimy HMAC per tenant, rotacja; domyślny brak dostępu; zabezpieczona
paginacja i eksport; nieujawnianie metryk innych tenantów nawet pośrednio.
Stan UNKNOWN przy braku telemetrii/heartbeat. Nigdy nie zapisywać promptów,
nazw plików, PESEL, pełnych URL/presigned URL, nazwisk ani sekretów.

## Lokalne kontrole

Uruchom:
python -m unittest discover -s private_ai_tests -v
node --check private_ai_dashboard/dashboard.js

Zobacz lokalnie private_ai_dashboard/index.html; sprawdź działanie na
desktop, tablecie i telefonie. Zmiana roli to TYLKO symulator — nie auth.
Nie kopiuj go do katalogu publicznego static bez serwerowej autoryzacji.
