# NotarAI × RejNET Office — nakładka AI / Virtual Employee

**Status:** projekt integracji, bez uruchomionej VM ani integracji produkcyjnej. **Data:** 2026-11-22.
**Priorytet:** RejNET Office jest pierwszym docelowym adapterem dla NotarAI Virtual Employee (zastępuje robocze założenie „Notaris jako pierwszy” w etapie 0 `docs/virtual-employee-architecture.md`).

## 1. Rozróżnienie systemów i zakres

- **RejNET Office** — program kancelaryjny dostawcy z `rejnet.pl`; przedmiot niniejszej integracji.
- **Rejestry Notarialne KRN** — odrębny system rejestrów dostępny przez `rejestry-notarialne.pl`; NIE jest RejNET Office, choć istnieją powiązania serwisowe.
- Celem jest **nakładka nad istniejącym programem**, nie zastąpienie repertorium ani kopiowanie jego całej bazy.
- Notariusz używa webowego NotarAI. Na komputerze notariusza **nie instalujemy naszego oprogramowania**. W dedykowanej VM Windows kancelarii działa RejNET Office, agent sesji Windows oraz interfejs do NotarAI.
- Uwaga: pierwsze testy i instalacja programu wymagają legalnej kopii i sprawdzenia warunków licencyjnych producenta. Dostęp do bazy rzeczywistej kancelarii wymaga osobnego uzgodnienia.

## 2. Co potwierdzono w źródłach zewnętrznych

Starsze instrukcje producenta (2016) i dotyczące programu (2017) pokazują:
- aplikację z własnym interfejsem desktopowym Windows, moduł **Repertorium A**, wyszukiwanie i filtrowanie wpisów, formularze czynności oraz wydruki;
- współpracę z Microsoft Word;
- generowanie raportów i plików eksportowych (np. MsNOT24) oraz interakcje z odrębnymi portalami internetowymi;
- osobne czynności podpisania i wysyłki dokumentów.
**To dowody na istnienie przepływów GUI/eksportu w ówczesnych wersjach, NIE dowód, że aktualna wersja ma identyczne kontrolki, API, eksport lub zgodę licencyjną na VM.**

Nie potwierdzono: publicznego oficjalnego API RejNET Office, rodzaju współczesnej bazy, dostępnych mechanizmów importu, zasad licencji stanowiska VM, zakresu dostępności UI Automation. Tego nie wolno domniemywać.

Źródła:
- Strona dostawcy: https://rejnet.pl/
- Strona produktu widoczna w indeksie: https://rejnet.pl/737/Program%20RejNET%20Office%20dla%20notariuszy
- Instrukcja RejNET „Elektroniczne deklaracje PCC-2 i SD-2” (2016): https://rejnet.pl/plik/sysPlik/2239
- Instrukcja „Przygotowanie i wysyłka raportu MsNOT24” (2017): https://www.notariusz.pl/plik/sysPlik/3141

## 3. Docelowa architektura

```text
Notariusz -> NotarAI Web (sprawa + zadanie + zatwierdzenia)
   -> Virtual Worker API (Cognito, tenant/RBAC, kolejka, approval gates)
   -> broker (outbound mTLS, urządzenie przypisane do jednej kancelarii)
   -> Windows VM kancelarii (jedna kancelaria = jedna VM na MVP)
       -> Supervisor (usługa sesji, watchdog, health)
       -> Interactive Worker (dedykowane konto Windows)
           -> RejNET Adapter (.NET UI Automation/FlaUI)
           -> RejNET Office (legalna kopia, osobne konto/stanowisko)
           -> Microsoft Word / eksport plików
       -> zatwierdzony prywatny dostęp do danych kancelarii, jeśli konieczny
   -> wynik / dokument do kontroli -> panel NotarAI
```

**Preferencja technologiczna:** Windows UI Automation z kontrolkami i ich AutomationId/ControlType/Patterns; WinApp CLI do rozpoznania struktury; FlaUI lub natywne UIA do adaptera produkcyjnego. Fallback do sterowania myszką/klawiaturą tylko dla kontrolek nieobsługujących UIA. CLI-Anything opcjonalnie jako generator warstwy komend. Żadnego omijania logowania, 2FA, CAPTCHA, kontroli dostępu, limitów lub podpisu.

**Panel webowy:** dwie karty: „Zadania” (wyniki, akceptacje, historia) oraz opcjonalny „Podgląd stanowiska” (bezpośredni widok kontrolowany z VM, ograniczony rolami, domyślnie wyłączony). To nie jest osadzanie aplikacji desktopowej w iframe. Operator NotarAI nie ma domyślnego dostępu do podglądu danych kancelarii.

## 4. Zakres adaptera i stany

### Wersja 0 — wyłącznie odczyt / rozpoznawanie (bez zapisu)
- `rejnet.get_capabilities()`
- `rejnet.get_ui_state()` (bez kopiowania danych klientów do logów)
- `rejnet.find_case(filters)` — tylko po potwierdzeniu widocznych kryteriów
- `rejnet.read_case(case_ref)` — zwrot danych tylko do autoryzowanej sprawy i tenantu
- `rejnet.export_draft(case_ref, format)` — wyłącznie jeśli aktualna wersja wspiera eksport i uprawnienia na to pozwalają

### Wersja 1 — szkic / pod kontrolą człowieka
- `rejnet.prepare_case_draft(payload)`
- `rejnet.fill_case_draft(payload, dry_run=true)`
- `rejnet.validate_screen(expected_case_ref)` przed i po operacji
- `rejnet.request_approval(action_summary)` przed zmianą trwałą
- `rejnet.commit_approved_draft(approval_id)` wyłącznie przy jednoznacznej polityce i potwierdzonym idempotentnym wykonaniu

**Nie udostępniać agentowi:** `sign`, `submit`, `send`, `delete`, dostępu do prywatnego PIN-u/klucza podpisu, arbitralnego shell ani arbitralnych współrzędnych kliknięć. Czynności wymagające działania notariusza kończyć w stanie `waiting_for_human`.

**Model stanów:** `queued -> running -> waiting_for_human -> completed`; błędy `failed / cancelled / needs_reconciliation`. Zanim robot coś zapisze, upewnić się, że tytuł/identyfikator aktualnie otwartej sprawy zgadza się z jobem. Gdy nie wiadomo, czy zapis się udał, bez automatycznej ponownej próby.

## 5. Kolejność prac (bez prawdziwych danych na początku)

1. **Kwalifikacja RejNET Office:** aktualny instalator/wersja, warunki korzystania, licencja dodatkowego stanowiska na VM, typ Windows, Word i sposób łączenia z bazą.
2. **VM demo w UE:** dedykowana VM i konto robota; osobny profil, bez danych produkcyjnych; sesja interaktywna niezależna od RDP administratora.
3. **Read-only UIA discovery:** uruchomienie aktualnego programu i inspekcja okien/kontrolek; zanotować nazwy menu, AutomationId, patterns oraz zmiany po otwarciu repertorium. Nie eksportować treści pól i nazwisk do repozytorium.
4. **Pierwszy scenariusz E2E:** wyszukaj fikcyjną sprawę -> odczytaj uprawnione pola -> wygeneruj testowy dokument/raport, o ile program to wspiera -> przekaż wynik do NotarAI.
5. **Drugi scenariusz E2E:** wypełnienie fikcyjnego formularza jako szkic, porównanie wartości, kontrolowany STOP przed zapisem.
6. **Fault injection:** utrata aktywnego okna, restart VM, inne okno modalne, rozłączenie sesji, timeout, niejednoznaczny zapis; sprawdzenie zatrzymania bez szkody i audytu bez PII.
7. **Dopiero potem** produkcyjny tenant, uzgodniony prywatny dostęp do bazy, zakres upoważnienia i ocena RODO/tajemnicy notarialnej.

Kryterium ukończenia MVP: obsługa rzeczywistej, legalnej i aktualnej instalacji RejNET Office na VM z fikcyjnymi danymi, potwierdzone read-only `find_case/read_case`, jeden eksport testowy albo udokumentowana alternatywa, pełny audyt i bezpieczne zatrzymanie na niejednoznacznych ekranach.

## 6. Ograniczenia i środki ochrony

- **Nie zakładać centralnej bazy w chmurze:** ustalić faktyczną topologię RejNET Office i możliwości przyłączenia dodatkowego stanowiska. Bez autoryzowanego połączenia do bazy kancelarii robot zobaczy tylko własne dane testowe.
- Własna VM per kancelaria w UE, tożsamość urządzenia, szyfrowanie, ograniczony egress, brak publicznego RDP.
- Windows session 0 nie nadaje się do operacji interfejsu użytkownika; worker w interaktywnej sesji.
- Brak niezależnego podpisywania czynności przez agenta, brak PIN-ów, brak automatycznej pracy na cudzej tożsamości.
- Minimalizacja danych i ekranów, nie przechowywać pełnych screenshotów ani nazwisk w logach; używać dedykowanych, kontrolowanych ścieżek wymiany dokumentów.
- Interfejs RejNET może się zmieniać: wersjonowanie mapy kontrolek, testy regresji i bezpieczne wyłączenie niezgodnego adaptera.
- Warunki VM/hostingu i automatyzacji muszą być zgodne z licencją programu oraz Windows. Robot nie ma szczególnego statusu prawnego „pracownika”.

## 7. Pierwszy brakujący zasób

Do rozpoczęcia faktycznej implementacji UIA potrzebna jest legalna **testowa instalacja RejNET Office**, numer wersji i możliwość uruchomienia jej na Windows VM z fikcyjnymi danymi. Zanim to dostaniemy, można przygotować interfejs adaptera i symulator aplikacji, ale nie wolno twierdzić, że integracja z RejNET działa.
