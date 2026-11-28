# Pomocnik na pulpicie: Klikamy w programie kancelaryjnym (Rejent)

Stan: prototyp (28.11.2026). Kod i testy z atrapą są gotowe. Próba z prawdziwym
programem kancelaryjnym czeka na dostęp: `docs/czeka-na-dostep.md`, NA-21.

## Co to robi

Notariusz pisze w notarai, co ma się stać w jego programie kancelaryjnym,
np. „dodaj w repertorium nową czynność dla tej sprawy”. Pomocnik na jego
komputerze odczytuje okno programu, model w notarai (Bedrock, eu-central-1)
wybiera kolejny krok, a pomocnik go wykonuje. Po każdym kroku widać, co zrobił.

To ta sama pętla co Klikamy w przeglądarce (`pomocnik/klikamy.py`). Zmienia się
tylko „ręka”: zamiast przeglądarki (CDP) jest okno programu Windows, które
pomocnik prowadzi przez **winapp CLI** Microsoftu (`winapp ui …`, UI Automation).

| Część | Plik |
|---|---|
| Okno programu w kształcie strony dla Klikamy, wywołania winapp, blokady pulpitu | `pomocnik/pulpit.py` |
| Wykonawca zlecenia `pulpit` | `pomocnik/zadania.py` (`pulpit`) |
| Zgoda na program przy komputerze | `notarai-pomocnik.exe --zezwol-program Rejent` (`pomocnik/__main__.py`) |
| Zlecenie z notarai | `POST /api/sprawy/{sprawa}/pulpit` `{"cel": "...", "program": "Rejent"}` (`app.py`) |
| Testy z atrapą winapp | `test_pomocnik_pulpit.py` |
| Próba na prawdziwym Windowsie (Notatnik) | `tests/test_pulpit_windows.py`, zadanie `pulpit-winapp` w `.github/workflows/pomocnik-windows.yml` |

## Jak pomocnik używa winapp

- Uruchamia wyłącznie `winapp.exe`: z `NOTARAI_WINAPP`, z
  `%LOCALAPPDATA%\notarai\winapp\winapp.exe` albo z PATH. Nakładkę `winapp.cmd`
  z npm zamienia na prawdziwy plik z `node_modules\@microsoft\winappcli\bin\<arch>\`.
  Przez `.cmd` argumenty szłyby przez `cmd.exe`, a w argumentach jest wpisywany
  tekst, więc `&` albo `%` w nazwisku stałyby się poleceniem.
- Każde wywołanie: `--json`, `WINAPP_CLI_TELEMETRY_OPTOUT=1`, wspólny
  `WINAPP_UI_WORKFLOW_ID` na cały przebieg, argumenty jako lista (bez powłoki),
  selektor i wartość za `--`.
- Polecenia: `status` (który proces), `inspect --app <PID>` (odczyt okien),
  `invoke --window <hwnd> --type <typ>` (klik), `get-property --property IsPassword`
  (sprawdzenie pola), `set-value` (wpis), `search` i `invoke --action select`
  (pozycja listy), `yield` (oddanie pulpitu).
- Format JSON zgodny z kopertą winapp v0.3.1+ (`windows[].elements[]`, zagnieżdżone
  `children`, błędy jako `{"error": {"code": ...}}` na stderr).

## Blokady (w mechanizmie, nie w poleceniu dla modelu)

Z Klikamy, bez zmian: podpis, płatności i usuwanie są zabronione; wysyłka
i zatwierdzenie wymagają jednorazowej zgody z telefonu; do pól hasła i PIN-u
nic nie wpisujemy; limit 20 kroków.

Dodatkowo na pulpicie:

1. **Tylko program, na który notariusz zgodził się przy tym komputerze.** Lista
   `programy_pulpitu` leży w `%LOCALAPPDATA%\notarai\pomocnik.json`. Serwer może
   program tylko wskazać, nie dopisać.
2. **Zakazane zawsze:** powłoki, eksplorator, narzędzia systemu, przeglądarki
   (mają własną drogę przez CDP), poczta i komunikatory, menedżery haseł,
   programy do podpisu kwalifikowanego, sam pomocnik i winapp.
3. **Proces, nie tytuł okna.** `winapp -a` dopasowuje też tytuł okna. Dlatego
   pomocnik sprawdza nazwę procesu w `status`, a dalej celuje w jego PID. Karta
   przeglądarki zatytułowana „Rejent” to nie Rejent.
4. **Dokładnie ten element.** Klik i wpis idą z `--window` i `--type`, więc
   winapp nie przeskoczy do innego okna ani do elementu nadrzędnego.
5. **„OK” i „Tak” oceniane razem z pytaniem okna.** Przycisk o nic niemówiącej
   nazwie dostaje jako kontekst tytuł i napisy swojego okna. „Tak” pod
   „Czy na pewno usunąć akt?” to usunięcie, więc pomocnik się zatrzymuje.
6. **Nieodwracalne czynności programu:** zamknięcie roku lub księgi, przywrócenie
   albo odtworzenie kopii, nadpisanie, odinstalowanie, wyjście z programu.
   Zatrzymanie zawsze, także ze zgodą.
7. **Pasek tytułu** (Zamknij, Minimalizuj) nie trafia do modelu.
8. **Nieczytelna nazwa przycisku** (zły znak po odczycie) to brak kliknięcia.
9. **Pole, o którym nie wiadomo, czy jest polem hasła,** to brak wpisu.

## Dane osobowe

- Do modelu (Bedrock w UE) trafia to, co widać w oknie programu: napisy
  i zawartość pól. Tak samo jak w Klikamy w przeglądarce.
- Do logów pomocnika i serwera trafiają nazwy poleceń winapp, kody błędów
  i liczby kroków. Nigdy nazwy elementów, wartości pól ani tytuły okien.
  Komunikat błędu winapp (może zawierać nazwę elementu) zastępujemy samym kodem.
- Wpisywany tekst idzie do winapp jako argument procesu. Widzi go tylko ten
  komputer, a telemetria winapp jest wyłączona.
- Pomocnik nie używa `screenshot` ani `record`.

## Czego jeszcze nie ma

- Przycisku zgody w oknie pomocnika. Na razie zgodę daje
  `notarai-pomocnik.exe --zezwol-program <nazwa procesu>` przy komputerze.
- Pola „Klikamy w programie” w interfejsie sprawy i w pilocie z telefonu.
  Na razie jest tylko endpoint.
- winapp w paczce pomocnika: dziś musi być zainstalowany na komputerze
  (licencja MIT pozwala go dołączyć).
- Mapy ekranów Rejenta. Zależy od tego, co program pokazuje przez UI Automation
  (NA-21, krok 1).
