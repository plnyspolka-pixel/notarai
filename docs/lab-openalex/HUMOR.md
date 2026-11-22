# Co śmieszy i jak to zrobić — stan wiedzy, 22.11.2026

Humor, dowcip i komizm: dlaczego coś jest śmieszne, jak to podać, kiedy
humor pomaga wiarygodności i sprzedaży, a kiedy szkodzi, i jak zmierzyć,
który żart jest lepszy. Uzupełnia [NARRACJA-SERIALE.md](NARRACJA-SERIALE.md)
i [OTWARCIA.md](OTWARCIA.md). Recepta dla „Komputerku…”:
[`marketing/komputerku/sezon-1/11_HUMOR_Z_BADAN.md`](../../marketing/komputerku/sezon-1/11_HUMOR_Z_BADAN.md).

Źródła: 225 pozycji w czterech rejestrach, 215 różnych prac z OpenAlex.

| Rejestr | Prefiks | Prac | Zakres |
|---|---|---|---|
| [`zrodla/humor-mechanizmy.jsonl`](zrodla/humor-mechanizmy.jsonl) | HM | 55 | niespójność, łagodne naruszenie i dystans, wyższość i ulga, śmiech jako sygnał, mózg, różnice indywidualne, co czyni żart śmieszniejszym |
| [`zrodla/humor-ekran.jsonl`](zrodla/humor-ekran.jsonl) | HE | 55 | forma sitcomu, powracający żart, wyczucie czasu, postacie komiczne, widownia komedii, komizm w dramacie, krótkie formy online |
| [`zrodla/humor-perswazja.jsonl`](zrodla/humor-perswazja.jsonl) | HP | 59 | humor w reklamie, status i zaufanie, humor w pracy, prawnicy, B2B i technologia, nauczanie, kiedy szkodzi |
| [`zrodla/humor-jezyk.jsonl`](zrodla/humor-jezyk.jsonl) | HJ | 56 | teorie językowe, śmieszne słowa, gra słów i ironia, humor polski, pomiar śmieszności, humor komputerowy i AI, głos i prozodia |

Pewność jak w [STAN-WIEDZY.md](STAN-WIEDZY.md). Liczby „według autorów”.

**Trzy zastrzeżenia:**

1. **Nie ma badań o humorze notariuszy** ani o tym, co śmieszy polską
   widownię zawodową. Najbliżej są sędziowie i prokuratorzy w Szwecji
   (HP031, bez streszczenia), lekarze (HP034) i studenci prawa (HP032).
2. **Nie ma polskich ocen śmieszności** słów ani żartów, ani polskiego
   testu żartów pisanych przez modele językowe.
3. **Rzemiosło komedii ekranowej jest słabo zmierzone.** Nie znaleźliśmy
   badań gęstości żartów, reguły trzech, nawiązań do wcześniejszych żartów
   (callbacków) ani eskalacji powracającego żartu. 12 z 55 prac o komedii na
   ekranie to eseje.

---

## Odpowiedź w jednym akapicie

Śmieszy coś, co **jednocześnie** wygląda na naruszenie normy i jest
nieszkodliwe (HM009, HM010, HM012). Samo zaskoczenie i sama wyższość nie
odróżniają śmiesznego od nieśmiesznego (HM012). Drobna wpadka śmieszy
bardziej, gdy dotyczy nas i jest blisko; nieszczęście tylko wtedy, gdy jest
daleko w czasie lub przestrzeni (HM011). Im szybciej odbiorca załapie żart,
tym jest śmieszniejszy (HM008). Lubimy, gdy obrywa ktoś niesympatyczny,
i nie lubimy, gdy obrywa ktoś, kogo lubimy (HM019). Żart jest śmieszniejszy,
gdy słowa puenty widz słyszał kilka minut wcześniej, a mniej śmieszny, gdy
usłyszał je tuż przed puentą (HM054 = HE010 = HJ020). Puentę mówi się niżej
i wolniej, a nie głośniej (HM051). Pauza przed puentą nie ma znaczenia dla
słuchaczy (HE017).

---

## A. Dlaczego coś śmieszy — **mocne**

### A1. Naruszenie, które nie szkodzi
- Pięć eksperymentów: łagodne naruszenia norm wywołują śmiech obok
  zniesmaczenia. Naruszenie staje się niegroźne, gdy działa inna norma, gdy
  odbiorcy mało zależy na łamanej normie albo gdy jest dystans (HM009).
- Niespójność ma co najmniej cztery różne definicje (zaskoczenie,
  zestawienie, nietypowość, naruszenie) i sama nie odróżnia humoru od jego
  braku (HM010). Przegląd ponad 20 teorii: działa jednoczesność, naruszenie
  i ocena „to nic groźnego”; nie działają zaskoczenie i wyższość (HM012).
- **Dystans:** wpadki śmieszą z bliska, tragedie z daleka (HM011, pięć
  badań). Efekt nie powtórzył się w Chinach dla dystansu społecznego (HM014).

### A2. Kto obrywa
- Teoria nastawienia: radość z żartu rośnie, gdy wyśmiewany jest ktoś
  nielubiany, a maleje, gdy ktoś lubiany (HM019).
- Marketing humorystyczny szkodzi marce, gdy wyśmiewa część ludzi, a nie
  ludzi w ogóle, i gdy reklama mocno zagraża odbiorcy (HP053).

### A3. Ulga
Strach, który okazuje się niepotrzebny, podnosi ocenę śmieszności (HM020,
1968: studenci mieli pobrać krew szczurowi, który okazał się zabawką).

### A4. Szybkość zrozumienia — **średnie**
Im szybciej rozpoznany żart, tym śmieszniejszy; nie potwierdzono odwróconego
U, że „trzeba się trochę napracować” (HM008, dorośli). U dzieci odwrócone U
wystąpiło (HM005).

### A5. Wiek odbiorców — **mocne**, ważne dla nas
- Starsi gorzej rozumieją żarty, co wiąże się z pamięcią roboczą, ale gdy
  zrozumieją, cieszą się nimi tak samo (HM038, HM039).
- Z wiekiem rośnie upodobanie do humoru, który ma logiczne rozwiązanie,
  a maleje do absurdu (HE030, 4 292 osoby).
- Starsi nie uważali za śmieszne scenek z gafami towarzyskimi, młodsi tak
  (HE031 = HP058). Starsi źle znoszą humor agresywny i żarty o starości
  (HP059).

## B. Jak podać żart

### B1. Przygotowanie i powtórka — **średnie**, cztery eksperymenty jednej pracy
- Słowa puenty pokazane 1–15 min wcześniej podnoszą śmieszność; pokazane tuż
  przed żartem ją obniżają. Pokazanie początku żartu nic nie zmienia (HM054).
  To jedyny eksperyment, który bezpośrednio wspiera powracający żart.
- Powtarzany ten sam materiał traci szybciej w grupie niż w pojedynkę
  (HE013, 1979, mała próba).
- Powiedzonka działają jak przysłowia: skrót do postaci i wspólnej wiedzy,
  przyjemność z rozpoznania (HE011, esej). Sama powtarzalność może być
  komiczna (HE012, esej).

### B2. Głos i wyczucie czasu — **mocne co do kierunku**
- Puenta: niższy ton, wolniejsze tempo, nie głośniej, bez istotnej pauzy
  przed nią, często z uśmiechem w głosie (HM051 = HE016 = HJ012; HM049
  na 20 wykonaniach).
- Komicy wydłużają pauzę przed puentą o ok. 157 ms, ale zmiana długości tej
  pauzy nie zmieniała ocen słuchaczy (HE017). Praca twierdząca odwrotnie
  pochodzi ze słabego czasopisma i nie ma testu słuchaczy (HE018).
- Robot-komik, który czekał na reakcję publiczności, był wyraźnie śmieszniejszy
  (HE050, 22 występy). Liczy się czas po puencie, nie przed.
- Uśmiech w głosie słuchacz odbiera mięśniami twarzy, nawet nieświadomie
  (HJ048). Sarkazm z samej intonacji rozpoznaje się tylko w ojczystym języku
  (HJ025).

### B3. Twarz, reakcja, montaż — **średnie**
- Neutralna twarz po ujęciu kontekstowym jest odczytywana zgodnie
  z kontekstem (HE023, efekt Kuleszowa, N=36) i z muzyką (HE045, N=30).
  Jedna praca znalazła efekt tylko dla strachu (HE046).
- U postaci animowanej bardziej ekspresyjny głos poprawiał rozpoznanie emocji,
  a przesadzona mimika obniżała naturalność (HE047).
- W filmach Hollywood rośnie udział „zagadkowych” ujęć reakcji: postać milczy,
  wyraz twarzy lekko negatywny, na końcu sceny (HE022).
- Pióro w ustach nie robi żartów śmieszniejszymi: 17 laboratoriów, różnica
  0,03 wobec 0,82 w oryginale (HM047).

### B4. Śmiech innych
- Śmiech pojawia się głównie w rozmowie, w ponad 99% na końcu frazy, często
  po zdaniach wcale nie śmiesznych (HM028, 1 200 epizodów).
- Z kimś śmiejemy się częściej i dłużej niż sami (HM052, N=162; HM029).
- Śmiech z taśmy zwiększa widoczną wesołość, ale nie ocenę żartu (HM032,
  HM053); śmiech grupy, z którą się nie utożsamiamy, działa przeciwnie
  (HM048, bez streszczenia).
- Ludzie w 21 kulturach odróżniają śmiech prawdziwy od udawanego w 56–69%
  (HM031), a śmiech przyjaciół od śmiechu nieznajomych w 53–67% (HM030).

### B5. Słowa — **średnie**
- Śmieszniejsze są słowa rzadsze i o nieprawdopodobnym układzie liter
  i dźwięków (HJ006, na normach dla 4 997 słów angielskich, HJ005).
- Rym i metrum podnoszą śmieszność i ułatwiają zapamiętanie (HJ021).
- Zdrobnienia wyrażają czułość albo pogardę; zakotwiczone są w bliskości
  (HJ016, 19 języków). Polskie zdrobnienia użyte ironicznie odbierano
  przeważnie jako aroganckie (HJ015, tylko 12 osób). Polskie zdrobnienie
  najczęściej ma przyrostek -k- (-ek, -ka), a przy rzeczownikach o zwierzętach
  wiąże się z młodością (HJ017).
- Ironia łagodzi krytykę: ironiczna przygana brzmi mniej ostro niż dosłowna,
  a ironiczna pochwała mniej entuzjastycznie (HJ022).
- W mailu ludzie przeceniają, jak dobrze przekazują sarkazm i żart (HJ027).

## C. Humor a wiarygodność i sprzedaż

### C1. Status i zaufanie — **mocne**
- Udany żart podnosi status przez postrzeganą pewność siebie i kompetencję;
  nieudany albo niestosowny daje wrażenie pewności siebie, ale niskiej
  kompetencji (HP014, osiem eksperymentów).
- **Płeć:** w eksperymencie (N=216) humor podnosił status mężczyzn, a obniżał
  status kobiet (HP015). Jedna praca, ale dotyczy wprost naszej obsady.
- Lekarze rodzinni bez skarg o błąd w sztuce częściej się śmiali i żartowali
  z pacjentami (HP034). U chirurgów tej różnicy nie było.
- Metaanaliza humoru w pracy (k=49, N=8 532): lepsze wyniki, spójność zespołu,
  mniej wypalenia; humor przełożonych wiąże się z lepszymi wynikami
  podwładnych (HP021). Humor na zebraniach przewidywał wyniki zespołu także
  po dwóch latach, ale tylko przy niskiej niepewności zatrudnienia (HP024).

### C2. Humor w reklamie — **mocne**
- Humor odciąga uwagę od marki i pogarsza pamięć jej nazwy, a poprawia pamięć
  samej reklamy (HP008, HP051).
- Najlepiej zapamiętywany jest humor mocny i związany z przekazem (HP010).
- Humor pomaga marce lubianej, a szkodzi marce ocenianej źle (HP007).
- Przy słabych argumentach humor poprawia postawę, przy mocnych ją obniża
  (HP055).
- Reklama działa tylko wtedy, gdy rzeczywiście śmieszy; nieudany humor jest
  ryzykiem (HP006). Liczy się też, ile negatywnych emocji wywołuje, bardziej
  niż jak bardzo śmieszy (HP054).
- Sarkazm i ironia w przekazie zwiększają kontrargumentowanie (HP056).

### C3. Humor maszyny
- Humor i głos sprawiają, że agent AI wydaje się bardziej ludzki i budzi
  zaufanie emocjonalne; zaufanie do kompetencji bierze się z postrzeganej
  inteligencji, nie z humoru (HP042).
- Dowcipny robot był bardziej lubiany, ale też oceniany jako „niepoważny”
  (HP043, N=91). Żartobliwy chatbot osłabiał poczucie kontroli (HP044).

### C4. Humor w nauczaniu — **średnie**
- Zajęcia z humorem związanym z tematem dały lepsze wyniki egzaminu (HP046,
  dwa eksperymenty semestralne). Humorystyczne zdania są lepiej zapamiętywane
  (HM035 = HP049; HP050).
- Teoria, która miała to wyjaśniać, nie wyjaśniła (HP048).

## D. Komedia na ekranie

- Sitcom opiera się na powtarzalnym założeniu i odcinkach dzielonych na
  segmenty (HE002, książka). Mockumentary z niezręcznością (The Office) to
  osobny tryb produkcji (HE003, HE026).
- Humor agresywny wystąpił w 87,9% seriali lubianych przez 10–14-latków,
  humor pomagający radzić sobie z problemami w 23,4% (HE008).
- Humor w dramacie medycznym („Dr House”): ironia, przekomarzanie,
  nieuprzejmość, dziwactwa postaci (HE041, analiza tekstu).
- Żarty bohatera w scenie przemocy zwiększały niepokój kobiet w trakcie
  filmu (HE039). Komiczny kontekst bagatelizuje przemoc (HE040).
- TikTok: odgrywanie stałych postaci wiązało się z ok. 21% więcej polubień
  i 42–48% więcej udostępnień (HE051, praca dyplomowa, 741 filmów).
  Najlepiej szedł humor życzliwy o codziennych sytuacjach (HE052, 914 postów).

## E. Jak mierzyć, który żart jest lepszy — **średnie**

- **Porównanie parami działa.** Klasyfikator wybierał zabawniejszy z dwóch
  podpisów w 69% przypadków, gdy oba opierały się na tym samym żarcie (HJ037).
  Zbiór New Yorkera ma ponad 250 mln ocen (HJ039).
- **Oceny w skali są porządkowe.** Średnia z Likerta zniekształca odległości;
  dokładniejsze są modele dla danych porządkowych (HJ055).
- **Oceniający różnią się bardzo.** Modele uwzględniające osobiste
  skrzywienie oceniającego radykalnie wygrywały z ogólnymi (HJ018, Wrocław).
- **Model językowy nie zastąpi ludzi jako sędzia.** Sędzia-LLM ułożył modele
  idealnie według rozmiaru, a ludzie nie widzieli różnicy (HJ045). Zgodność
  LLM z ekspertami κ = 0,28, ludzi między sobą 0,27, ale LLM między sobą 0,63,
  czyli modele mylą się tak samo (HJ052).
- **Model językowy jako autor:** ponad 90% z 1 008 żartów ChatGPT to te same
  25 żartów (HJ043), a w ślepych ocenach żarty ChatGPT 3.5 wypadły równie
  dobrze lub lepiej niż żarty laików i autorów „The Onion” (HJ044). Modele
  wyraźnie przegrywają z ludźmi w rozumieniu dowcipu rysunkowego (HJ040).
- Twarz jest słabym miernikiem: związek uśmiechu z oceną jest silniejszy
  w obrębie jednej osoby niż między osobami, a pogodni uśmiechają się nawet
  przy słabych żartach (HJ050).

## F. Popularne przekonania, których dane nie potwierdzają

- „Pauza przed puentą.” Brak w wykonaniach (HM049, HM051), bez znaczenia dla
  słuchaczy (HE017).
- „Puentę mów głośniej.” Niższy ton i wolniej (HM051).
- „Najważniejsze jest zaskoczenie.” Nie odróżnia śmiesznego (HM012).
- „Niech się trochę napracują.” Szybciej zrozumiane = śmieszniejsze (HM008).
- „Uśmiechnij się, to będzie śmieszniej.” Nie powtórzyło się w 17
  laboratoriach (HM047).
- „Śmiech z taśmy sprawia, że żart jest lepszy.” Zwiększa wesołość, nie
  ocenę (HM032, HM053).
- „Zdradzona puenta zabija żart.” Zależy od czasu: kilka minut wcześniej
  pomaga (HM054).
- „Humor zawsze pomaga reklamie.” Pomaga reklamie, często szkodzi pamięci
  marki (HP008, HP051), szkodzi marce źle ocenianej (HP007).

## Weryfikacja

Identyfikatory sprawdzono przez konektor OpenAlex; wyniki
w `weryfikacja/humor-*.jsonl`. Wszystkie 215 prac istnieją, żadna nie jest
wycofana, 225 z 225 pozycji ma werdykt `potwierdzona`. Zastrzeżenie jak
w poprzednich syntezach: pliki weryfikacji powstały z odpowiedzi konektora
przepisanych przez agentów.

Bez streszczenia w OpenAlex (opis z tytułu i słów kluczowych, bez wyniku):
m.in. HP001 i HP002 (metaanalizy Eisenda), HP037 (humor w reklamie B2B),
HP040, HP031, HM027 (Provine 1992), HM040, HM045, HM048, HJ003, HJ007–HJ010,
HJ029. Słabe źródła: HE018, HE025, HE043, HM022, HP029, HP030; prace
dyplomowe HE029, HE051; małe próby HJ015 (12 osób), HE013, HE028.

## Prace w kilku rejestrach

HE010 = HJ020 = HM054; HE016 = HJ012 = HM051; HE015 = HM049;
HE031 = HP058; HE033 = HM052; HJ027 = HP057; HJ033 = HM045;
HM035 = HP049.
