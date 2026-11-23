# Rozszerzenie notarai do Chrome i Edge

Pole polecenia notarai w panelu bocznym, obok strony urzędu albo rejestru.
Notariusz pisze, co ma się stać na otwartej stronie, a asystent wykonuje to
krok po kroku w tej samej karcie. Zastępuje sekcję „Klikamy” pomocnika
(`pomocnik/`, pobierany plik `.exe`) i nie wymaga instalowania programu.

## Dlaczego rozszerzenie, a nie okno w notarai

- Portale urzędowe zabraniają osadzania w ramce (`X-Frame-Options`,
  `frame-ancestors`), więc zwykły `iframe` w notarai pokazałby pustą stronę.
- Rozszerzenie pracuje w zwykłej przeglądarce notariusza: z jego sesją,
  certyfikatem, kartą i wtyczką podpisu. Serwis widzi zwykłą wizytę.
- Podpis elektroniczny zostaje tam, gdzie był. Asystent zatrzymuje się przed
  każdym przyciskiem, który wysyła, składa, podpisuje albo płaci, i oddaje
  stery. „Podpisz” klika notariusz; okno PIN-u należy do programu podpisu
  i rozszerzenie nie ma do niego dostępu.

## Jak to działa

| Plik | Rola |
|---|---|
| `manifest.json` | Manifest V3. Stały dostęp tylko do `app.notarai.pl`; do stron urzędów za zgodą, strona po stronie. Bez uprawnienia `debugger`. |
| `tlo.js` | Kliknięcie ikony otwiera panel boczny. |
| `panel.html`, `panel.js`, `panel.css` | Panel: łączenie z kancelarią, pole polecenia, lista kroków. |
| `silnik.js` | Pętla i zabezpieczenia (odpowiednik `pomocnik/klikamy.py`). Bez `chrome.*` i DOM. |
| `strona.js` | Odczyt strony i czynności przez `chrome.scripting`, we wszystkich ramkach. |
| `notarai.js` | Rozmowa z serwerem: łączenie kodem, pytanie modelu o krok, kolejka zleceń. |
| `krz.js`, `formularz.js` | Zlecenia ze spraw: sprawdzenie w KRZ i wypełnianie formularzy. |

Model stoi po stronie serwera (Bedrock, eu-central-1). Rozszerzenie wysyła do
`POST /api/pomocnik/klikamy/{zlecenie}/krok` adres strony, do 4000 znaków jej
widocznego tekstu i listę elementów (numer, rola, opis). Selektory i wpisywane
wartości zostają w przeglądarce. Serwer nie loguje treści strony ani polecenia,
a po zakończeniu zapisuje tylko liczbę kroków i rodzaj wyniku.

Łączenie z kancelarią jest takie samo jak w pomocniku: panel pokazuje kod,
notariusz klika „Połącz” w zalogowanej notarai, rozszerzenie odbiera token,
który otwiera wyłącznie `/api/pomocnik/`.

## Zabezpieczenia (w mechanizmie, nie w poleceniu dla modelu)

- Model wybiera element z ponumerowanej listy, nie współrzędne.
- Przycisku wysyłki, złożenia, podpisu, płatności ani usunięcia nie da się
  kliknąć. Sprawdzamy to dwa razy: na liście i tuż przed kliknięciem na stronie.
- Do pola hasła i PIN-u nic nie jest wpisywane.
- Asystent nie wychodzi poza serwis, na którym go uruchomiono. Gdy strona sama
  przejdzie gdzie indziej (np. do logowania), zatrzymuje się.
- Najwyżej 20 kroków na polecenie; „Zatrzymaj” przerywa w każdej chwili.

## Zlecenia ze spraw (kolejka notarai)

Dopóki panel jest otwarty, co 3 sekundy pyta notarai o zlecenia
(`GET /api/pomocnik/zlecenia`) - to samo pytanie zapala w notarai przycisk
„Sprawdź w KRZ”. Pierwsze zlecenie dla danego serwisu czeka w panelu na
„Zezwól i wykonaj” (zgoda na stronę musi iść z kliknięcia), następne ruszają same.

| Zlecenie | Co robi rozszerzenie | Plik |
|---|---|---|
| `krz` | Otwiera KRZ w karcie, dla każdej osoby dwa wyszukiwania po PESEL, rozpoznaje wynik na miejscu i odsyła status. Zakładki i wzorce rozpoznawania przychodzą ze zleceniem z `krz_portal.opis_portalu()`, więc po zmianie portalu poprawia się jeden plik na serwerze. | `krz.js` |
| `formularz` | Wpisuje dane sprawy w już otwarty, zalogowany formularz i zatrzymuje się przed wysyłką. Odrzuca całe zlecenie, jeśli któreś pole celuje w przycisk wysyłki; odmawia przy mapowaniu „szkic”, innej stronie i polu hasła. Raport bez wartości pól. | `formularz.js` |
| `klikamy` | Polecenie wpisane w sprawie w notarai - ta sama pętla co pole polecenia w panelu, na stronie otwartej w bieżącej karcie. | `silnik.js` |

## Czego rozszerzenie jeszcze nie robi

- Nie robi zrzutów ekranu z KRZ (pomocnik `.exe` je zapisuje). Wymagałoby to
  stałego dostępu do wszystkich stron. Przy wyniku „wpis” albo nierozpoznanym
  opis w sprawie mówi wprost: sprawdź w rejestrze.
- Zlecenia odbiera tylko przy otwartym panelu.
- Formularze: oba mapowania w `formularze/*.yaml` mają status „szkic” (czekają
  na dostęp, NA-1 i NA-4), więc serwer nie zleca jeszcze żadnego wpisywania.
- Gdy na tym samym komputerze działa też pomocnik `.exe`, zlecenie wykona ten,
  kto pierwszy je odbierze; drugi raport serwer pomija.
- Nie ma jeszcze pozycji w sklepie Chrome Web Store ani Edge Add-ons, więc
  w kreatorze notarai nie ma do niego odnośnika (patrz `docs/czeka-na-dostep.md`).
- Ramka z innego adresu niż strona wymaga osobnej zgody (panel o nią prosi).

## Uruchomienie do testów

1. Chrome albo Edge: `chrome://extensions` → „Tryb dewelopera” → „Załaduj
   rozpakowane” → katalog `rozszerzenie/`.
2. Kliknij ikonę notarai. Otworzy się panel z kodem połączenia.
3. W zalogowanej notarai kliknij „Połącz”.
4. Otwórz stronę rejestru, wpisz polecenie, kliknij „Wykonaj” i zezwól na tę stronę.

Adres serwera inny niż `https://app.notarai.pl` (np. środowisko testowe)
ustawia się w konsoli panelu: `chrome.storage.local.set({adres: "https://..."})`
i wymaga dopisania go do `host_permissions`.

## Testy

- `npm test` (w tym katalogu) - zabezpieczenia silnika, klient serwera, KRZ
  i formularze na atrapach.
- `pytest test_rozszerzenie.py` - serwerowa połowa, manifest, testy Node.
- `pytest test_rozszerzenie_ui.py` - panel na prawdziwych stronach w Chromium:
  pole polecenia (ramka, pole PIN, „Podpisz i wyślij”), próbny KRZ z formularzem
  w ramce i próbny formularz z przyciskiem „Wyślij”. Interfejs `chrome.*` jest
  w tym teście podstawiony.

## Identyfikacja wizualna

Panel i ikony Chrome/Edge korzystają z oryginalnego sygnetu `static/notarai-symbol.svg` i tokenów marki NotarAI (`tools/web-factory/design-system/tokens.json`). Ikony PNG (16/48/128 px) są rasteryzowane z tego samego SVG. Nie przywracać dawnych grafik Pieczapy ani kolorów `#c96442` / `#faf9f5`. Montserrat jest lokalnym plikiem WOFF2 (bez CDN).
