# Praca w programach kancelaryjnych z poziomu notarai

Notariusz zleca w notarai pracę w **dowolnym programie na swoim komputerze**,
np. „w programie kancelaryjnym otwórz repertorium A i znajdź ostatni akt z tego
miesiąca”. Robi to pomocnik notarai, ten sam jeden plik `.exe`, który już
obsługuje KRZ i Klikamy.

## Ścieżka notariusza (najkrótsza możliwa)

1. **Pobiera jeden plik** `notarai-pomocnik.exe` z kreatora w notarai i go
   uruchamia. Pomocnik instaluje się sam, bez uprawnień administratora, i dodaje
   się do autostartu (`pomocnik/instalacja.py`).
2. **Klika „Połącz”** w notarai przy kodzie, który pokazał pomocnik. Nie
   przepisuje żadnego tokenu (`urzadzenia.py`).
3. W **Klikamy → „W programie na komputerze”** klika **„Rozpoznaj programy”**.
   Pomocnik sam znajduje programy kancelaryjne i biurowe i dla każdego sam wybiera
   sposób połączenia.
4. Wybiera program z listy, pisze polecenie i patrzy, jak pomocnik pracuje.
   Po każdym kroku widzi, co pomocnik zrobił i dlaczego.

Notariusz nie musi wiedzieć, jak nazywa się jego program, gdzie jest
zainstalowany ani czy ma bazę ODBC.

## Jak pomocnik sam wybiera metodę połączenia

`pomocnik/programy.py` czyta spis „Aplikacje i funkcje” z rejestru Windows,
źródła ODBC i zarejestrowane serwery COM. Dla każdego programu ustala, które
drogi są dostępne, i wybiera najpewniejszą:

| Metoda | Kiedy jest wykrywana | Do czego najlepsza | Stan |
|---|---|---|---|
| `baza` | źródło ODBC pasujące do programu albo plik bazy (`.fdb`, `.mdb`, …) w katalogu programu | czytanie (repertorium, lista czynności), tylko odczyt | wykrywana, wykonanie po próbie na żywo |
| `pliki` | katalog `Eksport` / `Import` / `Wymiana` | wymiana danych | wykrywana, wykonanie po próbie na żywo |
| `com` | Word / Excel / ProgID wydawcy | pewne sterowanie dokumentem | wykrywana, wykonanie po próbie na żywo |
| `okna` | każdy program z oknem | **uniwersalna**: dowolna czynność w oknie | **działa** (`pomocnik/uia.py`) |

`okna` to **Windows UI Automation**, czyli interfejs dostępności, z którego
korzystają czytniki ekranu dla niewidomych. Program nie musi nic o nas
wiedzieć ani udostępniać kodu. To właściwie „wiersz poleceń dla dowolnego
programu”, budowany na żywo. Narzędzia w rodzaju CLI-Anything generują takie
polecenia z **kodu źródłowego** programu, więc nie zadziałają z zamkniętym
programem kancelaryjnym. UI Automation działa.

Czego świadomie nie robimy: klikania „w punkt x,y” na zrzucie ekranu. To
zgadywanie, a w księdze notarialnej różnica między pomyłką a jej brakiem.

## Zabezpieczenia (w mechanizmie, nie w poleceniu dla modelu)

`pomocnik/w_programie.py`:

- model wybiera kontrolkę z ponumerowanej listy, nigdy współrzędne,
- **nie kliknie** niczego, co zapisuje, zatwierdza, księguje, nadaje numer,
  drukuje, importuje, usuwa, wysyła ani podpisuje. W programie kancelaryjnym
  zapis nadaje numer w repertorium, więc zapisuje notariusz,
- „OK” albo „Tak” w okienku, które pyta o taką czynność, też jest zablokowane,
- dozwolone są tylko klawisze nawigacyjne (Tab, strzałki, Esc), bez Entera,
  bo Enter potrafi zatwierdzić okno,
- do pola hasła nic nie wpisze, a sprawdza to i silnik, i backend UIA,
- nie wychodzi poza okna wskazanego programu,
- wykonuje najwyżej 20 kroków,
- serwer wskazuje program **tylko identyfikatorem** ze spisu. Który plik
  uruchomić, pomocnik ustala sam u siebie, więc notarai nie może kazać mu
  uruchomić dowolnego pliku,
- dostęp serwisowy administratora nie steruje programami kancelarii
  (`/api/programy` w `_POZA_SERWISEM`, a zlecenie w sprawie zwraca 403),
- do notarai idą nazwy programów i metod. Nie idą ścieżki, nazwy plików ani
  nazwy źródeł ODBC (bywa w nich nazwisko notariusza). W logach są tylko
  rodzaje czynności i liczby.

Model (Bedrock, eu-central-1) stoi po stronie serwera, tak jak w Klikamy.
Widzi tekst okna, czyli także dane z repertorium. To ten sam zakres
przetwarzania co odczyt dokumentów sprawy w notarai, objęty umową powierzenia.

## „Z chmury, bez instalowania czegokolwiek”: co się da, a co nie

**Program zainstalowany na komputerze notariusza nie da się sterować z chmury
bez niczego na tym komputerze.** Przeglądarka i strona internetowa nie mają
dostępu do okien Windows. To celowe zabezpieczenie systemu, a nie brak
w notarai. Rozszerzenie przeglądarki też go nie ma: Native Messaging wymaga
zainstalowanego programu po stronie Windows.

Są dwie drogi, które dają efekt „z chmury”:

1. **Program kancelaryjny w pulpicie w chmurze (wariant „turbo”).**
   Program i jego baza chodzą na maszynie Windows w AWS eu-central-1
   (np. Amazon AppStream 2.0 albo WorkSpaces). Notariusz otwiera go
   **w przeglądarce**, bez instalacji. Pomocnik notarai działa na tej maszynie
   w chmurze, więc na komputerze kancelarii nie ma niczego. Kod pomocnika
   jest ten sam, zmienia się tylko miejsce, gdzie stoi.
   Do ustalenia przed startem:
   - czy licencja programu kancelaryjnego dopuszcza pracę na serwerze
     terminalowym lub w chmurze (pytanie do producenta),
   - przeniesienie bazy programu do chmury albo VPN do kancelarii,
   - koszt za godzinę pracy maszyny i licencje dostępu pulpitu (do wyceny),
   - zgoda notariusza, bo to nowy zasób z danymi osobowymi (zasada z `CLAUDE.md`).

   Pozycja testu: `docs/czeka-na-dostep.md`, NA-16.
2. **Jeden plik `.exe` (to, co jest teraz).** Minimum po stronie notariusza:
   jedno pobranie, jedno kliknięcie „Połącz”, bez administratora i bez
   instalatora z dziesięcioma ekranami.

## Pliki

- `pomocnik/programy.py`: rozpoznanie programów i wybór metody
- `pomocnik/w_programie.py`: pętla agenta i zabezpieczenia
- `pomocnik/uia.py`: Windows UI Automation (biblioteka `uiautomation`)
- `pomocnik/zadania.py`: zlecenia `programy` i `program`
- `app.py`: `/api/programy`, `/api/programy/rozpoznaj`,
  `/api/sprawy/{id}/program`, `/api/pomocnik/program/{zlecenie}/krok`
- `prompty.PROGRAM`, `bedrock.nastepny_krok_w_programie`
- `static/index.html`: Klikamy → „W programie na komputerze”
- testy: `test_pomocnik_programy.py`
