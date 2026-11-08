# NotarAI — API rezerwacji hurtowych i MCP

Moduł: \`rezerwacje_hurtowe.py\`, podłączony w \`app.py\`.

## Model dostępu

1. **Właściciel kancelarii** (JWT Cognito, tylko użytkownik z rolą \`wlasciciel\`) sam włącza publikację wolnych terminów, podając adres kancelarii, godziny i czas wizyty.
2. **Administrator NotarAI** tworzy klienta hurtowego i przypisuje mu konkretne kancelarie. Dostaje klucz \`nth_...\` **tylko raz**. Przechowywany jest wyłącznie jego SHA-256; przy cofnięciu dostępu klucz przestaje działać.
3. **Partner hurtowy** używa \`Authorization: Bearer nth_...\` i otrzymuje tylko opublikowane kancelarie, wolne okienka oraz swoje własne rezerwacje.
4. **MCP** korzysta z **tego samego klucza** i tych samych operacji domenowych. Nie istnieje osobny uprzywilejowany dostęp AI do spraw kancelarii.

W panelu kancelarii istniejący kalendarz pokazuje wizyty z API. Wpis ma \`zrodlo=hurtowe\` i numer \`zewnetrzne_id\`. Anulowane wizyty pozostają w JSON dla celów audytowych, ale nie blokują okienka i nie są pokazywane w zwykłej liście kalendarza.

Właściciel kancelarii musi zgodzić się na udostępnianie terminarza; domyślnie funkcja jest **wyłączona**. Kancelarie w trybie \`u-klienta\` nie mogą jej włączyć, bo przechowywanie kalendarza na serwerze byłoby sprzeczne z deklarowanym modelem pracy.

## Panel kancelarii

Po zalogowaniu właściciela konta w NotarAI otwórz przycisk **Rezerwacje hurtowe** w lewym panelu. Ustaw miasto i adres, zaznacz dni i godziny dostępności, określ czas wizyty i wyprzedzenie, a następnie włącz przełącznik i zapisz. Kancelaria w trybie przechowywania plików lokalnie lub członek zespołu bez roli właściciela nie widzą tego przycisku. Panel korzysta z poniższych endpointów.

## 1. Włączenie przez kancelarię

Autoryzowany JWT właściciela w nagłówku \`Authorization\`:

\`\`\`http
PUT /api/rezerwacje-hurtowe/ustawienia
Content-Type: application/json
Authorization: Bearer <Cognito ID token>
\`\`\`

\`\`\`json
{
  "wlaczone": true,
  "miasto": "Lublin",
  "adres": "ul. Przykładowa 1, Lublin",
  "godziny": {
    "0": ["09:00", "17:00"],
    "1": ["09:00", "17:00"],
    "2": ["09:00", "17:00"],
    "3": ["09:00", "17:00"],
    "4": ["09:00", "15:00"]
  },
  "czas_minut": 60,
  "wyprzedzenie_godzin": 24,
  "max_dni": 60
}
\`\`\`

\`godziny\`: dni tygodnia \`0\` (poniedziałek) ... \`6\` (niedziela). Starty co 30 minut. Czas wizyty 30, 60, 90 lub 120 minut. Strefa: **Europe/Warsaw**; daty w \`YYYY-MM-DD\`, godziny w \`HH:MM\`. Kancelaria może oznaczać dzień jako \`nieczynne\` w dotychczasowym \`/api/kalendarz/dni/{dzien}\`.

Odczyt ustawień: \`GET /api/rezerwacje-hurtowe/ustawienia\`; wyłączenie: \`PUT\` z \`wlaczone=false\`. Wyłączenie blokuje nowe rezerwacje; dotychczasowe wpisy pozostają w kalendarzu.

## 2. Klienci hurtowi: panel administratora

\`\`\`http
POST /api/admin/hurtowi
Authorization: Bearer <token administratora>
Content-Type: application/json
\`\`\`

\`\`\`json
{"nazwa":"Partner demonstracyjny","kancelarie":["kancelaria-a","kancelaria-b"]}
\`\`\`

Odpowiedź \`201\` zawiera ID partnera i jednorazowy \`api_key\` (przenieść od razu do menedżera sekretów). Administrator musi znać identyfikatory kancelarii z \`GET /api/admin/kancelarie\`.

- \`GET /api/admin/hurtowi\` — partnerzy, **bez hashy kluczy**.
- \`DELETE /api/admin/hurtowi/{partner_id}\` — natychmiastowe odebranie uprawnień.
- Rotacja: utworzyć nowego partnera/klucz i zablokować stary.

Przy większej skali należy zapewnić limity zapytań i alerty nadużyć na warstwie ingress/WAF.

## 3. REST dla partnera

Nagłówek do wszystkich poniższych żądań: \`Authorization: Bearer <api_key>\`.

| Metoda | Ścieżka | Działanie |
|---|---|---|
| GET | \`/api/hurtowe/kancelarie?miasto=Lublin\` | Kancelarie przypisane partnerowi i udostępniające rezerwacje |
| GET | \`/api/hurtowe/dostepnosc?kancelaria=kancelaria-a&data=2026-12-04\` | Wolne przedziały godzinowe, bez cudzych danych |
| POST | \`/api/hurtowe/rezerwacje\` | Tworzenie wizyty |
| GET | \`/api/hurtowe/rezerwacje?kancelaria=kancelaria-a\` | Własne rezerwacje partnera w danej kancelarii |
| PUT | \`/api/hurtowe/rezerwacje/{id}?kancelaria=kancelaria-a\` | Zmiana daty i godziny |
| POST | \`/api/hurtowe/rezerwacje/{id}/anuluj?kancelaria=kancelaria-a\` | Anulowanie i zwolnienie okienka |

Przykład rezerwacji:

\`\`\`json
{
  "kancelaria": "kancelaria-a",
  "data": "2026-12-04",
  "godzina": "10:00",
  "rodzaj": "sprzedaż",
  "uczestnicy": "Jan Przykładowy",
  "telefon": "600 000 000",
  "zewnetrzne_id": "ZLECENIE-123",
  "idempotency_key": "partner-zlecenie-123-wizyta-1",
  "potwierdzam": true
}
\`\`\`

Tworzenie i modyfikowanie wymaga jawnego \`potwierdzam=true\`. Identyczny ponowny POST z tym samym \`idempotency_key\` zwraca poprzednią rezerwację (bez duplikatu). Próba użycia tego samego klucza dla zmienionych danych daje \`409\`. Rezerwacja ma status \`potwierdzona\` i jest **automatycznie wpisywana** do istniejącego kalendarza kancelarii, bez dodatkowego ręcznego potwierdzenia przez notariusza. W przypadku kolizji \`409\`; klient powinien odświeżyć \`dostepnosc\`.

Zmiana:

\`\`\`json
{"data":"2026-12-04","godzina":"11:00","potwierdzam":true}
\`\`\`

Anulowanie:

\`\`\`json
{"potwierdzam":true}
\`\`\`

Wymagana jest odrębna podstawa do przekazania danych uczestników kancelarii, polityka retencji i umowa przetwarzania danych między odpowiednimi administratorami/podmiotami. **Moduł nie wysyła jeszcze SMS ani e-maili**; statusy są dostępne przez API i kalendarz.

## 4. MCP — agenci AI

Endpoint: \`POST https://app.notarai.pl/mcp\` (adres docelowy po wdrożeniu).
Transport: **stateless Streamable HTTP**, protokół \`2026-07-28\`; \`initialize\` i \`GET\` do strumienia SSE nie są w tej rewizji używane.

Obowiązkowe nagłówki:

\`\`\`text
Authorization: Bearer <api_key>
Content-Type: application/json
MCP-Protocol-Version: 2026-07-28
Mcp-Method: tools/list
\`\`\`

Dla \`tools/call\` dodatkowo \`Mcp-Name: wolne_terminy\` (odpowiednio do wywoływanej nazwy). Każdy POST musi zawierać \`params._meta\`, w tym zgodną wersję i \`clientCapabilities\`.

\`\`\`json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "_meta": {
      "io.modelcontextprotocol/protocolVersion": "2026-07-28",
      "io.modelcontextprotocol/clientCapabilities": {}
    },
    "name": "wolne_terminy",
    "arguments": {
      "kancelaria": "kancelaria-a",
      "data": "2026-12-04"
    }
  }
}
\`\`\`

Narzędzia: \`kancelarie\`, \`wolne_terminy\`, \`zarezerwuj_spotkanie\`, \`przeloz_spotkanie\`, \`anuluj_spotkanie\`, \`moje_rezerwacje\`.

Serwer obsługuje \`server/discover\`, \`tools/list\`, \`tools/call\`. Dla przeglądarkowych klientów MCP trzeba jawnie dopuścić zaufane źródła przez \`PIECZAPP_MCP_ORIGINS\` (lista originów po przecinku); domyślnie każdy obecny nagłówek \`Origin\` jest odrzucany. Połączenia serwer–serwer bez \`Origin\` są obsługiwane z kluczem partnera.

## Gwarancje i granice

- Terminy i potwierdzone rezerwacje są przechowywane w **jednym pliku kalendarza na kancelarię**. Zapis do S3 stosuje warunkowy \`If-Match\` / \`If-None-Match\` i ponawia próbę po kolizji.
- Żadnych danych cudzych wizyt w \`dostepnosc\`; każdy partner widzi tylko swoje wpisy.
- Moduł nie tworzy nowego bucketa, osobnej bazy ani nie uruchamia dodatkowej infrastruktury.
- Nie jest to integracja z Google Calendar, Outlook ani zewnętrznym kalendarzem notariusza; źródłem prawdy jest kalendarz NotarAI.
- Nie ma automatycznego wysyłania powiadomień, synchronizacji kalendarzy zewnętrznych, zamykania świąt ustawowych ani rozliczeń klientów hurtowych — to oddzielne funkcje.
- Po połączeniu PR należy uruchomić testy, ręcznie sprawdzić dwa konta kancelarii oraz partnerów w staging, a dopiero potem wdrożyć na produkcję.
