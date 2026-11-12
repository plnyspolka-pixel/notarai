# Brand i production bible NotarAI V4
Komputerku… • Kancelaria pod Siódemką • Kanon i wymagania realizacji

Wersja 4.0 z 12.11.2026. Dokument dla reżysera, grafika, montażysty, operatora generowania obrazów, realizatora dźwięku i producenta. Obowiązuje razem z biblią sezonu, matrycą i autoryzacją. Punktem zgodności jest PR #20, head 5e58dd03b79ba1228657ec858b3116e84e5f659d.

## Architektura nazw
NotarAI jest marką produktu. „Komputerku…” jest platformą kampanii i rytuałem zlecania pracy. „Kancelaria pod Siódemką” jest tytułem serialu. Na ekranie nie powstaje druga marka oprogramowania ani nowy sygnet. Tytuł serialu zapisujemy typograficznie, bez pieczęci, orła, pióra i herbu udających logo.

## Zasoby nadrzędne
Oryginalny sygnet pochodzi ze static/notarai-symbol.svg w repozytorium NotarAI. Logotyp użyty w dokumentach to gotowy lockup z pakiet/01_marki/logo_kampanijne_poziome_light.png w PR #20. Pakiet zawiera niezmienione kopie tych zasobów z odczytanego head. Nie przerysowujemy znaku, nie zmieniamy proporcji, kolorów i kierunku gradientu. Nazwy plików oraz sumy kontrolne umożliwiają sprawdzenie tożsamości zasobów. Starszy static/logo.png przedstawia inne oznaczenie i nie należy do aktualnej identyfikacji tej kampanii.

## Zakres produkcji
Ten pakiet definiuje koncepcje i wymagania. Nie uruchamia generowania głosów, awatarów, filmów ani kolejki publikacji. Identyfikatory postaci i głosów są dziedziczone z PR i nie są poświadczeniem dostępności kont, licencji lub zatwierdzenia kadrów. Brak zatwierdzenia w źródle blokuje wykorzystanie.

---PAGE---
# System wizualny marki
## Kolory z tokenów PR
Granat #071D49 i głęboki granat #061744 tworzą podstawę. Tekst #0D193C. Niebieski #2B52D9, błękit #2197D3 i cyan #00CFFF tworzą akcenty. Turkus znaku wynika z oryginalnego SVG, m.in. #00D6E8 i #00CDE9; nie zastępujemy nim dowolnie wszystkich tokenów UI. Tło #F5F7FC, biel #FFFFFF, obrys #D9E5F4, tekst pomocniczy #647392. Sukces #23764B i alert #B52E44 mają znaczenie statusowe, nie dekoracyjne.

Nie przenosić burgundu stroju Heleny ani mosiądzu scenografii do identyfikacji produktu. Świat kancelarii może być ciepły, a interfejs pozostaje jasny i zgodny z marką. Nie oświetlać twarzy turkusem dla podkreślenia AI.

## Typografia
Montserrat jest krojem podstawowym dokumentów, plansz, napisów i grafiki. W filmie używać czytelnych odmian Regular, Medium i SemiBold. Unikać Thin w małym tekście. Zapasowe Segoe UI i Arial służą awaryjnemu odczytowi dokumentów na urządzeniu bez Montserrat, nie stanowią zamiany projektu marki. W PDF font powinien być osadzony. W DOCX wskazano Montserrat; przed eksportem na innym komputerze sprawdzić dostępność fontu.

## Proporcje i odstępy
Logo zachowuje natywne proporcje i przezroczystość. Dla sygnetu na 1080p minimalna szerokość wynosi 72 px zgodnie z biblią PR. Robocze pole ochronne to co najmniej jedna czwarta szerokości sygnetu; jest to reguła produkcyjna V4 do zatwierdzenia, nie deklaracja oficjalnej księgi znaku. Zakaz rozciągania, obrysowywania i umieszczania na tle o podobnej jasności.

## Grafika i stany
Dymek „Komputerku…” może wskazywać początek zlecenia, ale nie zastępuje rzeczywistego sposobu uruchomienia mikrofonu. Animacja pracy asystenta pozostaje umowną warstwą filmu. Wynik podpisujemy adekwatnie: „Projekt do weryfikacji”, „Wynik do oceny” albo faktyczny komunikat produktu. Nie używać „Zatwierdzone”, „Bez ryzyka” i „Gotowe do podpisu” jako skutku operacji systemu.

---PAGE---
# Scenografia i kamery
## Kanon kancelaria v2
Pokój 6,5 × 5 m, wysokość 3,4 m, biała sztukateria. Parkiet w jodełkę #B98A52, kremowe ściany #EFE6D6, orzech #5A3A22, skóra koniak #8A4B2A, satynowy mosiądz #B08D57. Regały zachodnie, okna wschodnie, główne biurko Heleny w środku, stół roboczy SW, sekretariat SE. Miękkie światło dzienne 5600 K i lampy 3000 K. Brak kolorowych świateł i nagłych zmian pory dnia.

## Stanowiska kamer
K1: 28 mm, plan ogólny z południa, ujęcie matki i grupy. K2: 85 mm, biurko Heleny, ocena wyniku. K3: 50 mm, sekretariat i drukarka, Basia. K4: 50 mm, stół przez ramię, nagranie produktu. K5: 50 mm, stół en face, Marta i Kuba. K6: 50 mm, biblioteka i przekazanie materiału. K7: 35 mm, drzwi i wejścia. K8: 35 mm, okno i przebitki. K9: 85 mm, detal biurka i dokumentów. Źródłowe pozycje i azymuty pozostają w scenografia.json.

W konfiguracji postaci Heleny istnieje także kadr K2m. Traktować go jako wariant opisany w źródle postaci; nie dopisywać automatycznie nowej pozycji do planu kamer. Przed użyciem sprawdzić zgodność kadru i pole zatwierdzony. Nie zakładać, że każdy obraz w katalogu jest dopuszczony.

## Budowanie kadrów
Nowe ujęcie wykorzystuje zatwierdzoną planszę, referencję postaci, arkusz i plan kamery. Nie generować pokoju od nowa z samego opisu. Zmiana geometrii pokoju wymaga kancelaria-v3; zmiana wyglądu postaci wymaga obsada-v3. Klienci mogą być nierozpoznawalną sylwetką przy K7. Nowa stała postać wymaga osobnej karty i zatwierdzenia.

## Kontrola ciągłości
Porównać meble, orientację okien, drzwi, materiały, skalę ciała, kostium, rekwizyty i kierunek światła. Ruch ust i dłoni nie może zmieniać trzymanego dokumentu. Przy awatarze zachować widoczną twarz, spokojną pozę i swobodne dłonie zgodnie z kanonem PR. Nie generować czytelnej treści aktów w obrazie sceny; ekrany i teksty dokumentów dodaje się w kontrolowanej postprodukcji.

---PAGE---
# Obsada i tożsamość
## Role i wygląd
Helena: właścicielka, 56 lat, srebrny bob, bordowa marynarka i kremowa bluzka, spokojne gesty. Marta: notariuszka, 38 lat, ciemne włosy do ramion, granatowa marynarka, naturalny uśmiech, laptop. Basia: sekretariat, 51 lat, upięte włosy, okulary, beżowy kardigan i apaszka. Kuba: aplikant, 28 lat, kręcone włosy, biała koszula i grafitowa kamizelka. Szczegóły źródłowych kart mają pierwszeństwo wobec skrótowego opisu.

## Głosy odziedziczone z PR
Helena: IUhsOeEtgXvOVX7dbZPU. Marta: BDuEI9b2twykxFyFIbv4. Basia: XxH7vHpT0p7INeJx8ihA. Kuba: 4tlWcR8SYaOZ0nfbKuq6. Przed renderem producent sprawdza ich zgodność z aktualną konfiguracją postaci i uprawnienia do użycia. Głosy prowadzi osobny strumień pracy; V4 nie tworzy ich ponownie i nie zmienia ustawień.

## Awatary
README PR wskazuje aktualną obsadę v2, podczas gdy historyczny szablon nadal wskazuje v1. Źródłem prawdy jest aktualna karta postaci po zatwierdzeniu kadru, nie stary identyfikator awatara. W odczytanej karcie Heleny avatar_id v2 jest pusty, a kadry mają zatwierdzony=null. To blokada produkcji tych ujęć, nie powód do użycia v1 pod etykietą v2.

## Gra i ruch
Helena: małe skinienia i uniesienie brwi, bez triumfalnych gestów. Marta: sprawny, spokojny ruch, bez agresywnego tempa. Basia: operacyjna pewność i oszczędna ironia. Kuba: energia i uważność, bez karykaturalnej niekompetencji. Reakcje pozostają krótkie i wynikają z sytuacji. Wspólny kadr nie może zmieniać tożsamości postaci dla wygody generatora.

## Zgody i prawa
Przed wykorzystaniem sprawdzić pochodzenie wizerunków, głosów, licencje dostawców, możliwość komercyjnej publikacji i wymagane oznaczenia. Nie dodawać zdjęć realnych osób jako referencji bez osobnej podstawy i zgody. Sam fakt obecności zasobu w PR nie stanowi kompletnej dokumentacji praw do publikacji.

---PAGE---
# Ekrany i warstwy filmu
## Rzeczywisty produkt
Finalne ekrany działających funkcji pochodzą z nagrania zatwierdzonej wersji NotarAI na koncie demonstracyjnym i testowych danych. Nie generować ekranów modelem obrazu. Nie przerysowywać UI w sposób sugerujący przyciski lub integracje, których nie ma. Każde nagranie ma metrykę: funkcja, build, środowisko, tryb lokalny lub SaaS, urządzenie, data, osoba testująca i identyfikator dowodu.

## Plany rozwoju
Dla niewdrożonego zakresu obowiązuje etykieta „Koncepcja funkcji planowanej — niedostępna w prezentowanej wersji”, widoczna przez cały fragment, a nie tylko w opisie posta. Wizualnie używać planszy lub schematu, nie pseudozrzutu działającej aplikacji. CTA prowadzi do rozmowy o potrzebach, nie zakupu funkcji. Znaczek AI i etykieta funkcji planowanej mają różne znaczenia i nie zastępują się.

## Formaty i czytelność
Master 1080 × 1920, 9:16. Adaptacje 1920 × 1080 i 1080 × 1080 są osobnymi kompozycjami. Tekst i istotne elementy co najmniej 90 px od boków pionowego kadru zgodnie z PR. Dodatkowe górne i dolne rezerwy ustala się po podglądzie na docelowej platformie; nie stosować jednego założenia do wszystkich serwisów. Podgląd na rzeczywistym telefonie jest obowiązkowy.

## Napisy i oznaczenia
Napisy generowane z czasów zaakceptowanego audio, sprawdzone po polsku, maksymalnie dwie krótkie linie. Nie zasłaniają źródła, daty, ostrzeżenia i przycisku potwierdzenia. Zgodnie z najnowszym README PR mały znaczek AI jest obecny przez cały film. Stosować także wymagane ustawienia oznaczania na platformie po aktualnej ocenie prawnej. Nie polegać na samym znaczku, jeśli wymagane jest dodatkowe ujawnienie charakteru materiału.

## Ruch grafiki
Wejścia 180–250 ms ease-out, wyjścia 140–200 ms ease-in, spokojna animacja statusu. Bez błysków, losowych zoomów i świetlnych efektów sugerujących nieograniczoną sprawczość AI. Ekran utrzymany tak długo, aby dało się odczytać jeden kluczowy rezultat.

---PAGE---
# Dźwięk i montaż
## Warstwa chaosu
Na początku dwa lub trzy wiarygodne źródła: telefon, drukarka, pytanie z drzwi. Nie tworzyć nieprzerwanego hałasu utrudniającego odbiór. Widz ma rozpoznać przerwanie uwagi, a nie odczuć sensoryczny atak. Po punkcie zwrotnym tło pozostaje, lecz główna czynność jest wyraźna. Nie stosować magicznego wyciszenia całej kancelarii.

## Głos i muzyka
Polszczyzna naturalna, bez reklamowego patosu. Po opracowaniu dialogów wykonać test wymowy NotarAI, nazw rejestrów i terminów zawodowych. Muzyka opcjonalna, bez napięcia sugerującego sensację lub zagrożenie klienta. Mowa ma pierwszeństwo. Docelową głośność i szczyty ustalić zgodnie ze specyfikacją kanału, odsłuchując na telefonie i słuchawkach; nie przyjmować jednego niezweryfikowanego presetu.

## Ciągłość i skróty
Nie montować kliknięcia z jednej wersji produktu z wynikiem innej. Skrócenie czasu procesu musi być jawne, gdy mogłoby tworzyć obietnicę wydajności. Nie dodawać odliczania ani podpisu „w kilka sekund” bez pomiaru i zatwierdzenia warunków. Każdy wynik musi mieć prawdziwy związek z pokazanym wejściem.

## Rytm 38 sekund
0–3 hak, 3–10 konflikt, 10–13 zlecenie, 13–24 operacja, 24–31 kontrola, 31–35 puenta, 35–38 outro. To szkielet koncepcji, nie plan wypowiedzi. Jeśli wymogi prawne lub czytelność nie mieszczą się w czasie, uprościć odcinek albo zwiększyć czas w granicach zaakceptowanej adaptacji. Nie usuwać kontroli dla szybszego tempa.

## Kontrola montażu
Producent porównuje cały film z kartą odcinka i rejestrem twierdzeń. Sprawdza, czy puenta, napisy, muzyka lub cięcie nie zmieniają sensu zatwierdzonej informacji. Prawnik i produkt oglądają finalny plik, nie wyłącznie transkrypcję. Zmiana ekranu, CTA, etykiety lub sposobu działania wymaga ponownej kontroli.

---PAGE---
# Produkcja powtarzalna i zarządzanie zasobami
## Etapy i odpowiedzialność
Producent wybiera wariant i kompletuje dowody. Product owner zatwierdza zakres funkcji. Notariusz autoryzuje treść merytoryczną, prawnik sprawdza warunki publikacji, dane i prawa. Reżyser rozwija koncepcję w późniejszy scenariusz. Grafik i realizator obrazu używają zamrożonych referencji. Montażysta składa wyłącznie zaakceptowane źródła. Osoba publikująca sprawdza komplet zgód i zgodność sumy pliku.

## Tor z PR
Stałe głosy ElevenLabs → zatwierdzone kadry → HeyGen dla postaci mówiących i fal dla potrzebnych ujęć scenicznych → autentyczne nagrania produktu → Remotion lub caption-burner → napisy i warstwy → kontrola → kolejka. Domyślny kierunek awatara w aktualnej dokumentacji to heygen-avatar-6-turbo, ale wybór silnika i jego dostępność należy sprawdzić w chwili produkcji. V4 nie weryfikuje cen ani dostępu usług.

## Pakiet jednego odcinka
Karta koncepcji; późniejszy zaakceptowany scenariusz; manifest kadrów i postaci; dowody funkcji; nagrania wejścia i wyniku; audio z czasami; projekt montażu; eksport master i adaptacje; miniatura; opis; brief i finalny mail; potwierdzenia praw oraz podpisy autoryzacji. Nazwa robocza: NAI_S1_E03_V4_r01_9x16. Zmiana treści zwiększa rewizję i unieważnia podpisy poprzedniego pliku.

## Koszt i planowanie
Nie przenosić starych szacunków cen z PR do zobowiązania budżetowego. Przed produkcją zebrać aktualne stawki dostawców i koszt pracy ludzi. Budżet odcinka: zatwierdzone kadry + sekundy animacji × liczba prób + znaki audio × liczba prób + montaż + kontrola prawna i produktu + adaptacje. Najpierw jedna próbka ujęcia i jeden pilot; dopiero potem zamówienie pozostałych odcinków. Korekta napisu nie powinna wymuszać ponownego renderu postaci.

## Archiwizacja
Manifest zapisuje ścieżkę, wersję, źródło, licencję, zatwierdzającego i hash każdego zasobu. Pliki źródłowe są oddzielone od eksportów. Nie podmieniać po cichu twarzy, głosów, scenografii ani ekranu w zatwierdzonym materiale. Archiwalne scenariusze z PR pozostają osobnym zestawem.

---PAGE---
# Odbiór produkcyjny
## Lista oględzin
Ta sama twarz i fryzura w całym filmie. Kostium zgodny z kartą. Geometria pokoju i kierunek światła zachowane. Dłonie, dokumenty i usta bez artefaktów. Oryginalny znak i logotyp z PR w natywnych proporcjach. Montserrat i tokeny marki. Prawdziwe ekrany i fikcyjne dane. Czytelne źródła i statusy. Znaczek AI przez cały film oraz właściwe etykiety planów. Kontrola człowieka przed efektem zewnętrznym. Jedno CTA do zatwierdzonego celu.

## Warunki nieprzyjęcia
Brak praw do zasobu, niezatwierdzony kadr, różne wersje produktu sklejone w jedną demonstrację, nieczytelna etykieta planu, brak dowodu funkcji, prawdziwe dane w tle, symulowany wynik pomocnika, automatyczny podpis lub złożenie wniosku, twierdzenie o pełnej zgodności prawnej produktu. Każdy z tych przypadków zatrzymuje publikację, także gdy materiał wygląda poprawnie wizualnie.

## Dostępność i adaptacje
Sprawdzić kontrast, rozmiar napisów, odbiór bez dźwięku i zrozumiałość audio bez patrzenia na ekran. Wersja pozioma i kwadratowa przechodzą własny odbiór, ponieważ kadrowanie może ukryć status lub źródło. Miniatura i opis nie mogą obiecywać szerszego działania niż film.

## Kontrola zgodności z PR
Przed realizacją porównać aktualny head PR z zamrożonym punktem odniesienia V4. Zmiany postaci, scenografii, oznaczeń AI, szablonu odcinka i produkcji wymagają wpisu w dzienniku różnic. W razie sprzeczności producent zatrzymuje odpowiedni zasób do rozstrzygnięcia przez właściciela, zamiast wybierać wygodniejszy wariant.

## Materiały przekazywane dalej
V4 jest wejściem do scenariuszy i produkcji, nie gotowym zleceniem publikacji. Wszystkie bramki są domyślnie zablokowane. Odbiór plików koncepcyjnych nie odblokowuje emisji. Dokument AUTORYZACJA_V4 opisuje osobny proces nadania zgody dla finalnego filmu, mailingu i strony.
