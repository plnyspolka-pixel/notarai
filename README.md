# notarai.pl

Lokalny asystent kancelarii notarialnej. Wgrywasz wzór aktu i skany sprawy,
opisujesz czego potrzebujesz — aplikacja odczytuje dane ze skanów, waliduje je
i przygotowuje projekt dokumentu do sprawdzenia.

**Projekt wymaga akceptacji notariusza. Aplikacja nie tworzy dokumentów gotowych
do podpisu.**

## Wymagania

- Windows 10/11
- Python 3.11 lub nowszy — https://www.python.org/downloads/
  (przy instalacji zaznacz „Add Python to PATH")
- Skonfigurowany profil AWS z dostępem do Bedrock w regionie `eu-central-1`

Sprawdzenie, czy AWS działa:

```powershell
aws sts get-caller-identity
```

## Uruchomienie

Dwuklik w `uruchom.bat`. Przy pierwszym uruchomieniu skrypt zakłada środowisko
i pobiera zależności — to trwa kilka minut. Potem otwiera przeglądarkę na
`http://127.0.0.1:8000`.

Zatrzymanie: `Ctrl+C` w oknie konsoli.

## Jak się tego używa

1. **Materiały sprawy** — wgraj wzór aktu i skany, opisz czego potrzebujesz
2. **Weryfikacja odczytu** — sprawdź odczytane pola, popraw co trzeba
3. **Projekt dokumentu** — pobierz jako Word, sprawdź, podpisz

Pola wymagające uwagi są oznaczone czerwoną krawędzią: błędna suma kontrolna,
niska pewność odczytu albo brak danych. Miejsca, których nie dało się wypełnić,
zostają w tekście jako `<<BRAK: nazwa pola>>`.

## Wzory aktów

Wzór to zwykły plik `.docx` lub `.txt` z miejscami do wypełnienia:

```
Dnia {{data czynnosci}} przed notariuszem {{notariusz}} stawili się:
1. [IMIĘ I NAZWISKO SPRZEDAJĄCEGO], PESEL {{pesel sprzedajacego}}
```

Obsługiwane są oba zapisy — `{{nazwa}}` i `[NAZWA]`. Nazwy pól mogą być dowolne;
aplikacja przekazuje je modelowi jako listę do odczytania. Jeśli nazwa zawiera
słowo `pesel`, `nip`, `kw`, `cena`, `kwota` lub `wartosc`, wartość zostaje
dodatkowo sprawdzona sumą kontrolną.

## Gdzie są dane

Zależnie od trybu (patrz `SAAS.md`):

- **tryb lokalny** (domyślny): wszystko zostaje na tym komputerze, w katalogu `dane/`,
- **tryb SaaS**: skany, odczyty i projekty trafiają zaszyfrowane do S3 w AWS
  (region eu-central-1), a dysk aplikacji jest tylko pamięcią podręczną.

Stopka w aplikacji pokazuje, który tryb jest w użyciu. To zapewnienie dla
notariusza o miejscu przechowywania danych, więc nie jest wpisane na sztywno.

Układ katalogów w trybie lokalnym:

```
dane/sprawy/<id>/  wzor.docx, skany/, sprawa.json, projekt.docx
```

Katalog `dane/` jest wykluczony z gita. **Nigdy go nie commituj** — historia
gita jest trwała i usunięcie pliku późniejszym commitem go nie kasuje.

Do Amazon Bedrock trafiają obrazy stron i treść wzoru jako pojedyncze wywołanie
API. Bedrock nie zapisuje promptów ani odpowiedzi. Nie włączaj w konsoli AWS
funkcji *model invocation logging* — zapisywałaby treść aktów do S3.

Zrób kopię zapasową katalogu `dane/`. Awaria dysku to utrata spraw w toku.

## Ustawienia

Zmienne środowiskowe, wszystkie opcjonalne:

| Zmienna | Domyślnie | Znaczenie |
|---|---|---|
| `AWS_REGION` | `eu-central-1` | region Bedrock |
| `PIECZAPP_MODEL` | `eu.anthropic.claude-opus-4-6-v1` | profil modelu |
| `PIECZAPP_HOST` | `127.0.0.1` | adres nasłuchu |
| `PIECZAPP_PORT` | `8000` | port |
| `PIECZAPP_DPI` | `300` | rozdzielczość renderowania PDF |
| `PIECZAPP_MAX_BOK` | `1568` (4.7+: `2576`) | najdłuższy bok obrazu, który model widzi bez pomniejszania |
| `PIECZAPP_MAX_PIKSELI` | `1150000` | największa powierzchnia obrazu widziana bez pomniejszania |
| `PIECZAPP_MAX_STRON` | `400` | limit stron na sprawę |
| `PIECZAPP_STRON_W_PACZCE` | `4` | ile kolejnych stron w jednym zapytaniu do modelu |
| `PIECZAPP_ROWNOLEGLE` | `2` | ile paczek stron czytanych jednocześnie |
| `PIECZAPP_MAX_WYJSCIE` | `128000` | limit odpowiedzi modelu w tokenach (maksimum Opus 4.6) |
| `PIECZAPP_MYSLENIE` | `1` | `0` wyłącza myślenie modelu |
| `PIECZAPP_WYSILEK` | `max` | domyślny wysiłek myślenia; przełącznik „Dokładność odczytu” zmienia go dla sprawy |

Aplikacja odmawia startu, jeśli model nie jest profilem `eu.` — zabezpieczenie
przed przypadkowym wyjściem poza Unię Europejską.

Zmiana `PIECZAPP_HOST` na `0.0.0.0` wystawia aplikację na sieć. Rób to
świadomie i nigdy nie przekierowuj tego portu na routerze.

## Dostęp do AWS bez codziennego logowania

`aws login` daje sesję na maksymalnie 12 godzin i tego nie da się wydłużyć.
Zamiast tego narzędzia na laptopie (AWS CLI, Claude Code, pieczapp) używają
dedykowanego użytkownika IAM ze stałym kluczem i uprawnieniami wyłącznie do
Bedrock w regionach UE. Konfiguracja jednorazowa:

1. Dwuklik w `infra\USTAW_DOSTEP_AWS.bat`.
2. Zaloguj się rootem w przeglądarce, gdy skrypt o to poprosi (ostatni raz).
3. Skrypt zakłada użytkownika `pieczapp-claude` (CloudFormation
   `infra\pieczapp-iam.yaml`), generuje klucz i zapisuje go w
   `~\.aws\credentials` jako profil `default`. Sekret nie jest wyświetlany.

Zasady bezpieczeństwa, bo klucz nie wygasa sam:

- klucz leży tylko w `~\.aws\credentials` na tym laptopie; nigdy nie kopiuj
  go do repozytorium, `.env`, maila ani czatu,
- włącz szyfrowanie dysku (BitLocker) i hasło do konta Windows,
- root konta AWS: włącz MFA i używaj go tylko w konsoli w przeglądarce,
- raz na kilka miesięcy wygeneruj nowy klucz (ponowne uruchomienie skryptu;
  gdy użytkownik ma już 2 klucze, usuń stary w konsoli IAM),
- jeśli laptop zginie, natychmiast dezaktywuj klucz w konsoli IAM
  (użytkownik `pieczapp-claude`, zakładka *Security credentials*).

## Gdy coś nie działa

**`python` nie jest rozpoznawany** — Python nie jest w PATH. Przeinstaluj
z zaznaczoną opcją „Add Python to PATH".

**`AccessDeniedException`** — brak dostępu do modelu na koncie AWS. Sprawdź
w konsoli Bedrock (region Frankfurt), czy profil `eu.` jest aktywny.

**`ExpiredTokenException`** / **`Your session has expired`** — profil AWS używa
sesji `aws login` (max 12 h). Jednorazowo uruchom `infra\USTAW_DOSTEP_AWS.bat`
(patrz niżej), żeby przejść na stały klucz użytkownika IAM.

**Model źle odczytuje skany** — sprawdź jakość skanu. Poniżej 200 dpi drobny
druk i pieczątki bywają nieczytelne. Popraw pole ręcznie w etapie 2.

## Testy

Uruchomienie testów:

```cmd
uruchom_testy.bat
```

Więcej informacji w [TESTY.md](TESTY.md).

## Struktura

```
app.py              serwer i endpointy
bedrock.py          wywołania modelu — ekstrakcja i generowanie
dokumenty.py        PDF/obrazy na strony, docx tam i z powrotem
walidacja.py        sumy kontrolne PESEL, NIP, KW, kwoty
ekw.py              treść księgi wieczystej z EKW przez dostawcę (Finance You albo Apify), na żądanie
krz.py, krz_portal.py  sprawdzenie w KRZ w przeglądarce notariusza
rejestry.py         ślad audytowy sprawdzeń w rejestrach
prompty.py          treść promptów
config.py           ustawienia
static/             interfejs
test_*.py           testy automatyczne (pytest)
SPEC.md             specyfikacja kolejnego etapu
CLAUDE.md           reguły dla Claude Code
TESTY.md            dokumentacja testów
```
