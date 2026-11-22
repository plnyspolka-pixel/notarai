# NotarAI Universal Computer Agent — implementation v0.2

**Status 2026-11-22:** modularny **kod wykonawczy** + testy jednostkowe i mock-integration, bez działającej Windows VM / rzeczywistego RejNET / podpisów / produkcyjnego połączenia z NotarAI API. PR #63 jest draft. **NIE twierdzić, że NotarAI już obsługuje RejNET lub każdy program notarialny.**

## Jak działa kod

```
computer_use/
  fallback_router.py   # preferencje native_api > web_dom > windows_uia > vision > człowiek
  deployment.py        # dobór hostingu z potwierdzonych zdolności
  profiles.py          # uniwersalny, deklaratywny profil: web URL, Windows app, selektory
  profile_loader.py    # podpis HMAC-SHA256 + powiązanie profilu z tenantem
  browser.py           # Playwright: odczyt i testowane wypełnienie szkicu
  winapp.py            # Microsoft WinApp CLI: get-value / set-value + weryfikacja
  discovery.py         # read-only inspect UIA, minimalizacja danych, kandydaci AutomationId
  worker.py            # 1 tenant + 1 sesja + allowlista aplikacji + router

tests/
  test_computer_use_fallback_router.py
  test_computer_use_backends.py
  test_computer_use_worker.py
  test_computer_use_discovery.py
  test_computer_use_profile_loader.py
```

**Kluczowe:** kod jest niezależny od producenta programu i nie zawiera osobnych adapterów dla RejNET/Notaris/Wolters Kluwer. Zmieniamy profil i środowisko, nie implementację.

## Fallbacki — wykonanie

1. Oficjalne API/import/export (router przewiduje provider, ale jeszcze go NIE zaimplementowano).
2. Playwright, jeśli program jest webowy, wspiera zaufany profil i autoryzowany kontekst przeglądarki.
3. WinApp CLI UI Automation, jeśli program jest desktopowy i działa w uprawnionej sesji Windows.
4. UIA+vision, pełny Computer Use, uczenie z demonstracji — **zaplanowane, jeszcze bez backendów**.
5. Human handoff: router zwraca odpowiedni stan, bez prób obejścia uprawnień.

Zmiana metody po błędzie odczytu jest dopuszczalna. Nie przechodzić do następnej metody po niepewnym `set-value`/nieudanym potwierdzeniu; wynik `needs_reconciliation`. Przy odmowie polityki albo redirect poza dozwolony origin: **stop**.

## Fallbacki — środowisko

`choose_runtime(Capabilities(...))` używa zweryfikowanych informacji: oficjalne API -> chmurowa przeglądarka -> hostowana VM Windows -> VM w sieci kancelarii -> wąski lokalny konektor -> konfiguracja człowieka. To **planner, nie automatyczne provisionowanie chmury**. Żadnej VM nie utworzono.

## Uruchomienie testowe Windows (bez PII)

1. Przygotować licencjonowaną testową VM z **działającym programem**, zwykłym kontem Windows operatora i fikcyjną sprawą. Uprawnienia/licencję systemu kancelaryjnego sprawdzić przed instalacją.
2. Zainstalować WinApp CLI na Windowsie ze wspieranej dystrybucji Microsoftu i potwierdzić `winapp ui --help`.
3. Z testowej sesji Windows uruchomić: `python -m examples.computer_use_windows_probe --app notepad` (najpierw uruchomić Notatnik). Skrypt uruchamia jedynie `inspect --interactive --json` i wypisuje **zagregowane liczby**, bez danych klientów. Następnie powtórzyć na programie kancelaryjnym z danymi fikcyjnymi.
4. Po inspekcji utworzyć zaufany profil (nazwy kontrolek, wybrane `AutomationId`). Skrypt nie zapisuje niezweryfikowanych mapowań automatycznie.
5. Uruchomić `TenantWorker` tylko w sesji przypisanej do jednej kancelarii, z profilem i `tenant_id` dostarczonymi przez **uwierzytelniony control plane**. Nie przyjmować `tenant_id`, URL, selektorów, kluczy HMAC od modelu.

## Minimalny przykład użycia API Python z fikcyjnymi danymi

```python
from computer_use.profiles import AppProfile, Element
from computer_use.worker import TenantWorker
from computer_use.fallback_router import AutomationRequest, Risk

profile = AppProfile(
    app_id='test_notepad', windows_app='notepad',
    fields={'tekst': Element('uia', 'Text editor', value_mode='input')}
)
worker = TenantWorker(tenant_id='demo_tenant', profiles={'test_notepad': profile})
request = AutomationRequest(
    job_id='demo-001', tenant_id='demo_tenant', app_id='test_notepad',
    risk=Risk.READ_ONLY, action='read_field', payload={'field': 'tekst'}
)
result = worker.execute(request)
# Dane wyniku przekazać wyłącznie chronionym kanałem zadania, NIE do logów.
print(result.outcome.value)
```

Nazwy kontrolek są **przykładowe**; należy sprawdzić je na rzeczywistej, uruchomionej aplikacji. Backend WinApp zadziała tylko, kiedy WinApp CLI jest zainstalowany na Windows, a docelowa aplikacja jest dostępna w sesji operatora.

## Kontrolowane szkice

`fill_draft_field` wymaga w profilu `Element(value_mode='input', allow_draft_fill=True)`, `Risk.DRAFT` i odczytu potwierdzającego wartość po zmianie. W nowym programie flagę można włączyć **dopiero po stwierdzeniu, że dane pole nie wykonuje automatycznego trwałego zapisu**. Nie jest implementacją zapisu repertorium. `Risk.WRITE` i `Risk.EXTERNAL` nie mają obecnie żadnego dostępnego providera i nie powinny być udostępniane agentowi.

## Profil podpisany i zakres zaufania

`load_verified_profile(raw, signature, signing_key, tenant_id=...)` waliduje schemat, HMAC i tenant oraz tworzy `AppProfile`. Klucz HMAC musi pochodzić z runtime secrets/KMS (nigdy z repozytorium, promptu ani modelu). Kod **nie tworzy** podpisów na podstawie niezaufanej konfiguracji. Nie zmienia podpisanych profili automatycznie po wykryciu nowego interfejsu.

## Ograniczenia / kolejne prace

- Brak uruchomionej Windows VM i licencjonowanego programu kancelaryjnego na testach live.
- Brak modelu vision, screenshot redaction, generowania procedur przez demonstrację i generycznego workflow na wiele ekranów.
- Brak produkcyjnego mechanizmu uwierzytelnienia zadań, brokera VM, kolejki, podpisanej polityki wykonania i sekretów na workerze; `TenantWorker` jest **biblioteką**, nie niezależną usługą sieciową.
- Playwright wymaga osobnego kontekstu uwierzytelnionej kancelarii (dostarczanego przez środowisko), zablokowanego service worker i **egress deny-by-default** również w infrastrukturze. Warstwa `page.route` nie jest pełną zaporą sieciową, zwłaszcza dla WebSockets i DNS.
- Programy desktopowe mogą nie udostępniać wartości przez UIA, wymagać aktywnego pulpitu i posiadać lokalne bazy. Potrzebne fallbacki wizualne i odpowiedni dostęp sieciowy.
- Przed produkcją wykonać testy E2E na **min. dwóch odmiennych aplikacjach**, z zapewnieniem legalnej instalacji, bez danych prawdziwych klientów.
- Nie deklarować Zero Knowledge / Zero Operator Access bez odrębnego audytu, izolacji kluczy i dowodów.

## Źródła
- Microsoft: https://learn.microsoft.com/en-us/windows/apps/dev-tools/winapp-cli/ui-automation
- Playwright: https://playwright.dev/python/docs/locators
- Repo: `docs/fallback-policy.md`, `docs/universal-computer-agent.md`.
