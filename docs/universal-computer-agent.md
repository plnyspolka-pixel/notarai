# NotarAI Universal Computer Agent — jeden silnik dla dowolnego programu kancelaryjnego

**Status:** docelowy projekt MVP; **bez gotowego agenta, VM ani testu na żywym programie**.
**Decyzja (2026-11-22):** nie tworzymy odrębnego adaptera programistycznego dla RejNET, Notaris, Wolters Kluwer i pozostałych systemów. **Wdrażanie i obsługa mają automatyczne fallbacki od najbardziej bezobsługowej metody**: dokument nadrzędny `docs/fallback-policy.md`. Jeden uniwersalny silnik Computer Use pracuje na UI aplikacji. RejNET to wyłącznie **pierwsza aplikacja testowa**, nie zależność architektury.

## 1. Reguła nadrzędna: minimum wdrożenia

- Notariusz korzysta z NotarAI przez www; bez instalowania NotarAI na jego PC.
- Jeśli aplikacja jest desktopowa: dedykowana licencjonowana Windows VM + konto robota; uruchomienie programu kancelaryjnego na VM z autoryzowanym dostępem do danych kancelarii.
- Jeśli aplikacja jest webowa: priorytet dla bezpiecznej automatyzacji DOM/Playwright w odizolowanym browser workerze, bez kosztu Windows VM, chyba że wymaga komponentów Windows/podpisu.
- Nie narzucamy migracji repertorium do NotarAI, nie piszemy do nieudokumentowanych tabel bazy, nie reverse-engineerujemy logowania.
- *Prawdziwa przeszkoda* w "bez instalacji" to dostęp do istniejącej bazy: jeśli jest tylko lokalna, potrzeba autoryzowanego kanału sieciowego albo VM w sieci kancelarii; nie obiecujemy integracji bez konfiguracji.

## 2. Jeden engine, wielowarstwowa obserwacja i wykonanie

```text
NotarAI SaaS (zadania, uprawnienia, approval, tenant, AI)
    -> Job Queue -> Policy Gateway -> Windows/Browser Worker
        OBSERVE: UIA accessibility tree + aktualne okno + opcjonalny screenshot
        GROUND: dopasowanie celu do kontrolek; poziom pewności, wersja stanu ekranu
        ACT: preferuj Invoke/SetValue/Selection; następnie DOM; dopiero w fallback klik/klawiatura
        VERIFY: odczytaj nowy ekran/stan i sprawdź postcondition; inaczej STOP
        LEARN: zapisz *procedurę bez PII*, selektory semantyczne i reguły
    -> dokument / wynik / żądanie akceptacji -> panel NotarAI
```

**Silniki do porównania zamiast pisać nowe:**
1. Microsoft WinApp CLI / UI Automation — referencyjne podstawy Windows UIA; testy na legalnej testowej VM. 
2. Open-source: winuse (UIA, Java Access Bridge, WebView2, scenariusze replay), Okno (UIA + screenshot verification), windows-mcp-server (polityki, egress/audyt); traktować jako kandydatów do *audytu technicznego, licencji i supply chain*, nie zależności automatycznie akceptowane. Żaden projekt zewnętrzny nie może domyślnie otrzymać dostępu do danych kancelarii ani przekazywać screenshotów do zewnętrznego AI.
3. Playwright dla aplikacji webowych, jeżeli pozwala na to legalny i autoryzowany model dostępu.
4. CLI-Anything **nie jest wymagane**: nie rozwiązuje automatycznie nieznanego GUI i wymaga zwykle kodu źródłowego.

**Priorytet sposobu działania:** oficjalne API/import/eksport, gdy dostępne i bezpieczne -> DOM (web) -> UIA (desktop) -> UIA+vision (hybryda) -> sprawdzony click/type na aktualnym obrazie -> eskalacja do człowieka. Nie udostępniać otwartego shella, sieci ani dowolnych kliknięć sterowanych bez ograniczeń przez model.

## 3. Zero adapterów per program — profile i umiejętności

Zamiast `rejnet_adapter.py`, `notaris_adapter.py`:
- `capability_probe`: po pierwszym otwarciu rejestruje okna, technologię GUI, widoczne role kontrolek, tablice, menu, eksport/import, status dostępności (bez wartości PII).
- `app_profile`: nazwa aplikacji, fingerprint wersji UI, dozwolone okna/procesy, selektory semantyczne (AutomationId/Name/ControlType/pattern), reguły specyficznych dialogów, mapa terminów branżowych.
- `skill`: scenariusz semantyczny typu `find_case`, `read_case`, `prepare_document`, `export_draft`, `fill_draft`, `verify_case` z warunkami i weryfikacją.
- `learn_by_demonstration`: operator pokazuje jedną próbkę z fikcyjnymi danymi; system proponuje scenariusz i otrzymuje zatwierdzenie po powtórzeniu. *Nie zapisujemy skryptu współrzędnych jako uniwersalnej procedury*.
- `self_healing`: gdy UI się zmienia, agent ponawia bezpieczną obserwację, proponuje nowy selektor i weryfikuje; przy niejednoznaczności kończy bez akcji, wymaga ponownego przeszkolenia.
- Zatwierdzone skille globalne mają tylko strukturę i terminologię, bez danych konkretnych kancelarii i haseł. Uprawnienia / konfiguracja dostępu są zawsze per tenant.

**Ważny kompromis:** brak adapterów kodowanych per program nie oznacza braku jakiejkolwiek konfiguracji. Profil/walidacja per program (a często per wersja) pozostają konieczne, zwłaszcza dla złożonych tabel i czynności trwałych.

## 4. Kontrakt ogólny: planowanie, wykonanie, weryfikacja

```json
{
  "job_type": "find_case",
  "tenant_id": "<z kontekstu autoryzacji, nie od modelu>",
  "target_app": "<nazwa z inventory tenantowego>",
  "inputs": {"search": "<fikcyjne kryteria>"},
  "policy": {"mode": "read_only", "allowed_processes": ["<proces>"]},
  "preconditions": ["foreground_app_matches", "user_logged_in"],
  "postconditions": ["case_identifier_matches"],
  "on_uncertainty": "waiting_for_human"
}
```

Ten przykład to kontrakt koncepcyjny, nie działający endpoint.

Operacje: `observe`, `find_element`, `invoke`, `set_value`, `read_value`, `capture_redacted`, `verify`, `request_approval`, `stop`. Wszystkie wywołania mają `job_id`, `tenant` z uwierzytelnionego kontekstu, limit czasu, log bez PII i powiązanie z bieżącym stanem ekranu.

Nie implementować automatycznie `sign`, `submit`, `send`, `delete`, płatnych odpisów, obchodzenia CAPTCHA ani 2FA. Trwały zapis do repertorium dopiero po potwierdzonym odczycie sprawy, weryfikacji i approval. Przy nieznanym wyniku zapisu: `needs_reconciliation`, nigdy ślepy retry.

## 5. Onboarding kancelarii docelowo (minimum tarcia)

1. Kancelaria wskazuje, jakiego programu używa i gdzie ma dane.
2. NotarAI zapewnia oddzielne stanowisko (VM / browser worker). Administrator instaluje *normalnie* licencjonowany program; nie instalujemy NotarAI na PC notariusza.
3. Uprawniony pracownik autoryzuje osobne konto i prywatny dostęp do właściwych danych; klucze, PIN-y, 2FA notariusza nie trafiają do AI.
4. Robot automatycznie rozpoznaje UI i uruchamia read-only smoke test; w razie braku rozpoznania wykonuje demonstrację z użytkownikiem na danych testowych.
5. Notariusz uruchamia pierwszą bezpieczną czynność z przeglądarki; dopiero po wynikach testu włączamy akcje zmieniające stan.

**Stop conditions:** nie ma licencji/źródła danych/bezpiecznej sesji/czytelnych UI/zweryfikowanego wyniku -> wyświetlić diagnozę i ścieżkę ręczną; nie deklarować zgodności.

## 6. Instrumentacja jakości, nie marketing „każdy system”

Mierzyć na **co najmniej trzech różnych rzeczywistych programach**, wśród nich RejNET Office i jedna starsza aplikacja Windows:
- wykrycie i rozpoznanie okna, formularzy, tabel; odczyt dwóch fikcyjnych spraw;
- wykonanie „find/read/export draft” w różniących się UI;
- kompletność walidacji danych, odsetek zakończonych z weryfikacją, czas operatora na onboarding;
- błędy po zmianie rozdzielczości, restarcie sesji, modalnym oknie i wersji UI;
- zerowy brak autoryzacji przy operacjach formalnych, brak wycieku PII, rozdział tenantów.

**Kryterium akceptacji MVP:** jeden uniwersalny worker + jeden schemat komend, bez osobnych binarek adapterów, obsługuje dwa różne programy Windows na fikcyjnych danych; potwierdzone odczyt i eksport, odmowa niepewnych akcji i approval dla czynności trwałych. Trzeci program w testach kompatybilności. Skalę kompatybilności publikujemy dopiero po wynikach.

## 7. Główne ograniczenia realne

- Windows VM/sesja jest potrzebna dla desktopowego GUI; symulacja kliknięć wymaga interaktywnego pulpitu. Zablokowana sesja może obsłużyć część wzorców UIA, ale nie pełną obsługę wizualną.
- Program oparty o własny canvas, legacy kontrolki, Java bez Access Bridge, Citrix/RemoteApp lub technologię terminalową może wymagać innego poziomu dostępu.
- Wiele programów używa lokalnej bazy; dostęp do nich jest problemem sieciowym i licencyjnym, nie problemem samego Computer Use.
- Chmurowe VM, model AI, RDP, screenshoty i operator infrastruktury wymagają kontroli tajemnicy notarialnej, RODO oraz udowodnienia faktycznych granic dostępu. Nie deklarować zero-knowledge ani zero-operator-access na podstawie VM.

## 8. Źródła referencyjne

- UIA: https://learn.microsoft.com/en-us/windows/win32/winauto/uiauto-uiautomationoverview
- WinApp CLI: https://learn.microsoft.com/en-us/windows/apps/dev-tools/winapp-cli/ui-automation
- Unattended desktop flows: https://learn.microsoft.com/en-us/power-automate/desktop-flows/run-unattended-desktop-flows
- Silniki porównawcze: https://github.com/straygizmo/winuse ; https://github.com/vitalcc55/Okno ; https://github.com/deploymenttheory/windows-mcp-server

Zob. też `docs/virtual-employee-architecture.md` (VM i bezpieczeństwo) oraz `docs/rejnet-office-overlay.md` (RejNET jako **pilot kompatybilności**, nie osobny adapter).
