# NotarAI Virtual Employee — architektura i etap 0

**Status:** decyzja architektoniczna / plan prototypu; **nie wdrożono** VM ani robota Windows.  
**Data:** 2026-11-22  
**Priorytet:** pierwszy nowy kierunek NotarAI.  
**Zasada produktu:** notariusz używa `app.notarai.pl`; nie instaluje NotarAI na własnym komputerze. Oddzielne środowisko Windows uruchamia istniejący program kancelaryjny, z odrębną tożsamością operatora automatycznego.

## 1. Co już istnieje i czego nie dublujemy

Repo ma SaaS uruchamiany na AWS ECS Fargate, logowanie Cognito, role kancelarii (`stanowiska.py`), magazyn spraw S3, Bedrock z kontrolą profilu EU, ślad audytu i funkcje generowania projektów dokumentów. Patrz `SAAS.md`, `CLAUDE.md` i `SPEC.md`. Nowe komponenty mają korzystać z istniejącej tożsamości, tenantów i modelu zgód. **Nie zmieniać istniejących przepływów klientów w MVP.**

Secure Agent Factory (`docs/agent-factory.md`) to osobny prototyp do prac programistycznych; nie mieszać jego uprawnień/workerów z robotem kancelaryjnym.

## 2. Architektura logiczna

```text
Notariusz / pracownik -> app.notarai.pl (Cognito + RBAC kancelarii)
    -> Virtual Worker API (tworzenie zadań, autoryzacje, akceptacje, status)
    -> kolejka zadań (tenant_id, job_id, policy, TTL, idempotency_key)
    -> broker połączeń z VM kancelarii (tożsamość urządzenia, mTLS, egress-only)
    -> VM Windows kancelarii: Supervisor + Interactive Session Worker
         |-> adapter systemu (Notaris / inny, mapowanie kontrolek)
         |-> Windows UI Automation (WinApp CLI na discovery; FlaUI/.NET lub API w runtime)
         |-> program kancelaryjny na oddzielnym koncie operatora AI
         |-> baza kancelarii przez zatwierdzoną ścieżkę / API / import
    -> wynik techniczny, dokument do kontroli, metadane audytu
    -> notariusz zatwierdza czynności formalne i zewnętrzne
```

SaaS na Linux/ECS **nie steruje GUI bezpośrednio**. Operacje na GUI są wykonywane **w tej samej sesji Windows** co aplikacja. Service/supervisor uruchamia i monitoruje agenta użytkownika; sama usługa Windows w session 0 nie wystarcza do operacji graficznych. Nie opierać niezawodności na stale otwartym RDP administratora.

Jedna VM = jeden tenant (początkowo jeden robot/sesja z kolejką serialną). Nie współdzielić Windows session ani aplikacji kancelarii między tenantami. Skalowanie = dodatkowe izolowane stanowiska z zachowaniem licencji i limitów współbieżności bazy.

## 3. Stos technologiczny / decyzje

- Orkiestrator: istniejący NotarAI AWS eu-central-1, osobne API jobs, durable queue, stan zadań i metadane audytowe.
- VM: **najpierw kwalifikacja wymagań aplikacji**. Kandydat A: Windows Server VM z licencją infrastruktury, jeśli dostawca programu oficjalnie wspiera ten OS i scenariusz. Kandydat B: Windows 11 w zgodnym licencyjnie Azure VM/AVD albo AWS WorkSpaces BYOL, jeśli program wymaga desktopowego Windows. Nie zakładać, że zwykła licencja Windows 11 Pro wystarcza na hosted VM.
- Discovery/testy: `winapp ui inspect/search/status`; mapowanie AutomationId, Name, ControlType, pattern + okno nadrzędne. Nie wykonywać niezweryfikowanych komend.
- Docelowy adapter: .NET 8+ z Microsoft UI Automation / FlaUI i ewentualnie wbudowaną biblioteką WinApp UI Automation; fallback do kontrolowanej automatyzacji wejścia tylko gdy UIA nie wystarcza.
- Interfejs adaptera: `find_case`, `read_case`, `prepare_case_draft`, `fill_case_draft`, `export_document`, `get_ui_state`. Początkowo **brak** `sign`, `submit`, `delete`, `send`.
- Narzędzia agentów nie dostają arbitralnego `shell` ani generowania dowolnych kliknięć. Dispatcher wykonuje wyłącznie zatwierdzone operacje z walidacją pól. CLI-Anything to opcjonalny generator narzędzi, nie konieczna zależność.
- Połączenie: w pierwszej kolejności private network / połączenie inicjowane przez agenta; nie wystawiać RDP ani paneli UIA bezpośrednio na internet.
- Konto operatora AI: indywidualna tożsamość, najmniejsze wymagane uprawnienia; osobno konta serwisowe i administratora. Żadnego używania osobistego podpisu kwalifikowanego notariusza ani automatycznego zatwierdzania 2FA.

## 4. Stan i semantyka zadań

Stany: `queued -> assigned -> preparing -> running -> waiting_for_human -> completed`; ścieżki negatywne: `failed`, `cancelled`, `expired`, `needs_reconciliation`.

Każda operacja ma `tenant_id` **z uwierzytelnionej sesji** (nie z parametru dostarczonego przez model), `case_id`, `actor_id`, `job_id`, wersję polityki i klucz idempotencji. Przed zapisem adapter czyta bieżący ekran i potwierdza zgodność sprawy. Po zapisie ponownie odczytuje wynik i porównuje; przy niepewnym sukcesie nie ponawia ślepo akcji, tylko przechodzi w `needs_reconciliation`.

Domyślnie `dry_run` dla nowych integracji, włączenie zapisu per adapter/tenant po testach.

## 5. Polityka bezpieczeństwa i tajemnica notarialna

- Europejskie miejsce przetwarzania danych z weryfikacją faktycznej rezydencji wszystkich podwykonawców i profili AI; nie wysyłać danych klienta do niezatwierdzonych modeli ani screenshotów do zewnętrznych narzędzi.
- Ścisła izolacja tenantów na poziomie IAM/VPC/VM/dysków/sekretów/kluczy, ograniczony dostęp personelu operatora infrastruktury. Własna VM **nie dowodzi** Zero Knowledge/Zero Operator Access; takie deklaracje wymagają odrębnych mechanizmów i dowodów.
- AWS Secrets Manager / mechanizm bezpiecznego dostarczenia sekretów; brak haseł w promptach, repo, logach i konfiguracji publicznej.
- Logi: tylko identyfikatory techniczne, nazwa akcji, status, czas, typ błędu, approval_id; **zero** PESEL, treści aktów, haseł i pełnych zrzutów ekranu.
- Zrzuty diagnostyczne: domyślnie wyłączone, opcjonalnie maskowane/szyfrowane/krótko przechowywane za zgodą; osobny obieg access-review.
- Każda czynność o skutku zewnętrznym lub formalnym (wysłanie, podpis, rejestracja, zakup płatnego odpisu, usunięcie) wymaga jawnej autoryzacji uprawnionej osoby. CAPTCHA/2FA/podpis: interakcja człowieka, bez obchodzenia zabezpieczeń.
- Dane i teksty z otwartej aplikacji nie są instrukcjami systemowymi dla agenta (ochrona przed prompt injection).
- Szyfrowanie dysków, hardening VM, aktualizacje, EDR, kontrola egress i odtwarzanie z obrazu wzorcowego.

## 6. Trzy warianty integracji z bazą kancelarii

1. **Dostawca wspiera dostęp po sieci/API/serwerowym kliencie**: VM łączy się do autoryzowanego endpointu przez kanał prywatny. Najlepiej.
2. **Dostawca dopuszcza migrację/replicację do VM**: projektujemy spójność i procedurę synchronizacji; nie modyfikujemy schematu bazy bez specyfikacji.
3. **Baza wyłącznie lokalna, bez zdalnego dostępu i bez eksportu**: model cloud-only nie zrealizuje integracji. Potrzebna zmiana infrastruktury kancelarii lub rezygnacja z danej integracji. Nie obiecujemy „zero instalacji/zmian w każdej kancelarii”.

Nie pisać bezpośrednio do baz producentów przez SQL bez formalnie potwierdzonego wsparcia: ryzyko naruszenia integralności danych i licencji.

## 7. Plan realizacji i bramki jakości

### Etap 0 — kwalifikacja (bez danych produkcyjnych)
- [ ] Wybrać pierwszy program (Notaris jako kandydat, ewentualnie Wolters Kluwer) i ustalić numer wersji.
- [ ] Potwierdzić zgodę/licencję producenta na VM, osobne stanowisko i automatyzację; warunki Windows Server vs Windows 11 i zdalnej bazy.
- [ ] Zbudować listę 5 akcji do pomiaru UIA: uruchom, znajdź sprawę, odczytaj pole, wypełnij *testowy* formularz, eksportuj *testowy* dokument.
- [ ] Przeprowadzić inspekcję UIA na testowym systemie i zapisać listę obsługiwanych AutomationPattern + przeszkody.
- [ ] Wybrać wariant legalnego hostingu Windows; region UE, koszt po otrzymaniu aktualnego cennika.

### Etap 1 — demonstrator VM (fikcyjne dane)
- [ ] Jedna odizolowana VM, sesja operatora AI, testowa instalacja programu.
- [ ] Host Windows supervisor + interactive session worker + jeden konkretny adapter.
- [ ] Odczyt sprawy testowej i eksport projektu, bez zapisu do rejestrów.
- [ ] Zasymulować utratę sesji, błędny ekran, zmianę okna, RDP disconnect, ponowną próbę zadania i brak dostępu do obcego tenantu.

### Etap 2 — integracja z NotarAI SaaS
- [ ] Status robota, kolejka zadań, RBAC, akceptacje, wynik/dokument.
- [ ] Przydział jednego zadania GUI na sesję; limit i dead-letter queue.
- [ ] Weryfikacja audytu bez danych osobowych i uprawnień administratora SaaS.
- [ ] Uruchamianie/wyłączanie VM na żądanie (po zmierzeniu wpływu cold-start na UX i koszt).

### Etap 3 — pilotaż kancelaryjny
- [ ] Oddzielny tenant, podpisana umowa/powierzenie i decyzja o lokalizacji bazy.
- [ ] Kontrola poprawek przez notariusza, procedura błędu i ręczny fallback.
- [ ] Audyt techniczny i formalny przed uruchomieniem na danych klientów.

**Definition of Done MVP:** jedna realna aplikacja kancelaryjna w testowym Windows, cztery kolejne zadania poprawnie obsłużone z kolejki, kontrolowany eksport testowego dokumentu, bez naruszenia izolacji, bez działania na produkcyjnych danych, z widocznym stanem i audytem. Sam projekt dokumentu nie staje się aktem bez kontroli notariusza.

## 8. Ryzyka krytyczne / otwarte decyzje

| Ryzyko | Jak rozstrzygnąć |
| --- | --- |
| Program wymaga nieobsługiwanego systemu Windows | Test zgodności + dostawca |
| UIA nie ujawnia kontrolek (custom/legacy) | Inspekcja; alternatywa: eksport/API, jako ostatnia: kontrolowane GUI/OCR |
| Znikająca sesja interaktywna | Testy RDP, watchdog sesji, polityka requeue/reconcile |
| Licencja nie zezwala na robota/hosting | Pisemne potwierdzenie producenta |
| Baza kancelarii jest zamknięta w LAN | Prywatna łączność i autoryzacja; nie udawać integracji bez dostępu |
| Dane w zrzutach lub logach | DLP, brak screen capture domyślnie, testy negatywne |
| Operator infrastruktury może czytać dane | Odseparowanie kluczy i uprawnień; nie deklarować zero-knowledge bez dowodu |
| Akcje notarialne i podpisy | Techniczna blokada akcji bez aprobaty osoby uprawnionej |

## 9. Oficjalne źródła do walidacji

- Microsoft WinApp CLI UI Automation: https://learn.microsoft.com/en-us/windows/apps/dev-tools/winapp-cli/ui-automation
- Microsoft — unattended desktop flows/sesje Windows: https://learn.microsoft.com/en-us/power-automate/desktop-flows/run-unattended-desktop-flows
- Microsoft — UI Automation/UIPI limitations: https://learn.microsoft.com/en-us/troubleshoot/power-platform/power-automate/desktop-flows/ui-automation/uipi-issues
- Microsoft — Windows 11 virtual desktop licensing: https://www.microsoft.com/licensing/guidance/Windows-11-Licensing-for-Virtual-Desktops
- AWS — WorkSpaces Personal Windows desktop BYOL: https://docs.aws.amazon.com/workspaces/latest/adminguide/byol-windows-images.html
- AWS — WorkSpaces bundles/Windows Server availability: https://docs.aws.amazon.com/workspaces/latest/adminguide/amazon-workspaces-bundles.html

**Nie jest to potwierdzenie licencjonowania konkretnego dostawcy oprogramowania notarialnego.**
