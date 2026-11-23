# Kancelaria pod Siódemką / „Komputerku…” - Biblia V6

**Jedyne źródło prawdy serialu od 23.11.2026.** Zastępuje: `sezon-1/01_KANON/BIBLIA_INTRYGI.md`,
`sezon-1/05_REZYSERIA_V5_THRILLER.md`, `sezon-1/05_REZYSERIA_V5_THRILLER_ROMANS.md`,
`sezon-1/06_ZEWNETRZNE_LOKACJE_I_ZDALNY_ASYSTENT.md`, `sezon-1/07_SEZON2_WIZYTACJA_ZARYS.md`,
`sezon-1/08_MOTYW_KARMIENIE_KOMPUTERKA.md`, recepty `sezon-1/09`–`13` i
`sezon-1/03_PRODUKCJA/REUSE_I_QA.md`. Stare pliki zostają jako archiwum i źródło szczegółów;
przy sprzeczności obowiązuje ten plik.

Spis: 0. Decyzje właściciela · 1. Format bez końca · 2. Świat i postacie · 3. Szablon odcinka ·
4. Listy kontrolne · 5. Prawdziwe sprawy · 6. Sezon 1 (40 odcinków) · 7. Sezony 2 i 3 ·
8. Produkcja i koszty · 9. Publikacja i pomiar · 10. Tablica statusu.

---

## 0. Decyzje właściciela (nadrzędne)

| Data | Decyzja |
|---|---|
| 23.11.2026 | Serial bez końca: **2 odcinki dziennie, 09:00 i 16:00** (czas polski), codziennie. Premiera 23.11.2026, 16:00. |
| 23.11.2026 | Premiera i publikacja na **notarai.pl**. Media społecznościowe dopiero po założeniu i podłączeniu kont NotarAI (dziś podłączone konta należą do Finance You i Filip Bielak Consulting: nie publikujemy tam serialu). |
| 23.11.2026 | **Sezon = jedna główna sprawa + jeden główny antagonista.** Każdy odcinek ma własny niuans: drugą, prawdziwą sprawę. |
| 23.11.2026 | Odcinki opieramy na **prawdziwych, udokumentowanych sprawach**, pisanych jak fikcja, zanonimizowanych. Przestępstwo dopuszczalne, jeśli notariusz wypada korzystnie. Przestępstwa nigdy nie wykrywa AI. |
| 23.11.2026 | Opowiadamy **oczami Heleny**. Marta pokazuje narzędzie, Helena je ocenia. |
| 23.11.2026 | **Akceptacja jest automatyczna:** konsultantami są właściciel i Claude. Bez panelu ekspertów. **Nigdzie nie pada nazwisko notariusza** (notariuszom nie wolno się reklamować). |
| 23.11.2026 | Funkcje NotarAI pokazujemy tylko wtedy, gdy Claude **sprawdził je w prawdziwej aplikacji** przy produkcji danego odcinka. |
| 23.11.2026 | Produkcja najtańszym torem: **SaladCloud (ai-clip: LTX-2.5, InfiniteTalk), głosy ElevenLabs tylko v3+, montaż w CI.** Bez fal i bez HeyGen. Budżet bez limitu, ale cel to koszt minimalny. |
| 23.11.2026 | Oś Ireny zostaje jako główna sprawa sezonu 1. EP06 opiera się na sprawie H23 (banknoty w NBP). P01 (ucharakteryzowana oszustka) dopiero w sezonie 2. |
| 12.11.2026 | Tylko mały znaczek „AI” w rogu przez cały film; bez belki „treść wygenerowana przez AI”. |
| 16.11.2026 | ElevenLabs wyłącznie silniki v3+ (`eleven_v4`, `eleven_v3`); gdy narzędzie nie daje v3+, przerwać, nie schodzić niżej. |

Zasady stałe, które zostają z kanonu V4/V5: Paweł nie jest pełnomocnikiem; własność przechodzi
z umową, wydanie lokalu to osobna sprawa; projekt to nie akt; notariusz nie popełnia rażącego
błędu po to, żeby AI go poprawiło; tajemnica notarialna nie jest przedmiotem żartu ani romansu.

---

## 1. Format bez końca

### 1.1 Rytm
- **09:00 - „Sprawa sezonu”**: odcinek posuwa główną sprawę i wątek antagonisty.
- **16:00 - „Sprawa dnia”**: ten sam dzień w kancelarii, druga prawdziwa sprawa (niuans), a główna
  sprawa wraca w jednej scenie albo w ostatnim zdaniu.
- Oba odcinki dnia dzieją się w tym samym dniu fabularnym. Widz, który ogląda tylko jeden z nich,
  dostaje pełną historię.

### 1.2 Długość sezonu: 40 odcinków (20 dni)
Uzasadnienie:
- **Główna sprawa wytrzyma ok. 40 odsłon.** Odkładanie rozwiązania buduje pragnienie, ale bez
  postępu wyczerpuje widzów (RN019, RN010); telenowela trzyma się, bo ma koniec (TN006).
- **20 dni to dobre okno pomiaru**: wystarczy danych o powrotach i obejrzeniach, żeby zmienić
  sezon następny.
- **Produkcja:** 40 odcinków to 20 paczek GPU. Biblioteka ujęć z sezonu starcza na następny.
- Po sezonie nie ma przerwy (przerwa gubi widzów, KS032): **dzień 21 = odcinek 1 następnego
  sezonu**. Ostatni odcinek sezonu zawiera zapowiedź następnej głównej sprawy.

### 1.3 Łuk sezonu (40 odcinków)

| Akt | Odcinki | Co się dzieje | Zasada |
|---|---|---|---|
| I. Wejście | 1–10 | sprawa i stawka, antagonista pojawia się w tle, pierwsze rozbieżności | widz wie o ryzyku wcześniej niż postacie (TS022) |
| II. Komplikacje | 11–19 | antagonista naciska, każda sprawa dnia odsłania jedną nową regułę | jeden szczyt na odcinek (TS051) |
| Zwrot w połowie | 20 | odsłona, która zmienia ocenę antagonisty albo głównej sprawy | „upadek, potem wzlot” (FS001) |
| III. Eskalacja | 21–30 | antagonista działa otwarcie, kancelaria płaci za staranność czasem i nerwami | zamykające się drogi wyjścia (KS024) |
| IV. Dołek i rozstrzygnięcie | 31–38 | najgorszy moment (czynność odłożona, zarzut wobec kancelarii), potem decyzja stron | decyzja należy do ludzi, nie do AI |
| Finał | 39–40 | domknięcie głównej sprawy, dobry los bohaterów, zapowiedź nowej sprawy | domknięcie lepiej oceniane niż otwarte zakończenie (TS041) |

### 1.4 Rotacja, żeby się nie znudziło
- **Sprawa dnia** zmienia typ co odcinek: testament, sprzedaż, KW, pierwokup, dożywocie, spółka,
  odmowa czynności, awaria systemu, wyjazd do klienta.
- **Otwarcie** zmienia typ (A zdanie z luką, B gest i reakcja, C zegar i przeszkoda); nigdy ten sam
  typ dwa razy z rzędu.
- **Postać prowadząca odcinek** rotuje: Helena (co najmniej co drugi odcinek), Marta, Basia, Kuba,
  Teresa/Zosia. Punkt widzenia całości zostaje przy Helenie.
- **Lokacja**: kancelaria Heleny w większości, kancelaria Teresy co 4–5 odcinków, lokacja
  zewnętrzna co 3–4 odcinki.
- **Żart o karmieniu komputerka** najwyżej co trzeci odcinek; za każdym razem inny mówiący albo
  inne znaczenie.
- **Romans** najwyżej co trzeci odcinek, jeden beat.

---

## 2. Świat i postacie

### 2.1 Kancelaria pod Siódemką (stała scenografia, 9 kamer K1–K9)
Wspólna kancelaria dwóch notariuszek. Każda dokonuje czynności we własnym imieniu.
- **Helena Radecka (56)**: doświadczona notariuszka, prowadzi główną sprawę. Wymagająca, sucha
  ironia, która zawsze jest trafną uwagą zawodową. Łuk: od „muszę wszystkiego dopilnować sama” do
  „widzę całość, więc mogę słuchać ludzi”. Nigdy nie popełnia rażącego błędu.
- **Marta Domańska (38)**: notariuszka, rozumie technologię. Pokazuje narzędzie i mówi też o jego
  ograniczeniach. Jej „Komputerku…” to nawyk zwracania się do programu, pokazany kliknięciem w UI
  (bez hasła wybudzającego).
- **Barbara „Basia” Wrona (51)**: sekretariat, pamięć kancelarii, dyskrecja. Pierwsza mówi
  „A komputerka ktoś nakarmił?”.
- **Jakub „Kuba” Maj (28)**: aplikant notarialny, ambitny, bierze słowa dosłownie. Nie ma
  kompetencji notariusza. Żarty z niego zawsze życzliwe.

### 2.2 Kancelaria Teresy (druga stała scenografia, 3 kamery)
Mała kancelaria bez sekretariatu: odbicie dużej. Kamery: **KT1** biurko Teresy z telefonem,
**KT2** stanowisko Zosi i mini-recepcja, **KT3** drzwi i fragment korytarza.
- **Teresa Janicka (60)**: notariuszka, jedną ręką odbiera telefon, drugą przygotowuje dokumenty.
  Pyta rzeczowo o koszty („ile on miesięcznie zjada?”). Potrzebuje Zosi, ale nie zabrania jej
  niczego.
- **Zofia „Zosia” Lewicka (29)**: aplikantka u cioci, świetna w niuansach, sceptyczna wobec obietnic
  technologii, chce kiedyś mieć własną kancelarię.

### 2.3 Lokacje zewnętrzne (generowane raz, zmienia się pora dnia i pogoda)
EXT01 ulica przed kancelarią · EXT02 klatka schodowa · EXT03 parking i samochód Marty (fikcyjna
tablica) · EXT04 nocna ulica · EXT05 kawiarnia, stolik przy oknie (Kuba i Zosia) · EXT06 korytarz
budynku samorządu (bez emblematu prawdziwej izby) · EXT07 park nad rzeką · **EXT08 (nowa) biuro
pośrednika** (szyba, logo fikcyjne, bez tekstu do przeczytania).
Zasada: ujęcia z dowolnego miejsca w Polsce, bez danych lokalizacji; samochód nigdy w ruchu
z telefonem w ręku.

### 2.4 Romans Kuby i Zosi (szczegóły: `sezon-1/12_ROMANS_Z_BADAN.md`)
- Poznali się dziewięć miesięcy przed sezonem 1 na szkoleniu aplikantów: rzeczowy spór o brak dowodu
  uzgodnienia, potem kawa przerwana telefonem Teresy.
- Sezon 1: niepewność i slow burn, jeden beat najwyżej co trzeci odcinek, bez pocałunku. Najmocniejszy
  gest to dotknięcie dłoni albo podanie kubka. Kolacja w tej samej kawiarni (EXT05), w której przerwano
  kawę.
- Sezon 2: para razem najpóźniej w połowie sezonu; napięcie z przeszkód zewnętrznych (praca, plany
  Zosi, lojalność wobec Teresy).
- Granice: żadnej wymiany akt i danych klientów; nigdy po przeciwnych stronach tej samej czynności
  (a jeśli tak, zgłaszają konflikt); bez nacisku po odmowie; bez sprzeciwu Teresy.

### 2.5 Żart „nakarmić komputerka” (szczegóły: `sezon-1/08_MOTYW_KARMIENIE_KOMPUTERKA.md`)
Znaczy: doładować kredyty na płatne operacje AI. Nigdy w scenie z klientem, nigdy przy prawnej powadze,
nigdy z ceną w dialogu. Słowa puenty („karmić”, „głodny”) nie padają w scenie tuż przed puentą (HM054).
Helena wypowiada go sama dopiero w finale sezonu 1.

### 2.6 Program w serialu
NotarAI porządkuje dokumenty, terminy, odczyty i projekt. **Nie żartuje, nie ma komediowego głosu,
nie wykrywa przestępstw, nie podejmuje decyzji.** Ekrany wyłącznie z prawdziwej aplikacji na danych
testowych, nagrane w dniu produkcji odcinka.

---

## 3. Szablon odcinka (60–90 s, 9:16 i 16:9)

| Czas | Element | Zasada |
|---|---|---|
| 0–3 s | **Zimne otwarcie**: jedno miejsce, jedna rzecz, która się zaczyna (ruch, spojrzenie, głos), zdanie z konkretną luką | bez logo, bez muzyki reklamowej, bez tekstu na ekranie |
| 3–6 s | plansza tytułowa 1,5 s: tytuł odcinka + znak dźwiękowy z wypowiedzianym „Komputerku…” | marka słowem, nie obrazem |
| 6–20 s | świat i stawka: kto, o co, do kiedy | wolniej (FS004) |
| 20–35 s | **zwrot 1 w dół**: rozbieżność, przeszkoda | |
| 35–55 s | praca: postać używa programu, prawdziwy ekran 5–8 s | ekran poza szczytem napięcia (TS033) |
| 55–68 s | **zwrot 2 i szczyt**: decyzja należy do notariusza | jeden szczyt (TS051) |
| 68–80 s | zawieszenie: nowe pytanie, twarz, cięcie | pytanie o ocenę, nie o zgadywanie (TS017) |
| koniec | plansza: „Na motywach prawdziwych spraw z polskich sądów. Osoby i szczegóły zmienione.” + link | |

Na odcinek: **jedna sprawa dnia, jeden szczyt, najwyżej jeden żart, najwyżej jeden beat romansu.**
7–9 scen. Każdy odcinek zrozumiały bez poprzednich (pierwsze 20 s mówi, kto jest kim).

---

## 4. Listy kontrolne (bramka automatyczna przed publikacją)

### 4.1 Thriller prawniczy (12 punktów, `sezon-1/13`)
1. Czynność jako rama i znany termin. 2. Odkrycie wynika z tego, co notariusz przeczytał. 3. Konkretny
dokument w kadrze (warstwa `dokument`, nie generowany obraz). 4. Widz zna ryzyko wcześniej. 5. Wynik
niepewny bez przemocy. 6. Jeden szczyt. 7. Nic spoza świata nie przerywa sceny. 8. Ekran programu poza
szczytem. 9. Każdy krok zgodny z prawem. 10. Sprawiedliwość proceduralna. 11. Prawdziwa sprawa pod
spodem, bez danych pozwalających kogoś rozpoznać. 12. Finał sezonu domyka główną sprawę.

### 4.2 Otwarcie (`sezon-1/10`)
Jedno miejsce i punkt uwagi; początek zmiany; zagadka w zdaniu postaci; zero informacji o produkcie;
dwa głosy w pierwszych 10 s; muzyka brak albo ciepła, nigdy thrillerowa pod twarzą bohaterki; inny typ
otwarcia niż w poprzednim odcinku.

### 4.3 Humor (`sezon-1/11`)
Wpadka drobna, bliska, niegroźna; rozwiązanie widać od razu; obrywa rzecz albo sam mówiący, nigdy klient;
puenta niżej i wolniej, 0,5–1 s na reakcję po puencie; bez śmiechu z taśmy; bez ironii w napisach;
żarty Heleny i Marty to trafne uwagi zawodowe, komizm sytuacyjny niesie Kuba i rzeczy.

### 4.4 Romans (`sezon-1/12`)
Jeden beat; jedno zbliżenie i tylko z emocją; spojrzenie milczącej osoby osobnym ujęciem; emocja w brwiach
i oczach; ciepły motyw tylko pod beatem; granice z 2.4.

### 4.5 Produkcja (`sezon-1/03_PRODUKCJA/REUSE_I_QA.md`, METODYKA ai-clip)
Zero tekstu w ujęciach generowanych; transkrypcja mowy zgodna z kwestią (≥ 0,95); zgodność klatki końcowej
(SSIM ≥ 0,85); kontrola dźwięku (poza mową ≤ −45 dB); tożsamość postaci zgodna z kartą; funkcja programu
sprawdzona dziś w aplikacji; plansza końcowa i znaczek „AI”; brak nazwisk, sygnatur, kwot i miejscowości
z prawdziwych spraw.

### 4.6 Akceptacja
Odcinek jest gotowy, gdy przejdzie 4.1–4.5 (pomiary automatyczne) i Claude jako konsultant wpisze
akceptację w dzienniku produkcji z krótkim uzasadnieniem. Właściciel może zatrzymać każdy odcinek.
Odrzucenie jednego ujęcia = poprawka tylko tego ujęcia.

---

## 5. Prawdziwe sprawy

- **Źródło:** katalog z PR #93 (`docs/research/notarial-casebook-2026/`, gałąź
  `research/notarial-casebook-court-ministry-2026-11`): rekordy S (SN/TK), R (testamenty), K (KW,
  pierwokup, odpowiedzialność), H (nietypowe realia), A (instytucje i systemy), P (sprawy karne).
- **Wybór:** stopień A albo B jako motyw; C nigdy. Notariusz wypada korzystnie. **Wykluczone na stałe:**
  P05–P20 (zarzuty wobec notariuszy) i H17. P01 dopiero od sezonu 2.
- **Karta sprawy przed użyciem** (wzór: `sezon-1/03_PRODUKCJA/KARTA_SPRAWY_H23_BANKNOTY.md`): pełny tekst
  przeczytany, sentencja, prawomocność, ustalenia sądu oddzielone od twierdzeń stron, lista danych
  do pominięcia, mechanizm dla serialu. Karty w `sezon-<n>/03_PRODUKCJA/KARTA_SPRAWY_<ID>.md`.
- **Dziennik użycia:** każdy odcinek ma w nagłówku pole `sprawa_kotwica: <ID>`; ta sama sprawa nie wraca
  częściej niż raz na sezon.
- Gdy katalog się wyczerpie: dopisujemy nowe rekordy w PR #93 (tam tylko fakty), potem karty tutaj.

---

## 6. Sezon 1: „Nie wszystko jest w papierach” (40 odcinków)

### 6.1 Główna sprawa (bez zmian w kanonie)
Irena Nowak sprzedaje mieszkanie (56,40 m²) Joannie i Robertowi Kaczmarkom za 640 000 zł. Paweł, syn,
koordynuje kontakty, ale nie jest pełnomocnikiem. Spór: wydanie lokalu 1 grudnia czy 15 stycznia.
Pytanie sezonu: **kto naprawdę zgodził się na 1 grudnia?**

### 6.2 Antagonista sezonu 1: Adrian Sowa, pośrednik nieruchomości
- **Kim jest:** właściciel małego biura pośrednictwa „Klucz-Dom” (nazwa fikcyjna). Pośredniczy w obu
  transakcjach: sprzedaży mieszkania Ireny i rezerwacji mieszkania na parterze, którą Paweł opłacił
  z własnych pieniędzy. Prowizję za obie dostanie tylko wtedy, gdy obie zamkną się do 1 grudnia.
- **Co robi:** to jego maile zamieniły propozycję w „ustalenie” (EP05), to on rozesłał kupującym starszy
  wariant projektu umowy przedwstępnej (EP03), on dzwoni do kancelarii z prośbą, żeby „przyspieszyć”,
  i proponuje „drobne korekty” daty. Działa w granicach prawa aż do aktu III, potem próbuje nacisku,
  który kancelaria odpiera.
- **Dlaczego on:** daje presji twarz bez oskarżania rodziny. Paweł pomylił się z troski; Sowa wykorzystał
  jego pośpiech. Robert Kaczmarek zostaje sympatycznym kupującym pod presją kończącego się najmu.
  Pośrednik jest typową, realistyczną postacią obrotu (w sprawie H23 też występuje biuro pośrednictwa).
- **Granice:** Sowa nie fałszuje dokumentów w sprawie Ireny; jego „zło” to nacisk, przemilczenia
  i konflikt interesów. Notariusz nie oskarża go publicznie; wyjaśnia i odmawia. Kara spotyka go
  w świecie przedstawionym: traci podwójną prowizję i klientów.

### 6.3 Odcinki 1–8 (istniejące scenariusze, `sezon-1/02_SCENARIUSZE/`)
EP01–EP08 zostają jako pierwsze osiem odcinków z poprawkami z recept 09–13 i z kotwicami:
EP01 H18 + A13 · EP02 H16 · EP03 H02 · EP04 H04 · EP05 H24 + H06 · EP06 H23 · EP07 H08 + H26 · EP08 H25.
**Zmiana:** EP08 nie domyka już głównej sprawy. Irena mówi, że chce 15 stycznia, ale czynność zostaje
odłożona, a Sowa dzwoni z „nowym rozwiązaniem”. Pełne rozstrzygnięcie przechodzi do EP40.
Sowę dopisujemy w EP01–EP08 jako głos w telefonie i nazwisko w mailach (EP03, EP05, EP07).

### 6.4 Odcinki 9–40 (jedno zdanie, kotwica, slot)

| EP | Slot | Kotwica | Logline |
|---|---|---|---|
| 09 | 9:00 | A17 | Niedziela rano EKW nie działa; Sowa przysyła „pilną” prośbę o projekt na poniedziałek, Helena każe czekać na źródło. |
| 10 | 16:00 | H03 | Była teściowa i była synowa w świetnej komitywie podpisują darowiznę; Basia nie wierzy, Helena się uśmiecha. |
| 11 | 9:00 | H07 | Kupujący czekają od 16:00 do 16:40 na sprzedającego w innej sprawie; protokół niestawiennictwa, a Sowa sugeruje Irenie, że tak skończy się jej sprawa. |
| 12 | 16:00 | R14 | Helena rozmawia z testatorem bez rodziny w pokoju; Kuba uczy się, dlaczego drzwi są zamknięte. |
| 13 | 9:00 | K15 | Odpis KW sprzed tygodnia to nie dzisiejsza KW; Marta pobiera aktualną treść w programie, Helena porównuje. |
| 14 | 16:00 | H05 | Klientka umowy dożywocia przyjeżdża rowerem przed czasem; spokojna rozmowa w poczekalni mówi więcej niż zaświadczenie. |
| 15 | 9:00 | H06 | Sowa proponuje, że „kosztami aktu się nie przejmujcie”; Helena pyta, kto naprawdę płaci i za co. |
| 16 | 16:00 | K06 | Gmina wykonuje prawo pierwokupu, którego kupujący się nie spodziewali; Teresa tłumaczy Zosi, dlaczego to nie jej wina. |
| 17 | 9:00 | H24 | Kaczmarkowie dowiadują się, że część ceny ma być zapłacona przy akcie; Robert wpada w panikę, Sowa obiecuje „pożyczkę od znajomego”. |
| 18 | 16:00 | R03 | W szpitalu notariuszka nie może ustalić wyraźnej woli chorego i nie sporządza testamentu; rodzina wychodzi wściekła. |
| 19 | 9:00 | K02 | Żądanie wpisu jest w akcie, a nie ma go we wniosku elektronicznym; Kuba łapie brak przed wysłaniem. |
| 20 | 16:00 | H22 (motyw) | **Zwrot:** Paweł pokazuje przelew rezerwacyjny i umowę z Sową: prowizja zależy od 1 grudnia. Helena rozumie, kto pchał datę. |
| 21 | 9:00 | S01 | Sowa prosi o „neutralny” zapis daty; Helena wyjaśnia, kiedy notariusz musi odmówić. |
| 22 | 16:00 | A10 | Awaria systemów centralnych w dniu dwóch czynności; kancelaria przekłada terminy, Basia dzwoni do każdego klienta. |
| 23 | 9:00 | H21 (motyw) | Sowa proponuje Irenie zapłatę „na chodniku przed kancelarią, żeby było szybciej”; Irena opowiada to Helenie. |
| 24 | 16:00 | R17 | Czynność z osobą niesłyszącą: tłumacz, pisemna komunikacja i cierpliwość; Kuba pierwszy raz widzi art. 87 w praktyce. |
| 25 | 9:00 | H20 (motyw) | W projekcie od Sowy numery budynku i lokalu są zamienione; Helena odkrywa, że to nie literówka, tylko stary szablon biura. |
| 26 | 16:00 | H28 | Teresa jedzie piąty raz w miesiącu do chorej klientki; Zosia zostaje sama z telefonem i kolejką. |
| 27 | 9:00 | H23 (wariant) | Sowa ma „gotówkę od inwestora” na rezerwację; sprzedająca żąda sprawdzenia banknotów, Helena nie przyspiesza. |
| 28 | 16:00 | R16 | Projekt testamentu przygotowany wcześniej: klient potwierdza każde zdanie, Helena czyta powoli. |
| 29 | 9:00 | H04 (echo) | W KW mieszkania na parterze, które zarezerwował Paweł, pojawia się wzmianka; Sowa o niej wiedział. |
| 30 | 16:00 | A18 | Obowiązek raportowania do GIIF przy transakcji z gotówką; Marta pokazuje, co program przygotowuje, a co zostaje notariuszowi. |
| 31 | 9:00 | K13 | Sowa grozi zażaleniem na odmowę czynności; Helena spokojnie wyjaśnia, że to prawo stron i droga kontroli. |
| 32 | 16:00 | R08 | Godzinne zawieranie dożywocia poprzedzone rozmową z klientką; Basia mierzy czas, Helena nie. |
| 33 | 9:00 | K15 (dołek) | **Dołek:** wtorek, 11:30, czynność odłożona; Kaczmarkowie tracą termin najmu, Robert obwinia kancelarię. |
| 34 | 16:00 | H26 | Helena na wyjeździe bez drukarki; projekt na telefonie (tylko jeśli dostęp mobilny przeszedł test). |
| 35 | 9:00 | H01 | Para przed ślubem kłóci się o rozdzielność; Helena odmawia sporządzenia aktu w atmosferze nacisku, Irena to widzi w poczekalni. |
| 36 | 16:00 | K18 | Brak wymaganego zaświadczenia z urzędu skarbowego; odmowa i nowy termin, bez skrótów. |
| 37 | 9:00 | S14 | Kaczmarkowie przedłużają najem; Robert przeprasza. Sowa traci argument „nie ma czasu”. |
| 38 | 16:00 | H13 | Lekki oddech: Zosia namawia Kubę na warsztaty samorządu notarialnego dla młodzieży; wspólny śmiech. |
| 39 | 9:00 | H25 | Sowa przychodzi osobiście z „ostatnią propozycją”; Helena odmawia i wyjaśnia granice roli notariusza. Paweł staje po stronie matki. |
| 40 | 16:00 | H07 (odwrócony) | **Finał:** Irena przychodzi sama, przed czasem; akt z wydaniem 15 stycznia, Paweł przeprasza, Helena mówi „A komputerka ktoś nakarmił?”. Ostatni kadr: zawiadomienie o wizytacji. |

Uwagi: wiersze oznaczone „motyw” używają mechanizmu z twierdzenia strony (stopień B), nie przypisują
faktu. Kotwice z serii S, R, K wymagają kart sprawy przed produkcją, jak H23.

---

## 7. Sezony 2 i 3 (zarysy)

### 7.1 Sezon 2: „Kto widział akta?”
- **Rama:** zwykła, zgodna z prawem wizytacja kancelarii Heleny (szczegóły: `sezon-1/07`).
- **Główna sprawa:** próba przejęcia mieszkania starszej właścicielki na fałszywe pełnomocnictwo.
- **Antagonista:** Krystian Lis, organizator „pełnomocnictw” i podstawionych osób (postać fikcyjna;
  mechanizmy z P01, P02, K20, K21). Notariusz udaremnia; przestępstwa nie wykrywa AI.
- Loglines (przykładowe 10 z 40):
  1. P01: kobieta ucharakteryzowana na 85-letnią właścicielkę; Marta porównuje zdjęcie w dowodzie.
  2. Wizytacja zapowiedziana; Helena porządkuje dziennik dostępu, nie ukrywa niczego.
  3. P02: zatrzymanie w kancelarii przy próbie sprzedaży cudzego mieszkania na fałszywy dowód.
  4. K20: pełnomocnictwo z podrobioną pieczęcią innej kancelarii; weryfikacja autentyczności.
  5. P03: nieudana próba przekupienia notariusza, by poświadczył stawiennictwo testatora.
  6. Kuba i Zosia razem; Zosia pyta, czy może zobaczyć akta „dla nauki”; Kuba odmawia.
  7. S05: sąd żąda odpisu aktu; tajemnica i jej granice.
  8. Lis podsuwa „pełnomocnika” z prawdziwym dowodem; Helena pyta o rzeczy, których nie ma w papierach.
  9. H19: działka pominięta w akcie z 1973 r. wraca w sprawie spadkowej.
  10. Finał: wizytacja kończy się dobrze; Lis zatrzymany; zapowiedź sezonu 3.

### 7.2 Sezon 3: „Ostatnia wola”
- **Główna sprawa:** spór o testament dawnej klientki Teresy; rodzina twierdzi, że testatorka nie
  rozumiała czynności.
- **Antagonista:** Wiktor Zając, spadkobierca, który pozywa kancelarię Teresy o odszkodowanie
  (mechanizmy K14, K16, R05, R12, R13, R20). Sąd ostatecznie potwierdza staranność notariusza.
- Loglines (przykładowe 10 z 40):
  1. Pozew o odszkodowanie trafia do Teresy w piątek po 15:00.
  2. R05: Teresa odtwarza rozmowę weryfikującą wolę sprzed trzech lat.
  3. Zosia decyduje, czy zostać u cioci, czy przejść do kancelarii pod Siódemką.
  4. R02: testament z odciskiem palca po udarze; świadek z kancelarii.
  5. R13: granica między oceną notariusza a opinią psychiatry.
  6. Helena zostaje poproszona o pomoc i mówi, czego nie może zrobić.
  7. R12: zeznanie notariusza jako świadka; ile pamięta się po latach (H28).
  8. Zając proponuje ugodę „bez rozgłosu”; Teresa odmawia.
  9. S14: testament bez daty i spór o zdolność testowania.
  10. Finał: sąd oddala powództwo; Teresa i Zosia otwierają drugi pokój; zapowiedź sezonu 4.

---

## 8. Produkcja i koszty

### 8.1 Tor (bez fal, bez HeyGen)
1. **Scenariusz → `odcinek.json`** (`docs/kampania-komputerku/narzedzia/odcinek_json.py`, reguły zero
   tekstu). Kotwica i lista kontrolna wpisane w nagłówku.
2. **Głosy:** ElevenLabs, stałe głosy „NotarAI Komputerku v2”, model `eleven_v4` (zastępczo `eleven_v3`),
   Text to Dialogue dla całej sceny. Koszt ok. 0,1 USD na odcinek.
3. **Klatki:** z plansz kamer K1–K9, KT1–KT3, EXT i kart postaci. Ruch kamery bez modelu
   (`klatki.mjs ruch`, 0 USD). Nowe klatki tylko otwartym modelem edycji obrazu na Salad
   (**do sprawdzenia**: licencja komercyjna i jakość, zanim zastąpi klatki z biblioteki).
4. **Wideo:** `finyou/services/ai-clip`: LTX-2.5 dla ujęć niemych (2–3 s, dwie klatki), InfiniteTalk dla
   każdej mowy (kadr postaci + nagranie). **Jedna paczka GPU dziennie na oba odcinki** (rozruch ok. 5 min
   płacimy raz). RTX 5090 w Salad: 0,60 USD/h (priorytet `high`) albo 0,25 USD/h (`batch`, przerywalny).
5. **Dokumenty i ekrany:** `dokumenty.py` (0 USD) i nagrania prawdziwej aplikacji na koncie demo
   (Playwright, 0 USD). Funkcja sprawdzona tego dnia, inaczej scena bez ekranu.
6. **Montaż:** w CI (GitHub Actions), napisy z czasów kwestii, podkład pokoju, znaczek „AI”, plansza
   końcowa; wersje 9:16 i 16:9.
7. **Bramka:** lista 4.5 + akceptacja konsultanta (4.6).

### 8.2 Koszt docelowy
Ok. **0,5–1,5 USD za odcinek** (GPU + głosy), czyli ok. 2–6 zł, przy założeniu biblioteki klatek i jednej
paczki GPU na dzień. Mierzymy „USD za zaakceptowaną sekundę” (METODYKA ai-clip). Największe ryzyko kosztowe
to zły węzeł Salad; skrypt wymienia węzeł sam.

### 8.3 Bufor
Zawsze **co najmniej 4 gotowe odcinki** (2 dni) przed publikacją. Gdy render zawiedzie, wychodzi odcinek
z bufora, a zaległy idzie do kolejnej paczki. Awaryjny format: „odcinek dokumentowy” (warstwy czytelne,
głosy, jedno ujęcie mówione) za ok. 0,2 USD.

---

## 9. Publikacja i pomiar

- **09:00 i 16:00, codziennie** na notarai.pl, podstrona serialu z listą odcinków; publikacja przez
  repozytorium (workflow `strona.yml` po scaleniu do `master`). Social: po założeniu i podłączeniu kont
  NotarAI (YouTube, Facebook, Instagram, LinkedIn); LinkedIn dostaje 30–40 s cięcie informacyjne.
- **Tytuł** krótki, z napięciem, bez clickbaitu; informacja w opisie. **Pytanie pod odcinkiem** o ocenę
  postaci albo decyzji, nigdy o zgadywanie.
- **Mail tygodniowy** (poniedziałek): temat konkretny („Odcinek 12: klientka prosi o rozmowę bez syna, 75 s”).
- **Pomiar** (PostHog na notarai.pl za zgodą na cookies, linki UTM): odsetek widzów po 3 s i 10 s,
  obejrzenie do końca, powrót na następny odcinek, komentarze z oceną postaci, wejścia na demo.
  Raport po każdym tygodniu; zmiany formatu najwcześniej po 7 dniach danych.

---

## 10. Tablica statusu

| Element | Status |
|---|---|
| Postacie, kancelaria, oś Ireny, zakazy kanonu | **kanon** |
| Format: 2 odcinki dziennie, sezon 40 odcinków, antagonista sezonu | **kanon** (decyzja 23.11.2026; długość sezonu: propozycja Claude, przyjęta w V6) |
| Adrian Sowa jako antagonista S1 | **kanon V6** (do wpisania w EP01–EP08 przy przeglądzie) |
| EP01–EP08 | **scenariusze istnieją**, do poprawek: otwarcia (EP01, EP05, EP06, EP07), punkt widzenia Heleny, Sowa w tle, EP08 bez domknięcia |
| EP06 na H23 | **kanon**, karta sprawy gotowa, sceny E06S04–S05 do przepisania |
| EP09–EP40 | **propozycja** (loglines); każda kotwica wymaga karty sprawy |
| Sezony 2 i 3 | **zarys** |
| Kancelaria Teresy KT1–KT3, EXT08 | **do wygenerowania raz** |
| Tor produkcji Salad dla serialu | **narzędzia istnieją** (ai-clip, montaż); paczka dzienna i otwarty model edycji klatek **do sprawdzenia** |
| Podstrona serialu na notarai.pl, pomiar | **do zbudowania** |
| Konta social NotarAI | **czeka na właściciela** |
