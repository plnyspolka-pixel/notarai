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
- **Tresc ksiegi w projekcie aktu.** `POST /api/sprawy/{id}/projekt` sam
  wczytuje ksiegi sprawy (`ekw.do_projektu`) i przekazuje je modelowi jako
  osobny blok "TRESC KSIEGI WIECZYSTEJ ... Z EKW (nie odpis urzedowy, pobrano
  ...)" z dzialami I-O, I-Sp, II, III, IV (`prompty.blok_ksiag`). Gdy pola
  odczytu albo polecenie wymieniaja numery KW, do projektu ida tylko ksiegi
  o tych numerach; gdy zadnego numeru nie ma - wszystkie ksiegi sprawy.
  Ksiega rozstrzyga warianty o stanie ksiegi (dzialy III/IV, wlasciciel,
  oznaczenie lokalu) bez `<<WYBOR>>`. `ekw.porownaj_z_polami` porownuje
  numer KW, wlasciciela (dzial II) i powierzchnie (dzial I-O) z polami
  odczytu; rozbieznosc trafia do modelu z poleceniem zostawienia
  `<<WYBOR: ...>>`. Odpowiedz i `GET /api/sprawy/{id}` maja `zrodla`
  (`ksiegi`, `ksiegi_pobrano`, `weryfikacja`), zapisane w
  `projekt-zrodla.json`. W logach tylko identyfikator sprawy i liczby
  (ksiegi, rozbieznosci). Bez ksiegi projekt powstaje jak dotad.

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

## Listy sankcyjne i PEP (ustawa AML)

Dodane 07.11.2026 (przeniesione z modulu screeningu Finance You, zrodla
zweryfikowane tam 09.10.2026). Notariusz jest instytucja obowiazana (art. 2
ust. 1 pkt 13 ustawy z 1.03.2018 o przeciwdzialaniu praniu pieniedzy), wiec
sprawdza strony czynnosci na listach sankcyjnych i ustala, czy sa osobami na
eksponowanych stanowiskach politycznych (art. 2 ust. 2 pkt 11, art. 46-46c;
wykaz krajowych stanowisk: rozp. MF z 27.07.2021, t.j. Dz.U. 2023 poz. 1632).

**Zrodla (wylacznie oficjalne i publiczne, bez platnych baz):**

| Zrodlo | Adres | Format | Odswiezanie |
|---|---|---|---|
| UE - skonsolidowana lista sankcji finansowych | webgate.ec.europa.eu/fsd/fsf/public/files/xmlFullSanctionsList_1_1/content (token publiczny z dokumentacji FSF; wlasny w `PIECZAPP_EU_FSF_TOKEN`) | XML | codziennie |
| ONZ - lista Rady Bezpieczenstwa | scsanctions.un.org/resources/xml/en/consolidated.xml | XML | codziennie |
| MSWiA - lista z ustawy z 13.04.2022 | gov.pl/web/mswia/lista-osob-i-podmiotow-objetych-sankcjami | HTML (2 tabele) | codziennie |
| OFAC SDN (USA) | sanctionslistservice.ofac.treas.gov | CSV | domyslnie WYLACZONE (`PIECZAPP_AML_OFAC=1`) |
| API Sejmu (poslowie, 3 kadencje, z data urodzenia) | api.sejm.gov.pl/sejm/term{N}/MP | JSON | co tydzien |
| KPRM - sklad Rady Ministrow | gov.pl/web/premier/sklad-rady-ministrow | HTML | co tydzien |
| Wikidata (CC0) - osoby na stanowiskach z katalogu `aml_listy.KATALOG_PEP` | query.wikidata.org/sparql | SPARQL JSON | co tydzien |

Senat zwraca 403 dla automatow, a API KRS maskuje nazwiska czlonkow organow -
tych zrodel nie uzywamy. Pozycje wykazu bez zrodla maszynowego (sedziowie,
zarzad NBP i RPP, generalowie, samorzad, spolki Skarbu Panstwa...) pokrywa
wylacznie oswiadczenie strony - trzeba o nie pytac, aplikacja go nie zastepuje.

**Jak to dziala (`aml_listy.py`, `aml_dopasowanie.py`, `aml.py`):**
- Listy przychodza do notarai (migawka JSON na zrodlo: lokalnie `dane/listy_aml/`,
  w chmurze `<prefiks>/admin/listy_aml/` w S3). Porownanie liczymy u siebie.
  Dane stron czynnosci nie sa wysylane do zadnego zewnetrznego API.
- Pusta odpowiedz albo mniej niz polowa poprzedniej listy = blad, stara migawka
  zostaje. Wpisy wykreslone (MSWiA) nie trafiaja do indeksu.
- Dopasowanie: normalizacja (tytuly, nazwiska dwuczlonowe, transliteracja, cyrylica
  w 4 wariantach), Jaro-Winkler ograniczony odlegloscia edycyjna + szkielet
  fonetyczny, data urodzenia z PESEL (+10 zgodna, +5 zgodny rok, -25 niezgodna),
  obywatelstwo +3. Bez daty urodzenia po ktorejkolwiek stronie wynik najwyzej 89.
  Progi: 70 "mozliwe", 90 "silne".
- Automat sam stwierdza wylacznie "brak trafien". Kazde trafienie to wpis `wpis`
  w `sprawdzenia.json` i decyzja notariusza (`falszywe_trafienie` albo
  `potwierdzone`, uzasadnienie min. 10 znakow, bez PESEL) zapisywana jako NOWY
  wpis wskazujacy stary - slad jest tylko dopisywany.
- PEP: funkcja trwajaca albo zakonczona w ciagu 12 miesiecy = PEP; starsze =
  "byly PEP" (nie robi trafienia, zostaje w opisie).
- W sladzie nie ma pelnych PESEL-i (`rejestry.WynikSprawdzenia` to sprawdza takze
  w polu `trafienia`). Logi: etykieta roli, liczba trafien, czas - bez nazwisk.
- Odswiezanie: watek w tle co 6 h (`PIECZAPP_AML_LISTY=0` wylacza) oraz przycisk
  administratora `POST /api/admin/aml/listy/odswiez`. Stan list: `GET /api/aml/listy`.

**Do potwierdzenia przez notariusza:** warunki ponownego wykorzystania listy UE FSF
(dane Komisji dla instytucji finansowych) i listy ONZ (kontakt:
sc-sanctionslists@un.org). Listy nie sa nikomu redystrybuowane - sluza wylacznie
do porownan wewnatrz aplikacji.

## CRBR - Centralny Rejestr Beneficjentow Rzeczywistych

Dodane 07.11.2026. Oficjalne API Ministerstwa Finansow (SOAP 1.2, publiczne,
bez uwierzytelniania): `bramka-crbr.mf.gov.pl:5058/.../ApiPrzegladoweCRBR/2022/12/01`,
operacja `PobierzInformacjeOSpolkachIBeneficjentach`, wyszukiwanie po NIP,
KRS albo nazwie (`crbr.py`).

- Podstawa: art. 34 i 37 ustawy AML (ustalenie beneficjenta rzeczywistego
  klienta bedacego osoba prawna). Do bramki idzie NIP albo KRS spolki - dane
  podmiotu, nie osoby.
- Jedno zapytanie = jedna spolka w jednej sprawie, na zadanie notariusza, bez
  cache "na zapas". Wynik trafia do `sprawdzenia.json` (rejestr `CRBR`):
  spolka, beneficjenci (z zamaskowanym PESEL), zglaszajacy, identyfikator
  wniosku z bramki. Strony czynnosci porownujemy z beneficjentami po imieniu
  i nazwisku i zapisujemy, ktore sa, a ktorych brak.
- Statusy: `wpis` (spolka jest w CRBR), `brak_wpisu` (nie ma - sygnal: ustal
  beneficjenta inna droga i odnotuj), `blad` (wiele spolek dla nazwy / odrzucone
  formalnie), `niedostepny` (bramka nie odpowiada).
