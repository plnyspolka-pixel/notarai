# NotarAI — polityka fallbacków i minimalnego wdrożenia

**Data:** 2026-11-22
**Decyzja:** jeden ogólny silnik Computer Use do dowolnego autoryzowanego programu, z automatycznym wyborem najprostszej dostępnej techniki. Dotyczy programów desktopowych, webowych, terminalowych, starszych i niestandardowych. **Cel to maksymalna kompatybilność, nie obietnica 100% skuteczności bez testów.**

## 1. Dwa niezależne łańcuchy fallbacków

### A. Jak uruchomić środowisko — od najmniejszego tarcia dla kancelarii

1. **Istniejące oficjalne API/webhooks/import-eksport dostępne sieciowo.** Ominięcie GUI i Windows VM, gdy funkcja dostępna. Nie integrować się bez autoryzacji lub łamać umowy licencyjnej.
2. **Izolowany browser worker w NotarAI** dla aplikacji webowej; Playwright/DOM, bez instalacji na PC kancelarii. Odrębny profil i konto pracownika.
3. **Hostowana Windows VM per kancelaria** dla programu desktopowego: instalujemy legalny klient programu w VM, a notariusz korzysta z NotarAI przez www. To tryb preferowany desktop.
4. **Windows VM w sieci kancelarii** jeśli baza i program nie zezwalają na dostęp z hostowanej VM; nadal bez NotarAI na komputerze notariusza, ale wymaga lokalnej infrastruktury.
5. **Dopuszczony wąski konektor sieciowy / agent na serwerze kancelarii**, tylko gdy nie da się inaczej zapewnić zdalnego dostępu do bazy; nie instalować pełnego NotarAI na stanowiskach.
6. **Odrębny proces prowadzonej ręcznie konfiguracji / brak integracji**, jeśli licencja, dostęp do danych albo bezpieczeństwo blokują warianty techniczne.

Wyboru dokonuje onboarding na podstawie: rodzaju aplikacji, oficjalnych interfejsów, licencji, położenia bazy, wymaganego pulpitu Windows, dostępu do konta technicznego i prawnych granic przetwarzania.

### B. Jak wykonać czynność — od najmniej awaryjnej / bezobsługowej

1. `native_api`: oficjalne API / dozwolony konektor, wsparcie importu/eksportu.
2. `web_dom`: DOM i accessibility tree w przeglądarce (Playwright).
3. `windows_uia`: Microsoft UI Automation (WinApp CLI / FlaUI / UIA).
4. `uia_vision`: połączenie struktury UIA i obrazu.
5. `visual_computer_use`: analiza obrazu + ruchy myszy i klawiatury.
6. `guided_demonstration`: odtworzenie zweryfikowanej procedury pokazanej przez pracownika, najlepiej na danych fikcyjnych.
7. `human_handoff`: kontrolowane przejęcie zadania, gdy pozostałe metody zawodzą.

W praktyce poziom 6 jest **metodą pozyskania/naprawy skilla**, nie autonomicznym zapisem; wykonanie nowego skilla wraca do jednej z metod 1–5 i przechodzi testy. Na poziomie 7 robot nie wykonuje zakazanych czynności; przekazuje kontekst i oczekuje uprawnionej osoby.

**Ważne:** brakuje dostępu do bazy/licencji? To problem łańcucha środowiska A, nie pretekst do przeskoku z API do vision. Żadna metoda nie obchodzi logowania, CAPTCHA, PIN, 2FA ani ograniczeń uprawnień.

## 2. Samokonfiguracja i profil aplikacji

Po uruchomieniu:
- inventory aplikacji, wersji, otwartych okien i wspieranych interfejsów;
- `capability_probe` per metoda, z kontrolą, że jest *read-only*;
- wyszukaj znany profil w katalogu ogólnym (bez danych klienta), sprawdź fingerprint wersji i UI;
- jeśli profil niedostępny: read-only discovery automatyczne, a gdy nadal niewystarczające: pokazanie czynności przez użytkownika na danych testowych;
- zapis sprawdzonego skilla i warunków weryfikacji; nie zapisywać haseł, danych klientów ani współrzędnych jako jedynego selektora;
- nowe wersje aplikacji zawsze wymagają smoke-testu; fałszywy match to zatrzymanie.

Nie utrzymujemy osobnych binarek adapterów dla każdego programu. Mogą istnieć **niewielkie profile reguł** dla powtarzalnych niestandardowych ekranów.

## 3. Polityka przechodzenia do kolejnej metody

- Każda metoda ma preconditions, `supports()`, `perform()`, `postcondition_verified`, `clean_state_confirmed`.
- Nie udostępniać modelowi możliwości zmiany kolejności fallbacków, `tenant_id`, ryzyka ani `approval_id`.
- Fallback jest dozwolony po `unavailable` / `recoverable_failure` **gdy** brak efektów ubocznych lub stan został jawnie przywrócony i potwierdzony.
- Odczyt może przejść do następnej metody po braku wyniku; nie tracić kontroli nad granicami danych.
- Szkice/formularze/zapisy: nie przechodzić dalej po niejednoznacznym efekcie. `needs_reconciliation` i kontrola stanu, nigdy „spróbuj drugi raz” na ślepo.
- Jawna odmowa autoryzacji/polityki, brak licencji lub próba obejścia zabezpieczenia = **stop**, nie fallback.
- Formalne wysyłanie, podpisywanie, operacje z podpisem kwalifikowanym i płatne pobrania = jawne działanie uprawnionego człowieka, nie samodzielne kliknięcie robota.
- Audit techniczny nie zawiera PESEL/treści dokumentów/screenshotów/haseł. Wyniki mogą zawierać PII wyłącznie w autoryzowanym, chronionym kanale zadania.

**Kod początkowy:** `computer_use/fallback_router.py` (niezależny od provider SDK). Testy: `tests/test_computer_use_fallback_router.py`. Jest to **router wstępny**, nie gotowy worker dla Windows/Playwright.

## 4. Kolejność implementacji, żeby nie pisać wszystkiego naraz

1. Działa jeden router i kontrakt, bez szczególnych reguł per program.
2. Pierwszy backend `web_dom` na fikcyjnej stronie demo. Weryfikuje postconditions.
3. Backend `windows_uia` na testowej Windows VM (najpierw przykładowy program Windows i RejNET, jeśli jest licencja).
4. Hybrydowy backend obrazu i `visual_computer_use` dla celowo utrudnionego interfejsu.
5. Warstwa nauki przez demonstrację i katalog profili, walidacja kompatybilności na min. trzech aplikacjach.
6. Onboarding i automatyczny wybór hostingu, połączenia do danych i technologii; pomiar czasu ludzkiej konfiguracji.
7. Dopiero potem obsługa danych produkcyjnych, oddzielny audyt bezpieczeństwa i zgodności.

Wszystkie backendi muszą stosować te same zasady autoryzacji, verify/rollback, idempotencji i bezpiecznego zatrzymania. Nie dopuszczać fallbacku generującego zapis, gdy próba wcześniejsza może już mieć trwały skutek.

## 5. Kontrakt MVP i metryki

- Brak wymagania kodowania adapterów specyficznych dla RejNET/Notaris/Wolters Kluwer.
- Test funkcjonalny: `find_case`, `read_case`, `export_draft` na co najmniej dwóch różnych programach w izolowanym środowisku.
- Testy awarii: popup, zmiana okna, utrata sesji, zmieniony fingerprint GUI, timeout po zapisie, żądanie czynności bez uprawnień.
- Telemetria: wybrana metoda, liczba fallbacków, skuteczność weryfikacji, czas onboardingu, interwencje człowieka, błędy z niejednoznacznym skutkiem. **Bez danych osobowych**.
- Test izolacji tenantów, minimalnych uprawnień i braku podejmowania ryzykownych czynności bez jawnej autoryzacji.

**Zasada produktu:** każde nowe oprogramowanie ma być przyjmowane przez automatyczne rozpoznanie i istniejące backendi. Niestandardową obsługę tworzymy dopiero, kiedy uniwersalne mechanizmy wyczerpią możliwości.
