# Claude Code mission: PRIVATE AI CONTROL ROOM

## Intencja użytkownika

Wybuduj atrakcyjny, prosty i audytowalny panel, który pokazuje DOKŁADNIE:
kto, kiedy, jaki dokument/zasób (pseudonim), skąd przyszedł, dokąd trafił,
co agent i model zrobił, jaki był cel i region, jakie były uprawnienia,
co zostało zablokowane, czego nie wiemy i dlaczego. Zrób oś czasu,
graf pochodzenia danych, incydenty i historię przetwarzania/usunięcia.
Role: właściciel organizacji, operator, audytor, użytkownik, agent bez UI.

Wykorzystaj istniejący research NotarAI PR #36 (OPA/OpenFGA, workload
identity, SHA-384/Ed25519, KMS/HSM, TEE i niezależny witness),
aktualny PR #40 z EU Private AI i draft Finance You PR #389.
Research DARPA/BigTech to inspiracja do testów, NIE atest wojskowy.

## Stan faktyczny

- private_ai_dashboard/index.html + dashboard.css + dashboard.js:
  działający offline interaktywny prototyp. DEMO, żadnych realnych danych.
- private_ai/lineage.py: typed metadata-only event, role/tenant projection;
  test_lineage.py kontroluje wycieki między tenantami.
- private_ai/evidence.py: edukacyjny audit hash chain, NIE HSM/witness.
- private_ai/ingress.py i lambda_entry.py: hash-pin synthetic-only pilot;
  AWS nie został wdrożony ani zweryfikowany live.
- docs/private-ai/PILOT.md i REGION_EVIDENCE.md opisują warunki AWS.
- CLAUDE.md nakazuje nie wysyłać sekretów i PII do logów, działać w UE
  i nie tworzyć nowych zasobów z danymi bez akceptacji.

## Kolejność, wykonuj kod i testuj zamiast powtarzać plan

Faza A. Otwórz panel w Playwright, sprawdź desktop 1440, tablet 768,
mobile 390, keyboard focus, kontrast WCAG AA, filtrację, klikanie śladu,
eksport, persona demo. Popraw responsywność i ergonomię. Nie używaj CDN
ani zewnętrznych trackerów.

Faza B. Zdefiniuj wersjonowany schemat lineage.event.v1 (JSON Schema +
Python). Strict allowlist i enumy, absolutny zakaz promptów, nazw plików,
PESEL, nazwisk, emaili, URL/presigned URL, sekretów w audycie.
Pseudonimy HMAC per tenant (klucze poza runtime agenta, z rotacją).
Pola origin/action/destination od zaufanego producenta — nie od LLM.
Wymuś tenant_id, actor scope, resource ownership i purpose.

Faza C. Połącz prawdziwe zaufane event sources: IAM API gateway,
autoryzator OPA, storage, model inference, agent tools, decyzje
zatwierdzeń, usunięcia/retencja. Pipeline transactional outbox i
deduplikacja. Osobny system heartbeat i alarmy braku telemetrii;
żadnych „bezpiecznie” gdy brakuje logów.

Faza D. Wdroż autoryzowane, READ-ONLY API dziennika: żadnego
publicznego routingu do panelu bez server-side OIDC, RBAC/ABAC,
OpenFGA i tenant enforcement w storage/read model. Globalnych
pseudo-adminów nie wpuszczaj do cudzych tenantów. Zabezpiecz
pagination, count queries, cache, eksport i powiadomienia.
User-own tylko własne, auditor tylko metadane swojego tenantu,
agent bez UI. Testuj IDOR i różne role.

Faza E. Dowody: podpisy checkpointów KMS/HSM pod odrębnym principalem,
WORM w niezależnym koncie, niezależny verifier podpisów/hash chain,
rollback/fork/truncation i rotacja. Dopiero wtedy status verified.
Dla denied/error zbuduj bezpieczne kody przyczyn, SLA, eskalacje.

Faza F. AWS: rozpocznij od osobnej, gotowej do wykonania instrukcji
`.claude/commands/private-ai-aws-staging.md` (komenda Claude Code:
`/private-ai-aws-staging`). Wykonaj tamtą checklistę po kolei.
Przed deploymentem sprawdź read-only preflight,
GetInferenceProfile destinations, VPC/PrivateLink/Flow Logs, CloudTrail,
retencję, tożsamości OIDC. Żadnych prawdziwych dokumentów w stagingu.
Nowe zasoby i koszty wymagają osobnej zgody operatora. Nie używaj
roli produkcyjnego deploymentu do eksperymentów.

## Akceptacja (nigdy nie pomijaj)

1. Wszystkie Python/JS/OPA/IaC testy zielone, Playwright desktop/mobile.
2. Demonstracja: tenant A nie widzi B, operator widzi tylko swoje,
   auditor odczyt bez treści, agent zero UI.
3. Zablokowane są wycieki przez count, filter, pagination, export, cache.
4. Zdarzenia bez zaufanego źródła mają UNKNOWN; brak dowodu jest
   jednoznacznie widoczny.
5. Wykres drogi dokumentu jest z obserwowanych eventów, nie jest
   generowanym zgadywaniem ścieżki.
6. Weryfikacja podpisu audytu odporna na tamper/truncation/rollback.
7. Raport dowodowy zawiera metodę testu, wynik i identyfikator CI.
8. Żadnych danych rzeczywistych w PR, issue, logach ani fixture.
9. Wszystko na gałęzi PR #40, kolejne małe commity, osobne review.
10. Bez mergowania i produkcyjnego deployu przed przeglądem
    bezpieczeństwa i jawną zgodą.

Wykonuj zadania samodzielnie, iteracyjnie. Nie kończ na sugestiach.
Przy brakach dostępu dopisz punkt do docs/czeka-na-dostep.md,
nie obchodź polityk, nie podszywaj się pod operatora.
