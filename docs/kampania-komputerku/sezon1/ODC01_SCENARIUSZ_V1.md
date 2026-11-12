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
