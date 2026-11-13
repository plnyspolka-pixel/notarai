# Sceny poza kancelarią: biblioteka współdzielonych ujęć EXT v1

Cel: dodać dynamikę i prawdziwe życie postaci, nie generując nowej scenografii od zera w każdym odcinku. Zasada **STAŁE EXT + różnice pogodowe/pory dnia + nowa gra tylko na pierwszym planie**.

## Biblioteka lokacji
| ID | Miejsce | Master shot generowany/nagrywany jeden raz | Odcinki |
|---|---|---|---|
| EXT01 | Ulica przed kancelarią (dzień) | Fasada / wejście / tramwaj lub samochód w tle | S1 EP01,02,05,08 |
| EXT02 | Klatka schodowa i drzwi kancelarii | Przejścia i reakcje, zawsze ta sama topografia | S1 EP02,06 |
| EXT03 | Parking: samochód Marty, bok i wnętrze | Ten sam model, kolor, tablica **fikcyjna**, fotel i kokpit | S1 EP04,07; S2 EP01,04 |
| EXT04 | Ulica nocna, mokry asfalt | Przejazd z zewnątrz / reflektory, bez danych lokalizacji | S1 EP03,07,08 |
| EXT05 | Kawiarnia / okno przy stoliku | Pierwsza prywatna rozmowa Marty i Aleksandra | S1 EP07–08; S2 EP02,05 |
| EXT06 | Korytarz budynku samorządu (niespecyficzny) | Bez emblematu sugerującego realną izbę czy urząd | S2 EP01,03 |
| EXT07 | Park / nadrzeczny deptak | Krótkie rozmowy prywatne, oddech między napiętymi scenami | S2 EP03,06 |

### Przekrój sceny samochodowej (S1 EP07)
1. Marta wychodzi z kancelarii; rozpoznawalne drzwi (EXT01).
2. Wsiada do samochodu; insert kluczyka i dłoni, **telefon odłożony** (EXT03).
3. Krótki przejazd z zewnątrz; światła i muzyka (EXT04). Żadnego spoglądania na ekran.
4. Dynamiczne **ostre hamowanie wyłącznie montażem**: jedno szybkie cięcie, dźwięk hamulców i zatrzymanie obrazu. Bez inscenizowania niebezpiecznego manewru na drodze i bez wiązania go z używaniem asystenta.
5. Samochód stoi w bezpiecznym miejscu. Marta odzyskuje spokój, wybiera zatrzymanie pracy lub wydaje polecenie asystentowi **w postoju**.
6. Jeśli istnieje pełny, przetestowany przepływ: „Komputerku, przygotuj wariant projektu i pokaż go na komputerze w kancelarii”. Bez testu: Marta korzysta z rzeczywistego interfejsu SaaS po zatrzymaniu albo dzwoni do Basi. Nie dodawać fikcyjnego potwierdzenia wykonania.
7. Cięcie na autentyczny ekran w kancelarii i weryfikację przez człowieka. W każdym przypadku bez podpisywania lub wysyłania dokumentów przez agenta.

## Matryca ujęć powtarzalnych
- X01 wchodzenie do auta, X02 zamknięcie drzwi, X03 lampy w deszczu, X04 zewnętrzne 3/4 auta, X05 nieruchomy kokpit, X06 dłonie bez telefonu, X07 nocny parking, X08 wejście do kawiarni, X09 gest parzenia kawy, X10 spacer po chodniku, X11 klucz w zamku biura, X12 światła w oknach piętra.
- Kamera nie musi za każdym razem pokazywać twarzy. **Backplate i insert** można wykorzystać wielokrotnie. Unikalnie generować tylko twarze reagujące na konkretne wydarzenie oraz rozmowy.
- Składnica assetów: stałe \`ID, scena, czas_dnia, pogoda, kamera, model_auta, kostium, wersja\`; nie tworzyć „tego samego” samochodu innym kolorem lub kierownicą z prawej.
- Używać dźwięku zamiast drogiej animacji do przejść: klucz, sygnalizacja drzwi, opony po mokrej nawierzchni, daleki sygnał telefonu.

## Bramka funkcjonalna zdalnego komputerka
Prawdziwa droga: kanał autoryzacji użytkownika → uprawnienie do konkretnej sprawy i urządzenia → dyspozycja narzędziowa → ślad audytowy → wynik na urządzeniu → potwierdzenie użytkownika tam, gdzie niezbędne. Przed emisją: test na dwóch urządzeniach, ograniczenie ról, brak uprawnień do podpisu i wysyłki bez człowieka.
**Nie reklamować:** automatycznego podsłuchu na hasło „Komputerku”, wysyłki dokumentów urzędowych, nieograniczonego dostępu do sekretów kancelarii przez telefon, ani „gwarancji, że nikt fizycznie nie widział danych”.
