# Co trzyma widza przy opowieści — stan wiedzy, 22.11.2026

Książki, filmy, seriale, a przede wszystkim telenowele: co badania mówią
o tym, dlaczego ludzie czytają i oglądają do końca, wracają po następny
odcinek i zmieniają pod wpływem fabuły to, co robią. Pisane pod mikroserial
„Komputerku…” (Kancelaria pod Siódemką): pionowe odcinki 60–90 s, 8 na sezon,
widownia to notariusze i ich zespoły. Recepta produkcyjna wynikająca z tego
przeglądu: [`marketing/komputerku/sezon-1/09_RECEPTA_Z_BADAN.md`](../../marketing/komputerku/sezon-1/09_RECEPTA_Z_BADAN.md).

Źródła: 277 pozycji w pięciu rejestrach, 265 różnych prac z OpenAlex
(12 prac występuje w dwóch rejestrach, lista na końcu).

| Rejestr | Prefiks | Prac | Zakres |
|---|---|---|---|
| [`zrodla/narracja-telenowele.jsonl`](zrodla/narracja-telenowele.jsonl) | TN | 70 | forma telenoweli i opery mydlanej, widownia, więź z postaciami, przemysł, recepcja, pomiar, krótkie formy |
| [`zrodla/narracja-mikrodramy.jsonl`](zrodla/narracja-mikrodramy.jsonl) | MD | 58 | mikrodramat pionowy, zaangażowanie w krótkie wideo, marka w fabule, B2B, udostępnianie, wideo i głosy AI, kadencja |
| [`zrodla/narracja-edukacja-perswazja.jsonl`](zrodla/narracja-edukacja-perswazja.jsonl) | EE | 53 | edukacja przez rozrywkę, dowody przyczynowe, mechanizmy perswazji narracyjnej, porażki, widownia zawodowa |
| [`zrodla/narracja-film-serial.jsonl`](zrodla/narracja-film-serial.jsonl) | FS | 50 | struktura a sukces, napięcie i powrót widza, postacie, montaż, dramat zawodowy |
| [`zrodla/narracja-ksiazki.jsonl`](zrodla/narracja-ksiazki.jsonl) | KS | 46 | łuki emocjonalne, przewidywanie bestsellerów, transportacja, ciekawość, fikcja w odcinkach, konwencje |

**Pewność** jak w [STAN-WIEDZY.md](STAN-WIEDZY.md): **mocne** — kilka
niezależnych prac, w tym recenzowane, zgodny kierunek; **średnie** — jedna
dobra praca albo kilka słabszych; **słabe** — pojedyncza praca, esej albo
słabe czasopismo. Liczby zawsze „według autorów”.

**Trzy zastrzeżenia do całości:**

1. **Nie ma ani jednej pracy o mikrodramacie dla widowni zawodowej B2B.**
   Wszystko poniżej to przeniesienie z telenowel, seriali, reklam i badań
   nad lekarzami, prawnikami i policjantami. Wynik z pracy to hipoteza dla
   nas, a nie fakt o notariuszach.
2. **Efekty perswazji przez fabułę są małe.** Metaanalizy podają r = 0,06–0,23
   (EE012, EE021, EE022). Serial jest dźwignią, nie cudem.
3. **Literatura o mikrodramach jest młoda i słaba**: rośnie szybko (tabela na
   końcu), ale według kwerendy tylko ok. 10 prac ukazało się w solidnych
   czasopismach. Reszta to małe ankiety i analizy jednego tytułu.

---

## Punkty wspólne — to samo w książkach, filmach, serialach i telenowelach

1. **Liczy się ruch emocji, a nie ich poziom.** 6 174 scenariusze: najwięcej
   zarabia łuk „upadek, potem wzlot” niezależnie od gatunku i budżetu (FS001).
   30 000 filmów, seriali, powieści i zbiórek: więcej zwrotów i mocniejsze
   zwroty to większy sukces (FS002 = KS021). Ponad 4 000 filmów i eksperymenty:
   zmienność nastroju podnosi oceny (FS003). Sześć powtarzalnych łuków
   w 1 327 powieściach, niektóre częściej pobierane (KS001). → **mocne**
2. **Koniec jest jaśniejszy niż początek.** Niezależnie od gatunku zakończenie
   bywa bardziej pozytywne niż otwarcie (KS005). Widzowie telenoweli
   odrzucają śmierć bohatera i nieszczęśliwy finał (TN002). → **średnie**
3. **Zawieszenie akcji działa i nic nie kosztuje.** Dwa eksperymenty (N=202,
   N=273): zakończenie w zawieszeniu zwiększa chęć na następną część wobec
   zwycięstwa bohatera, bez straty przyjemności (FS008 = MD056; teksty, nie
   wideo). W telenoweli to „gancho”, narzędzie znane od powieści w odcinkach
   (TN001, TN004). → **mocne co do kierunku, średnie dla wideo**
4. **Napięcie wymaga lubianego bohatera, którego szanse wyglądają źle.**
   Napięcie było najwyższe przy szansach bohatera ok. 1 na 100 i znikało przy
   pewności (FS009). Rośnie, gdy widz widzi, że bohaterowi zamykają się
   kolejne drogi wyjścia (KS024). → **mocne**
5. **Ciekawość to konkretna luka w wiedzy.** Widz musi wiedzieć, czego nie
   wie (KS023). Kolejność opowiadania: chronologia daje napięcie, ukryta
   przyczyna daje ciekawość, a wynik podany na początku jest lubiany najmniej
   (KS022). Prostsza zagadka podoba się bardziej niż zawiła (KS044).
   → **mocne**
6. **Wolny początek, szybki koniec.** W 40 000 scenariuszy i 10 000 odcinków
   lepiej oceniane są historie, które na początku budują świat powoli,
   a potem przyspieszają (FS004). → **średnie** (jedna praca, duże dane)
7. **Ludzie wracają dla postaci i ich relacji bardziej niż dla intrygi.**
   250 000 tekstów fanowskich: czytelnicy wolą mniej fabuły, a więcej
   interakcji postaci niż w oryginałach (KS036). Popularność serialu
   przewiduje więź z postaciami i komentarze oceniające, bardziej niż same
   emocje (TN057). → **średnie**
8. **Podobieństwo do widza i punkt widzenia budują identyfikację.** Czyimi
   oczami opowiadasz, z tym widz się utożsamia i to zmienia postawy (KS017).
   Studenci prawa czytający o prawniku: zawód czytelnika wpływa na
   identyfikację (KS018). Metaanaliza: podobieństwo działa słabo (d ≈ 0,14),
   najmocniej w cechach takich jak zawód i miejsce (KS019). Metaanaliza 120
   badań: więź z postacią mocno wiąże się z podobieństwem i z efektami
   perswazyjnymi (FS019). → **mocne co do kierunku, efekt mały**
9. **Realizm jest warunkiem wejścia, szczególnie dla fachowców.** Naruszenie
   realizmu przerywa zaangażowanie i osłabia perswazję (EE039). Typowość
   buduje identyfikację (EE040). Kto zna temat, wciąga się mocniej, o ile
   obraz jest wierny (EE041). Policjanci cenią seriale za poprawną procedurę
   i fachowość (FS048, FS049). → **mocne**
10. **Nawyk i stały rytm.** Oglądanie telenoweli jest rytualne (TN012, TN014).
    Serie internetowe: wydanie codziennie lub częściej trzyma czytelników,
    a przerwa oznacza masowe odejście (KS032, KS033; koreańskie, mało
    cytowane). Wypuszczanie po trochu wygrywa z wypuszczeniem wszystkiego
    naraz (MD054, eksperyment terenowy). Oglądanie w odstępach daje trwalszą
    pamięć i więcej przyjemności niż maraton (FS017 = MD055). → **średnie**
11. **O sukcesie decyduje też start i dowód społeczny, nie sam tekst.** Sam
    tekst przewiduje sukces książki w 75–84% (KS006, KS011). Wysoka pozycja
    startowa wydłuża obecność na liście (KS007). Resztę robi wydawca,
    wcześniejsza sprzedaż autora i zachowanie pierwszych czytelników
    (KS008, KS010), a sygnał „inni to wybrali” zwiększa nieprzewidywalność
    wyniku (KS009, eksperyment na piosenkach). → **mocne**
12. **Rozmowa o opowieści jest częścią przyjemności.** Główne motywy
    oglądania oper mydlanych to rozrywka i użytek towarzyski, nie nauka
    (TN011, TN012, TN013, TN020). Widzowie tworzą „kulturę serialu w miejscu
    pracy” (TN029). → **mocne**

---

## A. Telenowela: dlaczego trzyma miliony przez miesiące

### A1. Forma — **mocne**
- **Matryca melodramatu plus lokalny szczegół.** „Brzydula” poszła do ok. 70
  krajów, bo łączy uniwersalną historię awansu z konkretem, w którym widz się
  rozpoznaje (TN035, TN039). Melodramat wchłania nowe tematy, umieszczając je
  w oswojonym świecie (TN005).
- **Mały świat.** Telenowela opowiada o kraju przez „mikrokosmos”, jedno
  wyobrażone miejsce (TN046). W Europie przyjęły się trzy typy: opera
  wspólnoty, dynastii i pary (TN045). Opera wspólnoty najczęściej porusza
  sprawy społeczne.
- **Zamknięta, nie wieczna.** Telenowela ma koniec, a opera mydlana go
  odwleka. Sukces potrafi zmienić jedno w drugie (TN006, TN003).
- **Zagadka na ostatnie tygodnie.** Globo od 1988 r. buduje finał pytaniem
  „kto zabił?” (TN007; praca opisuje zabieg, wyniku oglądalności w streszczeniu
  nie ma).
- **Czarny charakter jest stałym elementem** (TN010). W 201 powieściach
  antagoniści chcą dominacji, a bohaterowie współpracy, i właśnie to budzi
  emocje czytelników (KS041).

### A2. Widownia i więź — **mocne**
- Zaangażowanie rośnie z postrzeganym realizmem, uwagą i zamiarem oglądania,
  a nie z samym czasem przed ekranem (TN011, 328 widzów).
- Postacie to „znajomi”, z którymi dzieli się codzienność. Więź rośnie
  z długością emisji i codziennym kontaktem (TN028, 4 762 komentarze; TN029).
  Koniec serialu boli jak rozstanie, tym mocniej, im silniejsza więź (FS025).
- Widz bywa jednocześnie zaangażowany i ironiczny: „oglądam, ale…”
  (TN029, TN047 o „M jak miłość”). W Polsce: listy do postaci „Klanu” (TN033).
- Widzowie osądzają postacie jak „trybunał ludowy” (TN037). Komentarze
  oceniające i odnoszące fabułę do własnego życia przewidują popularność
  lepiej niż komentarze emocjonalne (TN057, TN061).

### A3. Produkcja — **mocne**
- Telenowelę pisze się w trakcie emisji i poprawia po reakcji widzów
  (TN037, TN038, TN048, TN050). To jedyna tak szeroko opisana pętla zwrotna
  w fabule telewizyjnej.
- Tania, szybka, mało dekoracji, stała obsada (TN038).
- **Lokowanie produktu jest w tym gatunku rodzime, ale ma cenę.** W Brazylii
  stało się siłą wpływającą na wybory fabularne (TN034). Gdy marketing bierze
  górę, telenoweli „się nie ogląda, tylko kupuje” (TN036, esej). Webnowele
  od początku były miejscem dla marek i źródłem danych o widzach (TN064).

### A4. Era platform — **średnie**
- Oglądanie na żądanie rozprasza się w czasie: szczyt przypada po południu
  w dniu po emisji, a w poniedziałki jest wyższy niż w weekend (TN058, jedna
  telenowela).
- Widz ogląda we fragmentach, na telefonie i telewizorze (TN069).
- Telenowela pionowa zachowuje matrycę melodramatu, a ściska czas (TN065,
  TN068). Globo powtarza odcinki w wielu oknach, żeby utrzymać widownię (TN068).

### A5. Czego w telenowelach nie zbadano
Nie znaleźliśmy badania, które zestawia zdarzenia fabuły z oglądalnością
odcinek po odcinku, ani analizy obliczeniowej scenariuszy telenowel. Nic
o skrótach „w poprzednim odcinku”. Nic o tureckich serialach w Polsce.

---

## B. Kiedy fabuła zmienia to, co ludzie robią

### B1. Działa, i to mierzalnie — **mocne**
- Brazylia: telenowele Globo a dzietność i rozwody (EE001, EE002).
- Nigeria, RCT: po „MTV Shuga” dwa razy więcej testów na HIV po 8 miesiącach.
  Efekt silniejszy u widzów bardziej zaangażowanych w fabułę (EE005).
- Rwanda, eksperyment terenowy: radiowa opera zmieniła postrzegane normy
  i zachowania, ale prawie nie zmieniła osobistych przekonań (EE006).
- RPA, „Scandal!”: po dwumiesięcznym wątku o długach widzowie prawie dwa razy
  częściej pożyczali w formalnych źródłach. **Infolinia polecana przez postać
  spoza głównej obsady nie chwyciła** (EE007; dokument roboczy Banku
  Światowego).

### B2. Mechanizm — **mocne**
- Nośnikiem jest postać, na której widzowi zależy (EE007, EE024: r = 0,27).
- Fabuła obniża opór: mniej wyczuwalnej intencji perswazyjnej i sympatia do
  postaci zmniejszają reaktancję (EE026). Metaanaliza: d = −0,21 (EE027).
- **Postać przejściowa**, czyli wątpiąca, która się zmienia: podobieństwo
  widza do niej podnosi identyfikację, a ta wiąże się z lepszą postawą; trzy
  kraje, N ≈ 290 każdy (EE020). Tło teoretyczne, modelowanie społeczne
  i metoda Sabido: EE016, EE017 (rozdziały bez wyników liczbowych).
- Fabuła buduje zamiar, a liczby budują przekonania (EE030). Efekt fabuły
  utrzymuje się w czasie, a „fakty” z fikcji po dwóch tygodniach działają
  nawet mocniej (EE028, EE029).
- Wideo i dźwięk działają, druk nie (EE022).

### B3. Kiedy zawodzi — **mocne**
- **Żart z ryzyka.** Ten sam wątek z humorem wokół konsekwencji: widzowie
  zbagatelizowali skutki i deklarowali więcej ryzykownych zachowań (EE034).
  Humor ogólnie: r = 0,13, lepiej gdy związany z tematem, o sile umiarkowanej
  (odwrócone U), bez efektu opóźnionego (EE035, 89 badań).
- **Ujawniona sprzedaż.** Oznaczenie treści sponsorowanej obniża postawę
  wobec marki i wiarygodność (EE036, 57 zbiorów danych).
- **Nierealność** (EE039) i **wyczuwalna intencja przekonywania**: fabuła
  tłumi kontrargumenty wtedy, gdy przekaz jest ukryty w akcji (EE015, EE026).
- **Wynik zerowy lub ujemny też się zdarza**: edutainment o przedsiębiorczości
  w Tanzanii pogorszył wyniki szkolne (EE033); wiedza zanika bez powtórek
  (EE011).

### B4. Widownia zawodowa — **średnie**
- Lokalni liderzy opinii: mediana +12 punktów procentowych zgodności
  z zalecaną praktyką (EE045, Cochrane, 18 RCT, rozrzut od −15 do +72).
- Przyjęcie innowacji przewidują: zgodność z dotychczasową pracą, względna
  korzyść i złożoność (EE046, 75 artykułów).
- Prawnicy wobec AI: trzy logiki — fachowość, dostępność, wydajność. Postawy
  są sprzeczne i zależą od roli w kancelarii (EE047, 30 wywiadów).
- Fachowcy oglądają „swoje” seriale ambiwalentnie: zarzucają zniekształcenie,
  ale serial zgodny z doświadczeniem wzmacnia tożsamość zawodową (FS049).
- Nauka na przypadkach i medycyna narracyjna: zadowolenie rośnie, dowody na
  zmianę praktyki są niejednoznaczne (EE042, EE044).

---

## C. Mikrodramat, krótkie wideo i marka w fabule

### C1. Forma mikrodramatu — **słabe do średnich**
Branża projektuje „punkty satysfakcji” i zawieszenia wokół momentu zakupu
kolejnych odcinków, a wynik rozstrzyga dystrybucja (MD002, etnografia
produkcji). Gęste konflikty i ciągłe zwroty (MD003, MD006). Motywacja →
zanurzenie → chęć dalszego oglądania (MD004, N=774, słabe czasopismo).

### C2. Pierwsze sekundy i utrzymanie — **mocne**
- Chwyty „pod uwagę” zwiększają pomijanie, bo widz rozpoznaje reklamę (MD012).
- Kto może pominąć, przetwarza głównie początek (MD013).
- Uwagę trzyma poziom zaskoczenia, a widza zatrzymuje tempo narastania
  radości (MD011).
- TikTok: uwaga to średnio ok. 45% długości filmu (MD016, 9,2 mln filmów).
  Liczba ujęć i złożoność obrazu mają optimum pośrodku (MD015, 2 511 filmów).
- Pion podnosi zaangażowanie, ale przewaga jest słabsza u starszych (MD014).

### C3. Marka w fabule — **mocne**
- **Związek z fabułą wygrywa z widocznością.** Najlepsza postawa wobec marki:
  mocno wpleciona w akcję, mało eksponowana (MD021, eksperyment w kinie;
  MD020). Ekspozycja nachalna psuje postawę u fanów programu (MD022)
  i u widzów świadomych perswazji (MD024).
- Wczesna, długa, stała obecność marki obniża udostępnianie (MD040).
- Oznaczenie lokowania poprawia pamięć, a pogarsza postawę (MD025 = EE037).

### C4. B2B — **średnie, sprzeczne**
Na Instagramie firm B2B informacja angażuje bardziej niż emocja (MD035,
5 362 posty). Nabywcy opisują decyzję jako użytkową, emocja tylko budzi
zainteresowanie (MD038). Z drugiej strony reklama emocjonalna buduje
zaangażowanie i działa na kadrę zarządzającą (MD037). Na LinkedIn lepiej
udostępniają się treści informacyjne, gdzie indziej emocjonalne (MD040).

### C5. Udostępnianie — **mocne**
Niesie pobudzenie, nie znak emocji: zachwyt, złość, niepokój, rozbawienie
(MD039, MD041). Udostępnianie reklam wideo ma szczyt przy 1,2–1,7 min (MD040).

### C6. Wideo i głosy AI — **średnie, sprzeczne**
- Ludzki głos: więcej przyjemności, uwagi i pamięci niż syntetyczny (MD049).
  Starsza praca: syntetyczny mniej lubiany, ale równie przekonujący (MD050).
- Niezgodność realizmu twarzy i głosu daje efekt niesamowitości (MD052).
- Oznaczenie „wygenerowane przez AI” obniża zaufanie (MD045, N=304; MD046),
  ale jest też wynik odwrotny, gdy oznaczenie pokazuje korzyść (MD047).

---

## D. Spory w literaturze

| Temat | Jedna strona | Druga strona |
|---|---|---|
| Spojlery | nie szkodzą (FS011) | szkodzą, zwłaszcza w wideo (FS012, FS014, KS028, KS029) |
| Maraton czy odstępy | odstępy lepsze (FS017, MD054) | bez różnicy (FS016) |
| Śmiech z puszki | pomaga, r = 0,39 (FS033) | szkodzi najlepszym odcinkom (FS034, FS032) |
| Emocja w B2B | działa (MD037) | informacja lepsza (MD035, MD038) |
| Długość | 1,2–1,7 min (MD040) | średnie i długie filmy na YouTube (MD019) |
| Oznaczenie AI | obniża zaufanie (MD045, MD046) | podnosi (MD047) |
| Transportacja a opór | tłumi kontrargumenty (EE015) | wiązała się z większą ich liczbą (EE026) |
| Tempo telenoweli | wolny przepływ to istota gatunku (TN040) | kompresja działa (TN065) |

---

## Tempo literatury (prace w OpenAlex rocznie)

| Temat | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026* |
|---|---|---|---|---|---|---|---|---|
| telenowela / opera mydlana | 376 | 684 | 347 | 308 | 333 | 300 | 301 | 249 |
| mikrodramat / duanju / dramat pionowy | 62 | 46 | 39 | 41 | 46 | 86 | 161 | 312 |

\* rok niepełny. Telenowele: łącznie 10 080 prac, najwięcej z Brazylii (1 398)
i USA (810); literatura stabilna, 2020 to zapewne artefakt indeksowania.
Mikrodramat: starsze lata zawierają inne znaczenia „short drama”; realny
wzrost zaczyna się w 2024 r. Wniosek: telenowele są dobrze opisane i nic się
tam szybko nie zmienia, a mikrodramat warto dodać do radaru.

## Weryfikacja

Weryfikator `tools/lab_openalex/weryfikuj.py` nie zadziałał w tej sesji, bo
sieć kontenera blokuje `api.openalex.org`. Identyfikatory sprawdzono przez
konektor OpenAlex (`resolve_references`); wyniki w `weryfikacja/narracja-*.jsonl`.
Wynik: wszystkie 265 identyfikatorów istnieje, żadna praca nie jest wycofana,
lata i DOI zgadzają się z rejestrami. 276 z 277 pozycji ma werdykt
`potwierdzona`. KS032 ma `tytul_inny` z przyczyny technicznej: miara
podobieństwa liczy tylko litery łacińskie, a tytuł jest koreański (tytuły
w obu miejscach są takie same). Pliki weryfikacji powstały z odpowiedzi
konektora przepisanych przez agenta, a nie z surowego zrzutu API, więc po
odblokowaniu sieci warto raz puścić właściwy weryfikator.

Treść pola `finding` pochodzi ze streszczeń w OpenAlex. Pozycje, w których
streszczenie było ucięte, jednozdaniowe albo w innym języku, są w rejestrach
opisane wprost (m.in. KS026, KS027, KS032, KS033, EE007, EE019, MD054, TN007,
TN033, FS011). Przed użyciem liczby z takiej pozycji w decyzji trzeba
przeczytać pracę.

## Czego nie znaleziono

- Brewer i Lichtenstein 1982, Horton i Wohl 1956, Martín-Barbero 1987,
  Rogers „Diffusion of Innovations”: brak w OpenAlex albo brak streszczenia.
- Eksperyment Wirz i in. 2023 o zawieszeniu akcji w wideo (W4213104204): jest,
  ale bez streszczenia.
- Brak badań o: haczyku w pierwszych 3 sekundach na danych platform, napisach
  i oglądaniu bez dźwięku, skrótach poprzedniego odcinka, powiedzonkach
  i powracających żartach w marketingu, humorze w B2B, wideo na LinkedIn,
  marketingu do prawników i notariuszy, spójności postaci generowanych przez
  AI w odbiorze widzów.

## Prace w dwóch rejestrach

EE023 = KS016, EE025 = KS013, EE037 = MD025, EE052 = FS044, FS002 = KS021,
FS008 = MD056, FS010 = KS043, FS011 = KS027, FS012 = KS028, FS017 = MD055,
FS020 = KS015, KS037 = TN004.
