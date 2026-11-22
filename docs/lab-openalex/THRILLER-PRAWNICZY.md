# Thriller prawniczy — stan wiedzy, 23.11.2026

Jak działa thriller prawniczy w literaturze i na ekranie, jak budować
napięcie i zagadkę, czego wymaga widownia prawnicza i jak opowiadać na
podstawie prawdziwych spraw. Recepta dla „Komputerku…”:
[`marketing/komputerku/sezon-1/13_THRILLER_PRAWNICZY_Z_BADAN.md`](../../marketing/komputerku/sezon-1/13_THRILLER_PRAWNICZY_Z_BADAN.md).

Źródła: 169 pozycji w trzech rejestrach, 166 różnych prac z OpenAlex.

| Rejestr | Prefiks | Prac | Zakres |
|---|---|---|---|
| [`zrodla/thriller-gatunek.jsonl`](zrodla/thriller-gatunek.jsonl) | TG | 57 | thriller prawniczy, dramat sądowy, struktura kryminału, dokument jako dramat, notariusz w fikcji, odmiany narodowe, etyka, fikcja na faktach |
| [`zrodla/thriller-napiecie.jsonl`](zrodla/thriller-napiecie.jsonl) | TS | 53 | napięcie, zaskoczenie i ciekawość, zagadka i wnioskowanie, presja czasu, ocena moralna, pomiar, napięcie w odcinkach, napięcie bez przemocy |
| [`zrodla/thriller-realizm.jsonl`](zrodla/thriller-realizm.jsonl) | TR | 59 | wierność prawu, obraz prawa, edukacja prawnicza, true crime, przyjemność z kompetencji, sprawiedliwość, kraje prawa stanowionego, prawdziwe sprawy |

Pewność jak w [STAN-WIEDZY.md](STAN-WIEDZY.md). Liczby „według autorów”.

**Trzy zastrzeżenia:**

1. **Limit OpenAlex był prawie wyczerpany**: rejestry powstały z 7–9
   wyszukiwań każdy. Nie sprawdziliśmy m.in. „Columbo”, reguł uczciwej gry
   w kryminale (Van Dine, Knox), „The Good Wife”, „Suits”, „Better Call Saul”
   osobno ani ryzyka zniesławienia przy adaptacji prawdziwych spraw. Warto
   dokończyć po odnowieniu limitu.
2. **Notariusz w fikcji jest prawie nieopisany.** Cztery prace: esej
   z rosyjskiego pisma notarialnego (TG029, słabe źródło), dwie o Balzaku bez
   streszczenia (TG030, TG031) i jedna o „Urszuli Mirouët” (TG032).
3. **Polski materiał jest szczątkowy**: dwa eseje o polskim kryminale (TG035,
   TG036) i raport dydaktyczny z Warszawy o „Sędzi Annie Marii Wesołowskiej”
   (TR049). Nie ma polskich badań widowni seriali prawniczych.

---

## A. Konwencje gatunku, które powtarzają się w źródłach — **średnie** (głównie eseje)

1. **Formalna czynność jako rama napięcia.** Thriller prawniczy, pisany
   zwykle przez prawników, używa procesu jako tła budującego napięcie (TG001).
   U nas odpowiednikiem procesu jest umówiona czynność notarialna.
2. **Bohater jako czytelnik śladów.** Detektyw odtwarza ukrytą historię,
   czytając znaki; jest modelowym czytelnikiem (TG015). Notariusz zawodowo
   czyta dokumenty, więc pasuje do tej roli lepiej niż detektyw.
3. **Dokument jako silnik fabuły.** Fałszerstwa weksli, testamentów i ksiąg
   parafialnych występują w co najmniej stu powieściach wiktoriańskich z lat
   1846–1879, często na kanwie prawdziwych spraw (TG022).
4. **Samotny profesjonalista z kodeksem honorowym.** „Anatomia morderstwa”
   przenosi bohatera westernu do kancelarii (TG047).
5. **Kryminał detektywistyczny przywraca porządek**; powieść kryminalna
   z punktu widzenia sprawcy już nie (TG019). Odmiany „metafizyczne” i nordyckie
   kończą się pytaniem (TG020, TG037).
6. **Lokalność i krytyka społeczna podróżują.** Nordycki kryminał przyciąga
   za granicą krytyką państwa opiekuńczego, silnymi kobietami i konkretnym
   krajobrazem (TG038).
7. **Dylemat etyczny jako punkt kulminacyjny**, np. obrońca wie, że klient
   jest winny (TG046). Popkultura nagradza „moralny spryt”, czyli obchodzenie
   reguł w imię sprawiedliwości, wbrew oficjalnej etyce zawodu (TG045).
   Filmowi prawnicy łamią kodeks dla sprawiedliwości, co czyni ich ciekawszymi
   (TR042).
8. **Dramat sądowy kształtuje wyobrażenia o sprawiedliwości**, choć rzadko
   oddaje rzeczywistość; nawet filmy europejskie kopiują wzór amerykański
   (TG008 = TR045).

## B. Napięcie i zagadka — **mocne** (eksperymenty)

- **Zapowiedź działa silniej niż zaskoczenie.** 20–30 s wskazówek przed
  wypadkiem dawało większy stres fizjologiczny niż wersja bez ostrzeżenia,
  a większość stresu przypadała na oczekiwanie (TS022, 1968). To najbliższy
  dowód dla „bomby pod stołem” Hitchcocka. Gdy widz wiedział o możliwym złym
  wyniku, częściej „podpowiadał” postaciom (TS011). Bezpośredniego
  eksperymentu z ironią dramatyczną nie znaleźliśmy.
- **Napięcie działa nawet, gdy znamy wynik.** Przeszkoda przed znanym faktem
  spowalniała jego potwierdzenie (TS003, trzy eksperymenty). Prawdziwa sprawa
  ze znanym zakończeniem nadal może trzymać.
- **Napięcie to niepewność co do następnego kroku.** Model formalny: napięcie
  to rozrzut przekonań w następnej chwili, zaskoczenie to odległość od
  poprzedniego przekonania; daje harmonogram odsłaniania informacji (TS008).
- **Nie przerywać z zewnątrz.** Opóźnienie spoza świata opowieści (plansza,
  narrator) obniżało napięcie i zanurzenie; opóźnienie wewnątrz opowieści nie
  (TS026).
- **Przewidywanie psuje przyjemność.** Kto przewidywał wynik, cieszył się nim
  mniej, z powodu przewidywanego żalu (TS017, cztery eksperymenty).
- **Przy niskiej stawce liczy się szczyt.** W zawodach o niskiej stawce
  przyjemność szła za szczytem napięcia bardziej niż za jego sumą (TS051).
  Stawka nie musi być życiem; wystarczy niepewny wynik.
- **W gorących punktach widz nie słyszy reszty.** Podczas scen podkreślających
  możliwe złe skutki widzowie częściej przegapiali sygnały dźwiękowe (TS033).
- **Muzyka sama tworzy napięcie**, a odczucia i fizjologia często się rozjeżdżają
  (TS037).
- **Oszustwo widać dopiero po fakcie.** W 54 grupach z ukrytym sabotażystą nikt
  nie zauważył go na bieżąco, ale po informacji, że było oszustwo, wskazywano
  go trafnie (TS021). Odcinek „Lie to Me” nie poprawił trafności wykrywania
  kłamstw, tylko zwiększył podejrzliwość wobec szczerych (TS030).
- **Koniec serialu: domknięcie i dobry los bohatera** wiązały się z większą
  przyjemnością i mniejszym niepokojem (TS041, N=840, korelacja).
- **Powtórka:** przy ponownym oglądaniu napięcie spada, przyjemność nie (TS009).

## C. Realizm i widownia prawnicza — **średnie**

- **Prawnicy odrzucają zniekształcenia.** W Warszawie studenci prawa uważali
  „Sędzię Annę Marię Wesołowską” za podobną do rzeczywistości, a aplikanci
  i praktycy stanowczo ją odrzucali (TR049, słabe źródło).
- **Postrzegany realizm wzmacnia wpływ.** Realizm seriali kryminalnych
  wpływał na decyzje symulowanych przysięgłych obok częstotliwości oglądania
  (TR008). Realizm zewnętrzny i spójność opowieści podnoszą zanurzenie
  i przyjemność (TR036).
- **Sprawiedliwość proceduralna podróżuje między systemami prawa.** Widzowie
  oceniają instytucje filmowe według ogólnych standardów uczciwości
  postępowania (TR044).
- **Przyjemność zależy od oceny moralnej.** Zadowolenie z kary dla sprawcy
  wynikało z przekonań o sprawiedliwości (TR040, N=151; TR038).
- **Efekt CSI jest sporny.** Ankiety i symulacje pokazują wpływ na postawy
  (TR007, N=1 201; TR008), ale prawdziwi przysięgli w Australii i dane
  o uniewinnieniach go nie potwierdzają (TR009, TR010).
- **Seriale prawnicze przyciągają na studia.** Oglądanie seriali prawniczych
  wiązało się z wyborem prawa, a po emisji „Suits” wzrosła liczba kandydatów
  (TR017, N=1 353, Münster). Studenci prawa z czasem odchodzą od
  „samosądowej” logiki „Dextera” ku proceduralnej (TR019).
- **True crime przyciąga głównie kobiety**: 73% słuchaczy podcastów (TR024),
  silna różnica płci także w innych badaniach (TR025 = TG050, TR026). Motywy:
  chorobliwa ciekawość, czujność obronna, emocje (TR026).

## D. Opowiadanie na prawdziwych sprawach — **mocne**

- **Etykieta „prawdziwa historia” nie zmienia zanurzenia.** N=1 742: oznaczenie
  historii jako opartej na faktach albo fikcyjnej nie zmieniało zanurzenia,
  oceny, przyjmowania perspektywy ani pamięci (TR055).
- **Ale zwiększa poczucie użyteczności.** Historie zapowiedziane jako
  prawdziwe uważano za bardziej wiarygodne i użyteczne; przekonywały we
  wszystkich wariantach (TR054). Etykieta „fakt” zwiększa krytyczną analizę,
  ale nie siłę perswazji (TR056).
- **Czytelnicy wolą historie prawdziwe napisane jak fikcja** i bardziej na nich
  opierają obraz świata (TR057).
- **Dokudrama przekonuje przez melodramat** (TG052). Oglądanie dokudramy
  zmieniło postawy, mocniej u widzów uważających ją za realistyczną (TG054,
  badanie panelowe).
- **Ryzyko krzywdy.** Dokumenty true crime splatają się z podglądactwem
  i pozasądowym karaniem (TG055, esej). Prawdziwych ludzi trzeba chronić.

## E. Spory

| Temat | Jedna strona | Druga strona |
|---|---|---|
| Domknięcie | kryminał przywraca porządek (TG019), finał z domknięciem bardziej lubiany (TS041) | odmiany nordyckie i metafizyczne nagradzają otwarte pytanie (TG020, TG037) |
| Obchodzenie reguł | popkultura nagradza „moralny spryt” (TG045, TR042) | widownia prawnicza odrzuca zniekształcenia (TR049) |
| Etykieta prawdy | bez wpływu na zanurzenie (TR055) | czytelnicy wolą historie prawdziwe (TR057) i uznają je za użyteczniejsze (TR054) |
| Efekt CSI | wpływ na postawy (TR007, TR008) | brak w danych o prawdziwych procesach (TR009, TR010) |

## F. Rady pisarskie, których dane nie potwierdzają

- „Niech widz zgaduje.” Przewidywanie obniża przyjemność (TS017).
- „Zakończ sezon otwartym pytaniem.” Finał z domknięciem jest lepiej oceniany
  (TS041).
- „Zaskoczenie jest silniejsze niż zapowiedź.” Odwrotnie (TS022).
- „Mowa ciała zdradza kłamcę.” Serial o tym pogorszył trafność (TS030).
- „Etykieta »na faktach« wciąga bardziej.” Nie zmienia zanurzenia (TR055).

## Weryfikacja

Identyfikatory sprawdzono przez konektor OpenAlex; wyniki
w `weryfikacja/thriller-*.jsonl`. Wszystkie 166 prac istnieją, żadna nie jest
wycofana, 169 z 169 pozycji ma werdykt `potwierdzona`. Pliki weryfikacji
powstały z odpowiedzi konektora przepisanych przez agentów.

Bez streszczenia (opis z tytułu i słów kluczowych): TG012, TG028, TG030,
TG031, TG032, TS001, TS023, TS029, TS034, TS046. Słabe źródła: TG006, TG029,
TS002, TS019, TS024, TR049 i kilka prac dyplomowych. Eseje i artykuły z pism
prawniczych to opinie, nie dane.

## Prace w dwóch rejestrach

TG008 = TR045, TG050 = TR025, TG057 = TR024.
