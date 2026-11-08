# Rejestry publiczne - ustalenia (SPEC, zadanie A1)

Sprawdzono: 16.09.2026. Zrodla oficjalne podane przy kazdym punkcie.
Reguła: jesli czegos nie da sie potwierdzic w oficjalnym zrodle, integracji nie budujemy.

## Rejestr Zastrzezen Numerow PESEL

**Sciezki dostepu dla podmiotu zobowiazanego (notariusz):**

1. **Modul w systemie "Rejestry Notarialne" Krajowej Rady Notarialnej.** To jest kanal,
   z ktorego notariusze korzystaja w praktyce: dodatkowy modul w systemie KRN daje
   "szybka lacznosc z Rejestrem Zastrzezen Numerow PESEL". Logowanie do Rejestrow
   Notarialnych - certyfikat notariusza. Zrodlo: KRN,
   https://krn.org.pl/aktualnosci/zastrzezenie-numeru-pesel-co-warto-wiedziec-przed-wizyta-u-notariusza
2. **Bezposrednie API Ministerstwa Cyfryzacji (REST, X-API-KEY, lista dozwolonych IP).**
   Wymaga: pisemnego wniosku do MC o udostepnienie danych, potem "wniosku dostepowego"
   do COI (cc.wnioski@coi.gov.pl) z dokumentacja techniczna systemu, ktora bada COI.
   Bezplatne. Srodowisko testowe: int-rejestr-zastrzezen.obywatel.gov.pl/api/v1/,
   endpointy /status-zastrzezenia/aktualny i /status-zastrzezenia/na-dzien, odpowiedz
   JSON ze statusem ZASTRZEZONY / NIEZASTRZEZONY i znacznikiem czasu.
   Zrodla: https://www.gov.pl/web/cyfryzacja/udostepnianie-danych-z-rejestru-zastrzezen-numerow-pesel
   oraz dokumentacja dla integratorow https://www.gov.pl/attachment/5781564b-68dd-4982-9898-5741694a9c67

**Obowiazek:** weryfikacja obowiazkowa przy nabyciu, zbyciu, obciazeniu nieruchomosci
i pelnomocnictwach do tych czynnosci; przy innych czynnosciach fakultatywna (KRN, j.w.).

**Decyzja dla pieczapp:**
- Kanal 2 (wlasne API) jest oficjalny i najsolidniejszy, ale wymaga postepowania
  administracyjnego i stalego IP kancelarii. Do rozwazenia w przyszlosci; wniosek
  sklada notariusz, nie aplikacja.
- Kanal 1 (modul KRN) jest interfejsem INSTYTUCJONALNYM dla notariuszy, nie aplikacja
  dla obywatela, wiec asysta w przegladarce (poziom 3 z formularze.md) nie narusza
  zakazu z SPEC A2. Warunek: regulamin Rejestrow Notarialnych (BIP KRN,
  https://bip.krn.org.pl/rejestry-notarialne) - do przeczytania przez notariusza
  przed wlaczeniem trybu faktycznego; do czasu potwierdzenia dziala tylko tryb podgladu.
- Nie odpytujemy masowo. Jedno sprawdzenie = jedna strona czynnosci, na zadanie
  notariusza, z wpisem w dane/sprawy/<id>/sprawdzenia.json (PESEL zamaskowany).

**Czego brakuje / kogo zapytac:** tresc regulaminu Rejestrow Notarialnych w zakresie
automatyzacji (KRN, bip.krn.org.pl); czy dostawca modulu KRN udostepnia interfejs
dla oprogramowania kancelaryjnego (pytanie do KRN / izby notarialnej).

## Elektroniczne Ksiegi Wieczyste (EKW) - tresc ksiegi

Sprawdzono 07.11.2026.

**Stan faktyczny portalu https://przegladarka-ekw.ms.gov.pl:**
- Publiczny, bez logowania, jedna ksiega na raz po pelnym numerze KW. Oficjalnego
  API dla oprogramowania brak; Ministerstwo nie oferuje dostepu masowego.
- Portal stoi za zapora Imperva/Incapsula. Wejscie z serwerow (chmura, CI) konczy
  sie HTTP 403 "Error 15" jeszcze przed formularzem - potwierdzone 02.11.2026
  z trzech srodowisk. Serwer notarai nie moze wiec czytac EKW sam.
- Rejestr jest jawny z mocy ustawy o ksiegach wieczystych i hipotece, ale dzial II
  zawiera dane osobowe (imiona, nazwiska, czasem PESEL).

**Decyzja dla notarai (ekw.py) - procedura:**
- **Dostawca tresci ksiegi wieczystej dla notarai to Finance You** (API
  partnerskie `POST/GET /api/public/partner-kw`, token `PIECZAPP_FINYOU_TOKEN`,
  adres `PIECZAPP_FINYOU_URL`). Notarai wysyla numer KW i dostaje piec dzialow
  jako tekst i HTML; gdy Finance You dopiero pobiera (`processing`), notarai
  dopytuje co 5 s, najdluzej 4 min. Finance You sam dobiera zrodlo pierwotne
  i to on jest dla kancelarii podmiotem przetwarzajacym (umowa powierzenia,
  docs/ochrona-danych.md). Zrodlo pierwotne zapisujemy przy ksiedze
  (`zrodlo: ... zrodlo pierwotne: ...`).
- Zapasowo / bez Finance You: aktor `regdata/ekw-ksiegi-wieczyste-scraper`
  na platformie Apify (https://apify.com/regdata/ekw-ksiegi-wieczyste-scraper),
  token `PIECZAPP_APIFY_TOKEN`. Rozliczenie za wynik: 0,005-0,010 USD za
  ksiege zaleznie od planu Apify plus 0,025 USD za uruchomienie; ksiegi
  nieodczytane i nieistniejace nie sa liczone. Plan bezplatny: 25 ksiag na
  30 dni. Gdy skonfigurowane sa oba, Finance You ma pierwszenstwo.
- Jedna ksiega na zadanie notariusza, z jawnym potwierdzeniem, zawsze widok
  "aktualna". Bez masowego pobierania i bez lokalnej kopii rejestru - tresc
  trafia tylko do sprawy (`dane/sprawy/<id>/ksiegi/<numer>.json` i `.txt`).
- Kazde pobranie (udane i nieudane) to wpis w `sprawdzenia.json` z rejestrem
  `EKW`; zapytaniem jest numer KW, status `wpis` oznacza wpisy w dziale III
  albo IV, `brak_wpisu` - oba dzialy puste.
- Ksiega z nieodczytanym dzialem jest odrzucana w calosci. Dostawca oznacza
  dzial jako pusty tylko, gdy portal oddal "BRAK WPISOW".
- Przy Apify po odczycie notarai kasuje u dostawcy zbior wynikow i magazyn
  zadania. Kazdy dostawca jest podmiotem przetwarzajacym poza nasza
  infrastruktura - patrz docs/ochrona-danych.md; wymaga umowy powierzenia
  przed uzyciem na danych klientow.
- To **nie jest odpis urzedowy**. Notariusz porownuje tresc ze zrodlem i tak
  oznacza ja interfejs.
- Sekrety w chmurze: `notarai/finyou` (infra/zapisz-sekret-finyou.ps1, adres
  parametrem `FinyouAdres`) albo `notarai/apify` (infra/zapisz-sekret-apify.ps1).
  Bez zadnego z nich karta w interfejsie jest ukryta.

## Krajowy Rejestr Zadluzonych (KRZ)

Sprawdzono 16.09.2026 w przegladarce notariusza (portal odrzuca zapytania spoza
przegladarki kodem 403, wiec pobranie automatyczne nie bylo mozliwe).

**Stan faktyczny portalu https://krz.ms.gov.pl (wersja systemu 1.22.002 - 2026.09.10):**
- Portal publiczny, bez logowania. Menu: Tablica obwieszczen, Wyszukiwanie podmiotow,
  Wyszukiwanie wspolnikow, Wyszukiwanie masy upadlosci, Wyszukiwanie doradcow,
  Weryfikacja autentycznosci dokumentu. Logowanie (Portal Uzytkownikow Zarejestrowanych,
  krz-ext.ms.gov.pl) dotyczy skladania pism, nie wyszukiwania.
- "Wyszukiwanie podmiotow" ma 4 zakladki: (1) Podmiot niebedacy osoba fizyczna,
  (2) Osoba fizyczna prowadzaca dzialalnosc gospodarcza - pola: Firma, Identyfikator
  (PESEL, NIP lub inny), Imie, Nazwisko, (3) Osoba fizyczna nieprowadzaca dzialalnosci
  gospodarczej - jedno pole: Identyfikator (PESEL, NIP lub inny), (4) Sygnatura.
  Przyciski: Wyszukaj, Wyczysc. Formularz siedzi w osobnej ramce
  (krz-rejpub-gui-krz-pub-prod.apps.ocp.prod.ms.gov.pl).
- Na formularzu nie stwierdzono CAPTCHA (brak skryptow recaptcha/hcaptcha/turnstile);
  nie sprawdzano, czy pojawia sie po wyslaniu, bo zapytanie testowe wykonuje notariusz.
- Oficjalnego API dla podmiotow zewnetrznych brak (publicznie dostepne sa tylko
  komercyjni posrednicy, np. MGBI - nie jest to zrodlo oficjalne).
- Na portalu nie ma regulaminu korzystania z wyszukiwarki; stopka zawiera tylko
  Deklaracje dostepnosci, Polityke cookies i Instrukcje (podreczniki PDF na
  krz-info-prod.apps.ocp.prod.ms.gov.pl/krz-help/, m.in.
  KRZ_PP_Podrecznik_uzytkownika_v1.04.pdf). Rejestr jest z mocy ustawy jawny
  (ustawa z 6.12.2018 o Krajowym Rejestrze Zadluzonych).

**Decyzja dla pieczapp:**
- Sprawdzenie w KRZ to zapytanie tylko do odczytu, bezplatne, bez skutku zewnetrznego,
  a portal publiczny jest jedyna oficjalna droga - takze dla notariuszy. Wykonujemy je
  w przegladarce notariusza, JEDNO na strone czynnosci, na zadanie z pieczapp,
  z odstepem miedzy zapytaniami. Bez masowego odpytywania, bez lokalnej kopii rejestru.
- Dla kazdej osoby fizycznej dwa zapytania po PESEL: zakladka "prowadzaca" i
  "nieprowadzaca dzialalnosci". Wynik = zrzut ekranu (dowod starannosci) w
  dane/sprawy/<id>/sprawdzenia/ + wpis w sprawdzenia.json (PESEL zamaskowany).
- Rozpoznanie wyniku (brak wynikow / lista) jest heurystyczne; notariusz OGLADA zrzut
  i zatwierdza status. Wpis w KRZ = alarm, czynnosc do rozwazenia.
- Zaslepka "niedostepny", gdy portal nie odpowiada albo zmienil uklad.
- Do potwierdzenia przez notariusza: tresc podrecznika KRZ_PP (czy wprowadza
  ograniczenia korzystania) - link wyzej.
