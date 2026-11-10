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

## Budowa paczek

Aplikacja jest w stylu „managed” Expo. Paczki `.aab`/`.ipa` buduje EAS:

```bash
npx eas-cli build --platform android --profile production
```

Identyfikatory: Android `pl.notarai.klient`, iOS `pl.notarai.klient`, schemat linków `notarai://`.
Ikony w `assets/` są tymczasowe (z szablonu Expo); przed publikacją podmień na znak notarai.

## Prywatność

- Lokalizacja tylko po kliknięciu „Najbliżej mnie” i tylko do posortowania kancelarii;
  współrzędne idą do `/api/klient/kancelarie`, nie są zapisywane.
- Dane klienta (imię, telefon, e-mail, uwagi) trafiają wyłącznie do kalendarza wybranej
  kancelarii. Serwer trzyma numer i kod SMS tylko jako odciski SHA-256 z terminem ważności.
- Aplikacja nie ma analityki ani reklam.
