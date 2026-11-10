# NotarAI: aplikacja klienta i rezerwacje online (08.11.2026)

Klient umawia wizytę u notariusza z telefonu jak w Booksy: wybiera kancelarię,
wolną godzinę, potwierdza numer kodem SMS i ma termin w kalendarzu kancelarii.
Kod aplikacji: `mobilna/` (Expo, React Native, Android + iOS + web).
Backend: `rezerwacje_klienta.py` (API `/api/klient/*`) i `sms.py` (Twilio).

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
| terminy | GET | `/api/klient/kancelarie/{id}/terminy?od=&dni=14` | max 14 dni na zapytanie, dni nieczynne puste |
| kod SMS | POST | `/api/klient/weryfikacja` `{telefon}` | 201 `{id, wygasa_s, koncowka}`; w trybie `test` także `kod_testowy` |
| rezerwacja | POST | `/api/klient/rezerwacje` | kod + dane + `zgoda=true`; 201 z `token` (tylko raz); 409 gdy termin zajęty |
| podgląd | POST | `/api/klient/rezerwacje/{id}/podglad` `{kancelaria, token}` | token w ciele, nie w adresie (logi dostępowe) |
| odwołanie | POST | `/api/klient/rezerwacje/{id}/anuluj` `{kancelaria, token}` | SMS do klienta, e-mail do kancelarii |
| przełożenie | PUT | `/api/klient/rezerwacje/{id}` `{kancelaria, token, data, godzina}` | jak wyżej |
| webhook Twilio | POST | `/api/klient/sms-przychodzacy?token=` | STOP wypisuje numer z przypomnień |
| admin | POST/GET | `/api/admin/klient/przypomnienia`, `/api/admin/klient/stan` | token administratora |

Wpis w kalendarzu kancelarii ma `zrodlo: "klient"`, tytuł „Wizyta z aplikacji: …”,
telefon klienta w `telefony` i e-mail/uwagi w `uwagi`. Kancelaria pracuje na nim
jak na każdym innym terminie; usunięcie albo przesunięcie w aplikacji kancelarii
wysyła klientowi SMS (`powiadom_o_zmianie_kancelarii` w `app.py`).

## SMS-y (co i kiedy)

| Wiadomość | Kategoria | Hamulec |
|---|---|---|
| kod weryfikacyjny | krytyczny | limit na numer (5/h), 3 aktywne kody naraz, 5 prób na kod, ważność 10 min |
| potwierdzenie, odwołanie, przełożenie, zmiana przez kancelarię | krytyczny | limit na numer |
| przypomnienie dzień przed | automatyczny | okno 8–20 Warszawa, bez powtórki treści w 24 h, STOP wypisuje |

Przypomnienia: wątek w aplikacji co 15 min (`PIECZAPP_PRZYPOMNIENIA=1`) oznacza
wpis atomowo (zapis warunkowy), dopiero potem wysyła, więc dwie kopie na ECS nie
wyślą dwa razy. Alternatywa: `PIECZAPP_PRZYPOMNIENIA=0` i zewnętrzny harmonogram
wołający `POST /api/admin/klient/przypomnienia`.

Treści bez polskich znaków (UCS-2 skraca SMS do 70 znaków). Numer i treść nie
trafiają do logów; logujemy kategorię, status i SID.

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

`test_sms.py` (16) i `test_rezerwacje_klienta.py` (23): atrapa Twilio, kolizje,
idempotencja, token, przypomnienia, STOP, brak danych osobowych w logach.
Aplikacja: `cd mobilna && npm run typecheck`; CI sprawdza typy i eksport web.

## Czego świadomie nie ma

- Konta klienta, płatności zaliczki, ocen kancelarii. Tokeny w telefonie wystarczają
  na MVP; konto ma sens dopiero przy historii wizyt na kilku urządzeniach.
- Głosowego umawiania przez ElevenLabs/Twilio Voice: agent z Finance You ma inną
  bazę wiedzy; dla notarai to osobny projekt z własnym numerem i agentem.
- Rezerwacji dla kancelarii w trybie „pliki u klienta” (kalendarz nie jest na serwerze).
