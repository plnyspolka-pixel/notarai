# Formularze w systemach urzedowych - wybor podejscia (SPEC, zadanie B1)

Sprawdzono: 16.09.2026. Kolejnosc podejsc wg SPEC: 1 API -> 2 eksport pliku ->
3 schowek/asysta -> 4 automatyzacja przegladarki. Ponizej werdykt per system.

## Skad biora sie wartosci (dodane 20.09.2026)

Silnik potrafi wpisac wartosci do pol, ale ktos musi zdecydowac, co wpisac.
Pola w akcie nazywaja sie po swojemu ("??5: ..., PESEL __ , zamieszkaly"),
a rubryki w rejestrze inaczej. Robi to `formularze/dopasowanie.py`:

1. pole sprawy o nazwie dokladnie takiej, jak `zrodlo` w mapowaniu,
2. tresc aktu odczytana przez model - z cytatem uzasadniajacym kazda wartosc,
3. brak - i tak to nazywamy, zamiast zgadywac.

Kazda wartosc przechodzi przez walidacje (sumy kontrolne). Bledna suma nie
kasuje wartosci, tylko ja oznacza: decyzje podejmuje notariusz, ale musi to
zobaczyc.

Gdy do pola pasuje kilka danych (dwie osoby, dwa numery), rozstrzyga `opis`
pola w mapowaniu. Dlatego kazde nowe pole powinno miec opis napisany jezykiem
notariusza, np. "PESEL zbywcy, bo to on rozporzadza prawem".

Punkt `POST /api/formularze/<system>/dopasuj` zwraca propozycje wraz z cytatami
i ostrzezeniami. Niczego nie wpisuje - to material do sprawdzenia.

## Wspolne ustalenia dla wszystkich trzech systemow

- Wszystkie wymagaja logowania certyfikatem notariusza i/lub podpisu kwalifikowanego.
  **Czlowiek loguje sie sam.** Automatyzacja podlacza sie do JUZ zalogowanej
  przegladarki notariusza (Playwright, polaczenie CDP z uruchomiona przegladarka),
  nigdy nie wpisuje hasla, PIN-u karty ani nie klika w podpis.
- **Skrypt wypelnia, czlowiek wysyla.** Zatrzymanie przed "wyslij / zloz / umiesc /
  podpisz". Podsumowanie tego, co wpisano, przed oddaniem sterowania.
- **Tryb podgladu domyslnie** (pokazuje, co by wpisal). Tryb faktyczny wymaga jawnego
  przelacznika w interfejsie i potwierdzenia regulaminu danego systemu.
- Mapowanie pol w `formularze/<system>.yaml`, nie w kodzie.
- Zadnych danych osobowych w logach; log zawiera: sprawa, system, liczba pol, czas, typ bledu.

## 1. Rejestr Zastrzezen PESEL (przez modul KRN "Rejestry Notarialne")

- Poziom 1 (API): istnieje oficjalne API MC, ale wymaga wniosku administracyjnego
  i stalego IP - patrz rejestry.md. Nie wchodzi w gre "od reki".
- Poziom 2 (plik): brak.
- Poziom 3 (schowek): trywialne - jeden PESEL. Wdrazamy jako minimum.
- Poziom 4 (przegladarka): uzasadnione - sprawdzenie jest obowiazkowe przy KAZDEJ
  sprawie nieruchomosciowej, a formularz to jedno pole. Wynik trafia do sladu
  audytowego sprawdzenia.json. **Od tego systemu zaczynamy.**
- Do potwierdzenia przez notariusza: regulamin Rejestrow Notarialnych.

## 2. CREWAN (Centralne Repozytorium Elektronicznych Wypisow Aktow Notarialnych, KRN)

- Poziom 1: brak publicznej dokumentacji API (strona KRN opisuje tylko obowiazek
  umieszczenia wypisu; https://krn.org.pl/rejestry-notarialne/crewan).
- Poziom 2: nieznane; do sprawdzenia w regulaminie (uchwala KRN nr X/11/2018) i po
  zalogowaniu - czy system przyjmuje paczke/plik.
- Poziom 3: dane opisowe wypisu (rep. A, data, strony) z przycisku "kopiuj".
- Poziom 4: mozliwe jako drugi krok - wypelnienie metadanych i zalaczenie pliku,
  zatrzymanie przed "umiesc". Umieszczenie wypisu ma skutek zewnetrzny -> zawsze czlowiek.
- Status: PO systemie 1.

## 3. Wnioski wieczystoksiegowe (system teleinformatyczny MS, art. 79 pkt 8a PrNot)

- Dostep: certyfikat dostepowy wydawany w DIRS po zalozeniu konta; wyslanie wniosku
  wymaga kwalifikowanego podpisu elektronicznego. System pozwala przygotowac wniosek
  wczesniej i wstepnie zweryfikowac.
  Zrodlo: https://nawokandzie.ms.gov.pl/numer-30/dobre-praktyki-2-numer-30/notariusz-w-elektronicznym-postepowaniu-wieczysto-ksiegowym.html
- Poziom 1/2: brak potwierdzenia publicznego API lub importu XML dla notariuszy;
  do sprawdzenia w dokumentacji MS po zalogowaniu.
- Poziom 3: dane wniosku (KW, zadanie wpisu, dane nabywcy) z przycisku "kopiuj".
- Poziom 4: mozliwe jako trzeci krok - wypelnienie wniosku, zatrzymanie przed
  podpisem i wyslaniem. Wniosek ma skutek zewnetrzny i oplate -> zawsze czlowiek.
- Status: PO systemach 1 i 2.

## 4. Program kancelaryjny (repertorium) - poziom "okienkowy"

Nazwa programu nie zostala jeszcze podana. Zanim cokolwiek: sprawdzic, czy program
ma import z pliku (CSV/XML) albo wlasny interfejs - to prawie zawsze lepsze niz
klikanie po oknach. Sterowanie oknami (poziom 4b) tylko gdy import nie istnieje,
z tymi samymi regulami: podglad domyslnie, czlowiek zapisuje.
