# NOTARAI — KAMPANIA „KOMPUTERKU…” — BIBLIA WIZUALNA

## Decyzja nadrzędna
Jedyną marką komercyjną na ekranie jest **NotarAI**. Kampania NIE tworzy zastępczego logo i NIE zmienia produktu. Oryginalny sygnet pochodzi z `static/notarai-symbol.svg` w repo `plnyspolka-pixel/notarai`. Kolorystyka pochodzi z opublikowanego `notarai.pl`, `app.notarai.pl` oraz `strona/brand-site.css`, `static/financeyou-theme.css`. Stan sprawdzony 11.11.2026.

## Warstwy estetyczne
1. **Produkt**: jasne UI, Montserrat, biały, granat #071D49, tekst #0D193C, indygo #1C1CC0, niebieski #2B52D9, cyan #00CFFF, subtelne obrysy #D9E5F4. Bez burgundowych i złotych elementów interfejsu.
2. **Świat fizyczny**: prawdziwe drewno, książki, neutralne ściany, ciepłe światło boczne, rośliny, wysokie okna. Bordowy żakiet Heleny i mosiądz lampy dopuszczalne jako elementy rzeczywistości, NIE jako identyfikacja.
3. **Grafika filmowa**: używa tylko tokenów marki. Logo i znak pozostają niezmienione; nie zastępować ich piórem, orłem, pieczęcią ani inną grafiką.

## Stałe ramy
* Rodzaj: mikrofabuły informacyjno-edukacyjne z notariuszami. Humor subtelny, wiarygodny.
* Kancelaria: dokładnie ten sam pokój; biblioteka z lewej, biurko centralnie, wysokie okna z prawej, drukarka po prawej. Stosować `plan_kancelarii.svg`.
* Bohaterowie: Helena, Marta, Basia, Kuba. Zachować jeden wzorzec wyglądu, roli, ubioru oraz rekwizytów; patrz `BIBLIA_POSTACI.md`.
* Niezmienny motyw: wypowiedź „Komputerku…” (głos aktora), sygnał wizualny w barwach NotarAI, czytelny rezultat, ocena człowieka.
* Dopuszczalna puenta: żart wynikający z charakterów, NIE z naruszania etyki i wiedzy zawodowej notariuszy.

## Zasady kadrowania i filmowania
* Główne formaty 9:16 (1080x1920); inne 16:9 i 1:1 to adaptacje, nie mechaniczne obcięcia.
* Obiektywy orientacyjne: plan ogólny 28–35 mm; medium 50 mm; portret / reakcja 85 mm; ekran z ramienia 50–70 mm.
* Kamera: statyczna lub dyskretny ruch 10–25 cm; żadnych przypadkowych zoomów i agresywnych obrotów.
* Światło: naturalne miękkie z okna po prawej, stała praktyczna lampa, lekki kontur; neutralne kolory skóry; bez turkusowego światła rzucanego na twarze.
* Pokazanie interfejsu: zrzut/ujęcie prawdziwego frontendu lub wierna makieta, oznaczenie demo; zachować realne ikony, układ i proporcje; nie generować losowych pseudoekranów.
* W dokumentach tylko fikcyjne dane, bez numerów PESEL rzeczywistych osób i bez realnych aktów.

## Grafika systemowa i animacja
* Stan 1: „Komputerku…” — pojawia się niebiesko-cyjanowy dymek z mikrofonem.
* Stan 2: „Już sprawdzam…” — animowane 11 słupków, niska amplituda, maksymalnie 1.1 s pętli.
* Stan 3: „Projekt do weryfikacji” / „Gotowe do sprawdzenia” — nie sugerować podpisania ani wysłania.
* Wejścia 180–250 ms ease-out. Wyjścia 140–200 ms ease-in. Bez złotych świecących łuków i bez bordowych paneli.
* Safe area pionowa: tekst i istotne elementy nie bliżej niż 90 px od boków; środek kadru przedkładamy nad brzegi.
* Logo zawsze w natywnych proporcjach. Przezroczyste logo może mieć minimalnie 72 px szerokości sygnetu na 1080p.

## Produkcja: siatka kontrolna dla każdego odcinka
1. Ten sam obsadowy wzorzec twarzy i fryzur? 2. Ta sama geometria pokoju? 3. Kolory interfejsu i grafiki są zgodne z domeną? 4. Logo jest oryginalne? 5. Hasło „Komputerku” występuje w sposób naturalny? 6. Czy w ekranach pokazano tylko istniejącą funkcję? 7. Czy efekt zewnętrzny wymaga potwierdzenia notariusza? 8. Czy prawdziwe dane osobowe są wykluczone? 9. Czy materiał ma czytelne napisy? 10. Czy plansza końcowa zawiera notarai.pl?

## Stan funkcji głosowej
Repo zawiera `transkrypcja.py` i `/api/transkrypcja`, a front pokazuje przyciski mikrofonu, gdy transkrypcja jest dostępna. Aktualne nagranie wymaga kliknięcia i weryfikacji przepisanej komendy; brak potwierdzonego, nieprzerwanego nasłuchu hasła „Komputerku”. Docelowa automatyzacja pokazywana jako propozycja rozwojowa; nie prezentować jej jako działającej bez testu.

## Osobne ekrany produktu
Do finalnej postprodukcji zamienić makiety na nagrania z bieżącej wersji `app.notarai.pl`, nagrane na danych fikcyjnych. Strona marketingowa sama oznacza makietę kokpitu jako poglądową.
