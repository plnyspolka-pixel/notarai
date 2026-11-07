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

## Wyszukiwanie ksiag wieczystych po wlascicielu (osoba fizyczna / firma)

Sprawdzono: 07.11.2026. Pytanie: czy notarai moze znalezc numery KW klienta po
nazwisku / PESEL albo po firmie (np. po weryfikacji tozsamosci w Didit).

**Stan prawny i faktyczny:**

1. **Publiczna przegladarka ekw.ms.gov.pl wyszukuje WYLACZNIE po numerze KW.** FAQ MS:
   "Aby przegladac ksiegi wieczyste za posrednictwem portalu http://ekw.ms.gov.pl, nalezy
   posiadac numer ksiegi wieczystej. Nie ma mozliwosci korzystania z innych numerow."
   Portal ma limity sesji i czestotliwosci z jednego IP przeciw masowemu pobieraniu, MS nie
   udostepnia go firmom komercyjnym na innych warunkach, API brak.
   Zrodlo: https://www.gov.pl/web/sprawiedliwosc/ekw-pytania-i-odpowiedzi (strona z 29.10.2021).
   Pismo MS do RPO z 09.04.2026 (DL-II.41.24.2026): system "nie umozliwia wyszukiwania danych
   wedlug kryteriow osobowych"; wyszukiwanie w CBDKW "przysluguje wylacznie podmiotom
   wskazanym w ustawie". Zrodlo:
   https://bip.brpo.gov.pl/sites/default/files/2026-04/Odpowiedz_MS_ksiegi_wieczyste_projekt_dostep_9_04_2026.pdf
2. **Notariusz jest podmiotem uprawnionym do wyszukiwania w CBDKW** - art. 36(4) ust. 8 pkt 18
   ustawy o ksiegach wieczystych i hipotece (lista zamknieta: sady, prokuratura, komornicy,
   Policja, ZUS, KAS, ... "18) notariusze"). Warunek: "jezeli jest to niezbedne do realizacji
   zadan ustawowych"; zgoda Ministra Sprawiedliwosci w drodze decyzji, na wniosek (ust. 8,
   10-12). Ust. 9: o zgode moze wystapic tez podmiot dzialajacy w imieniu grupy notariuszy
   (izba notarialna / KRN). Zrodlo (kopia tekstu ustawy, t.j. Dz.U. 2026 poz. 1066 -
   potwierdzic w ISAP): https://arslege.pl/centralna-informacja-ksiag-wieczystych/k49/a7187/
3. **Jak dziala wyszukiwanie** - rozporzadzenie MS z 24.03.2026 w sprawie Centralnej
   Informacji Ksiag Wieczystych (Dz.U. 2026 poz. 411, obowiazuje od 31.03.2026),
   https://eli.gov.pl/eli/DU/2026/411/ogl/pol/pdf :
   - § 20 ust. 1-3: wniosek o zgode (oznaczenie wnioskodawcy, zadania ustawowe z przepisami,
     uzasadnienie niezbednosci; dla notariuszy - imie, nazwisko i PESEL osob, ktore beda
     wyszukiwac). Po zgodzie Centralna Informacja zaklada **konta uzytkownikow z prawem
     wyszukiwania**.
   - § 20 ust. 4-5: osoba wyszukujaca **uwierzytelnia sie w systemie** i przy kazdym
     wyszukaniu **wskazuje kryterium oraz uzasadnia szczegolowo potrzebe**, chyba ze sprawa
     ma sygnature - wtedy wystarczy sygnatura.
   - § 21 ust. 2: kryteria (katalog zamkniety): (1) oznaczenie nieruchomosci / lokalu / domu,
     (2) **oznaczenie podmiotu wpisanego do dzialu II** (wlasciciel - osoba albo firma),
     (3) numer dziennika KW, (4) elementy numeru KW (kod wydzialu + numer repertorium).
   - § 21 ust. 1, § 22: wynik = **lista numerow KW** na ekranie, z kryteriami i znacznikiem
     czasu (data, godzina, minuta, sekunda); znalezione ksiegi mozna przegladac bez osobnych
     wnioskow; Centralna Informacja moze ograniczyc liczbe jednorazowo wyszukanych ksiag.
   - § 8: wniosek o wyszukanie sklada sie **wraz z oplata** przez system (platnosc tylko
     mechanizmem systemu). Stawka 20 zl wg rozporzadzenia z 29.11.2013 (akt oznaczony jako
     archiwalny) - aktualna stawke potwierdzic.
   - § 23 + art. 36(4) ust. 13: osobny tryb "bez kazdorazowego wniosku do Centralnej
     Informacji" (wyszukiwanie z wlasnego systemu podmiotu). Wymaga m.in. systemu
     identyfikujacego osobe, zakres i date pobrania, zabezpieczen technicznych i
     organizacyjnych, uzasadnienia specyfika zadan i decyzji MS; Centralna Informacja tworzy
     wtedy "techniczne warunki". To jedyna ustawowa sciezka do integracji programistycznej -
     publicznej dokumentacji interfejsu brak.
4. **Logowanie notariusza do EKW**: certyfikatem zawodowym wydanym przez Ministra
   Sprawiedliwosci; system rejestruje kazda czynnosc (wypowiedz czlonka KRN). Stanowisko MS:
   notariusz bedzie przegladal "tak jak dotychczas", jako uzytkownik uwierzytelniony
   certyfikatem. Projekt UD310 (uwierzytelnianie przegladajacych przez Wezel Krajowy / konta
   PRS) jest w konsultacjach i nie zmienia sciezki dla notariuszy. Zrodlo: rp.pl 17.11.2025,
   https://www.rp.pl/nieruchomosci/art43335391-koniec-z-anonimowym-przegladaniem-ksiag-wieczystych-rykoszetem-dostana-notariusze
5. **Didit** (weryfikacja tozsamosci): wynik zawiera m.in. first_name, last_name,
   date_of_birth, document_number, personal_number (identyfikator krajowy z dokumentu - dla
   polskiego dowodu powinien to byc PESEL; potwierdzic na dokumencie testowym), issuing_state.
   Zrodlo: https://docs.didit.me/reference/data-models.md. Dla firm Didit ma wyszukiwanie
   w rejestrze (KYB) dla Polski: nazwa / numer rejestrowy -> dane spolki. Didit NIE ma
   dostepu do ksiag wieczystych - daje pewne dane podmiotu, ktore wpisujemy jako kryterium (2).

**Decyzja dla notarai:**
- Wyszukiwanie po wlascicielu jest mozliwe WYLACZNIE z konta notariusza w EKW, po decyzji
  MS. Nie budujemy niczego na publicznej przegladarce ani na komercyjnych posrednikach
  (scrapery, portale "po adresie / po nazwisku" - nieoficjalne, sprzeczne ze SPEC A2 i z
  pismem MS).
- Interfejs wyszukiwania jest INSTYTUCJONALNY (jak modul KRN) - asysta w zalogowanej
  przegladarce notariusza (poziom 4 z formularze.md) nie narusza SPEC A2. Czlowiek loguje
  sie certyfikatem sam; notarai podpina sie do zalogowanej przegladarki (CDP, jak przy KRZ).
- Wyszukanie jest wnioskiem z oplata i z uzasadnieniem rejestrowanym przez MS -> ma skutek
  zewnetrzny. **Skrypt wypelnia, czlowiek wysyla**: notarai wpisuje kryterium (imie,
  nazwisko, PESEL z Didit albo ze skanu; dla firmy nazwa, REGON) i uzasadnienie (czynnosc
  i sprawa, np. "umowa sprzedazy, sprawa <id>"), notariusz klika "Wyszukaj". Jedno
  wyszukanie = jedna strona czynnosci w konkretnej sprawie, na zadanie notariusza. Bez
  odpytywania "na zapas", bez lokalnej kopii.
- Wynik (lista numerow KW + znacznik czasu) trafia do dane/sprawy/<id>/sprawdzenia.json
  (PESEL zamaskowany) + zrzut ekranu; numery KW zasilaja sprawe (dalej jak dotad: wydruk
  z przegladarki -> odczyt skanow).
- Tryb z art. 36(4) ust. 13 (integracja systemowa) - do rozwazenia dopiero, gdy kancelaria
  zechce wystapic o taka decyzje; wniosek sklada notariusz, nie aplikacja.

**Czego brakuje / kogo zapytac:**
- Czy notariusz ma juz konto z prawem wyszukiwania (zakladka wyszukiwania po zalogowaniu
  do EKW)? Jesli nie - wniosek z § 20 do MS (Departament Informatyzacji i Rejestrow
  Sadowych) albo przez izbe notarialna (art. 36(4) ust. 9).
- Uklad formularza wyszukiwania po zalogowaniu (pola dla osoby: imie, nazwisko, PESEL?;
  dla firmy: nazwa, REGON?; pole uzasadnienia / sygnatury; postac wyniku) - do zebrania
  w przegladarce notariusza (zrzuty), zanim powstana selektory. Bez tego kod nie powstaje.
- Regulamin / warunki korzystania z systemu EKW dla uzytkownikow uwierzytelnionych (czy
  dopuszczaja asyste w przegladarce) - notariusz czyta przed wlaczeniem trybu faktycznego.
- Aktualna oplata od wniosku o wyszukanie i sposob jej rozliczania na koncie notariusza.
- Czy w wyniku Didit dla polskiego dowodu personal_number = PESEL (sesja testowa).
