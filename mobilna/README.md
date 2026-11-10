# notarai – aplikacja klienta (Android / iOS / web)

Klient kancelarii wybiera notariusza i wolną godzinę, potwierdza numer telefonu
kodem SMS i ma wizytę w kalendarzu kancelarii (jak Booksy, tylko u notariusza).
Bez konta i logowania: dowodem własności rezerwacji jest token trzymany w telefonie.

Backend: `app.notarai.pl`, moduł `rezerwacje_klienta.py` (ścieżki `/api/klient/*`)
oraz `wizyty.py` (zapytania do kancelarii bez terminarza). Kancelaria włącza
rezerwacje klientów w aplikacji notarai: pasek boczny → **Rezerwacje hurtowe** →
„Przyjmuj rezerwacje klientów z aplikacji notarai”.

## Ekrany

| Ekran | Plik | Co robi |
|---|---|---|
| Start | `app/index.tsx` | miejscowość z podpowiedziami, „Najbliżej mnie” (lokalizacja), wejście do wizyt, kalkulator taksy |
| Kancelarie | `app/kancelarie.tsx` | kancelarie online (terminarz) i z bazy (zapytanie), odległość, telefon |
| Terminy | `app/kancelaria/[id].tsx` | pasek 14 dni, wolne godziny, przekładanie wizyty |
| Rezerwacja | `app/rezerwacja.tsx` | dane, zgoda, kod SMS, zapis w telefonie |
| Potwierdzenie | `app/potwierdzenie.tsx` | szczegóły, „Dodaj do kalendarza”, nawigacja |
| Zapytanie | `app/zapytanie.tsx` | kancelarie spoza notarai: zgłoszenie e-mail do kancelarii |
| Moje wizyty | `app/wizyty.tsx` | status z serwera, odwołanie (dwa kliknięcia), przełożenie |

Wspólne: `src/api.ts` (klient API, daty, linki), `src/storage.ts` (AsyncStorage),
`src/ui.tsx` (elementy), `src/theme.ts` (kolory notarai).

## Uruchomienie deweloperskie

```bash
cd mobilna
npm install
```

Adres serwera ustawia `EXPO_PUBLIC_API_URL` (plik `.env`, wzór w `.env.example`).
Domyślnie aplikacja łączy się z produkcją `https://app.notarai.pl`.

Backend lokalny z rezerwacjami online (nic nie wychodzi, kod SMS wraca w odpowiedzi):

```powershell
$env:PIECZAPP_SMS_TRYB="test"; $env:PIECZAPP_KALKULATOR_ORIGINS="http://localhost:8081,http://127.0.0.1:8081"
.venv\Scripts\python scripts\demo_klienta.py      # kancelaria demo z terminarzem
.venv\Scripts\python -m uvicorn app:app --port 8000
```

Aplikacja:

```bash
npm run web                 # przeglądarka (http://localhost:8081), EXPO_PUBLIC_API_URL=http://127.0.0.1:8000
npm run android             # emulator Androida, EXPO_PUBLIC_API_URL=http://10.0.2.2:8000
npm start                   # kod QR dla Expo Go na telefonie (telefon w tej samej sieci Wi-Fi,
                            # EXPO_PUBLIC_API_URL=http://<adres IP komputera>:8000)
npm run typecheck
```

## Ikony i splash

Ikony w `assets/` (ikona, adaptive icon Androida: tło/znak/monochromatyczna, splash,
favicon web) generuje skrypt ze znaku `static/notarai-symbol.svg` w kolorach aplikacji
(granat `#0d193c`, złoto `#e4c47a`):

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
