# NotarAI: aplikacja klienta i rezerwacje online (08–10.11.2026)

Klient umawia wizytę u notariusza z telefonu jak w Booksy: wybiera kancelarię,
wolną godzinę, potwierdza numer kodem SMS i ma termin w kalendarzu kancelarii.
Kod aplikacji: `mobilna/` (Expo, React Native, Android + iOS + web).
Backend: `rezerwacje_klienta.py` (API `/api/klient/*`) i `sms.py` (Twilio).
Wersja przeglądarkowa: `https://app.notarai.pl/aplikacja/` (ten sam kod, eksport web).

## Skąd się to bierze

- **Wolne godziny i kolizje**: ten sam silnik co rezerwacje B2B
  (`rezerwacje_hurtowe.py`: polityka dni/godzin, czas wizyty, wyprzedzenie,
  horyzont) oraz jeden plik kalendarza na kancelarię z zapisem warunkowym w S3.
  Nie ma drugiej bazy terminów.
- **Zgoda kancelarii**: nowy przełącznik `klienci` w polityce terminarza
  (pasek boczny → „Rezerwacje hurtowe” → „Przyjmuj rezerwacje klientów z aplikacji
  notarai”). Domyślnie wyłączony. Partnerzy B2B (`wlaczone`) i klienci są niezależni.
- **Kancelarie spoza notarai** (baza `seo/kancelarie.json`, 3,5 tys. wpisów) są
  w aplikacji na liście bez terminarza: klient wysyła zapytanie dotychczasową
  ścieżką `/api/wizyty/zgloszenie` (źródło `aplikacja`), kancelaria dostaje e-mail.
- **SMS**: klient Twilio i hamulec przeniesione z Finance You
  (`finyou/src/lib/twilio-api.server.ts`, `sms-guard.server.ts`) do Pythona,
  bez nowych zależności (httpx).
- **Święta państwowe**: `kalendarz.swieto()` (stałe daty, Wielkanoc i święta
  ruchome, Wigilia od 2025) – w święta silnik nie oferuje godzin ani klientom,
  ani partnerom B2B; `terminy` zwraca taki dzień jako `nieczynne` z polem `swieto`.

## Rozdzielenie od Finance You

| | Finance You | notarai |
|---|---|---|
| konto Twilio | konto FY (`TWILIO_*`) | osobne konto albo podkonto (`PIECZAPP_TWILIO_*`), sekret `notarai/twilio` |
| numer nadawcy | +48 732 059 898, webhook `app.financeyou.pl/.../twilio-sms-inbound` | osobny numer, webhook `app.notarai.pl/api/klient/sms-przychodzacy?token=` |
| ElevenLabs | agenci Ania itd. | nieużywane w tym etapie (głosowe umawianie to osobna funkcja) |
| baza | Supabase | S3 (pliki kancelarii) + plik administracyjny `klienci.json` |
| AWS | — | stos `notarai-aplikacja`, prefiks `notarai-`, eu-central-1 |

Numer telefonu w Twilio ma jeden webhook, więc współdzielenie numeru kierowałoby
odpowiedzi klientów kancelarii do systemu pożyczkowego. Dlatego osobny numer jest
wymogiem, nie opcją. Klucz API Twilio może być wspólny, ale osobne podkonto
rozdziela koszty i limity.

## Przepływ i API

| Krok | Metoda | Ścieżka | Uwagi |
|---|---|---|---|
| możliwości | GET | `/api/klient/konfiguracja` | `rezerwacje_online` = czy SMS działa |
| miejscowość | GET | `/api/klient/miejscowosci?q=lub` | podpowiedzi z bazy |
| kancelarie | GET | `/api/klient/kancelarie?miasto=lublin` albo `?lat=&lon=` | online na górze; po współrzędnych tylko online, od najbliższej |
| terminy | GET | `/api/klient/kancelarie/{id}/terminy?od=&dni=14` | max 14 dni na zapytanie; dni nieczynne i święta puste (`nieczynne`, `swieto`) |
| kod SMS | POST | `/api/klient/weryfikacja` `{telefon}` | 201 `{id, wygasa_s, koncowka}`; w trybie `test` także `kod_testowy` |
| rezerwacja | POST | `/api/klient/rezerwacje` | kod + dane + `zgoda=true`; 201 z `token` (tylko raz); 409 gdy termin zajęty |
| podgląd | POST | `/api/klient/rezerwacje/{id}/podglad` `{kancelaria, token}` | token w ciele, nie w adresie (logi dostępowe); `status`, `anulowal` (`klient`/`kancelaria`) |
| odwołanie | POST | `/api/klient/rezerwacje/{id}/anuluj` `{kancelaria, token}` | SMS do klienta, e-mail do kancelarii |
| przełożenie | PUT | `/api/klient/rezerwacje/{id}` `{kancelaria, token, data, godzina}` | jak wyżej |
| webhook Twilio | POST | `/api/klient/sms-przychodzacy?token=` | STOP wypisuje numer z przypomnień |
| admin | POST/GET | `/api/admin/klient/przypomnienia`, `/api/admin/klient/stan` | token administratora |

Wpis w kalendarzu kancelarii ma `zrodlo: "klient"`, tytuł „Wizyta z aplikacji: …”,
telefon klienta w `telefony`, e-mail i uwagi w `klient` (i opisowo w `uwagi`).
Kancelaria pracuje na nim jak na każdym innym terminie:

- kokpit (`static/index.html`) oznacza go plakietką **„z aplikacji”** i złotym paskiem
  (miesiąc, tydzień, dzień, „Najbliższe terminy”); okno terminu pokazuje ramkę
  z e-mailem i uwagami klienta oraz uprzedza, że zmiana terminu wyśle SMS;
- zapis bez żadnej zmiany nie wysyła `PUT` („Bez zmian – nic nie zapisano”);
  przeniesienie i usunięcie pytają z dopiskiem o SMS do klienta;
- przesunięcie daty/godziny: SMS do klienta (`powiadom_o_zmianie_kancelarii`)
  i wyzerowany znacznik przypomnienia (przypomnienie przyjdzie przed nowym terminem);
- usunięcie: wpis nie znika, tylko dostaje `status: "anulowana"`, `anulowal: "kancelaria"`
  (`odwolaj_przez_kancelarie`) – schodzi z kalendarza i zwalnia godzinę, klient
  dostaje SMS, a aplikacja po odświeżeniu pokazuje „Kancelaria odwołała tę wizytę”;
- `GET /api/kalendarz` nie zwraca odcisku tokenu klienta ani identyfikatora weryfikacji.

## SMS-y (co i kiedy)

| Wiadomość | Kategoria | Hamulec |
|---|---|---|
| kod weryfikacyjny | krytyczny | limit na numer (5/h), 3 aktywne kody naraz, 5 prób na kod, ważność 10 min |
| potwierdzenie, odwołanie, przełożenie, zmiana przez kancelarię | krytyczny | limit na numer |
| przypomnienie dzień przed | automatyczny | okno 8–20 Warszawa, bez powtórki treści w 24 h, STOP wypisuje |

Przypomnienia: wątek w aplikacji co 15 min (`PIECZAPP_PRZYPOMNIENIA=1`) oznacza
wpis atomowo (zapis warunkowy), dopiero potem wysyła, więc dwie kopie na ECS nie
wyślą dwa razy. Alternatywa: `PIECZAPP_PRZYPOMNIENIA=0` i zewnętrzny harmonogram
wołający `POST /api/admin/klient/przypomnienia`. W chmurze ustawia to parametr
`Przypomnienia` stosu `notarai-aplikacja` (domyślnie `1`).

Treści bez polskich znaków (UCS-2 skraca SMS do 70 znaków). Numer i treść nie
trafiają do logów; logujemy kategorię, status i SID.

## Wersja web (`/aplikacja`)

- `app.py` serwuje `mobilna/dist` (eksport `expo export --platform web`, `baseUrl`
  `/aplikacja` w `app.json`) pod `https://app.notarai.pl/aplikacja/`: pliki z hashem
  z długim cache, trasy aplikacji (`/aplikacja/wizyty`, `/aplikacja/kancelaria/…`)
  dostają `index.html`, brakujący plik to 404. Bez zbudowanego `dist/` trasa zwraca 404.
  Ścieżka jest otwarta bez logowania (`autoryzacja._OTWARTE`).
- Obraz: `Dockerfile` ma etap `node:22-slim` (lustro ECR Public), który robi
  `npm ci` i `expo export`; do obrazu Pythona trafia tylko `dist/`, bez `node_modules`.
  CodeBuild (`infra/notarai-budowanie.yaml`) niczego nie zmienia – buduje ten sam
  `Dockerfile`, etap dokłada ok. 2–4 minuty. `.dockerignore` pomija `mobilna/node_modules`,
  `mobilna/dist` i każde `.env`.
- Ta sama domena co API, więc bez CORS. Linki „Umów wizytę w aplikacji”: sekcja
  „Dla klientów” na `strona/index.html` i panel mapy `static/notariusze.html`.
- Alternatywa bez przebudowy obrazu (np. gdy CodeBuild nie ma dostępu do npm):
  zbudować lokalnie `dist/` z `EXPO_PUBLIC_API_URL=https://app.notarai.pl` i wgrać
  go przez `infra/strona.ps1` jako `/aplikacja/` na hosting notarai.pl. Wtedy
  `PIECZAPP_KALKULATOR_ORIGINS` musi zawierać `https://notarai.pl`, a serwer www
  musi kierować nieznane ścieżki `/aplikacja/*` do `index.html`. Domyślnie nie używane.
- Wizyty z wersji web są zapisane w przeglądarce (localStorage), nie w telefonie.

## Ochrona danych

- Imię, telefon, e-mail, uwagi klienta trafiają tylko do kalendarza kancelarii, która
  jest ich administratorem (klient wyraża zgodę w formularzu; treść zgody w aplikacji).
- Numer i kod weryfikacyjny leżą w `kancelarie/_administracja/klienci.json` tylko
  jako SHA-256, kasowane godzinę po wygaśnięciu. Wypisy (STOP) też jako odciski.
- Token zarządzania rezerwacją: SHA-256 w kalendarzu, oryginał tylko w telefonie klienta.
- Adres IP służy wyłącznie do limitów i nie jest zapisywany.
- Współrzędne klienta („Najbliżej mnie”) służą do posortowania listy, nie są zapisywane.

## Konfiguracja

Lokalnie: `PIECZAPP_SMS_TRYB=test`, `scripts/demo_klienta.py`, patrz `mobilna/README.md`.

Chmura:
1. Twilio: osobne podkonto, polski numer z SMS, webhook numeru
   `https://app.notarai.pl/api/klient/sms-przychodzacy?token=<losowy>`.
2. `infra\zapisz-sekret-twilio.ps1` zapisuje konto, token, numer i token webhooka
   w sekrecie `notarai/twilio` (Secrets Manager).
3. `infra\3-wdroz-aplikacje.ps1` wykrywa sekret i ustawia `PIECZAPP_SMS_TRYB=twilio`
   oraz zmienne `PIECZAPP_TWILIO_*` z sekretu (ECS `Secrets`, nie `Environment`).
4. `GET /api/admin/klient/stan` pokazuje, czy SMS jest gotowy i które kancelarie są online.

Bez sekretu `/api/klient/konfiguracja` zwraca `rezerwacje_online=false`: aplikacja
pokazuje wszystkie kancelarie jako „Zapytanie o termin” i nic się nie psuje.

## Testy

- `test_sms.py` i `test_rezerwacje_klienta.py`: atrapa Twilio, kolizje, idempotencja,
  token, przypomnienia, STOP, brak danych osobowych w logach, święta, kokpit
  (lista bez tokenu, zapis bez zmian bez SMS, przeniesienie zeruje przypomnienie,
  odwołanie przez kancelarię widoczne w podglądzie).
- `test_aplikacja_web.py`: trasa `/aplikacja` (SPA, cache, 404, nic spoza `dist/`,
  otwarta przy `PIECZAPP_MULTI`), linki na stronie i mapie.
- `test_kokpit.py`: plakietka „z aplikacji”, brak `PUT` bez zmian.
- Aplikacja: `cd mobilna && npm run typecheck && npm test` (12 testów `src/api.ts`
  przez `node --test`); CI sprawdza typy, testy i eksport web.

## Czego świadomie nie ma

- Konta klienta, płatności zaliczki, ocen kancelarii. Tokeny w telefonie wystarczają
  na MVP; konto ma sens dopiero przy historii wizyt na kilku urządzeniach.
- Głosowego umawiania przez ElevenLabs/Twilio Voice: agent z Finance You ma inną
  bazę wiedzy; dla notarai to osobny projekt z własnym numerem i agentem.
- Rezerwacji dla kancelarii w trybie „pliki u klienta” (kalendarz nie jest na serwerze).
- Powiadomień push: przypomnienia idą SMS-em, który działa bez instalacji aplikacji.
- Linku do aplikacji w SMS-ach: aplikacja trzyma wizyty w pamięci urządzenia, więc link
  `https://app.notarai.pl/aplikacja/wizyty` otwarty w innej przeglądarce byłby pusty.
