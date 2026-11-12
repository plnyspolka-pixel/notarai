# NotarAI — Kancelaria pod Siódemką / Sezon 1
## Wszystkie scenariusze w jednym pliku Markdown
**Wersja V4, 12 listopada 2026 · 8 odcinków · status: do autoryzacji prawnej i produktowej.**

**Kanon:** Helena Radecka, Marta Domańska, Barbara Wrona, Jakub Maj, Irena Nowak, Paweł Nowak, Joanna i Robert Kaczmarkowie. Cena 640 000 zł, mieszkanie 56,40 m²; wydanie lokalu po uzgodnieniach 15 stycznia 2027 r. Paweł nie jest pełnomocnikiem.

**Wspólne zasoby:** pliki referencyjne i brand w folderze `03_ASSETY_SHARED`, klipy współdzielone R01–R22 i detale promptu w folderze `04_PROMPTY_I_MONTAZ`. Oznaczenia Rxx w scenariuszach odnoszą się do biblioteki klipów do jednorazowego przygotowania, nie do już istniejących filmów.

---

---
title: "Kancelaria pod Siódemką — Odcinek 01: Poniedziałek, 8:57"
brand: NotarAI
series: Kancelaria pod Siódemką
season: 1
episode: 1
version: "Scenariusz produkcyjny V1"
duration: "85 sekund"
status: "Projekt do autoryzacji prawnej, produktowej i realizacyjnej"
date: "2026-11-12"
---

# NotarAI — „Kancelaria pod Siódemką”
## Odcinek 01: „Poniedziałek, 8:57”

**Format:** film fabularno-edukacyjny, około 85 sekund, 13 scen.  
**Gatunek:** obyczajowy mikroserial o pracy kancelarii, z lekkim humorem i tajemnicą na koniec.  
**Główna funkcja:** sporządzanie projektu aktu notarialnego na podstawie własnego wzoru kancelarii i uprzednio odczytanych dokumentów.  
**Funkcje dodatkowe:** kalendarz powiązany ze sprawą, elektroniczna teczka, zdjęcia telefonem, kontrola danych po odczycie, pobranie Worda.  
**Motyw marki:** „Komputerku…” — charakterystyczny sposób zwracania się do asystenta, bez sugerowania funkcji automatycznego nasłuchu, której nie potwierdzono.  
**Zasada nadrzędna:** NotarAI przygotowuje i porządkuje dane; notariusz dokonuje oceny, sprawdzenia i podejmuje decyzje.

## Założenie dramaturgiczne

Kancelaria rozpoczyna kolejny intensywny dzień. Telefony, interesanci, dokumenty i terminy nachodzą na siebie. Wszyscy pracują profesjonalnie, lecz liczba równoległych obowiązków powoduje napięcie. Stopniowo widzimy, jak NotarAI porządkuje informacje i przyspiesza przygotowanie projektu aktu. W finale pojawia się zagadkowa prośba klientki — pani Ireny Nowak — o rozmowę z notariuszką bez obecności syna.

**Bohaterowie:**
- **Helena:** doświadczona notariuszka, wymagająca, bardzo uważna na poprawność czynności.
- **Marta:** notariuszka otwarta na nowe narzędzia, operacyjnie prowadzi sprawę.
- **Basia:** organizuje recepcję i przepływ informacji, zna klientów i terminy.
- **Kuba:** aplikant, pracuje z dokumentami i ustala dane wymagające wyjaśnienia.
- **Pani Irena Nowak:** klientka, której historia będzie rozwijana w kolejnych odcinkach.

---

## Scenariusz scena po scenie

### SCENA 01 — „Nie ma jeszcze dziewiątej”
**Czas:** 00:00–00:05  
**Miejsce:** recepcja.  
**Kamera:** seria bardzo krótkich ujęć; zegar, słuchawka telefonu, drzwi, wydruk z drukarki, twarze klientów.  
**Dźwięk:** telefon, drukarka, drzwi, urwane rozmowy. Bez muzyki.

Zbliżenie na zegar: **8:57**. Dzwoni telefon. Basia odbiera. W tej samej chwili otwierają się drzwi kancelarii. Za pierwszym klientem wchodzi drugi. Drukarka kończy wydruk. Ktoś z gabinetu pyta o teczkę.

**Kuba (spoza kadru):** „Basiu, gdzie są dokumenty do jutrzejszej sprzedaży?”

Basia patrzy w stronę głosu, ale nie może odpowiedzieć, bo rozmawia przez telefon.

**Funkcja NotarAI:** żadna — najpierw widz musi rozpoznać problem: normalne, nakładające się obowiązki kancelarii.

### SCENA 02 — „Jeszcze jeden telefon”
**Czas:** 00:05–00:12  
**Miejsce:** recepcja.  
**Kamera:** głównie twarz i gesty Basi; równoległa akcja w głębi kadru.

Basia kończy pierwszą rozmowę.

**Basia:** „Tak, jutro o jedenastej trzydzieści. Termin jest zapisany”.

Odkłada słuchawkę. Telefon odzywa się ponownie.

**Klient:** „Dzień dobry. Ja tylko na chwilę, przyniosłem jeszcze dokument”.

**Basia:** „Dzień dobry. Już się panem zajmuję”.

Z gabinetu wychodzi Marta z teczką w ręku.

**Marta:** „Basiu, sprawa pani Ireny?”

**Basia:** „Już sprawdzam”.

Moment przeciążenia — Basia musi skojarzyć informację z kilkoma równoległymi sprawami.

**Funkcja NotarAI:** budowanie potrzeby szybkiego dotarcia do informacji o sprawie.

### SCENA 03 — „Wszystko jest zapisane”
**Czas:** 00:12–00:19  
**Miejsce:** stanowisko Basi.  
**Kamera:** plan na Basię i rzeczywisty ekran aplikacji; bez makiety udającej produkt.

Basia otwiera NotarAI i przechodzi do **Kalendarza**. Widać zaplanowany na następny dzień, na 11:30, termin sprzedaży nieruchomości powiązany z istniejącą sprawą.

**Basia:** „Irena Nowak. Jutro, jedenasta trzydzieści. Teczka jest założona”.

**Marta:** „Dobrze. Zobaczmy, co już mamy”.

**Funkcja NotarAI:** kalendarz kancelarii, data, godzina, rodzaj czynności, powiązanie terminu ze sprawą.  
**Źródło w repo:** `kalendarz.py`, `static/index.html`.  
**Granica:** nie pokazujemy automatycznej rezerwacji terminu przez agenta; jest on już zapisany.

### SCENA 04 — „Ten dokument też do sprawy”
**Czas:** 00:19–00:25  
**Miejsce:** recepcja.  
**Kamera:** półzbliżenie klienta i Basi, potem ekran telefonu.

Klient przekazuje Basi dokument uzupełniający, dotyczący lokalu.

**Klient:** „To ten dokument, o który pani prosiła”.

**Basia:** „Dziękuję. Dołączę go do sprawy. Proszę zaczekać chwilę”.

Basia otwiera właściwą sprawę w NotarAI na telefonie. Kuba podchodzi po teczkę, ale Basia gestem prosi, by zaczekał.

**Funkcja NotarAI:** mobilny dostęp do istniejącej sprawy w aplikacji.  
**Granica:** kadr powinien pokazywać ten sam identyfikator sprawy, co w kalendarzu; mobilną ścieżkę potwierdzamy testem na koncie demonstracyjnym.

### SCENA 05 — „Jedno zdjęcie”
**Czas:** 00:25–00:33  
**Miejsce:** telefon Basi → ekran komputera Marty.  
**Kamera:** zbliżenie na prawdziwe UI aparatu i listę plików sprawy.

Basia otwiera **Pliki sprawy**, wybiera **Aparatem**, fotografuje dokument i naciska **Wyślij**. Montażowe przejście do komputera Marty, która otwiera pliki tej samej sprawy. Widzimy nowy plik JPG.

**Marta:** „Widzę. Zdjęcie jest już w teczce”.

**Basia:** „To dobrze, bo za chwilę zadzwonią z następną sprawą”.

Odzywa się telefon.

**Funkcja NotarAI:** dodanie zdjęcia z telefonu do archiwum konkretnej sprawy.  
**Źródło w repo:** `static/index.html`, `app.py` — `POST /api/sprawy/{id}/pliki`, `test_aparat_ui.py`.  
**Granica:** zdjęcie zostaje zapisane po kliknięciu „Wyślij”; nie twierdzimy, że od razu automatycznie uruchamia odczyt ani że samo zdjęcie oznacza stwierdzenie tożsamości.

### SCENA 06 — „Co jeszcze zostało?”
**Czas:** 00:33–00:40  
**Miejsce:** biurko Marty.  
**Kamera:** ekran rzeczywistego widoku „Weryfikacja odczytu”, twarze Marty i Kuby.

Kuba siada obok Marty.

**Kuba:** „Mamy już wszystko do projektu?”

**Marta:** „Do pierwszej wersji — mamy materiały odczytane w piątek. Sprawdźmy jeszcze pola”.

Marta otwiera **Weryfikację odczytu**. Widać dane wyciągnięte z uprzednio przetworzonych skanów oraz ewentualne pola wymagające uwagi.

**Marta:** „Tutaj trzeba coś potwierdzić. Tego nie uzupełniamy na wyczucie”.

**Kuba:** „Dopytam klienta”.

Krótki kadr na filtr **Wymagają uwagi**.

**Funkcja NotarAI:** odczyt danych, walidacja, sygnalizacja braków, niepewnych lub rozbieżnych pól.  
**Źródło w repo:** `app.py`, `static/index.html` — etap „Weryfikacja odczytu”, `odczyt.json`.  
**Granica:** nowo sfotografowany dokument jest dołączony do sprawy, ale nie został automatycznie włączony do wcześniejszego odczytu.

### SCENA 07 — „Pani rejent chce to dzisiaj”
**Czas:** 00:40–00:46  
**Miejsce:** wejście do gabinetu Heleny.

Helena wychodzi, trzymając okulary.

**Helena:** „Marto, chciałabym dziś przejrzeć projekt na jutro. Bez zostawiania tego na ostatnią chwilę”.

**Marta:** „Dane są już odczytane. Przygotuję pierwszą wersję na naszym wzorze”.

**Helena:** „Pierwszą wersję — dobrze. Potem ją sprawdzimy”.

Helena wraca do gabinetu. Marta i Kuba wymieniają krótkie uśmiechy.

**Funkcja NotarAI:** przygotowanie projektu na wzorze kancelarii.  
**Wymowa zawodowa:** Helena nie rezygnuje z nadzoru ani oceny treści.

### SCENA 08 — „Komputerku…”
**Czas:** 00:46–00:52  
**Miejsce:** stanowisko Marty.  
**Dźwięk:** odgłosy z recepcji lekko cichną, montaż zwalnia.

Marta siada przed ekranem.

**Marta, z półuśmiechem:** „No dobrze, komputerku. Bierzemy się za akt”.

Klika rzeczywisty przycisk **Sporządź projekt**. Na ekranie pojawia się komunikat **„Sporządzam projekt…”**.

**Funkcja NotarAI — główna:** generowanie projektu aktu na podstawie zapisanych i zweryfikowanych pól, wzoru kancelarii oraz obowiązujących zasad redakcyjnych.  
**Źródło w repo:** `app.py` — `POST /api/sprawy/{id}/projekt`, `docs/styl-i-zasady.md`.  
**Granica:** „Komputerku” to na tym etapie motyw narracyjny. Marta uruchamia akcję przyciskiem; nie sugerujemy działania niewdrożonego hasła wybudzającego.

### SCENA 09 — „Kancelaria nie przestaje pracować”
**Czas:** 00:52–01:01  
**Miejsce:** recepcja, stanowiska pracy, gabinet.  
**Kamera:** spokojniejszy montaż równoległy.

Widzimy kilka czynności wykonywanych podczas generowania projektu:
- Basia odbiera telefon i sprawdza termin w kalendarzu.
- Kuba wyjaśnia z klientem dane, które wymagają potwierdzenia.
- Marta przegląda pozostałe dokumenty.
- Helena prowadzi inną rozmowę zawodową.

Wracamy do ekranu: projekt nadal się sporządza. Przeskok czasu — zegar pokazuje **9:24**.

**Funkcja NotarAI:** przygotowywanie projektu jako proces, który może trwać kilkanaście minut lub dłużej.  
**Granica:** nie obiecujemy błyskawicznego wygenerowania obszernego aktu w kilka sekund.

### SCENA 10 — „Projekt jest”
**Czas:** 01:01–01:08  
**Miejsce:** biurko Marty.  
**Kamera:** ekran „Projekt dokumentu”, następnie reakcje Marty i Kuby.

Marta otwiera wygenerowany projekt. Jeśli wynik demonstracji je zawiera, pokazujemy znaczniki `<<BRAK: ...>>` i `<<WYBOR: ...>>`.

**Marta:** „Projekt jest. Zostały miejsca do wyjaśnienia”.

**Kuba:** „Przynajmniej wiadomo dokładnie, czego szukamy”.

Marta wybiera **Pobierz jako Word**.

**Funkcja NotarAI:** projekt aktu Word i oznaczenie elementów wymagających kontroli.  
**Źródło w repo:** `app.py`, `static/index.html` — „Projekt dokumentu”, `GET /api/sprawy/{id}/plik`.  
**Granica:** wyświetlany tekst i znaczniki muszą pochodzić z rzeczywistej demonstracji na danych fikcyjnych.

### SCENA 11 — „Dobrze, że nie zgaduje”
**Czas:** 01:08–01:15  
**Miejsce:** gabinet Heleny.

Marta przekazuje Helenie projekt. Helena przegląda oznaczone fragmenty i zatrzymuje się przy jednym z nich.

**Helena:** „Tu jeszcze trzeba wyjaśnić stan faktyczny”.

**Marta:** „Dlatego zostawił to do sprawdzenia”.

**Helena:** „I bardzo dobrze. Dokumentów się nie uzupełnia domysłami”.

Helena pierwszy raz wyraźnie aprobuje sposób działania systemu.

**Funkcja NotarAI:** wskazywanie braków i ograniczeń odczytu; zachowanie kontroli notariusza.  
**Wymowa merytoryczna:** projekt nie jest aktem gotowym do podpisu.

### SCENA 12 — „Pani Irena prosiła…”
**Czas:** 01:15–01:21  
**Miejsce:** drzwi gabinetu Heleny.  
**Dźwięk:** cisza; bez sensacyjnej muzyki.

Basia uchyla drzwi.

**Basia:** „Pani rejent, dzwoniła jeszcze pani Irena. Chciałaby z panią porozmawiać przed jutrzejszą czynnością”.

**Helena:** „Oczywiście”.

Basia waha się przez moment.

**Basia:** „Powiedziała, że najlepiej… bez syna”.

Helena odkłada długopis. Cięcie.

**Funkcja NotarAI:** żadna nowa; budowanie serialowej intrygi z poszanowaniem autonomii klientki i zawodowej roli notariusza.

### SCENA 13 — Plansza końcowa
**Czas:** 01:21–01:25  
**Obraz:** oryginalny znak NotarAI, granatowo-niebiesko-turkusowa identyfikacja i Montserrat. Bez alternatywnego, bordowo-złotego logotypu.

**Tekst planszy:**

> **NotarAI**  
> Mniej chaosu. Więcej czasu na to, co ważne.  
> **Kancelaria pod Siódemką — ciąg dalszy nastąpi.**

---

## Matryca prezentowanych funkcji

| Funkcja | Sceny | Podstawa w repozytorium | Status w filmie |
|---|---:|---|---|
| Kalendarz kancelarii | 03 | `kalendarz.py` | Rzeczywisty ekran |
| Termin powiązany ze sprawą | 03 | `kalendarz.py` | Rzeczywiste dane demonstracyjne |
| Mobilny aparat | 04–05 | `static/index.html`, `test_aparat_ui.py` | Prawdziwe wykonanie i kliknięcie „Wyślij” |
| Pliki przypisane do sprawy | 05 | `app.py`, `/api/sprawy/{id}/pliki` | Rzeczywista lista załączników |
| Weryfikacja odczytanych danych | 06 | `app.py`, `static/index.html` | Wynik na wcześniej odczytanych materiałach |
| Sporządzenie projektu | 08–10 | `app.py`, `/api/sprawy/{id}/projekt` | Własny wzór i faktyczny czas generowania |
| Braki i warianty projektu | 10–11 | `app.py`, `dokumenty.py` | Tylko jeżeli wystąpią w prawdziwym wyniku |
| Eksport Word | 10 | `app.py`, `/api/sprawy/{id}/plik` | Rzeczywisty plik DOCX |

## Wytyczne realizacyjne

### Estetyka
- Kancelaria ma wyglądać jak wiarygodne, dobrze prowadzone biuro notarialne — nie jako miejsce pełne bałaganu i niekompetencji.
- Napięcie wynika z przeciążenia liczbą równoległych obowiązków, pośpiechu i przerywania pracy.
- Montaż pierwszych 20 sekund jest dynamiczny, po uruchomieniu pracy w NotarAI stopniowo spokojniejszy.
- Nie tworzyć fikcyjnych ekranów udających rzeczywiste UI.
- Oryginalna identyfikacja NotarAI: sygnet z repozytorium, Montserrat i aktualna paleta granatu, błękitu oraz turkusu.

### Dane i demonstracja
- Wszystkie nazwiska, PESEL, KW, dokumenty, numery repertorium i inne dane na ekranach muszą być fikcyjne, lecz wewnętrznie spójne.
- Materiały do odczytu muszą być przygotowane przed zdjęciami i rzeczywiście przetworzone w aplikacji.
- Zdjęcie wykonane przez Basię w trakcie odcinka jest załącznikiem sprawy; nie przypisujemy mu automatycznie wpływu na projekt sporządzony z wcześniejszych danych.
- Z ekranu pokazujemy tylko stany i komunikaty rzeczywiście uzyskane z programu na danych testowych.
- Wybór sposobu przechowywania danych (SaaS kontra lokalny) musi umożliwiać używany w filmie przepływ między urządzeniami.

### Bezpieczeństwo narracji prawnej
- Projekt Word nie jest dokumentem gotowym do podpisu i musi zostać zweryfikowany przez notariusza.
- NotarAI nie dokonuje oceny prawnej zamiast notariusza ani nie rozstrzyga o dokonaniu lub odmowie czynności.
- Samo sfotografowanie dowodu lub innego dokumentu nie jest równoznaczne ze stwierdzeniem tożsamości.
- Nie sugerujemy, że polecenie wypowiedziane do urządzenia jest już realizowane przez funkcję stale nasłuchującego asystenta; Marta rzeczywiście klika przycisk.
- Każde twierdzenie o prawie, procedurze i funkcjonalności ma przejść odrębną autoryzację przed publikacją.

## Mailing do odcinka 01 — wytyczne, bez gotowego tekstu

**Problem:** fragmentaryzacja pracy kancelarii — telefony, terminy, dokumenty, klienci i projekt aktu na jutro.  
**Obietnica:** NotarAI porządkuje informacje o sprawie i pomaga przygotować projekt aktu, tak aby notariusz mógł skupić się na ocenie i kontakcie z klientami.  
**Zainteresowanie:** zaproszenie do obejrzenia krótkiego odcinka „Poniedziałek, 8:57”.  
**Następny krok:** demonstracja rzeczywistego przebiegu przygotowywania aktu.  
**Nie ujawniać:** prośby pani Ireny o rozmowę bez syna — to zakończenie mające zachęcić do drugiego odcinka.

## Kontrola przed nagraniem

- [ ] Ustalić fikcyjną sprawę sprzedaży lokalu i przygotować spójne dokumenty testowe.
- [ ] Utworzyć w NotarAI sprawę z uprzednio odczytanymi materiałami oraz wzorem aktu.
- [ ] Powiązać termin w kalendarzu z identyfikatorem tej sprawy.
- [ ] Sprawdzić na realnym telefonie zalogowanym na konto demonstracyjne aparat i przesyłanie plików do sprawy.
- [ ] Zweryfikować, że plik dodany przez Basię jest widoczny na komputerze Marty w wybranym trybie przechowywania danych.
- [ ] Przeprowadzić prawdziwy odczyt i zapisać widok pól wymagających uwagi.
- [ ] Wykonać pełne generowanie projektu, zmierzyć czas i nagrać rzeczywiste stany interfejsu.
- [ ] Zweryfikować dokument Word i brakujące/niepewne informacje.
- [ ] Potwierdzić zgodność scen z odpowiednimi uprawnieniami kont zespołu.
- [ ] Zatwierdzić materiał przez redaktora prawnego, praktykującego notariusza i osobę odpowiedzialną za produkt.
- [ ] Sprawdzić gotowy film, napisy, mailing i planszę końcową jako jeden materiał kampanii.

## Cel emocjonalny

**Początek:** odbiorca rozpoznaje własną codzienność i presję.  
**Środek:** widzi konkretne działanie NotarAI, spokój i odzyskiwanie uwagi.  
**Koniec:** dostrzega profesjonalizm notariusza oraz nowe pytanie dotyczące pani Ireny.

**Skrót idei odcinka:**

> Sprawy nie przestają się piętrzyć. Ale kiedy dokumenty, terminy i informacje są uporządkowane, kancelaria może skupić się na tym, czego komputer za nią nie zrobi.

**Status:** scenariusz roboczy oparty na elementach znalezionych w repozytorium NotarAI. Przed publikacją wymagane są testy środowiska produkcyjnego oraz autoryzacja prawna i zawodowa.

---

# EP01 — nota koniecznej korekty continuity
# EP01 — obowiązkowa poprawka continuity przed nagraniem

Ten plik uzupełnia kanoniczny scenariusz `EP01_Poniedzialek_857.md` i NIE zastępuje jego 13 scen.

1. Bohater określony w pierwotnym scenariuszu jako „Klient” (sceny 02, 04, 05) to **Paweł Nowak, syn Ireny**, 45 lat. **Nie dodawać Zenona**, brata, kredytobiorcy ani nie czynić syna właścicielem.
2. Dokument przyniesiony przez Pawła to **D08: zaświadczenie od zarządcy nieruchomości dotyczące rozliczeń eksploatacyjnych**. D04 to fotografia tego samego papieru wykonana przez Basię. Nie jest to bankowa umowa kredytu kupujących.
3. Scena 03: wtorek 17 listopada, 11:30, termin planowanej czynności. Scena 09: montażowy skok od 8:57 do ok. 9:24 — prawdziwy czas generowania nie jest stały.
4. Marta w scenie 08 **klika** „Sporządź projekt” po wypowiedzeniu „Komputerku”; brak aktywnego wake-word. Widz nie może uznać, że głos uruchamia wykonanie.
5. Zdjęcie dodane w scenie 05 jest **załącznikiem**, nie jest automatycznie ponownie odczytywane w tym samym przebiegu generacji. Projekt w pilocie korzysta z dokumentów, które przetworzono w piątek.
6. Kalendarz i sprawa używają tego samego rekordu w realnym interfejsie; na overlayu można zachować identyfikator produkcyjny `S-041-2026`, ale nie podszywać go pod format identyfikatora backendu.
7. Ostatnia prośba Ireny: „bez syna”; bez sugerowania, że syn jest sprawcą przestępstwa, pełnomocnikiem lub beneficjentem sprzedaży.
8. Oryginalna nazwa serii i logotyp pozostają niezmienione; nie wprowadzać burgundowego alternatywnego logo.


---

# EP02 — Proszę nie przy nim

**Data fabularna:** 17.11.2026 · **Czas:** 78 s · **Wersja:** robocza do autoryzacji · **Format:** 9:16, adaptacja 16:9


> **Kanon:** nie zmieniać nazwisk, wieku, relacji, dat ani dokumentów z `01_KANON/BIBLIA_INTRYGI_KANON_2026-11-12.md`. Odcinek nie jest konsultacją prawną; przed publikacją wymaga kontroli notariusza.


## Funkcja główna
Weryfikacja danych i zatrzymanie projektu do wyjaśnienia


**Uzupełniające:** Kalendarz: ręczna zmiana planowanego terminu; historia rozmowy jako zapis roboczy.


**Logline:** Irena przychodzi na rozmowę z Heleną i pokazuje, że nie wszystkie ustalenia przesłane przez rodzinę są ustaleniami sprzedającej.


**Hak:** Cichy głos: „Dziś nie chcę podpisywać tego w takim brzmieniu”.


**Co widz odkrywa:** Irena chce sprzedać, lecz nie przyjęła wydania lokalu 1 grudnia.


**Pytanie końcowe:** Skąd do projektu i rozmów trafiła niepotwierdzona data?


## Scenopis — wszystkie sceny


### E02S01 · 00–05 · Zimny początek

- **Miejsce:** korytarz; **obsada:** Helena, Irena.

- **Działanie:** Irena stoi przed drzwiami gabinetu; w dłoni ściska niewielką kartkę. Korytarz jest spokojny, za ścianą słychać telefon.

- **Dialog / napisy:** IRENA: „Nie chciałabym, żeby Paweł teraz był przy tej rozmowie”.

- **Kadr i montaż:** CU dłoni i twarzy Ireny; bez sensacyjnej muzyki.

- **Prawdziwa funkcja / ograniczenie:** Brak. Dajemy przestrzeń człowiekowi.

- **Biblioteka wspólna:** `R05,R18` · **nowy beat/ujęcie:** `N02A: powstrzymywany niepokój Ireny`.

- **Punkt kontrolny:** Nie sugerować przymusu lub ograniczenia zdolności do czynności prawnych bez faktów.

- **Minimalny prompt delta** (dołączany do jednego promptu bazowego, nie samodzielny): `elderly client at notary hallway holding folded note, restrained anxiety`.



### E02S02 · 05–12 · Słuchanie

- **Miejsce:** gabinet Heleny; **obsada:** Helena, Irena.

- **Działanie:** Helena zaprasza klientkę, odkłada projekt i zamyka laptop, okazując pełną uwagę.

- **Dialog / napisy:** HELENA: „Proszę powiedzieć własnymi słowami, jak wyobraża sobie pani tę sprzedaż”.

**IRENA:** „Sprzedać chcę. Ale nie tak szybko się wyprowadzić”.

- **Kadr i montaż:** Dwuplan statyczny; ujęcie zza ramienia Ireny.

- **Prawdziwa funkcja / ograniczenie:** Nie używać AI w momencie ustalania woli strony.

- **Biblioteka wspólna:** `R06,R19` · **nowy beat/ujęcie:** `N02B: szczera rozmowa`.

- **Punkt kontrolny:** Art. 80 PrNot.

- **Minimalny prompt delta** (dołączany do jednego promptu bazowego, nie samodzielny): `notary respectfully listening to elderly property seller, serious two shot`.



### E02S03 · 12–21 · Rozbieżność dat

- **Miejsce:** gabinet Heleny; **obsada:** Helena, Irena.

- **Działanie:** Irena mówi, że 1 grudnia nigdy nie był przez nią potwierdzonym terminem wydania. Helena zaznacza ten punkt w swojej roboczej notatce.

- **Dialog / napisy:** IRENA: „Syn mówił o grudniu, ale ja mówiłam o połowie stycznia”.

**HELENA:** „Rozumiem. Musimy to wyjaśnić ze wszystkimi stronami”.

- **Kadr i montaż:** CU kartki 1 XII / 15 I; zapis ręczny, bez efektu automatycznego „alarmu AI”.

- **Prawdziwa funkcja / ograniczenie:** Brak: odróżniamy dokument od ustalenia strony.

- **Biblioteka wspólna:** `R09,R11` · **nowy beat/ujęcie:** `N02C: para kontrastujących terminów na papierze`.

- **Punkt kontrolny:** Oddzielić wydanie lokalu od przejścia własności.

- **Minimalny prompt delta** (dołączany do jednego promptu bazowego, nie samodzielny): `two handwritten conflicting move-out dates on confidential case note no real data`.



### E02S04 · 21–28 · Dobre intencje

- **Miejsce:** recepcja; **obsada:** Basia, Paweł.

- **Działanie:** Paweł przyszedł do kancelarii, ale respektuje prośbę matki o prywatność. Czeka, sprawdzając telefon.

- **Dialog / napisy:** PAWEŁ: „Mama długo rozmawia?”

**BASIA:** „Pani rejent wszystko z nią spokojnie wyjaśni”.

- **Kadr i montaż:** Półzbliżenie Pawła; bez podejrzliwego oświetlenia.

- **Prawdziwa funkcja / ograniczenie:** Brak; budujemy wiarygodne postacie.

- **Biblioteka wspólna:** `R01,R03` · **nowy beat/ujęcie:** `N02D: życzliwie niecierpliwy Paweł`.

- **Punkt kontrolny:** Nie przedstawiać Pawła jako osoby umocowanej prawnie.

- **Minimalny prompt delta** (dołączany do jednego promptu bazowego, nie samodzielny): `middle-aged adult son waiting respectfully in notary office reception`.



### E02S05 · 28–36 · Dane a ustalenia

- **Miejsce:** stanowisko Marty; **obsada:** Marta, Kuba.

- **Działanie:** Marta otwiera zapisaną sprawę, zakładkę weryfikacji odczytu, filtr „Wymagają uwagi”. Kuba porównuje z roboczą kartą warunków T1.

- **Dialog / napisy:** KUBA: „Czyli data z maila nie może być traktowana jako potwierdzona przez sprzedającą?”

**MARTA:** „Właśnie. Źródło to nie zawsze zgoda strony”.

- **Kadr i montaż:** Rzeczywisty ekran; osobny kadr roboczej notatki D05.

- **Prawdziwa funkcja / ograniczenie:** Weryfikacja odczytu, oznaczenia braków; brak automatycznego dowodu akceptacji.

- **Biblioteka wspólna:** `R07,R08,R14` · **nowy beat/ujęcie:** `N02E: konkretne ludzkie porównanie D05 z notatką`.

- **Punkt kontrolny:** Dane na ekranie z realnego testowego odczytu; żaden spreparowany wynik AI.

- **Minimalny prompt delta** (dołączany do jednego promptu bazowego, nie samodzielny): `notary and trainee reviewing data verification screen, highlighting unresolved source`.



### E02S06 · 36–44 · Granica

- **Miejsce:** gabinet Heleny; **obsada:** Helena, Irena.

- **Działanie:** Helena wyjaśnia, że bez potwierdzonych uzgodnień nie przeprowadzi planowanej czynności w zaplanowanym terminie.

- **Dialog / napisy:** HELENA: „Nie musimy się spieszyć kosztem jasności ustaleń. Dziś tej umowy nie podpiszemy”.

**IRENA:** „Dziękuję”.

- **Kadr i montaż:** Spokojny plan średni, szerzej niż na otwarciu.

- **Prawdziwa funkcja / ograniczenie:** Wynik pracy zespołu wymaga decyzji notariusza.

- **Biblioteka wspólna:** `R06` · **nowy beat/ujęcie:** `N02F: ulga Ireny`.

- **Punkt kontrolny:** To przełożenie czynności, a nie automatyczna odmowa z art. 81.

- **Minimalny prompt delta** (dołączany do jednego promptu bazowego, nie samodzielny): `senior notary explaining transaction must be clarified, relieved elderly client`.



### E02S07 · 44–52 · Kalendarz się zmienia

- **Miejsce:** recepcja / komputer; **obsada:** Basia, Marta.

- **Działanie:** Basia wprowadza zmianę terminu w kalendarzu; przy sprawie pozostaje ten sam identyfikator. Marta sprawdza listę spraw.

- **Dialog / napisy:** BASIA: „W kalendarzu już poprawiłam. Stara teczka zostaje”.

**MARTA:** „Tak. Nie zaczynamy wszystkiego od nowa”.

- **Kadr i montaż:** Screen-record kalendarza, wskazanie istniejącej sprawy.

- **Prawdziwa funkcja / ograniczenie:** Kalendarz `kalendarz.py`; ręczna edycja terminu, bez automatyzacji.

- **Biblioteka wspólna:** `R10,R14` · **nowy beat/ujęcie:** `N02G: rejestracja zmiany terminu realnym UI`.

- **Punkt kontrolny:** Potwierdzić dokładny ekran zmiany w bieżącej wersji.

- **Minimalny prompt delta** (dołączany do jednego promptu bazowego, nie samodzielny): `secretary manually rescheduling appointment on authentic application calendar`.



### E02S08 · 52–62 · Nieoczywisty konflikt

- **Miejsce:** korytarz; **obsada:** Irena, Paweł.

- **Działanie:** Irena wychodzi. Paweł próbuje zaopiekować się nią, ale po raz pierwszy przyznaje jej przestrzeń.

- **Dialog / napisy:** PAWEŁ: „I co teraz?”

**IRENA:** „Porozmawiamy, ale w domu. Spokojnie”.

- **Kadr i montaż:** Długi dwujęciowy kadr; zero złowrogiej muzyki.

- **Prawdziwa funkcja / ograniczenie:** Nie ma funkcji produktu: rozwój relacji.

- **Biblioteka wspólna:** `R05` · **nowy beat/ujęcie:** `N02H: napięcie bez przemocy`.

- **Punkt kontrolny:** Zachować sprawczość Ireny.

- **Minimalny prompt delta** (dołączany do jednego promptu bazowego, nie samodzielny): `mother and adult son in hallway, complex but loving relationship`.



### E02S09 · 62–72 · Nowe pytanie

- **Miejsce:** stanowisko Marty; **obsada:** Marta, Kuba.

- **Działanie:** Kuba bierze kartę z warunkami T1, na której widnieje 1 grudnia.

- **Dialog / napisy:** KUBA: „Tylko… skąd oni wszyscy wzięli tę datę?” Marta spogląda na kartkę.

- **Kadr i montaż:** CU odręcznego „1 XII”; powrót do oczu Marty.

- **Prawdziwa funkcja / ograniczenie:** Brak. Intryga wynika z ludzkiej komunikacji.

- **Biblioteka wspólna:** `R09` · **nowy beat/ujęcie:** `N02I: notatka T1 z datą`.

- **Punkt kontrolny:** Oznaczyć „robocze — niepotwierdzone”.

- **Minimalny prompt delta** (dołączany do jednego promptu bazowego, nie samodzielny): `close up provisional terms memo dated December 1 clearly marked unconfirmed`.



### E02S10 · 72–78 · Pytanie na dalej

- **Miejsce:** plansza; **obsada:** -.

- **Działanie:** Skrótowy obraz folderu sprawy; plansza brandowa i punkt zawieszenia.

- **Dialog / napisy:** NAPIS: „Czyja data trafiła do projektu?”

- **Kadr i montaż:** OUTRO_9x16 i znak oryginalny; bez nowego intro.

- **Prawdziwa funkcja / ograniczenie:** Brak. CTA do materiałów o weryfikacji.

- **Biblioteka wspólna:** `R20` · **nowy beat/ujęcie:** `-`.

- **Punkt kontrolny:** Sprawdzić continuity, dane demonstracyjne i realne UI.

- **Minimalny prompt delta** (dołączany do jednego promptu bazowego, nie samodzielny): `clean brand outro cyan navy with suspense tease`.




## Kluczowe warunki prawne i produktowe

- Nie utożsamiać przełożenia planowanej czynności z odmową na podstawie art. 81; syn nie jest pełnomocnikiem.

- Nie wprowadzać screenów lub komunikatów, których rzeczywisty NotarAI nie wygenerował podczas testu.

- W każdym ujęciu ze sprawą główną zachować cenę 640 000 zł, wydanie 15.01.2027 r. po ustaleniach T2 i tytuł „NOWAK — KACZMAREK”.

- Tytuł własności, sytuację majątkową stron, sposoby zapłaty oraz stan KW zweryfikować przed inscenizacją czynności.


## Mailing do odcinka: kierunek
Największy problem to nie brak pliku, lecz brak potwierdzonego ustalenia.

**CTA:** Zobacz, jak system oznacza dane do weryfikacji. Nie zdradzać w mailu puenty odcinka.


## Reuse

Ujęcia R** odczytać w `04_PROMPTY_I_MONTAZ/BIBLIOTEKA_UREC.md`. Nowy beat N** jest unikalną grą aktorską lub realnym nagraniem UI, ale nie wymaga nowego wygenerowania całej scenografii ani nowego promptu tożsamości.


## Decyzja o publikacji

**HOLD** do czasu zatwierdzenia przez praktykującego notariusza, testów UX na syntetycznej teczce oraz kontroli napisów.

---

# EP03 — U nas się tak nie pisze

**Data fabularna:** 18.11.2026 · **Czas:** 68 s · **Wersja:** robocza do autoryzacji · **Format:** 9:16, adaptacja 16:9


> **Kanon:** nie zmieniać nazwisk, wieku, relacji, dat ani dokumentów z `01_KANON/BIBLIA_INTRYGI_KANON_2026-11-12.md`. Odcinek nie jest konsultacją prawną; przed publikacją wymaga kontroli notariusza.


## Funkcja główna
Styl i zasady kancelarii; ponowna kontrola projektu


**Uzupełniające:** Praca na własnym wzorze; korekty z raportem zgodności.


**Logline:** Zespół naprawia zbyt swobodny obieg informacji i jednocześnie uczy aplikację formalnego stylu kancelarii.


**Hak:** Helena skreśla jedno sformułowanie w projekcie, a Kuba zamiera.


**Co widz odkrywa:** Dokładność języka jest cechą pracy notariusza, nie estetycznym kaprysem; sporna data nie ma źródła w potwierdzeniu Ireny.


**Pytanie końcowe:** Kto wprowadził 1 grudnia do maili i dlaczego?


## Scenopis — wszystkie sceny


### E03S01 · 00–05 · Otwarcie komediowe

- **Miejsce:** gabinet Heleny; **obsada:** Helena, Kuba.

- **Działanie:** Helena pochyla się nad projektem, unosi brew i zakreśla skrót „w/w”.

- **Dialog / napisy:** HELENA: „Kubo… od kiedy tak się u nas pisze?”

- **Kadr i montaż:** CU czerwonego zaznaczenia i spojrzenia Kuby.

- **Prawdziwa funkcja / ograniczenie:** Jeszcze brak; scena o warsztacie.

- **Biblioteka wspólna:** `R06,R09` · **nowy beat/ujęcie:** `N03A: klasyczna reakcja Heleny`.

- **Punkt kontrolny:** Sprawdzić continuity, dane demonstracyjne i realne UI.

- **Minimalny prompt delta** (dołączany do jednego promptu bazowego, nie samodzielny): `silver-haired notary displeased with formatting in draft, young trainee nervous`.



### E03S02 · 05–12 · Zasada

- **Miejsce:** gabinet Heleny; **obsada:** Helena, Kuba.

- **Działanie:** Kuba przyznaje, że przepisujący wzór zawierał skrót; Helena wskazuje przyjęty w kancelarii zapis.

- **Dialog / napisy:** KUBA: „Tak było w materiale wejściowym”.

**HELENA:** „Dlatego materiał wejściowy nie jest jeszcze naszym projektem”.

- **Kadr i montaż:** Dwuplan, lekki humor bez ośmieszania aplikanta.

- **Prawdziwa funkcja / ograniczenie:** Zasada personalizacji w kancelarii, nie reguła ustawowa.

- **Biblioteka wspólna:** `R06` · **nowy beat/ujęcie:** `N03B: gest wskazujący różnicę`.

- **Punkt kontrolny:** Nie mylić stylistyki z wymogami prawa.

- **Minimalny prompt delta** (dołączany do jednego promptu bazowego, nie samodzielny): `notary explaining preferred drafting language to diligent apprentice`.



### E03S03 · 12–20 · Komputerku

- **Miejsce:** stanowisko Marty; **obsada:** Marta, Helena.

- **Działanie:** Marta wchodzi do „Styl i zasady kancelarii”. Pokazuje istniejącą regułę zamiany albo zapisuje ją w UI zgodnie z testem.

- **Dialog / napisy:** MARTA: „Komputerku, u nas tego skrótu nie używamy”.

**HELENA:** „I proszę, żeby już tak zostało”.

- **Kadr i montaż:** Ujęcie UI z realnego testu + ręka Marty klikająca.

- **Prawdziwa funkcja / ograniczenie:** `personalizacja.py`: zasada zastępowania frazy i raport zgodności; polecenie nie jest triggerem głosowym.

- **Biblioteka wspólna:** `R07,R08,R15` · **nowy beat/ujęcie:** `N03C: autentyczny ekran reguły`.

- **Punkt kontrolny:** Dopisać w filmowym montażu kliknięcie ustawienia; nie pokazywać bezdotykowego wykonania.

- **Minimalny prompt delta** (dołączany do jednego promptu bazowego, nie samodzielny): `notary colleague setting office style rule in authentic desktop UI`.



### E03S04 · 20–28 · Kontrola stylu

- **Miejsce:** stanowisko Marty; **obsada:** Marta, Kuba.

- **Działanie:** System przeprowadza kontrolę zasad w projekcie. Marta otwiera raport zgodności, jeśli demonstracja zwróci taki wynik.

- **Dialog / napisy:** KUBA: „A jeśli zasada się nie zastosuje?”

**MARTA:** „Raport nam to pokaże. I sprawdzimy sami”.

- **Kadr i montaż:** Długie ujęcie na wiarygodny interfejs, bez magicznych ikon.

- **Prawdziwa funkcja / ograniczenie:** Raport zgodności i zapis reguł.

- **Biblioteka wspólna:** `R14` · **nowy beat/ujęcie:** `N03D: realne nagranie raportu`.

- **Punkt kontrolny:** Jeśli raport oznacza „nie sprawdzono”, pokazujemy ten status bez retuszu.

- **Minimalny prompt delta** (dołączany do jednego promptu bazowego, nie samodzielny): `close up authentic office drafting style compliance report UI`.



### E03S05 · 28–36 · Humor sytuacyjny

- **Miejsce:** recepcja; **obsada:** Basia, Marta.

- **Działanie:** Telefon dzwoni w połowie rozmowy; Basia odruchowo sięga po słuchawkę. Marta odsuwa jej filiżankę przed zalaniem klawiatury.

- **Dialog / napisy:** BASIA: „Jeszcze naucz go odbierać telefony”.

**MARTA:** „Nie obiecuję cudów”.

- **Kadr i montaż:** Półplan dwóch kobiet; szybka riposta, bez klaunady.

- **Prawdziwa funkcja / ograniczenie:** Brak: programu nie przedstawiamy jako automatycznego telefonisty.

- **Biblioteka wspólna:** `R01,R03` · **nowy beat/ujęcie:** `N03E: reakcja Basi`.

- **Punkt kontrolny:** Sprawdzić continuity, dane demonstracyjne i realne UI.

- **Minimalny prompt delta** (dołączany do jednego promptu bazowego, nie samodzielny): `secretary and colleague joke during busy office phone call`.



### E03S06 · 36–45 · Granica AI

- **Miejsce:** gabinet Heleny; **obsada:** Helena, Marta.

- **Działanie:** Marta pokazuje projekt. Helena docenia poprawiony styl, lecz wskazuje pole terminu wydania jako nadal nierozstrzygnięte.

- **Dialog / napisy:** HELENA: „Sformułowanie poprawione. Ale daty komputer za nas nie uzgodni”.

**MARTA:** „I nie powinien”.

- **Kadr i montaż:** Połączenie CU projektu i plan średni Heleny.

- **Prawdziwa funkcja / ograniczenie:** Projekt i weryfikacja luk, nie automatyczne uzgodnienie warunków.

- **Biblioteka wspólna:** `R06,R08` · **nowy beat/ujęcie:** `N03F: merytoryczne zwrócenie uwagi`.

- **Punkt kontrolny:** Termin T1 wciąż nie jest uzgodniony.

- **Minimalny prompt delta** (dołączany do jednego promptu bazowego, nie samodzielny): `senior notary emphasizes unresolved handover date on Word draft`.



### E03S07 · 45–55 · Poszukiwanie źródła

- **Miejsce:** biurko Kuby; **obsada:** Kuba, Marta.

- **Działanie:** Kuba zestawia roboczy PDF D05 z wcześniejszymi materiałami i znajduje, że data 1 grudnia nie pochodzi z podpisanego dokumentu właścicielki.

- **Dialog / napisy:** KUBA: „Mam tę datę w podsumowaniu. Nie mam jej potwierdzenia od pani Ireny”.

- **Kadr i montaż:** Spokojny over-shoulder; dokumenty obok siebie zestawione przez człowieka.

- **Prawdziwa funkcja / ograniczenie:** Pliki sprawy, źródła. Bez fikcyjnej automatycznej detekcji zgód.

- **Biblioteka wspólna:** `R07,R09` · **nowy beat/ujęcie:** `N03G: ręczne porównanie źródeł`.

- **Punkt kontrolny:** Różnica źródło/zgoda.

- **Minimalny prompt delta** (dołączany do jednego promptu bazowego, nie samodzielny): `young legal trainee cross checking owner instructions and informal draft`.



### E03S08 · 55–63 · Kompetencja

- **Miejsce:** gabinet Heleny; **obsada:** Helena, Marta.

- **Działanie:** Helena odkłada okulary, patrzy na wspólne notatki.

- **Dialog / napisy:** HELENA: „Dobrze, że wiemy, czego nie wiemy”.

- **Kadr i montaż:** Ujęcie na spokojną twarz Heleny; pauza.

- **Prawdziwa funkcja / ograniczenie:** Brak: prawo i ocena człowieka.

- **Biblioteka wspólna:** `R06` · **nowy beat/ujęcie:** `N03H: aprobacja Heleny`.

- **Punkt kontrolny:** Sprawdzić continuity, dane demonstracyjne i realne UI.

- **Minimalny prompt delta** (dołączany do jednego promptu bazowego, nie samodzielny): `experienced notary approving careful legal review`.



### E03S09 · 63–68 · Cliffhanger

- **Miejsce:** plansza; **obsada:** -.

- **Działanie:** Na tle kadru z korespondencją widnieje pytanie.

- **Dialog / napisy:** NAPIS: „Kto potwierdził termin, którego nie potwierdzono?”

- **Kadr i montaż:** Zakończenie stałym overlayem.

- **Prawdziwa funkcja / ograniczenie:** Brak.

- **Biblioteka wspólna:** `R20` · **nowy beat/ujęcie:** `-`.

- **Punkt kontrolny:** Sprawdzić continuity, dane demonstracyjne i realne UI.

- **Minimalny prompt delta** (dołączany do jednego promptu bazowego, nie samodzielny): `brand title over confidential email blur`.




## Kluczowe warunki prawne i produktowe

- Styl redakcyjny ≠ gwarancja legalności projektu; nie przedstawiać autocorrectu jako merytorycznej decyzji.

- Nie wprowadzać screenów lub komunikatów, których rzeczywisty NotarAI nie wygenerował podczas testu.

- W każdym ujęciu ze sprawą główną zachować cenę 640 000 zł, wydanie 15.01.2027 r. po ustaleniach T2 i tytuł „NOWAK — KACZMAREK”.

- Tytuł własności, sytuację majątkową stron, sposoby zapłaty oraz stan KW zweryfikować przed inscenizacją czynności.


## Mailing do odcinka: kierunek
Komputerek może nauczyć się warsztatu kancelarii, ale nie może wymyślić brakujących faktów.

**CTA:** Zobacz własne wzory i zasady kancelarii. Nie zdradzać w mailu puenty odcinka.


## Reuse

Ujęcia R** odczytać w `04_PROMPTY_I_MONTAZ/BIBLIOTEKA_UREC.md`. Nowy beat N** jest unikalną grą aktorską lub realnym nagraniem UI, ale nie wymaga nowego wygenerowania całej scenografii ani nowego promptu tożsamości.


## Decyzja o publikacji

**HOLD** do czasu zatwierdzenia przez praktykującego notariusza, testów UX na syntetycznej teczce oraz kontroli napisów.

---

# EP04 — Wczoraj tego nie było

**Data fabularna:** 19.11.2026 · **Czas:** 72 s · **Wersja:** robocza do autoryzacji · **Format:** 9:16, adaptacja 16:9


> **Kanon:** nie zmieniać nazwisk, wieku, relacji, dat ani dokumentów z `01_KANON/BIBLIA_INTRYGI_KANON_2026-11-12.md`. Odcinek nie jest konsultacją prawną; przed publikacją wymaga kontroli notariusza.


## Funkcja główna
Pobieranie aktualnej treści KW przez skonfigurowanego dostawcę


**Uzupełniające:** Pliki sprawy, ręczne zestawienie odczytów z dwiema datami.


**Logline:** Osobna sprawa pani Borowskiej pokazuje, dlaczego samo posiadanie starego odczytu KW nie wystarcza.


**Hak:** Kuba: „Wczoraj tej wzmianki nie widziałem”.


**Co widz odkrywa:** Wzmianka w odrębnej księdze wymaga wyjaśnienia, ale nie przesądza o wyniku postępowania.


**Pytanie końcowe:** Czy niektóre ważne informacje ukrywają się także w nieuporządkowanej korespondencji?


## Scenopis — wszystkie sceny


### E04S01 · 00–05 · Zimny start

- **Miejsce:** biurko Kuby; **obsada:** Kuba, Marta.

- **Działanie:** Kuba porównuje dwa dokumenty dotyczące osobnej sprawy pani Borowskiej, nagle prostuje się na krześle.

- **Dialog / napisy:** KUBA: „Marta… tego wczoraj nie było”.

- **Kadr i montaż:** CU twarzy Kuby, ostre cięcie na dwa datowane wydruki.

- **Prawdziwa funkcja / ograniczenie:** Brak; odkrycie po ręcznym porównaniu.

- **Biblioteka wspólna:** `R07,R09` · **nowy beat/ujęcie:** `N04A: nagłe zauważenie różnicy`.

- **Punkt kontrolny:** Sprawdzić continuity, dane demonstracyjne i realne UI.

- **Minimalny prompt delta** (dołączany do jednego promptu bazowego, nie samodzielny): `trainee comparing two different dated printed property register extracts`.



### E04S02 · 05–13 · Jaka sprawa?

- **Miejsce:** stanowisko Marty; **obsada:** Marta, Kuba.

- **Działanie:** Marta upewnia się, że nie chodzi o mieszkanie Ireny: to odrębna sprawa pani Borowskiej.

- **Dialog / napisy:** MARTA: „Borowska? Nie Nowak?”

**KUBA:** „Borowska. Inna teczka”.

- **Kadr i montaż:** Na ekranie widać nazwę BOROWSKA — odrębna sprawa.

- **Prawdziwa funkcja / ograniczenie:** Lista spraw w kokpicie; numer nie może sugerować rzeczywistej księgi.

- **Biblioteka wspólna:** `R08,R14` · **nowy beat/ujęcie:** `N04B: porównanie dwóch różnych teczek`.

- **Punkt kontrolny:** Nie mieszać dwóch nieruchomości.

- **Minimalny prompt delta** (dołączany do jednego promptu bazowego, nie samodzielny): `two separate cases in notary dashboard, clear distinct fictitious labels`.



### E04S03 · 13–22 · Aktualny odczyt

- **Miejsce:** stanowisko Marty; **obsada:** Marta.

- **Działanie:** Marta pobiera treść EKW na jawne potwierdzenie, jeśli partner jest skonfigurowany; wynik zawiera datę pobrania i źródło.

- **Dialog / napisy:** MARTA: „Sprawdzamy stan aktualny i skąd pochodzi odczyt”.

- **Kadr i montaż:** Rzeczywisty UI, pole numeru fikcyjnej KW demonstracyjnej, źródło.

- **Prawdziwa funkcja / ograniczenie:** Endpoint `/api/sprawy/{id}/ekw`, dostawca Finance You/Apify jeśli dostępny.

- **Biblioteka wspólna:** `R08,R14` · **nowy beat/ujęcie:** `N04C: autentyczny ekran pobrania EKW`.

- **Punkt kontrolny:** Przed emisją test źródła i wiarygodność demonstracyjnej księgi; brak gwarancji dostępu.

- **Minimalny prompt delta** (dołączany do jednego promptu bazowego, nie samodzielny): `authentic EKW reading module in office UI with source timestamp`.



### E04S04 · 22–33 · Wzmianka

- **Miejsce:** gabinet Marty; **obsada:** Marta, Kuba.

- **Działanie:** Na osobnych wydrukach widać oznaczenie nowej wzmianki względem poprzedniego stanu. Kuba nie formułuje konkluzji prawnej; wskazuje różnicę do sprawdzenia.

- **Dialog / napisy:** KUBA: „Na tym odczycie jest wzmianka. Na starszym jej nie ma”.

**MARTA:** „To dopiero sygnał do weryfikacji”.

- **Kadr i montaż:** CU dat i rubryk; kontrast światła neutralny.

- **Prawdziwa funkcja / ograniczenie:** Brak auto-diff; ręczne porównanie przeprowadzone przez ludzi.

- **Biblioteka wspólna:** `R09,R11` · **nowy beat/ujęcie:** `N04D: rzetelny pokaz dwóch datowanych dokumentów`.

- **Punkt kontrolny:** Dokładny wariant wzmianki i jej rubryka do autoryzacji notariusza.

- **Minimalny prompt delta** (dołączany do jednego promptu bazowego, nie samodzielny): `two dated official-style synthetic property extracts manually reviewed`.



### E04S05 · 33–42 · Znaczenie

- **Miejsce:** gabinet Heleny; **obsada:** Helena, Marta.

- **Działanie:** Helena otrzymuje informację o nowym elemencie w sprawie Borowskiej.

- **Dialog / napisy:** HELENA: „Wzmianka mówi nam, że coś wpłynęło do systemu. Trzeba ustalić, czego dotyczy. Nie zgadujemy”.

- **Kadr i montaż:** Zbliżenie spokojnej reakcji Heleny.

- **Prawdziwa funkcja / ograniczenie:** Ocena prawna należy do notariusza.

- **Biblioteka wspólna:** `R06` · **nowy beat/ujęcie:** `N04E: fachowa ocena`.

- **Punkt kontrolny:** W finalnej wersji doprecyzować prawny skutek wskazanego rodzaju wzmianki.

- **Minimalny prompt delta** (dołączany do jednego promptu bazowego, nie samodzielny): `senior notary professionally explaining limitation of registry annotation`.



### E04S06 · 42–51 · Dwa równoległe światy

- **Miejsce:** recepcja; **obsada:** Basia, Marta.

- **Działanie:** Basia odbiera kolejny telefon w sprawie Ireny; Marta w tym czasie kończy wpis do teczki Borowskiej.

- **Dialog / napisy:** BASIA: „A pani Nowak? Mam już od nich nowe wiadomości”.

**MARTA:** „Za chwilę do tego wrócę. Najpierw zapiszę źródło dla Borowskiej”.

- **Kadr i montaż:** Przebitka recepcja / laptop.

- **Prawdziwa funkcja / ograniczenie:** Archiwum sprawy, ślad pobrania.

- **Biblioteka wspólna:** `R01,R07,R03` · **nowy beat/ujęcie:** `N04F: przekazanie krótkiej wiadomości`.

- **Punkt kontrolny:** Sprawdzić continuity, dane demonstracyjne i realne UI.

- **Minimalny prompt delta** (dołączany do jednego promptu bazowego, nie samodzielny): `busy notary office coordinating two unrelated cases`.



### E04S07 · 51–61 · Ślad

- **Miejsce:** ekran / teczka; **obsada:** Marta.

- **Działanie:** Marta zapisuje zawartość pobranej księgi w sprawie wraz z metadanymi. Jeżeli system nie przechowuje historycznych wersji, wcześniejszy eksport pozostaje wyraźnie osobnym plikiem rekwizytowym.

- **Dialog / napisy:** BEZ DIALOGU; odgłos kliknięć i przewracanych kartek.

- **Kadr i montaż:** Kamera na źródło, czas, plik sprawy; żadnej fikcyjnej osi wersji.

- **Prawdziwa funkcja / ograniczenie:** `ekw.py` zapis aktualnego wyniku; historyczne zestawienie wymaga osobnej kopii.

- **Biblioteka wspólna:** `R08,R11` · **nowy beat/ujęcie:** `N04G: zapis źródła`.

- **Punkt kontrolny:** Sprawdzić continuity, dane demonstracyjne i realne UI.

- **Minimalny prompt delta** (dołączany do jednego promptu bazowego, nie samodzielny): `notary filing time stamped KW reading in case folder`.



### E04S08 · 61–68 · Zostaje pytanie

- **Miejsce:** stanowisko Marty; **obsada:** Kuba, Marta.

- **Działanie:** Kuba kładzie obok siebie dwie sprawy i wraca do wiadomości od kupujących Ireny.

- **Dialog / napisy:** KUBA: „A skoro tu coś się zmieniło… to kiedy ostatnio sprawdzaliśmy, co naprawdę uzgodniono w sprawie pani Ireny?”

- **Kadr i montaż:** Statyczny plan, kartka z datą 1 XII wyłania się spod teczki.

- **Prawdziwa funkcja / ograniczenie:** Jedna informacja musi zostać potwierdzona z właściwego źródła.

- **Biblioteka wspólna:** `R07,R09` · **nowy beat/ujęcie:** `N04H: płynne przejście do wątku Ireny`.

- **Punkt kontrolny:** Sprawdzić continuity, dane demonstracyjne i realne UI.

- **Minimalny prompt delta** (dołączany do jednego promptu bazowego, nie samodzielny): `trainee looking at informal transaction date after separate registry case`.



### E04S09 · 68–72 · Zapowiedź

- **Miejsce:** plansza; **obsada:** -.

- **Działanie:** Krótki napis na tle skrzynki mailowej, bez sugerowania integracji.

- **Dialog / napisy:** NAPIS: „Wszystko zaczęło się od jednej wiadomości”.

- **Kadr i montaż:** Stały outro.

- **Prawdziwa funkcja / ograniczenie:** Brak.

- **Biblioteka wspólna:** `R20` · **nowy beat/ujęcie:** `-`.

- **Punkt kontrolny:** Sprawdzić continuity, dane demonstracyjne i realne UI.

- **Minimalny prompt delta** (dołączany do jednego promptu bazowego, nie samodzielny): `email teaser under consistent blue logo endcard`.




## Kluczowe warunki prawne i produktowe

- System nie ma potwierdzonego auto-diff i alarmów; nie wykrywa automatycznie nowych wzmianek.

- Nie wprowadzać screenów lub komunikatów, których rzeczywisty NotarAI nie wygenerował podczas testu.

- W każdym ujęciu ze sprawą główną zachować cenę 640 000 zł, wydanie 15.01.2027 r. po ustaleniach T2 i tytuł „NOWAK — KACZMAREK”.

- Tytuł własności, sytuację majątkową stron, sposoby zapłaty oraz stan KW zweryfikować przed inscenizacją czynności.


## Mailing do odcinka: kierunek
Księga z wczoraj może nie odpowiadać stanowi z dziś; ważne źródło i data odczytu.

**CTA:** Zobacz, jak NotarAI pobiera i porządkuje treść KW. Nie zdradzać w mailu puenty odcinka.


## Reuse

Ujęcia R** odczytać w `04_PROMPTY_I_MONTAZ/BIBLIOTEKA_UREC.md`. Nowy beat N** jest unikalną grą aktorską lub realnym nagraniem UI, ale nie wymaga nowego wygenerowania całej scenografii ani nowego promptu tożsamości.


## Decyzja o publikacji

**HOLD** do czasu zatwierdzenia przez praktykującego notariusza, testów UX na syntetycznej teczce oraz kontroli napisów.

---

# EP05 — Przyszło mailem

**Data fabularna:** 20.11.2026 · **Czas:** 70 s · **Wersja:** robocza do autoryzacji · **Format:** 9:16, adaptacja 16:9


> **Kanon:** nie zmieniać nazwisk, wieku, relacji, dat ani dokumentów z `01_KANON/BIBLIA_INTRYGI_KANON_2026-11-12.md`. Odcinek nie jest konsultacją prawną; przed publikacją wymaga kontroli notariusza.


## Funkcja główna
Pliki sprawy: ręczne dołączenie korespondencji


**Uzupełniające:** Ewidencja terminów; rozmowa o sprawie i sprawdzanie źródeł.


**Logline:** W mailach kupujących odkrywamy, jak propozycja wydania lokalu zamieniła się w rzekomo uzgodniony termin.


**Hak:** Basia mówi: „Dwa maile, dwa różne znaczenia tego samego zdania”.


**Co widz odkrywa:** Termin 1 grudnia był propozycją, której Irena osobiście nie potwierdziła.


**Pytanie końcowe:** Dlaczego Paweł nie sprostował informacji, choć widział pośpiech kupujących?


## Scenopis — wszystkie sceny


### E05S01 · 00–06 · Dwa maile

- **Miejsce:** recepcja; **obsada:** Basia.

- **Działanie:** Na ekranie prawdziwej skrzynki przychodzą dwie wiadomości: jedna z roboczym terminem, druga o potrzebie przedłużenia najmu.

- **Dialog / napisy:** BASIA: „Dwa maile. Ten sam lokal. Zupełnie inne oczekiwania”.

- **Kadr i montaż:** Zbliżenie prawdziwego mail klienta demo, nie NotarAI.

- **Prawdziwa funkcja / ograniczenie:** Brak automatycznego importu: to ekran osobnego programu pocztowego.

- **Biblioteka wspólna:** `R03,R12` · **nowy beat/ujęcie:** `N05A: sztuczna korespondencja D09,D10 w realnym kliencie poczty`.

- **Punkt kontrolny:** Żadnych danych istniejących osób; źródło wiadomości czytelne.

- **Minimalny prompt delta** (dołączany do jednego promptu bazowego, nie samodzielny): `email client with two contradictory fictitious property transaction messages`.



### E05S02 · 06–14 · Uproszczenie, które szkodzi

- **Miejsce:** stanowisko Marty; **obsada:** Basia, Marta.

- **Działanie:** Basia przypomina, że Robert w jednej wiadomości napisał „zakładamy wydanie do 1 grudnia”; Paweł powtórzył tę datę.

- **Dialog / napisy:** MARTA: „Zakładają — to nie znaczy, że sprzedająca się zgodziła”.

**BASIA:** „A wszyscy czytali to jak ustalenie”.

- **Kadr i montaż:** Dwuplan; podbicie słów „zakładamy” i „potwierdzono” tylko jako typografia filmu, nie funkcja AI.

- **Prawdziwa funkcja / ograniczenie:** Brak automatycznej interpretacji czy zatwierdzania umowy.

- **Biblioteka wspólna:** `R07,R12` · **nowy beat/ujęcie:** `N05B: emocja rozpoznania błędu komunikacji`.

- **Punkt kontrolny:** Nie traktować e-maila syna jako oświadczenia sprzedającej.

- **Minimalny prompt delta** (dołączany do jednego promptu bazowego, nie samodzielny): `notary and secretary reviewing tentative handover proposal email`.



### E05S03 · 14–24 · Z jednej skrzynki do jednej sprawy

- **Miejsce:** stanowisko Marty; **obsada:** Basia.

- **Działanie:** Basia zapisuje wiadomość jako plik `.eml` lub PDF, wchodzi w NotarAI → istniejąca sprawa → Pliki sprawy → Z pliku i ręcznie dodaje załącznik.

- **Dialog / napisy:** BASIA: „Niech to będzie przy sprawie, nie w piątym wątku na poczcie”.

- **Kadr i montaż:** Ujęcie prawdziwych dwóch aplikacji; jawny wybór pliku.

- **Prawdziwa funkcja / ograniczenie:** `POST /api/sprawy/{id}/pliki`; ręczny import z poczty.

- **Biblioteka wspólna:** `R08,R12,R14` · **nowy beat/ujęcie:** `N05C: realne wgranie pliku i jego pojawienie się w liście`.

- **Punkt kontrolny:** Wykluczone: automatyczne rozpoznanie klienta w skrzynce.

- **Minimalny prompt delta** (dołączany do jednego promptu bazowego, nie samodzielny): `secretary manually uploading email attachment to an existing legal case folder`.



### E05S04 · 24–32 · Presja zrozumiała

- **Miejsce:** poczekalnia; **obsada:** Joanna, Robert.

- **Działanie:** Kupujący czekają, Robert patrzy na kalendarz własnego telefonu, Joanna składa dokumenty najmu.

- **Dialog / napisy:** ROBERT: „Wynajem kończy nam się z końcem listopada”.

**JOANNA:** „Ale pani Irena też musi się gdzieś przeprowadzić”.

- **Kadr i montaż:** Dwuplan w poczekalni, bez efektów villain.

- **Prawdziwa funkcja / ograniczenie:** Brak; motywacje klientów.

- **Biblioteka wspólna:** `R01` · **nowy beat/ujęcie:** `N05D: kupujący jako realni ludzie`.

- **Punkt kontrolny:** Bez deklarowania nieuzgodnionych praw.

- **Minimalny prompt delta** (dołączany do jednego promptu bazowego, nie samodzielny): `young married couple worried about apartment move and rental ending`.



### E05S05 · 32–42 · Warunki nie są ostateczne

- **Miejsce:** gabinet Heleny; **obsada:** Helena, Joanna, Robert.

- **Działanie:** Helena wyjaśnia, że strony muszą porozumieć się co do wydania, kosztów i zasad płatności, a projekt może powstać dopiero na potwierdzonych danych.

- **Dialog / napisy:** HELENA: „Mamy projekt warunków. Nie mamy jeszcze wspólnego ustalenia”.

**JOANNA:** „Czyli termin wydania jest nadal otwarty?”

**HELENA:** „Tak”.

- **Kadr i montaż:** Stabilna kamera, bez udawania rozmowy doradczej trwającej 5 sekund; montaż skrótowy.

- **Prawdziwa funkcja / ograniczenie:** Ocena i wyjaśnienia notariusza, żadna autonomiczna decyzja AI.

- **Biblioteka wspólna:** `R06` · **nowy beat/ujęcie:** `N05E: rzeczowa rozmowa z kupującymi`.

- **Punkt kontrolny:** Weryfikacja obowiązków z art. 80 PrNot; nie sugerować gotowości aktu.

- **Minimalny prompt delta** (dołączany do jednego promptu bazowego, nie samodzielny): `notary calmly explaining unresolved terms to buyers`.



### E05S06 · 42–50 · Teczka jest jedna

- **Miejsce:** stanowisko Marty; **obsada:** Marta, Kuba.

- **Działanie:** Marta otwiera Pliki sprawy; pokazujemy papierową kartę T1 i nowo dołączony e-mail. Kuba zaznacza źródła w swojej roboczej notatce.

- **Dialog / napisy:** KUBA: „Znalezione. To wersja z korespondencji, nie potwierdzona przez panią Irenę”.

- **Kadr i montaż:** Match cut z poczty na jedną teczkę.

- **Prawdziwa funkcja / ograniczenie:** Pliki sprawy i rozdzielenie źródeł; brak automatycznego klasyfikatora maili.

- **Biblioteka wspólna:** `R08,R09,R14` · **nowy beat/ujęcie:** `N05F: potwierdzenie pochodzenia źródła`.

- **Punkt kontrolny:** Sprawdzić continuity, dane demonstracyjne i realne UI.

- **Minimalny prompt delta** (dołączany do jednego promptu bazowego, nie samodzielny): `authentic case attachments list with manually added email file and provisional terms`.



### E05S07 · 50–61 · Zawahanie Pawła

- **Miejsce:** recepcja; **obsada:** Paweł, Basia.

- **Działanie:** Paweł przynosi kolejną wiadomość od kupujących. Basia pyta o aktualne ustalenia z matką.

- **Dialog / napisy:** BASIA: „Czy pani Irena mówiła panu, że potwierdziła pierwszy grudnia?”

**PAWEŁ:** „Myślałem, że to już… załatwione”.

- **Kadr i montaż:** Dłuższa pauza na twarz Pawła, bez złowrogiej muzyki.

- **Prawdziwa funkcja / ograniczenie:** Brak. Prawdziwa intryga jest w ludzkich relacjach.

- **Biblioteka wspólna:** `R01` · **nowy beat/ujęcie:** `N05G: Paweł pierwszy raz pokazuje wątpliwości`.

- **Punkt kontrolny:** Paweł nie jest pełnomocnikiem.

- **Minimalny prompt delta** (dołączany do jednego promptu bazowego, nie samodzielny): `son hesitates when asked whether his mother actually confirmed terms`.



### E05S08 · 61–70 · Pytanie

- **Miejsce:** plansza + drobna reakcja; **obsada:** Paweł.

- **Działanie:** Pawłowi wibruje telefon. Na ekranie nie ma nowego zwrotu fabularnego — tylko krótka etykieta „Rezerwacja mieszkania”. Paweł chowa aparat.

- **Dialog / napisy:** NAPIS: „Dlaczego tak mu zależy na czasie?”

- **Kadr i montaż:** Krótki telefoniczny insert + outro.

- **Prawdziwa funkcja / ograniczenie:** Brak.

- **Biblioteka wspólna:** `R10,R20` · **nowy beat/ujęcie:** `N05H: preview prywatnego przypomnienia rezerwacji`.

- **Punkt kontrolny:** Nie pokazywać prawdziwej płatności czy tytułów.

- **Minimalny prompt delta** (dołączany do jednego promptu bazowego, nie samodzielny): `phone showing fictional apartment reservation reminder held discreetly`.




## Kluczowe warunki prawne i produktowe

- BRAK potwierdzonego mail-inbox→automatyczne przypisanie: nie inscenizować AI, które samo czyta przychodzącą skrzynkę.

- Nie wprowadzać screenów lub komunikatów, których rzeczywisty NotarAI nie wygenerował podczas testu.

- W każdym ujęciu ze sprawą główną zachować cenę 640 000 zł, wydanie 15.01.2027 r. po ustaleniach T2 i tytuł „NOWAK — KACZMAREK”.

- Tytuł własności, sytuację majątkową stron, sposoby zapłaty oraz stan KW zweryfikować przed inscenizacją czynności.


## Mailing do odcinka: kierunek
Zawsze dobrze wiedzieć, skąd pochodzi załącznik i kto potwierdził warunki.

**CTA:** Zobacz elektroniczną teczkę sprawy. Nie zdradzać w mailu puenty odcinka.


## Reuse

Ujęcia R** odczytać w `04_PROMPTY_I_MONTAZ/BIBLIOTEKA_UREC.md`. Nowy beat N** jest unikalną grą aktorską lub realnym nagraniem UI, ale nie wymaga nowego wygenerowania całej scenografii ani nowego promptu tożsamości.


## Decyzja o publikacji

**HOLD** do czasu zatwierdzenia przez praktykującego notariusza, testów UX na syntetycznej teczce oraz kontroli napisów.

---

# EP06 — Kto ma tę sprawę?

**Data fabularna:** 23.11.2026 · **Czas:** 80 s · **Wersja:** robocza do autoryzacji · **Format:** 9:16, adaptacja 16:9


> **Kanon:** nie zmieniać nazwisk, wieku, relacji, dat ani dokumentów z `01_KANON/BIBLIA_INTRYGI_KANON_2026-11-12.md`. Odcinek nie jest konsultacją prawną; przed publikacją wymaga kontroli notariusza.


## Funkcja główna
Sprawdzenie KRZ przez lokalnego pomocnika w osobnej sprawie


**Uzupełniające:** Zespół i uprawnienia; kalendarz; lista spraw; archiwum wyniku.


**Logline:** Jednocześnie prowadzone sprawy naświetlają rolę kalendarza, zespołu i sprawdzenia KRZ, a Paweł ujawnia swój błąd.


**Hak:** Trzy osoby pytają naraz, kto zajmuje się którym dokumentem.


**Co widz odkrywa:** Paweł wpłacił z własnych środków opłatę rezerwacyjną za mieszkanie na parterze.


**Pytanie końcowe:** Czy Irena wybaczy mu przejęcie inicjatywy?


## Scenopis — wszystkie sceny


### E06S01 · 00–07 · Nakładają się pytania

- **Miejsce:** recepcja / korytarz; **obsada:** Basia, Marta, Kuba.

- **Działanie:** Basia rozmawia przez telefon, Marta pyta o termin, Kuba o plik w innej sprawie. Urywki rozmów splatają się w jeden rytm.

- **Dialog / napisy:** BASIA: „Jedno po drugim, proszę…”

**KUBA:** „Która teczka jest teraz pilna?”

**MARTA:** „Najpierw terminy”.

- **Kadr i montaż:** Montaż trzy plany; kontrolowany chaos dźwiękowy.

- **Prawdziwa funkcja / ograniczenie:** Brak. Początek organizacyjny.

- **Biblioteka wspólna:** `R01,R03,R04` · **nowy beat/ujęcie:** `N06A: potrójna interakcja w recepcji`.

- **Punkt kontrolny:** Sprawdzić continuity, dane demonstracyjne i realne UI.

- **Minimalny prompt delta** (dołączany do jednego promptu bazowego, nie samodzielny): `busy secretary and two notary colleagues coordinate overlapping tasks`.



### E06S02 · 07–15 · Wspólna lista spraw

- **Miejsce:** stanowisko Marty; **obsada:** Marta, Kuba.

- **Działanie:** Marta otwiera kokpit „Moje sprawy”, filtruje i znajduje sprawę Nowak oraz odrębną sprawę do sprawdzenia w KRZ.

- **Dialog / napisy:** MARTA: „Sprawa Nowak jest tu. Borowska jest osobno. A to jest sprawa do KRZ”.

- **Kadr i montaż:** Rzeczywisty kokpit, nie plansza nierealnych przypisań do pracowników.

- **Prawdziwa funkcja / ograniczenie:** Kokpit rzeczywisty `/api/sprawy`, wyszukiwanie/filtr.

- **Biblioteka wspólna:** `R08,R14` · **nowy beat/ujęcie:** `N06B: dwa różne wpisy listy spraw`.

- **Punkt kontrolny:** Nie sugerować automatycznego delegowania bez implementacji.

- **Minimalny prompt delta** (dołączany do jednego promptu bazowego, nie samodzielny): `authentic NotarAI cases dashboard showing several separate demo matters`.



### E06S03 · 15–23 · Termin i ludzie

- **Miejsce:** stanowisko Basi; **obsada:** Basia, Marta.

- **Działanie:** Basia przegląda kalendarz i listę osób zespołu. Zaznacza, jaki termin wymaga kontaktu z klientem.

- **Dialog / napisy:** BASIA: „Kontakt mam. Termin widzę. Teraz potrzebujemy potwierdzenia od stron”.

- **Kadr i montaż:** Przebitka kalendarz → twarz Basi.

- **Prawdziwa funkcja / ograniczenie:** Kalendarz, telefony do stron, konta zespołu.

- **Biblioteka wspólna:** `R10,R14` · **nowy beat/ujęcie:** `N06C: prawdziwe elementy menu`.

- **Punkt kontrolny:** Nie tworzyć fikcyjnej tablicy „przydzielono Basi”, jeśli brak w UI.

- **Minimalny prompt delta** (dołączany do jednego promptu bazowego, nie samodzielny): `secretary reviewing real calendar entries and contacts`.



### E06S04 · 23–33 · KRZ nie jest jednym magicznym wynikiem

- **Miejsce:** lokalny komputer Kuby; **obsada:** Kuba, Marta.

- **Działanie:** Kuba, po jawnym potwierdzeniu i z uruchomionym lokalnym pomocnikiem, otwiera sprawdzenie KRZ w ODREBNEJ fikcyjnej sprawie. Portal może działać wolno.

- **Dialog / napisy:** KUBA: „Sprawdzenie ruszyło przez pomocnika na tym komputerze”.

**MARTA:** „Zapisz wynik, a potem go ocenimy”.

- **Kadr i montaż:** Ujęcie pomagające zrozumieć, że przeglądarka jest lokalna; bez fałszywego wyniku.

- **Prawdziwa funkcja / ograniczenie:** `/api/sprawy/{id}/krz`, pomocnik KRZ; działanie zależne od portalu.

- **Biblioteka wspólna:** `R08,R11,R16` · **nowy beat/ujęcie:** `N06D: prawdziwy przebieg KRZ na środowisku testowym`.

- **Punkt kontrolny:** Nie używać prawdziwego PESEL ani nie twierdzić, że „brak wpisu” oznacza bezwzględne bezpieczeństwo.

- **Minimalny prompt delta** (dołączany do jednego promptu bazowego, nie samodzielny): `notary local browser assistant checking KRZ publicly with human review`.



### E06S05 · 33–41 · Zapis, nie wyrok

- **Miejsce:** stanowisko Marty; **obsada:** Kuba, Marta.

- **Działanie:** Marta ogląda ślad sprawdzenia w sprawie. Nie wyciąga automatycznego wniosku prawnego.

- **Dialog / napisy:** MARTA: „Dobrze. Mamy datę i wynik próby sprawdzenia. Teraz weryfikacja”.

- **Kadr i montaż:** CU rzeczywistej historii sprawdzeń, jeśli demo działa; w przeciwnym razie dokumentacyjne ujęcie bez nazwiska.

- **Prawdziwa funkcja / ograniczenie:** Ślad audytowy `rejestry.py`, `krz.py`; odpowiedzialność człowieka.

- **Biblioteka wspólna:** `R14` · **nowy beat/ujęcie:** `N06E: podgląd faktycznie uzyskanego wyniku`.

- **Punkt kontrolny:** Wynik portalu tylko z dozwolonych danych testowych.

- **Minimalny prompt delta** (dołączany do jednego promptu bazowego, nie samodzielny): `authentic case check audit log without personal identifiers`.



### E06S06 · 41–50 · Prawda wychodzi na jaw

- **Miejsce:** korytarz; **obsada:** Paweł, Marta.

- **Działanie:** Paweł zostaje na chwilę na osobności z Martą, pokazuje własną notatkę o rezerwacji mieszkania na parterze.

- **Dialog / napisy:** PAWEŁ: „Znalazłem mamie mieszkanie bez schodów. Zapłaciłem za rezerwację. I potem zacząłem wszystko przyspieszać”.

- **Kadr i montaż:** Zbliżenie na dłoń Pawła trzymającą potwierdzenie D21.

- **Prawdziwa funkcja / ograniczenie:** Brak. Rewelacja nie pochodzi z AI.

- **Biblioteka wspólna:** `R05,R09` · **nowy beat/ujęcie:** `N06F: wyznanie Pawła`.

- **Punkt kontrolny:** Paweł nie przerzuca własnych zobowiązań na matkę; dokument to fikcyjna rezerwacja.

- **Minimalny prompt delta** (dołączany do jednego promptu bazowego, nie samodzielny): `adult son confesses he reserved ground-floor flat with his own money`.



### E06S07 · 50–60 · Wstyd, nie przestępstwo

- **Miejsce:** korytarz; **obsada:** Paweł, Marta.

- **Działanie:** Marta nie ocenia go moralnie; wyjaśnia znaczenie potwierdzania informacji przez właściwe osoby.

- **Dialog / napisy:** MARTA: „Chciał pan jej pomóc. Ale to pani Irena decyduje, czy i kiedy”.

**PAWEŁ:** „Wiem. Teraz już wiem”.

- **Kadr i montaż:** Dłuższe ujęcie dwuosobowe, żadnego agresywnego cięcia.

- **Prawdziwa funkcja / ograniczenie:** Nie ma interwencji AI.

- **Biblioteka wspólna:** `R05` · **nowy beat/ujęcie:** `N06G: szczery wstyd Pawła`.

- **Punkt kontrolny:** Prawidłowa reprezentacja Ireny; nie sugerować winy karnej.

- **Minimalny prompt delta** (dołączany do jednego promptu bazowego, nie samodzielny): `gentle frank talk about autonomy and family pressure`.



### E06S08 · 60–71 · Wiedza o człowieku

- **Miejsce:** gabinet Heleny; **obsada:** Helena, Marta.

- **Działanie:** Marta przekazuje Helenie informację, że termin był efektem nadgorliwości syna. Helena rozumie sytuację, ale nie poświęca zasad.

- **Dialog / napisy:** HELENA: „Nie jest źle mieć dobry zamiar. Trzeba jeszcze zostawić drugiemu człowiekowi decyzję”.

- **Kadr i montaż:** Statyczny, bezpośredni portret Heleny.

- **Prawdziwa funkcja / ograniczenie:** Granice oceny prawnej.

- **Biblioteka wspólna:** `R06` · **nowy beat/ujęcie:** `N06H: lekcja Heleny`.

- **Punkt kontrolny:** Sprawdzić continuity, dane demonstracyjne i realne UI.

- **Minimalny prompt delta** (dołączany do jednego promptu bazowego, nie samodzielny): `experienced notary thoughtful reaction to family conflict`.



### E06S09 · 71–80 · Zawieszenie

- **Miejsce:** recepcja / plansza; **obsada:** Basia, Paweł.

- **Działanie:** Paweł wychodzi. Basia patrzy za nim, telefon dzwoni ponownie — tym razem nie rzuca się od razu, spokojnie kończy notatkę.

- **Dialog / napisy:** NAPIS: „Czy odważy się powiedzieć to matce?”

- **Kadr i montaż:** Wyjście z budynku + outro.

- **Prawdziwa funkcja / ograniczenie:** Brak.

- **Biblioteka wspólna:** `R01,R03,R20` · **nowy beat/ujęcie:** `N06I: cisza wśród hałasu`.

- **Punkt kontrolny:** Sprawdzić continuity, dane demonstracyjne i realne UI.

- **Minimalny prompt delta** (dołączany do jednego promptu bazowego, nie samodzielny): `somber adult man leaving legal office as secretary calmly finishes task`.




## Kluczowe warunki prawne i produktowe

- Nie ma globalnej, potwierdzonej tablicy przydziałów zadań. KRZ wynik to materiał do kontroli, nie automatyczna decyzja.

- Nie wprowadzać screenów lub komunikatów, których rzeczywisty NotarAI nie wygenerował podczas testu.

- W każdym ujęciu ze sprawą główną zachować cenę 640 000 zł, wydanie 15.01.2027 r. po ustaleniach T2 i tytuł „NOWAK — KACZMAREK”.

- Tytuł własności, sytuację majątkową stron, sposoby zapłaty oraz stan KW zweryfikować przed inscenizacją czynności.


## Mailing do odcinka: kierunek
Wspólne informacje o sprawach nie wymagają wspólnej pamięci jednej osoby.

**CTA:** Zobacz, jak sprawy i sprawdzenia trafiają do teczki. Nie zdradzać w mailu puenty odcinka.


## Reuse

Ujęcia R** odczytać w `04_PROMPTY_I_MONTAZ/BIBLIOTEKA_UREC.md`. Nowy beat N** jest unikalną grą aktorską lub realnym nagraniem UI, ale nie wymaga nowego wygenerowania całej scenografii ani nowego promptu tożsamości.


## Decyzja o publikacji

**HOLD** do czasu zatwierdzenia przez praktykującego notariusza, testów UX na syntetycznej teczce oraz kontroli napisów.

---

# EP07 — Pokaż mi to na komputerze

**Data fabularna:** 25.11.2026 · **Czas:** 76 s · **Wersja:** robocza do autoryzacji · **Format:** 9:16, adaptacja 16:9


> **Kanon:** nie zmieniać nazwisk, wieku, relacji, dat ani dokumentów z `01_KANON/BIBLIA_INTRYGI_KANON_2026-11-12.md`. Odcinek nie jest konsultacją prawną; przed publikacją wymaga kontroli notariusza.


## Funkcja główna
Mobilny kokpit sprawy w trybie chmurowym; przygotowanie projektu


**Uzupełniające:** Lokalny pomocnik „Klikamy” na komputerze kancelarii, lecz bez bezdotykowego zdalnego wywołania z telefonu.


**Logline:** Helena poza kancelarią sprawdza status sprawy na telefonie, a w biurze Marta przygotowuje kolejną wersję projektu.


**Hak:** Helena poza biurem widzi status „Projekt Word”, ale wciąż potrzebuje potwierdzenia warunków.


**Co widz odkrywa:** Irena, kupujący i Paweł wreszcie rozmawiają o jednej wersji warunków z wydaniem 15 stycznia.


**Pytanie końcowe:** Czy zdążą przygotować bezpieczny projekt do piątku?


## Scenopis — wszystkie sceny


### E07S01 · 00–06 · Zdalny podgląd

- **Miejsce:** korytarz poza kancelarią; **obsada:** Helena.

- **Działanie:** Helena wychodzi z budynku, zatrzymuje się przed wejściem na spotkanie. Na ekranie telefonu widać NotarAI, nie tę samą makietę co na laptopie.

- **Dialog / napisy:** HELENA (pod nosem): „Sprawdźmy, co mamy”.

- **Kadr i montaż:** Półplan Helena, screen-record realnego mobilnego frontendu.

- **Prawdziwa funkcja / ograniczenie:** `/api/sprawy` i kokpit w trybie SaaS po autoryzacji.

- **Biblioteka wspólna:** `R10,R17` · **nowy beat/ujęcie:** `N07A: Helena poza biurem z telefonem`.

- **Punkt kontrolny:** Przed emisją test mobile konta, uprawnień i danych w chmurze.

- **Minimalny prompt delta** (dołączany do jednego promptu bazowego, nie samodzielny): `senior notary checking authentic NotarAI mobile case dashboard outside office`.



### E07S02 · 06–15 · Projekt nie oznacza końca

- **Miejsce:** telefon Heleny; **obsada:** Helena.

- **Działanie:** Helena otwiera „Moje sprawy” → NOWAK–KACZMAREK. Ekran wskazuje zapisany projekt, ale nie „sprawa zakończona”.

- **Dialog / napisy:** HELENA: „Projekt jest. Czekam jeszcze na potwierdzenie terminu wydania”.

- **Kadr i montaż:** Ujęcie mobilnego ekranu z prawdziwym statusem; zero fikcyjnych kart z automatycznym assignment.

- **Prawdziwa funkcja / ograniczenie:** Kokpit statusu projektu, nie pełny global task manager.

- **Biblioteka wspólna:** `R10,R14` · **nowy beat/ujęcie:** `N07B: rzeczywisty status sprawy na telefonie`.

- **Punkt kontrolny:** W aplikacji tryb SaaS.

- **Minimalny prompt delta** (dołączany do jednego promptu bazowego, nie samodzielny): `mobile dashboard genuine review-needed status not falsely marked approved`.



### E07S03 · 15–23 · Dobra rozmowa zamiast komendy

- **Miejsce:** stanowisko Marty; **obsada:** Marta, Kuba.

- **Działanie:** Helena dzwoni do Marty. Marta sprawdza, czy strony przekazały zgodne ustalenia i dokumenty D11.

- **Dialog / napisy:** HELENA (przez telefon): „Marto, pokaż mi, co jest już potwierdzone. Bez założeń”.

**MARTA:** „Sprawdzam źródła”.

- **Kadr i montaż:** Split edit dwóch realnych ujęć, bez animacji zdalnego kliknięcia.

- **Prawdziwa funkcja / ograniczenie:** Dane w sprawie + zwykły telefon; żadnego wywołania AI na zdalnym PC.

- **Biblioteka wspólna:** `R07,R10` · **nowy beat/ujęcie:** `N07C: autentyczna współpraca na odległość`.

- **Punkt kontrolny:** Nie podawać „Komputerku pokaż na moim komputerze” jako funkcji, dopóki nie przetestowano.

- **Minimalny prompt delta** (dołączany do jednego promptu bazowego, nie samodzielny): `colleague on office laptop reporting case status by phone`.



### E07S04 · 23–34 · Wspólny język

- **Miejsce:** recepcja / stół; **obsada:** Irena, Paweł, Joanna, Robert.

- **Działanie:** Przedstawiciele stron rozmawiają przy stole; Paweł nie mówi już za matkę. Kupujący potwierdzają, że mogą przedłużyć najem.

- **Dialog / napisy:** IRENA: „Potrzebuję czasu do piętnastego stycznia”.

**JOANNA:** „Udało nam się przedłużyć najem”.

**PAWEŁ:** „Mamo, przepraszam, że wszystko przyspieszyłem”.

- **Kadr i montaż:** Szeroki czteroosobowy plan, potem CU Ireny.

- **Prawdziwa funkcja / ograniczenie:** Brak. To człowiek ustala fakty.

- **Biblioteka wspólna:** `R02` · **nowy beat/ujęcie:** `N07D: unikalne emocjonalne pojednanie`.

- **Punkt kontrolny:** Nie przedstawiać jeszcze, że umowa została zawarta.

- **Minimalny prompt delta** (dołączany do jednego promptu bazowego, nie samodzielny): `mother son and married couple reach agreement around notary table`.



### E07S05 · 34–43 · Nowa wersja warunków

- **Miejsce:** stanowisko Marty; **obsada:** Marta, Kuba.

- **Działanie:** Marta wpisuje potwierdzone ustalenia do rzeczywistej rozmowy o sprawie lub aktualizuje pola i opis; źródłem jest oddzielnie przygotowana notatka D11, nie sam mail Pawła.

- **Dialog / napisy:** KUBA: „Piętnasty stycznia. Ustalony już ze wszystkimi”.

**MARTA:** „Zapisz źródło, nie tylko datę”.

- **Kadr i montaż:** CU notatki D11, klawiatura i prawdziwe UI.

- **Prawdziwa funkcja / ograniczenie:** Rozmowa o sprawie, dane do projektu; brak automatycznej formalnej akceptacji warunków.

- **Biblioteka wspólna:** `R08,R09` · **nowy beat/ujęcie:** `N07E: aktualizacja warunków z kontrolą źródła`.

- **Punkt kontrolny:** Komplet dokumentów i finansowania nadal do weryfikacji.

- **Minimalny prompt delta** (dołączany do jednego promptu bazowego, nie samodzielny): `notary enters verified January 15 handover terms in case notes`.



### E07S06 · 43–53 · Komputerku, robimy projekt

- **Miejsce:** stanowisko Marty; **obsada:** Marta.

- **Działanie:** Marta zwraca się do komputera zwyczajowo, klika „Sporządź projekt”; w filmie następuje wyraźny przeskok czasu.

- **Dialog / napisy:** MARTA: „Komputerku, przygotujmy kolejną wersję. Na tych ustaleniach”.

- **Kadr i montaż:** Prawdziwe UI i kliknięcie, nie sztuczny głos sterujący.

- **Prawdziwa funkcja / ograniczenie:** Generowanie projektu i raport zgodności.

- **Biblioteka wspólna:** `R08,R14,R15` · **nowy beat/ujęcie:** `N07F: unikalne rozpoczęcie generowania po nowym potwierdzeniu`.

- **Punkt kontrolny:** Projekt nadal jest do kontroli; nie obiecywać natychmiastowego wyniku.

- **Minimalny prompt delta** (dołączany do jednego promptu bazowego, nie samodzielny): `authentic word drafting UI after verified data update`.



### E07S07 · 53–61 · Granica pomocnika

- **Miejsce:** lokalny komputer kancelarii; **obsada:** Kuba, Marta.

- **Działanie:** Kuba pokazuje uruchomionego na komputerze pomocnika. Marta zaznacza, że może on pomóc w pracy z dozwolonymi portalami, ale zatrzymuje się przed wysłaniem, podpisaniem i płatnością.

- **Dialog / napisy:** KUBA: „Pomocnik działa tutaj, na naszym komputerze”.

**MARTA:** „A decyzje i podpisy zostają przy nas”.

- **Kadr i montaż:** Tylko prawdziwy ekran lokalnego pomocnika.

- **Prawdziwa funkcja / ograniczenie:** `pomocnik/klikamy.py`; kontrola działań o skutku zewnętrznym.

- **Biblioteka wspólna:** `R16,R14` · **nowy beat/ujęcie:** `N07G: autentyczna praca lokalnego pomocnika`.

- **Punkt kontrolny:** Połączenie urządzeń należy potwierdzić; nie udawać zdalnego polecenia z telefonu.

- **Minimalny prompt delta** (dołączany do jednego promptu bazowego, nie samodzielny): `local notary computer browser helper with cautious human control`.



### E07S08 · 61–69 · Spokój, ale nie koniec

- **Miejsce:** poza kancelarią; **obsada:** Helena.

- **Działanie:** Helena kończy połączenie, na telefonie widzi otwartą sprawę. Chowa urządzenie i idzie na spotkanie.

- **Dialog / napisy:** HELENA: „Dobrze. Jutro sprawdzę to na spokojnie”.

- **Kadr i montaż:** Kadr średni, dzień pochmurny, naturalna uliczna cisza.

- **Prawdziwa funkcja / ograniczenie:** Mobilny dostęp do stanu sprawy, bez fikcyjnego raportu zadań.

- **Biblioteka wspólna:** `R17,R10` · **nowy beat/ujęcie:** `N07H: komfort bez bycia stale online`.

- **Punkt kontrolny:** Sprawdzić continuity, dane demonstracyjne i realne UI.

- **Minimalny prompt delta** (dołączany do jednego promptu bazowego, nie samodzielny): `senior professional pockets phone after checking office case progress`.



### E07S09 · 69–76 · Cliffhanger

- **Miejsce:** plansza; **obsada:** -.

- **Działanie:** Plansza z datą „Piątek, 27 listopada” nad konturem dokumentu.

- **Dialog / napisy:** NAPIS: „Czy wszystko jest gotowe do podpisania?”

- **Kadr i montaż:** Stały outro.

- **Prawdziwa funkcja / ograniczenie:** Brak.

- **Biblioteka wspólna:** `R20` · **nowy beat/ujęcie:** `-`.

- **Punkt kontrolny:** Sprawdzić continuity, dane demonstracyjne i realne UI.

- **Minimalny prompt delta** (dołączany do jednego promptu bazowego, nie samodzielny): `clean legal technology suspense endcard with upcoming Friday date`.




## Kluczowe warunki prawne i produktowe

- Tryb lokalnego przechowywania nie uprawnia do obietnicy dostępu z całego świata; głos nie wykonuje zadań automatycznie.

- Nie wprowadzać screenów lub komunikatów, których rzeczywisty NotarAI nie wygenerował podczas testu.

- W każdym ujęciu ze sprawą główną zachować cenę 640 000 zł, wydanie 15.01.2027 r. po ustaleniach T2 i tytuł „NOWAK — KACZMAREK”.

- Tytuł własności, sytuację majątkową stron, sposoby zapłaty oraz stan KW zweryfikować przed inscenizacją czynności.


## Mailing do odcinka: kierunek
Notariusz może zobaczyć status sprawy poza biurem, ale nie musi wszystkiego robić sam.

**CTA:** Zobacz mobilny kokpit i projekt Word. Nie zdradzać w mailu puenty odcinka.


## Reuse

Ujęcia R** odczytać w `04_PROMPTY_I_MONTAZ/BIBLIOTEKA_UREC.md`. Nowy beat N** jest unikalną grą aktorską lub realnym nagraniem UI, ale nie wymaga nowego wygenerowania całej scenografii ani nowego promptu tożsamości.


## Decyzja o publikacji

**HOLD** do czasu zatwierdzenia przez praktykującego notariusza, testów UX na syntetycznej teczce oraz kontroli napisów.

---

# EP08 — To moja decyzja

**Data fabularna:** 27.11.2026 · **Czas:** 96 s · **Wersja:** robocza do autoryzacji · **Format:** 9:16, adaptacja 16:9


> **Kanon:** nie zmieniać nazwisk, wieku, relacji, dat ani dokumentów z `01_KANON/BIBLIA_INTRYGI_KANON_2026-11-12.md`. Odcinek nie jest konsultacją prawną; przed publikacją wymaga kontroli notariusza.


## Funkcja główna
Projekt aktu, kontrola danych, własny wzór i archiwum sprawy


**Uzupełniające:** Kalendarz i zespół; materiały KW i rejestrów według wymagań konkretnej czynności.


**Logline:** Po serii przygotowań strony spotykają się z kompletem uzgodnień, a Irena decyduje samodzielnie. Helena godzi się oddać technice rutynę, ale nie ocenę.


**Hak:** Zbliżenie do otwartej teczki: ten sam termin w dwóch miejscach — tym razem zgodny.


**Co widz odkrywa:** Strony rozumieją warunki; Irena mówi własnym głosem; Paweł przeprasza; sprzedaż dochodzi do skutku po ludzkiej kontroli.


**Pytanie końcowe:** Pierwsze spontaniczne „Komputerku” Heleny zapowiada nowy sezon.


## Scenopis — wszystkie sceny


### E08S01 · 00–07 · Dwie daty

- **Miejsce:** gabinet Heleny; **obsada:** Helena.

- **Działanie:** Helena otwiera teczkę, w której pierwsza wersja T1 ma przekreślony termin 1 XII, a aktualna T2 ma 15 I. Dłuższa pauza; zero przeciągania.

- **Dialog / napisy:** HELENA (cicho): „Teraz to są ustalenia stron”.

- **Kadr i montaż:** Zbliżenie na dwie papierowe notatki; konkretne daty.

- **Prawdziwa funkcja / ograniczenie:** Brak automatycznego konkludowania przez AI.

- **Biblioteka wspólna:** `R06,R09` · **nowy beat/ujęcie:** `N08A: kanoniczne T1/T2`.

- **Punkt kontrolny:** Nie pomylić wydania z przeniesieniem własności.

- **Minimalny prompt delta** (dołączany do jednego promptu bazowego, nie samodzielny): `older notary checks two consistent final transaction dates on synthetic paperwork`.



### E08S02 · 07–15 · Każdy wie, za co odpowiada

- **Miejsce:** recepcja; **obsada:** Basia, Kuba.

- **Działanie:** Basia sprawdza termin w kalendarzu. Kuba przekazuje Martcie teczkę z oznaczonymi źródłami i roboczymi dokumentami.

- **Dialog / napisy:** BASIA: „Strony potwierdziły przyjście”.

**KUBA:** „Materiały do kontroli są razem”.

- **Kadr i montaż:** Sekwencja spokojnych match cutów znanych z pilota.

- **Prawdziwa funkcja / ograniczenie:** Kalendarz, pliki sprawy i lista spraw, bez nieistniejącego task boardu.

- **Biblioteka wspólna:** `R01,R07,R10` · **nowy beat/ujęcie:** `N08B: spokojniejsze powtórzenie poniedziałkowego korytarza`.

- **Punkt kontrolny:** Nie wywodzić prawnej gotowości wyłącznie ze statusu w aplikacji.

- **Minimalny prompt delta** (dołączany do jednego promptu bazowego, nie samodzielny): `busy but orderly notary reception on transaction day`.



### E08S03 · 15–24 · Ostatnia wersja projektu

- **Miejsce:** stanowisko Marty; **obsada:** Marta, Kuba.

- **Działanie:** Marta otwiera projekt dokumentu, raport zgodności i ewentualne znaczniki. Ponownie sprawdza rozbieżności i źródła.

- **Dialog / napisy:** MARTA: „Tu już mamy uzgodniony termin. Teraz całość do kontroli”.

- **Kadr i montaż:** Autentyczny ekran projektu; nie pokazujemy „zatwierdzono przez AI”.

- **Prawdziwa funkcja / ograniczenie:** Projekt Word, „Weryfikacja odczytu”, raport zasad.

- **Biblioteka wspólna:** `R08,R14,R15` · **nowy beat/ujęcie:** `N08C: realny projekt na podstawie T2`.

- **Punkt kontrolny:** Projekt nie jest aktem podpisanym.

- **Minimalny prompt delta** (dołączany do jednego promptu bazowego, nie samodzielny): `notary reviewing final Word draft and data verification on real UI`.



### E08S04 · 24–32 · Zaufanie do narzędzia

- **Miejsce:** gabinet Heleny; **obsada:** Helena, Marta.

- **Działanie:** Marta przynosi projekt Helenie. Ta nie przegląda sterty przypadkowych papierów, tylko przechodzi przez uporządkowane materiały.

- **Dialog / napisy:** HELENA: „Wreszcie wiem, skąd mamy każdą z tych informacji”.

**MARTA:** „I gdzie jeszcze trzeba spojrzeć”.

- **Kadr i montaż:** Półplan dwóch notariuszek; spokojne światło.

- **Prawdziwa funkcja / ograniczenie:** Dokumenty i projekt w jednej sprawie; nie zapewniać, że AI niezawodnie cytuje wszystko.

- **Biblioteka wspólna:** `R06` · **nowy beat/ujęcie:** `N08D: wzajemny szacunek Heleny i Marty`.

- **Punkt kontrolny:** Źródła widoczne tylko tam, gdzie faktycznie istnieją w UI.

- **Minimalny prompt delta** (dołączany do jednego promptu bazowego, nie samodzielny): `two experienced women notaries review organized transaction file`.



### E08S05 · 32–41 · Przeprosiny

- **Miejsce:** poczekalnia; **obsada:** Irena, Paweł.

- **Działanie:** Paweł czeka z matką. Zanim wejdą, zabiera głos bez obronnego tonu.

- **Dialog / napisy:** PAWEŁ: „Mamo, chciałem ci pomóc. Zacząłem decydować za ciebie”.

**IRENA:** „Wiem. Teraz mi po prostu pomóż spokojnie się przeprowadzić”.

- **Kadr i montaż:** CU dłoni na poręczy, potem twarzy Ireny; scenie dać czas.

- **Prawdziwa funkcja / ograniczenie:** Brak. Kulminacja emocjonalna.

- **Biblioteka wspólna:** `R02` · **nowy beat/ujęcie:** `N08E: pojednanie matki i syna`.

- **Punkt kontrolny:** Irena zachowuje sprawczość.

- **Minimalny prompt delta** (dołączany do jednego promptu bazowego, nie samodzielny): `emotional mother son reconciliation in notary waiting room`.



### E08S06 · 41–53 · Zrozumienie treści

- **Miejsce:** gabinet Heleny; **obsada:** Helena, Irena, Joanna, Robert.

- **Działanie:** Helena wyjaśnia kluczowe warunki dotyczące nieruchomości, zapłaty i wydania, upewniając się, że strony rozumieją skutki. Unikamy odgrywania ustawowej formuły odczytania aktu w 12 s.

- **Dialog / napisy:** HELENA: „Własność i wydanie lokalu to nie to samo. Termin wydania ustalili państwo na piętnastego stycznia, zgadza się?”

**IRENA:** „Tak. To moja decyzja”.

- **Kadr i montaż:** Szeroki, godny kadr; reakcja kupujących.

- **Prawdziwa funkcja / ograniczenie:** Ludzka ocena, żadna autonomiczna czynność przez NotarAI.

- **Biblioteka wspólna:** `R06` · **nowy beat/ujęcie:** `N08F: świadome potwierdzenie Ireny`.

- **Punkt kontrolny:** Kwestie konkretnych warunków, stawiennictwa i finansowania do legal signoff.

- **Minimalny prompt delta** (dołączany do jednego promptu bazowego, nie samodzielny): `notary checking seller informed will and handover terms before signing`.



### E08S07 · 53–62 · Zgoda kupujących

- **Miejsce:** gabinet Heleny; **obsada:** Joanna, Robert, Helena.

- **Działanie:** Joanna i Robert potwierdzają, że znaleźli rozwiązanie najmu i rozumieją późniejszy termin wydania.

- **Dialog / napisy:** JOANNA: „Przedłużyliśmy najem. To dla nas teraz jasne”.

**ROBERT:** „Tak, możemy poczekać do piętnastego stycznia”.

- **Kadr i montaż:** Dwuplan kupujących, niewymuszona ulga.

- **Prawdziwa funkcja / ograniczenie:** Brak. Warunki ustalone między ludźmi.

- **Biblioteka wspólna:** `R06` · **nowy beat/ujęcie:** `N08G: reakcja kupujących`.

- **Punkt kontrolny:** Nie ujawniać prywatnych szczegółów niespójnych z D09.

- **Minimalny prompt delta** (dołączany do jednego promptu bazowego, nie samodzielny): `married couple calmly confirm revised move-in date`.



### E08S08 · 62–71 · Czynność notarialna poza krótką sceną

- **Miejsce:** przejście / upływ czasu; **obsada:** Helena, Irena.

- **Działanie:** Montażowy przeskok: detal teczki, zamknięte drzwi gabinetu, później strony wychodzące. Narracja zakłada, że czynność doszła do skutku dopiero po pełnej wymaganej procedurze i autoryzacji realistycznej sceny.

- **Dialog / napisy:** BEZ DIALOGU; delikatny dźwięk zamykanej teczki.

- **Kadr i montaż:** Nie imitować podpisu kwalifikowanego ani złożenia wniosku przez AI.

- **Prawdziwa funkcja / ograniczenie:** Nie ma automatyzacji czynności notarialnej.

- **Biblioteka wspólna:** `R05,R09` · **nowy beat/ujęcie:** `N08H: subtelny upływ czasu`.

- **Punkt kontrolny:** Przed realizacją notariusz zatwierdza zgodność fabuły: płatność, finansowanie i wszystkie elementy.

- **Minimalny prompt delta** (dołączany do jednego promptu bazowego, nie samodzielny): `time passing montage notary office professional transaction completed off camera`.



### E08S09 · 71–80 · Nagroda emocjonalna

- **Miejsce:** korytarz; **obsada:** Irena, Helena.

- **Działanie:** Irena zatrzymuje się przy wyjściu i odwraca do Heleny.

- **Dialog / napisy:** IRENA: „Dziękuję, że pani mnie wysłuchała”.

**HELENA:** „Od tego tu jestem”.

- **Kadr i montaż:** Zbliżenie twarzy Ireny, realny oddech, cisza.

- **Prawdziwa funkcja / ograniczenie:** Brak. Puenta człowieka.

- **Biblioteka wspólna:** `R05` · **nowy beat/ujęcie:** `N08I: finał emocjonalny, nie używać w innych odcinkach`.

- **Punkt kontrolny:** Nie tworzyć wrażenia, że rolą notariusza było zaakceptowanie niepoprawnego aktu.

- **Minimalny prompt delta** (dołączany do jednego promptu bazowego, nie samodzielny): `elderly woman thanks senior notary for listening after transaction`.



### E08S10 · 80–87 · Nowe przyzwyczajenie

- **Miejsce:** gabinet Heleny; **obsada:** Helena, Marta.

- **Działanie:** Marta zbiera dokumenty, Helena otwiera kolejną teczkę.

- **Dialog / napisy:** MARTA: „No i jak, pani rejent, nasz komputerek?”

**HELENA:** „Przydał się. Ale ostatnie słowo wciąż należy do nas”.

- **Kadr i montaż:** Dwa średnie plany, lekkie rozluźnienie.

- **Prawdziwa funkcja / ograniczenie:** Granice produktu.

- **Biblioteka wspólna:** `R06,R09` · **nowy beat/ujęcie:** `N08J: wspólna reakcja obu notariuszek`.

- **Punkt kontrolny:** Sprawdzić continuity, dane demonstracyjne i realne UI.

- **Minimalny prompt delta** (dołączany do jednego promptu bazowego, nie samodzielny): `friendly exchange between senior and younger notary after complex case`.



### E08S11 · 87–92 · Komputerku po raz pierwszy

- **Miejsce:** gabinet Heleny; **obsada:** Helena, Marta.

- **Działanie:** Helena siada, uśmiecha się i otwiera na laptopie następną sprawę.

- **Dialog / napisy:** HELENA: „Komputerku, zobaczmy, co jest w następnej teczce”.

- **Kadr i montaż:** CU Heleny na chwilę; Marta zaskoczona w drugim planie.

- **Prawdziwa funkcja / ograniczenie:** Hasło jako nawyk; ręczne otwarcie kokpitu, bez nasłuchu 24/7.

- **Biblioteka wspólna:** `R06,R08` · **nowy beat/ujęcie:** `N08K: KLUCZOWY UNIKALNY HERO SHOT SEZONU`.

- **Punkt kontrolny:** Widz musi widzieć naturalny klik, nie magiczny voice-trigger.

- **Minimalny prompt delta** (dołączany do jednego promptu bazowego, nie samodzielny): `silver-haired senior notary casually says computerku while opening next legal case`.



### E08S12 · 92–96 · Finał marki

- **Miejsce:** plansza; **obsada:** -.

- **Działanie:** NotarAI, oryginalny sygnet; krótki podpis; bez obietnic kompletnej automatyzacji.

- **Dialog / napisy:** NAPIS: „Mniej chaosu. Więcej czasu na to, co ważne”.

- **Kadr i montaż:** Stały OUTRO_9x16, końcowe CTA.

- **Prawdziwa funkcja / ograniczenie:** Brak.

- **Biblioteka wspólna:** `R20` · **nowy beat/ujęcie:** `-`.

- **Punkt kontrolny:** Sprawdzić continuity, dane demonstracyjne i realne UI.

- **Minimalny prompt delta** (dołączany do jednego promptu bazowego, nie samodzielny): `clean branded outro with original logo and legally accurate tagline`.




## Kluczowe warunki prawne i produktowe

- Obowiązki notariusza, forma aktu, stwierdzenie tożsamości, weryfikacja oświadczeń i wniosek KW nie mogą być zasymulowane jako automatyczne.

- Nie wprowadzać screenów lub komunikatów, których rzeczywisty NotarAI nie wygenerował podczas testu.

- W każdym ujęciu ze sprawą główną zachować cenę 640 000 zł, wydanie 15.01.2027 r. po ustaleniach T2 i tytuł „NOWAK — KACZMAREK”.

- Tytuł własności, sytuację majątkową stron, sposoby zapłaty oraz stan KW zweryfikować przed inscenizacją czynności.


## Mailing do odcinka: kierunek
Finał współpracy zespołu: AI porządkuje, notariuszka ocenia.

**CTA:** Zobacz pełny proces przygotowania projektu aktu. Nie zdradzać w mailu puenty odcinka.


## Reuse

Ujęcia R** odczytać w `04_PROMPTY_I_MONTAZ/BIBLIOTEKA_UREC.md`. Nowy beat N** jest unikalną grą aktorską lub realnym nagraniem UI, ale nie wymaga nowego wygenerowania całej scenografii ani nowego promptu tożsamości.


## Decyzja o publikacji

**HOLD** do czasu zatwierdzenia przez praktykującego notariusza, testów UX na syntetycznej teczce oraz kontroli napisów.

---

## Uwagi końcowe
Pełna biblia intrygi, dokumenty D01–D22 i rygory autoryzacji znajdują się w pozostałych plikach. Wszelkie integracje wymagające testu end-to-end mają pozostać jako „do demonstracji” aż do faktycznej weryfikacji. Nie publikować bez prawnej autoryzacji.