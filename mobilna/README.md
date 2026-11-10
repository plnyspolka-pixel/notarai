# notarai – aplikacja klienta (Android / iOS / web)

Klient kancelarii wybiera notariusza i wolną godzinę, potwierdza numer telefonu
kodem SMS i ma wizytę w kalendarzu kancelarii (jak Booksy, tylko u notariusza).
Bez konta i logowania: dowodem własności rezerwacji jest token trzymany w telefonie.

Backend: `app.notarai.pl`, moduł `rezerwacje_klienta.py` (ścieżki `/api/klient/*`)
oraz `wizyty.py` (zapytania do kancelarii bez terminarza). Kancelaria włącza
rezerwacje klientów w aplikacji notarai: pasek boczny → **Rezerwacje hurtowe** →
„Przyjmuj rezerwacje klientów z aplikacji notarai”. Wizyty z aplikacji widzi
w kalendarzu z plakietką „z aplikacji”.

Wersja przeglądarkowa tego samego kodu: `https://app.notarai.pl/aplikacja/`
(szczegóły w `docs/aplikacja-klienta.md`, sekcja „Wersja web”).

## Ekrany

| Ekran | Plik | Co robi |
|---|---|---|
| Start | `app/index.tsx` | miejscowość z podpowiedziami, „Najbliżej mnie” (lokalizacja), wejście do wizyt, kalkulator taksy |
| Kancelarie | `app/kancelarie.tsx` | kancelarie online (terminarz) i z bazy (zapytanie), odległość, telefon |
| Terminy | `app/kancelaria/[id].tsx` | pasek 14 dni, wolne godziny, przekładanie wizyty |
| Rezerwacja | `app/rezerwacja.tsx` | dane, zgoda, kod SMS, zapis w telefonie |
| Potwierdzenie | `app/potwierdzenie.tsx` | szczegóły, „Dodaj do kalendarza”, nawigacja |
| Zapytanie | `app/zapytanie.tsx` | kancelarie spoza notarai: zgłoszenie e-mail do kancelarii |
| Moje wizyty | `app/wizyty.tsx` | status z serwera (pociągnij w dół / „Odśwież”), odwołanie (dwa kliknięcia), przełożenie, odwołanie przez kancelarię |
| O aplikacji | `app/o-aplikacji.tsx` | wersja, kontakt `kontakt@notarai.pl`, prywatność, regulamin, operator |
| Nieznany adres | `app/+not-found.tsx` | po polsku, powrót do startu albo wizyt |

Wspólne: `src/api.ts` (klient API, daty, linki), `src/storage.ts` (AsyncStorage),
`src/ui.tsx` (elementy), `src/theme.ts` (kolory notarai).

### Sieć i błędy

- Każde żądanie ma limit 15 s. Odczyty (konfiguracja, kancelarie, terminy, status
  wizyty) i sama rezerwacja są ponawiane 2 razy po zerwanym połączeniu albo
  502/503/504 – serwer rozpoznaje powtórzoną rezerwację po kodzie SMS i zwraca tę samą.
- Wysłanie kodu SMS, odwołanie i przełożenie nie są powtarzane automatycznie
  (żeby nie wysłać drugiego SMS-a); użytkownik widzi komunikat i przycisk.
- Listy pokazują „Spróbuj ponownie”; „Moje wizyty” bez sieci pokazują dane z pamięci
  telefonu z informacją, że status nie jest aktualny.
- Token rezerwacji nie trafia do adresu ekranu (historia przeglądarki) ani do URL
  żądania – „Przełóż” bierze go z pamięci telefonu.

### Linki do aplikacji

Schemat `notarai://` (ustawiony w `app.json`, expo-router mapuje ścieżki na ekrany):
`notarai://wizyty` otwiera „Moje wizyty”, `notarai://kancelaria/<id>` terminy kancelarii.
W wersji web te same ekrany mają adresy `https://app.notarai.pl/aplikacja/wizyty` itd.
Sprawdzenie na Androidzie z zainstalowaną aplikacją:

```bash
adb shell am start -W -a android.intent.action.VIEW -d "notarai://wizyty" pl.notarai.klient
```

## Uruchomienie deweloperskie

```bash
cd mobilna
npm install
```

Adres serwera ustawia `EXPO_PUBLIC_API_URL` (plik `.env`, wzór w `.env.example`).
Domyślnie aplikacja łączy się z produkcją `https://app.notarai.pl`.

Backend lokalny z rezerwacjami online (nic nie wychodzi, kod SMS wraca w odpowiedzi,
kancelarie demo `demo-lublin` i `demo-warszawa`):

```powershell
powershell -ExecutionPolicy Bypass -File scripts\dev-klient-backend.ps1   # z katalogu repo, port 8000
```

Aplikacja:

```bash
npm run web                 # serwer Metro, http://localhost:8081/aplikacja, EXPO_PUBLIC_API_URL=http://127.0.0.1:8000
npm run android             # emulator Androida, EXPO_PUBLIC_API_URL=http://10.0.2.2:8000
npm start                   # kod QR dla Expo Go na telefonie
npm run typecheck           # TypeScript
npm test                    # testy jednostkowe src/api.ts (node --test, bez zależności)
npx expo-doctor             # zgodność paczek z SDK 58 i schematu app.json
```

Na słabszym komputerze (mało RAM) zamiast serwera Metro: zbuduj wersję web i otwórz ją
przez lokalny backend, który serwuje `mobilna/dist` pod `/aplikacja`:

```powershell
$env:NODE_OPTIONS="--max-old-space-size=1024 --max-semi-space-size=2"
npx expo export --platform web --output-dir dist --max-workers 1
# potem http://127.0.0.1:8000/aplikacja/ (backend z dev-klient-backend.ps1)
```

### Test na telefonie (Expo Go)

1. Zainstaluj Expo Go ze sklepu (musi obsługiwać SDK 58 – aktualna wersja ze sklepu).
2. Telefon i komputer w tej samej sieci Wi-Fi. W `mobilna/.env`:
   `EXPO_PUBLIC_API_URL=http://<adres IP komputera>:8000` (albo produkcja
   `https://app.notarai.pl`, gdy tam działa SMS).
3. Backend lokalny musi słuchać w sieci: `scripts\dev-klient-backend.ps1 -Adres 0.0.0.0`
   i port 8000 dopuszczony w zaporze Windows (tylko w zaufanej sieci; tryb SMS `test`
   zwraca kod w odpowiedzi API).
4. `npx expo start` i zeskanuj kod QR aparatem (iOS) albo w Expo Go (Android).
5. Sprawdź: lokalizację („Najbliżej mnie”), rezerwację z kodem, „Dodaj do kalendarza”,
   „Nawiguj”, pociągnięcie listy wizyt, tryb samolotowy (komunikat i ponowienie),
   link `notarai://wizyty` (w Expo Go adres zaczyna się od `exp://…/--/wizyty`).

## Ikony i splash

Ikony w `assets/` (ikona, adaptive icon Androida: tło/znak/monochromatyczna, splash,
favicon web) generuje skrypt ze znaku `static/notarai-symbol.svg` w kolorach aplikacji
(granat `#0d193c`, złoto `#e4c47a`). Splash konfiguruje plugin `expo-splash-screen`
w `app.json` (SDK 58 nie przyjmuje już klucza `splash` na najwyższym poziomie):

```powershell
.venv\Scripts\python scripts\generuj_ikony_aplikacji.py
```

## Budowa paczek i publikacja (EAS)

Aplikacja jest w stylu „managed” Expo (bez katalogów `android/` i `ios/`). Paczki buduje
EAS w chmurze Expo według `eas.json`:

| Profil | Co powstaje | Do czego |
|---|---|---|
| `development` | APK + build na symulator iOS | szybki test na telefonie bez sklepu |
| `preview` | APK (dystrybucja wewnętrzna, link do pobrania) | testerzy w kancelariach |
| `production` | Android App Bundle `.aab`, iOS `.ipa` | Google Play / App Store |

Każdy profil łączy się z `https://app.notarai.pl` (`env.EXPO_PUBLIC_API_URL` w `eas.json`).

Jednorazowo (konto Expo nie jest jeszcze przypisane, w `app.json` celowo nie ma `owner`):

```bash
cd mobilna
npx eas-cli login                 # konto Expo właściciela notarai
npx eas-cli init                  # dopisze extra.eas.projectId (i owner) do app.json – zacommituj
```

Build i wysyłka do sklepów:

```bash
npx eas-cli build --platform android --profile preview       # APK do testów
npx eas-cli build --platform android --profile production    # .aab do Google Play
npx eas-cli build --platform ios --profile production        # wymaga konta Apple Developer
npx eas-cli submit --platform android --profile production   # ścieżka "internal", szkic
```

Pierwszy `.aab` w Google Play trzeba wgrać ręcznie w Play Console (potem działa `eas submit`
z kluczem konta usługi Google, którego nie trzymamy w repo).

Wersje: `version` w `app.json` (np. `1.0.1`) to wersja widoczna dla użytkownika i zarazem
`runtimeVersion` (polityka `appVersion`). Przed każdym buildem do sklepu podbij też
`android.versionCode` (liczba, +1) i `ios.buildNumber` (tekst, +1) – `eas.json` ma
`appVersionSource: local`, więc EAS bierze je z `app.json`.

Identyfikatory: Android `pl.notarai.klient`, iOS `pl.notarai.klient`, schemat linków `notarai://`.

## Prywatność

- Lokalizacja tylko po kliknięciu „Najbliżej mnie” i tylko do posortowania kancelarii;
  współrzędne idą do `/api/klient/kancelarie`, nie są zapisywane.
- Dane klienta (imię, telefon, e-mail, uwagi) trafiają wyłącznie do kalendarza wybranej
  kancelarii. Serwer trzyma numer i kod SMS tylko jako odciski SHA-256 z terminem ważności.
- Aplikacja nie ma analityki ani reklam.
- Przy każdej zgodzie (rezerwacja, zapytanie) jest link do polityki prywatności
  `https://notarai.pl/prywatnosc/`; pełniejsza informacja na ekranie „O aplikacji”.
- W wersji web wizyty (z tokenami) leżą w localStorage tej przeglądarki.
