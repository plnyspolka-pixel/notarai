# NotarAI — odczyt KW z Obscura MCP (stealth)

Status: **integracja kodu / niepotwierdzony test EKW na realnym runtime**. 
Nie deklarowac jako produkcyjnie dzialajace do spelnienia kryteriow ponizej.

## Uzycie przez notariusza

W **Rozmowie o sprawie** wpisz np.:

- `Sprawdź księgę wieczystą WA4M/00160286/2`
- `Sprawdź hipotekę w tej sprawie` — tylko gdy w kontekście sprawy jest **dokładnie jeden** poprawny numer KW
- `Pobierz aktualną treść KW WA4M/00160286/2`

Naturalne polecenie z jawnym czasownikiem uruchamia istniejący endpoint
`pobierz_ksiege` z potwierdzeniem, po sprawdzeniu uprawnienia `rejestry`.
Nie uruchamiamy narzędzia na podstawie tekstu zeskanowanych dokumentów ani
samych wniosków modelu językowego. Przy kilku numerach KW aplikacja pyta, którą księgę.
Wynik to pięć działów, widok „aktualna”, w sprawie JSON/TXT + audyt; w czacie
tylko statusy działów (bez PESEL). Wynik nie jest odpisem urzędowym.

## Konfiguracja

Obscura to **oddzielny proces**; Cloudflare Worker/NotarAI nie uruchamia go sam.

1. Uruchom zainstalowany w `finyou` obraz `render+stealth` Obscura
   v0.2.7 z `obscura mcp --http --stealth` i tokenem Bearer.
   Nie używaj domyślnego obrazu pozbawionego stealth transport.
2. Serwer MCP jest single-operator. Przydziel **dedykowaną instancję na jedną
   kancelarię** i tylko jeden aktywny worker żądań. Blokada w kodzie działa
   wewnątrz procesu, nie zastępuje kolejki rozproszonej przy wielu workerach.
3. Na serwerze NotarAI ustaw sekrety (tylko backend, AWS Secrets Manager):
   - `PIECZAPP_OBSCURA_MCP_URL=https://your-private-access-host/mcp`
   - `PIECZAPP_OBSCURA_MCP_TOKEN=<token z hosta Obscura>`
   - `PIECZAPP_OBSCURA_KANCELARIA=<identyfikator kancelarii w NotarAI>`
   - `PIECZAPP_CF_ACCESS_CLIENT_ID`, `PIECZAPP_CF_ACCESS_CLIENT_SECRET` (jeśli tunnel używa Access Service Auth)
4. `PIECZAPP_OBSCURA_KANCELARIA` musi **dokładnie** odpowiadać
   `magazyn.kancelaria()` w kontekście żądania. Inne kancelarie w tej aplikacji
   **nie otrzymają** wspólnego MCP; zachowują dotychczasowy Finance You/Apify.
   Dla trybu lokalnego wartość identyfikatora to `lokalna`.

Przed uruchomieniem tunelu obowiązkowo zabezpiecz host przez Cloudflare Access
oraz Bearer, odrzuć anonimowe żądania i nie wystawiaj portów 13000/9222 publicznie.
Na środowisku produkcyjnym wymuś HTTPS, dedykowaną tożsamość i
rozdzielenie sieci i sekretów per kancelaria.

## Przebieg

1. Walidacja numeru KW wraz z cyfrą kontrolną, limit jednej księgi.
2. MCP `browser_navigate` do oficjalnej wyszukiwarki.
3. MCP `browser_fill_form` w trzy pola EKW (identyfikatory potwierdzone
   otwartym rozszerzeniem marcin-l/KsiegiWieczyste).
4. Przejście na **aktualną** treść, odczyt działów I-O, I-Sp, II, III, IV.
5. Walidacja domeny, numeru KW, niepustych działów i różnic widoków.
6. Dopiero pełny wynik jest przekazywany do istniejącego `ekw.zapisz()`,
   który archiwizuje treść w sprawie i zapisuje ślad audytowy.
7. `browser_close` niezależnie od sukcesu.

Portal za Impervą może odmówić dostępu. Program **nie próbuje rozwiązywać CAPTCHA,
obchodzić aktywnych wyzwań ani rotować adresów IP**. Przy błędzie nie zapisuje
niepełnej księgi jako zweryfikowanej. Nie wykonuje masowych pobrań.

## Ważne ograniczenia

- Selektory kolejnych ekranów bazują na udokumentowanym UI, lecz wymagają
  testu z prawdziwą stroną (MCP może napotkać zmieniony DOM). Błędy są fail-closed.
- Obscura i pośredniczący Cloudflare Access **technicznie widzą dane** przesyłane
  w sesji. Ta integracja nie stanowi dowodu zero knowledge / zero operator access.
  Przed uruchomieniem na danych klientów wymagana jest analiza powierzenia,
  lokalizacji infrastruktury, retencji i tajemnicy notarialnej.
- Wewnętrzny mutex nie zapewnia izolacji przy wielu instancjach NotarAI.
  Do SaaS trzeba uruchomić odrębne pule lub kolejkę per kancelaria.
- Udostępniona treść jest materiałem pomocniczym. Notariusz sprawdza
  dział III, IV i **wzmianki** względem oryginału; wydruk ekranu to nie odpis urzędowy.

## Kryteria odbioru (bez przypisywania sukcesów na wyrost)

- `python -m pytest test_ekw_obscura.py test_ekw.py test_ekw_finyou.py test_rozmowa.py`
  przechodzi na CI i lokalnie (bez sieci).
- Na rzeczywistym runtime MCP zwraca pięć odrębnych, zgodnych z EKW działów
  testowej KW; data, numer, informacje i wzmianki zgadzają się z ręcznym odczytem.
- Przypadki 403/Error 15, CAPTCHA, niepełnego działu i zmiany DOM zwracają
  błąd i nie produkują „pozytywnego” sprawdzenia.
- Nieuprawniony użytkownik, inna kancelaria, brak tokenu i nieautoryzowany klient
  nie otrzymują dostępu do MCP ani danych sprawy.
- Realne testy obciążenia i izolacji wielu workerów przed włączeniem w SaaS.

Źródła: oficjalna instrukcja EKW
https://ekw.ms.gov.pl/eukw_ogol/pomoc/instrukcja.pdf
oraz Obscura MCP https://github.com/h4ckf0r0day/obscura/blob/main/docs/Use-the-MCP-server.md
