# Strona notarai.pl dla klientów: wykaz kancelarii, blog, umawianie wizyt

Stan na 07.11.2026.

## Co to jest

Trzy części, wszystkie na notarai.pl (hosting az.pl, pliki statyczne) z API
w aplikacji (app.notarai.pl):

1. **Strony miejscowości** (`/notariusz/<miasto>/`, 602 stron + hub
   `/notariusz/`): lista kancelarii z wykazu, przykłady kosztów z `taksa.py`,
   FAQ, formularz umówienia wizyty, dane strukturalne (schema.org `Notary`,
   `FAQPage`, `BreadcrumbList`), `sitemap.xml`, `robots.txt`.
2. **Blog** (`/blog/`): artykuły pisane przez model wyłącznie na podstawie
   faktów z `taksa.py` (stawki, przykłady, dokumenty), po przeczytaniu przez
   człowieka.
3. **Umawianie wizyt**: klient wybiera kancelarię i zostawia kontakt.
   Zgłoszenie trafia do kancelarii korzystającej z notarai (aplikacja, e-mail,
   kalendarz) albo do obsługi notarai (panel `/admin`), która przekazuje je
   kancelarii spoza notarai jednym kliknięciem. To realizuje ofertę „mamy
   klientów dla kancelarii, które korzystają z notarai”.

## Baza kancelarii

- Źródło: arkusz „Baza kancelarii notarialnych Polska 2025” (3501 kancelarii,
  stan wykazu 31.12.2025): oficjalny wykaz z dane.gov.pl (zbiór 22657),
  wyszukiwarki izb (1443 + 567 wpisów) i katalog branżowy (1029 wpisów
  oznaczonych „do ponownej weryfikacji”); 462 kancelarie bez kontaktu.
- `seo/baza.py` czyta XLSX bez dodatkowych bibliotek, naprawia zepsute
  kodowanie (56 adresów), normalizuje telefony (komórkowe `xxx xxx xxx`,
  stacjonarne `xx xxx xx xx`, bez faksów), wybiera jedną wersję adresu, łączy
  literówki miejscowości (604 -> 602) i zapisuje `seo/kancelarie.json`.
- Na strony nie trafiają adresy e-mail; w JSON zostają wyłącznie do
  przekazywania zgłoszeń przez aplikację.
- Aktualizacja: nowy arkusz -> `py -3 seo\baza.py plik.xlsx` -> commit JSON.

## Generowanie i publikacja

```
py -3 seo\generuj.py        strona/notariusz/*, sitemap.xml, robots.txt
py -3 seo\blog.py zbuduj    strona/blog/* z seo/blog/*.md
infra\strona.ps1 wyslij     robi oba kroki i wysyła katalog strona\ na az.pl
```

Katalogi `strona/notariusz/`, `strona/blog/` i `sitemap.xml` nie są w git
(generowane). Po pierwszej publikacji zgłoś `https://notarai.pl/sitemap.xml`
w Google Search Console i Bing Webmaster Tools.

Każda strona miejscowości ma treść, której nie ma inna (lista kancelarii,
liczba, izba, adresy, telefony, formularz), a wspólne części (przykłady
kosztów, FAQ) są rzeczywiście użyteczne; mimo to to 602 podobne strony, więc
po indeksacji obserwuj w Search Console, czy Google nie traktuje ich jako
„thin content”. Wzmocnienie: linkowanie z bloga do miast, uzupełnianie
kart kancelarii o godziny otwarcia i opisy, gdy kancelarie je nadeślą.

## Blog

```
py -3 seo\blog.py generuj "Ile kosztuje darowizna mieszkania"   -> seo/blog/szkice/<slug>.md
py -3 seo\blog.py tematy                                         -> szkice dla seo/tematy.txt
```

Model dostaje prompt `prompty.BLOG` i blok FAKTY (`seo/blog.py fakty`):
stawki, przykłady policzone przez kalkulator, dokumenty. Ma zakaz wymyślania
kwot. Szkic czyta człowiek i przenosi plik z `seo/blog/szkice/` do
`seo/blog/`; dopiero wtedy `zbuduj` go publikuje. Domyślny model to
`PIECZAPP_MODEL` (Opus); `--model eu.anthropic.claude-sonnet-4-6` jest tańszy.
Trzy pierwsze artykuły (zakup mieszkania, nowe stawki, testament) powstały
07.11.2026 na Sonnecie 4.6 i są opublikowane po sprawdzeniu kwot.

## Umawianie wizyt (wizyty.py)

- `POST /api/wizyty/zgloszenie` (otwarty, CORS dla notarai.pl, limit 5 na IP
  na godzinę i 300 na dobę, pole-pułapka): imię, telefon lub e-mail, czynność,
  wartość, termin, wiadomość, zgoda, kancelaria z bazy albo miejscowość,
  parametry z kalkulatora (liczone na nowo na serwerze).
- Routing: kancelaria z bazy jest klientem notarai, gdy jej e-mail z wykazu
  jest w zespole kancelarii w rejestrze albo administrator ustawił powiązanie
  (`PUT /api/admin/wizyty/powiazania/<baza_id>`). Wtedy zgłoszenie dostaje
  `kancelaria_id`, kancelaria widzi je w aplikacji (pasek boczny „Zapytania
  klientów”), dostaje e-mail, a status „umówiona” z datą tworzy wpis w jej
  kalendarzu z telefonem klienta.
- Kancelaria spoza notarai: zgłoszenie widzi obsługa w `/admin` (sekcja
  „Zapytania klientów”) i przekazuje je e-mailem na adres z bazy
  (`POST /api/admin/wizyty/<id>/przekaz`). Wysyłka jest decyzją człowieka,
  nic nie idzie automatycznie do obcych kancelarii. Treść e-maila zawiera
  zgłoszenie klienta i jedno zdanie o notarai.
- Klient dostaje potwierdzenie e-mailem (jeśli podał adres).
- Magazyn: `kancelarie/_administracja/wizyty.json` (S3, szyfrowany, UE);
  retencja 180 dni (`PIECZAPP_WIZYTY_RETENCJA_DNI`). Dane klienta nie trafiają
  do logów. `GET /api/wizyty/kancelarie?miejscowosc=` zwraca id kancelarii
  korzystających z notarai, żeby strona je wyróżniła.

### E-mail (Amazon SES)

1. W konsoli SES (eu-central-1) dodaj tożsamość domeny `notarai.pl`, wpisz
   rekordy DKIM (CNAME) w az.pl, poczekaj na weryfikację.
2. Złóż wniosek o wyjście z piaskownicy SES (bez tego SES wysyła tylko na
   zweryfikowane adresy).
3. Etap 3 wdrożenia z parametrami stosu `EmailNadawcy` (np.
   `notarai <zapytania@notarai.pl>`) i `EmailZgloszen` (kopia dla obsługi).
   Stos dodaje roli zadania uprawnienie `ses:SendEmail`.
Bez tych kroków zgłoszenia działają, tylko bez e-maili.

### Prawo

- Polityka prywatności (wersja 07.11.2026) opisuje kalkulator, formularz
  wizyt (zgoda, odbiorca: kancelaria, retencja 180 dni) i wykaz kancelarii
  (dane zawodowe z rejestrów publicznych, art. 6 ust. 1 lit. f RODO, prawo do
  sprostowania przez kontakt@notarai.pl).
- Przekazanie zgłoszenia kancelarii spoza notarai to wiadomość w imieniu
  klienta na publiczny adres kancelarii, z jednym zdaniem o notarai. Nie
  rozsyłaj z tego mechanizmu ofert bez zgłoszenia klienta.

## Co jeszcze warto zrobić

- Strony miejscowości: „w pobliżu” liczy się po izbie i liczbie kancelarii,
  nie po odległości (brak współrzędnych w bazie).
- Kancelarie mogą prosić o uzupełnienie kart (godziny, opis, zdjęcie):
  formularz zgłoszenia poprawek i pole w rejestrze.
- Blog: generować kolejne tematy z `seo/tematy.txt` partiami (po 3-5) i czytać
  przed publikacją; dopisać linki z artykułów do stron miast.
