# Booking notariuszy: neutralna kolejność i zachęty bez reklamy

Stan: 08.11.2026, wersja reguł `2026-11-08` (`rekomendacje.WERSJA`).
Kod: `rekomendacje.py`, użycie w `wizyty.py` (strona miejscowości, „dowolna
kancelaria”) i `notariusze.py` (mapa). Testy: `test_rekomendacje.py`.

## Problem

Notariusz nie może się reklamować ani pozyskiwać klientów w sposób sprzeczny
z godnością zawodu i zasadami uczciwej konkurencji (Prawo o notariacie oraz
Kodeks Etyki Zawodowej Notariusza; konkretne paragrafy trzeba potwierdzić
z izbą, ten dokument ich nie przesądza). Jeśli w naszej wyszukiwarce wyżej
stoi kancelaria, która nam płaci, to:

1. dla notariusza wygląda to na **kupioną reklamę** (ryzyko dyscyplinarne),
2. dla nas to **ukryte płatne pozycjonowanie**, a ukrywanie go przed
   konsumentem jest praktyką rynkową zakazaną w każdych okolicznościach
   (ustawa o przeciwdziałaniu nieuczciwym praktykom rynkowym po dyrektywie
   Omnibus; rozporządzenie P2B 2019/1150 art. 5 wymaga ujawnienia głównych
   parametrów rankingu).

Do 08.11.2026 strona miejscowości robiła dokładnie to: kancelarie z notarai
były przesuwane na górę listy (`seo/generuj.py`). To zostało usunięte.

## Zasada

> **Równa widoczność, różna jakość obsługi.**
> To, czy kancelaria korzysta z notarai, nigdy nie decyduje, GDZIE ją widać.
> Decyduje tylko o tym, JAK klient zostanie obsłużony, gdy już ją wybierze.

Analogia, którą łatwo obronić przed izbą: kancelaria, która ma stronę www
albo odbiera telefon po 16, dostaje więcej klientów nie dlatego, że książka
telefoniczna ją wyróżnia, tylko dlatego, że łatwiej się z nią umówić.

## Algorytm kolejności (jednakowy dla wszystkich)

Wejście: wszystkie kancelarie z publicznego wykazu w miejscowości (nie tylko
nasi klienci). Kryteria, po kolei:

| # | kryterium | skąd | dlaczego wolno |
|---|---|---|---|
| 1 | odległość od punktu klienta, w pasmach co 2 km | klient podał położenie | o to pyta klient; pasma, żeby 200 m nie rozstrzygało |
| 2 | czy jest jakikolwiek kontakt w publicznym wykazie | wykaz izby / dane.gov.pl | z kancelarią bez kontaktu nie da się umówić |
| 3 | rotacja dzienna: SHA-256(wersja, dzień, miejscowość, kancelaria) | nic, czysta arytmetyka | każdy ma tę samą szansę na każde miejsce |

Czego algorytm **nie dostaje** (i test to pilnuje): abonamentu, płatności,
konta w notarai, liczby zgłoszeń, ocen, „jakości profilu”, wolnych terminów
z kalendarza notarai. To ostatnie jest najważniejsze: dane, które mają tylko
nasi klienci (np. najbliższy wolny termin), użyte w rankingu dałyby
pośrednie płatne pozycjonowanie.

Własności, które da się pokazać izbie:
- rotacja jest deterministyczna: tego samego dnia każdy odwiedzający widzi
  tę samą kolejność, a każdy może ją przeliczyć z opublikowanej reguły,
- w długim okresie każda kancelaria średnio stoi w środku listy
  i tyle samo razy jest pierwsza (test na 4000 dni),
- koniec z alfabetem, który na stałe faworyzuje nazwiska na „A”.

## „Dowolna kancelaria w miejscowości”

Klient może zostawić wybór nam. Przydział robi kolejka sprawiedliwa:
kancelaria, która w ostatnich 90 dniach dostała od nas najmniej przydziałów,
remis rozstrzyga rotacja. Kancelaria spoza notarai dostaje przydział na równi
z innymi; zgłoszenie przekazuje jej obsługa z panelu /admin (jak dotąd).
Klient widzi wprost: „dobraliśmy z kolejki, po równo dla wszystkich
kancelarii”. Zgłoszenie zapisuje `przydzial: {sposob, wersja, kandydaci}`,
więc każdy przydział da się później rozliczyć.

To zdejmuje też ryzyko, że nasza obsługa ręcznie „podsuwa” zgłoszenia
klientom notarai.

## Zachęty do korzystania z notarai (dozwolone, bo nie zmieniają kolejności)

Wszystkie poniżej działają dopiero **po** wyborze kancelarii przez klienta
albo przez kolejkę. Każda jest opisem sposobu obsługi, a nie wyróżnieniem.

| zachęta | kancelaria w notarai | kancelaria spoza notarai |
|---|---|---|
| przyjęcie zgłoszenia | od razu w aplikacji i e-mailem | obsługa notarai przekazuje e-mailem (dziś ręcznie) |
| termin (rezerwacja online, `rezerwacje_klientow.py`) | klient wybiera wolną godzinę z kalendarza, potwierdzenie od razu | klient podaje preferencję, kancelaria oddzwania |
| przypomnienia (e-mail; SMS do zbudowania) | e-mail/SMS dzień przed wizytą, mniej nieobecności | brak |
| przed wizytą *(częściowo: projekt aktu jest, przesyłanie skanów przez klienta do zbudowania)* | lista dokumentów do zabrania dla danej czynności, bezpieczne przesłanie skanów, wstępny projekt aktu w aplikacji | lista dokumentów ogólna |
| koszt | szacunek taksy z kalkulatora od razu w zgłoszeniu | szacunek też (kalkulator jest dla wszystkich) |
| informacja na karcie | „Zgłoszenie trafia od razu do kancelarii” | brak tej linijki |

Ważne: nie wolno sztucznie pogarszać obsługi kancelarii spoza notarai
(opóźniać przekazania, chować telefonu). Różnica ma wynikać tylko z tego,
co technicznie daje aplikacja.

Linijka na karcie jest **funkcjonalna** („trafia od razu”), bez logo
i bez słów typu „polecana”, „sprawdzona”, „partner”. Nie przesuwa karty.

## Co jest zbudowane (stan 08.11.2026)

| element | gdzie | jak działa |
|---|---|---|
| neutralna kolejność | `rekomendacje.py` | pasma odległości, kontakt, rotacja SHA-256 dnia |
| kolejka „dowolna kancelaria” | `wizyty._przydziel` | najmniej przydziałów w 90 dniach, także dla kancelarii spoza notarai |
| rezerwacja online | `rezerwacje_klientow.py`, `GET /api/wizyty/terminy`, `POST /api/wizyty/rezerwacja` | kancelaria włącza przełącznik „Rezerwacja online dla klientów” (okno Terminy dla klientów hurtowych, te same godziny); termin wchodzi do kalendarza atomowo |
| odwołanie przez klienta | `POST /api/wizyty/rezerwacja/odwolaj`, strona `/wizyta/odwolaj/#token` | token jednorazowy, w pliku tylko skrót SHA-256; najpóźniej 2 h przed wizytą |
| przypomnienia | `rezerwacje_klientow.przypomnij`, wątek przy `PIECZAPP_PRZYPOMNIENIA=true`, ręcznie `POST /api/admin/wizyty/przypomnienia` | po 17:00 e-mail o jutrzejszych wizytach, znacznik zapisywany atomowo, więc bez dubli z kilku kontenerów |
| filtr klienta „tylko z rezerwacją online” | strona miejscowości, `?tylko_online=1` | domyślnie wyłączony, tylko zawęża, nie zmienia kolejności pozostałych |
| sprawdzarka publiczna | `/zasady-kolejnosci/`, `GET /api/wizyty/przejrzystosc` | przeglądarka sama liczy SHA-256 i mówi, czy kolejność zgadza się z regułą; pokazuje liczbę przydziałów z kolejki |
| audyt kolejki | `GET /api/admin/wizyty/rownosc` | różnica między najczęściej i najrzadziej wybieraną kancelarią w mieście; >1 do sprawdzenia |
| mapa z całego wykazu | `seo/geokoduj_wykaz.py` -> `seo/polozenia.json`, `notariusze.lista` | wszystkie kancelarie z wykazu; notarai tylko z dopiskiem „zgłoszenie trafia od razu”; mapa w przeglądarce używa tych samych pasm i rotacji |

Mapa z wykazu zadziała po jednorazowym `python seo/geokoduj_wykaz.py`
(około godziny dla ~3500 adresów przy limicie Nominatim, można porcjami
`--limit 500`) i commicie `seo/polozenia.json`. Bez tego pliku mapa działa
jak dotąd.

## Kolejne pomysły techniczne (nie zbudowane)

1. **Zobowiązanie kolejności z wyprzedzeniem**: codziennie publikujemy
   skrót listy na następny miesiąc (np. w repozytorium albo w pliku na
   stronie). Wtedy nie da się po fakcie „poprawić” kolejności, a izba może
   to sprawdzić bez dostępu do naszych serwerów.
2. **Licznik ekspozycji**: zagregowane (bez danych osobowych) liczniki,
   ile razy każda kancelaria była na 1.–3. miejscu i ile razy ją kliknięto.
   Dowód liczbowy, że rotacja wyrównuje widoczność.
3. **Darmowa wizytówka dla każdej kancelarii z wykazu**: logowanie linkiem
   wysłanym na e-mail z wykazu, edycja godzin, języków, dostępności.
4. **Przypomnienia SMS** przez Amazon SNS w eu-central-1.
5. **Rezerwacja online po przydziale z kolejki**: gdy kolejka wybierze
   kancelarię z rezerwacją online, klient od razu widzi jej wolne godziny.

## Do decyzji (nie wdrożone)

1. **Mapa `/notariusze`** (kod gotowy, potrzebne geokodowanie wykazu, patrz wyżej). Do tego czasu pokazuje tylko kancelarie z ważnym abonamentem
   notarai (`notariusze.publikowana`). To jest de facto lista naszych
   klientów, więc publiczna mapa to wprost wyróżnienie płatne. Propozycja:
   mapa z całego publicznego wykazu (`seo/kancelarie.json` + geokodowanie
   wsadowe), a abonament wpływa tylko na linijkę „rezerwacja online”.
   Do tego czasu mapy nie linkować jako wyszukiwarki notariuszy.
2. **Filtr „tylko z terminem online”** (zbudowany) jako świadomy wybór klienta.
   Prawdopodobnie dopuszczalny (klient sam zawęża, domyślnie wyłączony),
   ale to graniczny przypadek: zapytać izbę przed wdrożeniem.
3. **Darmowa wizytówka dla każdej kancelarii** (godziny, języki,
   dostępność dla osób z niepełnosprawnościami, poprawka danych): taka
   sama dla klientów i nie-klientów. Wzmacnia argument o równości.
4. **Publiczna strona „Zasady kolejności”** (zbudowana: `/zasady-kolejnosci/`; P2B art. 5) z treścią
   sekcji „Algorytm kolejności” i wersją reguł. Dziś opis jest w akapicie
   nad listą kancelarii na stronie miejscowości.
5. Opinia izby notarialnej / KRN na piśmie przed szerszą kampanią.

## Zmiana reguł

Każda zmiana kryteriów: nowa `WERSJA`, aktualizacja tej strony i tekstu na
stronie miejscowości, test w `test_rekomendacje.py`. Nowe kryterium musi
spełniać jedno: jest dostępne na równych zasadach dla każdej kancelarii
z wykazu, także tej, która nigdy nie słyszała o notarai.
