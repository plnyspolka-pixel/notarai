# Tokenomia notarai: koszty, kredyty, modele biznesowe

Stan na 08.11.2026. Kod: `tokenomia.py`, symulacja: `scripts/symulacja_tokenomii.py`,
testy: `test_tokenomia.py`. Domyślnie wyłączona (`PIECZAPP_TOKENOMIA=false`): koszty
są liczone w logach i w panelu admina, ale nikt nie płaci kredytami.

## 1. Skąd biorą się koszty

Na każdą sprawę składają się trzy rodzaje kosztów:

| Koszt | Źródło | Rząd wielkości |
|---|---|---|
| **Zmienny, AI** | Bedrock, Claude Opus 4.6 w profilu `eu.`: 5 USD / 1 mln tokenów wejścia, 25 USD / 1 mln wyjścia, +10% za wnioskowanie geograficzne (założenie, `PIECZAPP_PREMIA_REGIONALNA`), kurs 3,70 zł | **ok. 22 zł na typową sprawę** (95% kosztów zmiennych) |
| **Zmienny, dane** | treść KW przez Finance You: Apify 0,005–0,010 USD + 0,025 USD za uruchomienie, awaryjnie EasyMKW (2 kredyty EasyMKW) | średnio ok. 0,35 zł, P90 2,20 zł za księgę (`finyou/src/lib/apify-ekw.server.ts`) |
| **Stały, platforma** | 2 × Fargate 1 vCPU / 3 GB, ALB, publiczne IPv4, CloudWatch, Secrets Manager, S3, ECR, Cognito | ok. 550 zł / mies. niezależnie od liczby kancelarii |
| **Płatności** | Stripe: karta ok. 1,5% + 1 zł, Billing 0,7%, Tax 0,5% | ok. 2,7% przychodu |
| **Człowiek** | wsparcie, wdrożenie, utrzymanie | przyjęto 60 zł / kancelaria / mies. |

KRZ (przez pomocnika na komputerze kancelarii), śledzenie Poczty Polskiej, kalendarz
i magazyn spraw (S3 to ułamki grosza na sprawę) są praktycznie darmowe.

### Co w sprawie kosztuje najwięcej

Strona A4 idzie do modelu jako obraz całej strony + 4 pasy w pełnej rozdzielczości
(`dokumenty.py`), czyli ok. **7 650 tokenów obrazu na stronę** (policzone na tym kodzie).
Do tego warstwa tekstowa i polecenie (ok. 850) oraz ponowne przeczytanie transkrypcji
w zestawieniu danych (ok. 2 000). Wyjście to transkrypcja + myślenie modelu; przy
dokładności „maksymalna” myślenie potrafi zużyć kilka razy więcej tokenów niż typowo.

Dlatego każda akcja ma dwa szacunki: **P50** (typowe wykonanie) i **P90** (90% wykonań
jest tańszych). Z nich wynika średnia (rozkład log-normalny).

| Akcja | Jednostka | Koszt P50 | Średnio | P90 | **Cena** |
|---|---|---:|---:|---:|---:|
| Odczyt strony, dokładność maksymalna | strona | 0,54 zł | 0,62 zł | 0,97 zł | **2 kr** |
| Odczyt strony, dokładność wysoka | strona | 0,46 zł | 0,50 zł | 0,74 zł | **1,5 kr** |
| Odczyt strony, dokładność standardowa | strona | 0,39 zł | 0,41 zł | 0,56 zł | **1,5 kr** |
| Zestawienie danych + pytania wstępne | sprawa | 1,38 zł | 1,82 zł | 3,51 zł | **7,5 kr** |
| Tura rozmowy o sprawie (do 30 tys. tokenów kontekstu) | tura | 0,62 zł | 0,79 zł | 1,52 zł | **3,5 kr** |
| Projekt aktu (wzór do 40 tys. znaków) | projekt | 3,37 zł | 3,79 zł | 6,18 zł | **12,5 kr** |
| Projekt aktu, każde dalsze 10 tys. znaków | 10 tys. zn. | 0,62 zł | 0,70 zł | 1,17 zł | **2,5 kr** |
| Dopasowanie formularza urzędowego | formularz | 0,63 zł | 0,82 zł | 1,57 zł | **3,5 kr** |
| Krok asystenta w przeglądarce | krok | 0,12 zł | 0,13 zł | 0,20 zł | **0,5 kr** |
| Treść KW z EKW | księga | 0,35 zł | 0,35 zł | 2,20 zł | **5 kr** (cena za wartość; ta sama KW w tej sprawie w ciągu doby – 0) |
| Odsłonięcie kontaktu klienta z zapytania | zapytanie | ~0 | ~0 | ~0 | **5 kr** po wyczerpaniu puli planu |
| Kalkulator taksy (Sonnet 4.6) | tura | 0,08 zł | 0,11 zł | 0,22 zł | 0,5 kr (wliczone) |
| Nadanie przesyłki przez e-Nadawcę | przesyłka | ~0 | ~0 | ~0 | **0,5 kr** (opłata usługowa) |
| Sprawdzenie w KRZ | sprawdzenie | ~0 | ~0 | ~0 | **0 kr** |

1 kredyt = 1 zł w cenie katalogowej. Koszt zawiera +15% na nieudane i ponowione próby
(zestawienie próbuje do 3 razy), za które kancelaria nie płaci.

**Typowa sprawa** (14 stron, 4 tury rozmowy, projekt, 1 KW): koszt AI ok. 22 zł,
cena ok. 64–77 kr.

## 2. Reguła ceny (narzut co najmniej 100%)

```
kredyty = zaokrąglij_w_górę_do_0,5(max(
    koszt_P90    × 2 / cena_katalogowa_kredytu (1,00 zł),     (a)
    koszt_średni × 2 / najniższa_cena_kredytu  (0,80 zł),     (b)
))
```

- (a): przy cenie katalogowej narzut 100% trzyma się nawet dla 90% najdroższych wykonań,
- (b): kancelaria z największym rabatem (najtańszy plan albo pakiet, 0,80 zł/kr) i tak
  płaci średnio co najmniej 2 × koszt,
- kredyty nie są ustawiane ręcznie, tylko liczone z profilu kosztów; zmiana kursu,
  ceny modelu albo narzutu (`PIECZAPP_NARZUT`) przelicza cennik sama,
- test `test_kazda_akcja_ma_narzut_co_najmniej_100_procent` pilnuje obu warunków dla
  każdej akcji, a `test_najnizsza_cena_kredytu_nie_schodzi_ponizej_zalozenia_cennika`
  nie przepuści planu ani pakietu tańszego niż 0,80 zł/kr.

## 3. Prototyp, test, poprawki, drugi test

Symulacja losuje 20 000 spraw (strony log-normalnie wokół 14, czasem 100+; dokładność
60/25/15% max/high/medium; tury rozmowy z rosnącym kontekstem; długość wzoru; księgi;
formularze; 8% ponowionych wywołań) i dla każdej akcji losuje tokeny z rozkładu P50/P90.

| Wersja cennika | kr/sprawę | Narzut portfela (0,80 zł/kr) | Sprawy < 100% (0,80 zł) | Sprawy < 100% (1 zł) | Sprawy ze stratą |
|---|---:|---:|---:|---:|---:|
| v0: 2 × koszt typowy, stała cena tury i projektu | 42,8 | 57% | 90,0% | 46,5% | 1,6% |
| v1: 2 × P90 przy najniższej cenie kredytu | 108,6 | 299% | 0,2% | 0,0% | 0% |
| **v2: obecna reguła + skalowanie tur i projektu** | **76,7** | **181%** | 2,9% | 0,5% | **0%** |

Co wyszło w kolejnych iteracjach i co zmieniłem:

1. **v0 odrzucony.** Koszt modelu ma długi ogon (myślenie), więc „2 × typowy koszt” daje
   w praktyce 57% narzutu, a długie rozmowy i duże wzory przynoszą stratę.
2. **v1 bezpieczny, ale za drogi:** ok. 109 zł za sprawę, czyli ok. 5 × koszt.
3. **v2:** podwójny warunek (a)+(b), tura rozmowy liczona od długości kontekstu
   (kontekst sprawy i cała historia idą do modelu przy każdej wiadomości), projekt
   z dopłatą za każde 10 tys. znaków wzoru ponad 40 tys.
4. **Błąd w modelu kosztów:** cena strony nie zawierała ponownego czytania jej
   transkrypcji w zestawieniu (ok. 2 tys. tokenów/stronę). Poprawione w profilu.
5. **Model C (39 zł za akt) łamał 100% narzutu** (89–93%). Teraz 49 zł za sprawę
   z limitem 40 stron i 10 tur + 149 zł opłaty platformowej; nadwyżka w kredytach.
6. **Pule planów były za małe** (200/600/1500 kr przy ~77 kr/sprawę): kancelaria
   w praktyce kupowała głównie pakiety. Nowe pule: 300 / 700 / 1 875 / 4 500 kr.

Drugi test po zmianach: 55 testów tokenomii i cały dotychczasowy zestaw przechodzą.

## 4. Gdzie i jak pobieramy kredyty

| Punkt API | Akcja | Jednostki |
|---|---|---|
| `POST /api/sprawy`, `POST /api/odczyt` | odczyt strony (wg dokładności) + zestawienie | liczba stron + 1 |
| `POST /api/sprawy/{id}/rozmowa`, `POST /api/rozmowa` | tura rozmowy | `ceil(tokeny kontekstu / 30 000)` |
| `POST /api/sprawy/{id}/projekt`, `POST /api/projekt` | projekt (+ dopłata za długi wzór) | 1 + dopłaty |
| `POST /api/formularze/{system}/dopasuj` | formularz | 1 |
| `POST /api/sprawy/{id}/ekw` | treść KW | 1 (tylko pobrana księga) |
| `POST /api/pomocnik/klikamy/{id}/krok` | krok asystenta | 1 |
| `POST /api/poczta/nadaj` | przesyłka | tyle, ile nadano |

Zasady:
- **Saldo sprawdzamy przed pierwszym wywołaniem modelu**, pobieramy **po sukcesie**.
  Błąd modelu, przeciążenie, odrzucona KW = 0 kredytów.
- **Debet 30 kr** (`PIECZAPP_DEBET_KREDYTOW`): notariusz nie traci możliwości
  dokończenia aktu w połowie pracy (jak karencja abonamentu).
- Brak kredytów = HTTP 402 z komunikatem; przeglądarka otwiera okno Abonament
  z saldem, cennikiem i pakietami (także przy odczycie strumieniowym).
- Kolejność zużycia: najpierw pula z abonamentu (przepada co okres), potem dokupione.
- Każde wywołanie modelu jest liczone (`bedrock._rozmowa` → `tokenomia.dolicz`),
  także w wątkach równoległego odczytu stron. Obok ceny zapisujemy rzeczywisty koszt.
  W logu: akcja, liczba wywołań, tokeny, koszt, kredyty. Zero danych osobowych.
- Portfel leży w obszarze administracyjnym S3 (`admin/kredyty/{kancelaria}.json`),
  zapis warunkowy (If-Match), więc dwie kopie aplikacji nie gubią pobrań. Działa też
  dla kancelarii, które trzymają pliki u siebie (to dane rozliczeniowe, nie sprawy).

API:
- `GET /api/kredyty` – saldo, pula, dokupione, cennik (bez kosztów), plany, pakiety, historia,
- `POST /api/kredyty/pakiet {"pakiet": "500"}` – strona płatności Stripe (tylko właściciel),
- `GET /api/admin/tokenomia` – cennik z kosztami P50/P90, kalibracja z pomiarów,
  wynik miesiąca każdej kancelarii (kredyty, koszt, zrealizowany narzut),
- `POST /api/admin/kancelarie/{id}/kredyty {"kredyty": 250, "powod": "..."}` – ręczna korekta.

Stripe: pakiet to płatność jednorazowa (`mode=payment`, faktura), kredyty dopisuje
webhook `checkout.session.completed` dopiero przy `payment_status=paid`, raz na sesję.
Opłacona faktura abonamentu (`invoice.paid`) odnawia pulę planu, raz na fakturę.
Nowa kancelaria dostaje 150 kr próbnych.

### Kalibracja

Profile tokenów są szacunkiem z budowy promptów. Po kilkuset prawdziwych akcjach
`GET /api/admin/tokenomia` → `kalibracja` pokazuje dla każdej akcji koszt P50/średni/P90
z pomiarów, zrealizowany narzut i **zalecaną liczbę kredytów**. `ok: false` = trzeba
poprawić profil w `tokenomia.AKCJE`. Logi `tokenomia: ... ponizej progu narzutu`
ostrzegają o pojedynczych wykonaniach poniżej 100%.

## 5. Trzy modele biznesowe

Wynik miesięczny na jednej kancelarii (symulacja, pełne wykorzystanie kredytów,
bez kosztów stałych platformy):

| Profil kancelarii | Model | Przychód | Koszt AI | Narzut na AI | Marża po Stripe i wsparciu | zł/sprawę |
|---|---|---:|---:|---:|---:|---:|
| mała, 25 spraw AI/mies. | A abonament + pula | 1 600 zł | 544 zł | 194% | 952 zł | 64 |
| | B pakiety | 1 729 zł | 544 zł | 218% | 1 077 zł | 69 |
| | C opłata za sprawę | 1 516 zł | 544 zł | 178% | 869 zł | 61 |
| średnia, 70 spraw | A | 4 500 zł | 1 524 zł | 195% | 2 793 zł | 64 |
| | B | 4 841 zł | 1 524 zł | 218% | 3 125 zł | 69 |
| | C | 3 976 zł | 1 524 zł | 161% | 2 283 zł | 57 |
| duża, 180 spraw | A | 11 100 zł | 3 919 zł | 183% | 6 820 zł | 62 |
| | B | 12 448 zł | 3 919 zł | 218% | 8 132 zł | 69 |
| | C | 9 989 zł | 3 919 zł | 155% | 5 739 zł | 56 |

Koszty stałe platformy (ok. 550 zł/mies.) pokrywa marża jednej średniej kancelarii.

### Model A: abonament z pulą kredytów + dokupowanie (zalecany na start)

| Plan | Cena / mies. | Pula | zł / kr | Osób | Kontaktów klientów w cenie |
|---|---:|---:|---:|---:|---:|
| Start | 290 zł | 300 kr | 0,97 | 2 | 2 |
| Kancelaria | 600 zł | 700 kr | 0,86 | 6 | 5 |
| Pro | 1 500 zł | 1 875 kr | 0,80 | 20 | 15 |
| Kancelaria+ | 3 600 zł | 4 500 kr | 0,80 | 50 | 40 |

(Start ~4 sprawy z AI, Kancelaria ~9, Pro ~25, Kancelaria+ ~60; plan „Kancelaria” = obecna cena w Stripe.)

Pakiety do dokupienia: 100 kr = 100 zł, 500 kr = 450 zł, 2 000 kr = 1 600 zł (ważne 12 mies.).

- Plusy: przewidywalny przychód (MRR), istniejąca subskrypcja Stripe zostaje, niewykorzystana
  pula przepada (w symulacji założyłem 100% wykorzystania, więc realna marża jest wyższa),
  kancelaria płaci „ryczałt”, do którego jest przyzwyczajona.
- Minusy: trzeba dobrze dobrać pule; notariusz płaci za puste miesiące (urlopy).
- Wdrożenie: `PIECZAPP_TOKENOMIA=true`, plan „kancelaria” = obecna cena 600 zł.

### Model B: tylko pakiety (pay-as-you-go)

Bez abonamentu, kancelaria kupuje kredyty, gdy potrzebuje. Opłata dostępowa 0 zł albo
symboliczna (np. 49 zł/mies. za konta i magazyn spraw).

- Plusy: najniższy próg wejścia, najlepszy do pozyskania małych kancelarii
  i do okresu próbnego; najwyższy narzut (218%), bo bez rabatu za zobowiązanie.
- Minusy: przychód nieprzewidywalny, sezonowy; większe ryzyko odejścia.
- Wdrożenie: to samo co A, bez subskrypcji (pakiety działają niezależnie).

### Model C: opłata za sprawę (akt) z limitem

149 zł / mies. za platformę + 49 zł za każdą sprawę z AI, w cenie do 40 stron skanów
i 10 tur rozmowy, nadwyżka w kredytach.

- Plusy: najprostszy do zrozumienia dla notariusza („49 zł za akt”), łatwy do porównania
  z taksą i czasem pracy aplikanta, dobry do rozmowy z izbą notarialną.
- Minusy: najniższy narzut (155–178%), ryzyko dużych spraw (dlatego limit), trzeba
  liczyć „sprawy” (definicja: sprawa z odczytem skanów w danym miesiącu).
- Wdrożenie: wymaga dodatkowego licznika spraw w Stripe (usage-based billing);
  w kodzie jest gotowy pomiar, brak rozliczenia.

### Dodatkowe źródła przychodu (do każdego modelu)

- **Licencja dla izby notarialnej / sieci kancelarii**: stała opłata roczna + pula,
  z rabatem do 0,80 zł/kr (nie niżej – pilnuje test).
- **Wdrożenie i szkolenie**: jednorazowo, np. 1 500–3 000 zł (wzory aktów, pomocnik, RODO).
- **Usługi danych na zlecenie notariusza**: EKW (4,5 kr), nadania pocztowe (0,5 kr) –
  już w cenniku.
- **Ostrożnie:** opłaty od klientów kancelarii, prowizje za „polecanie” notariuszy czy
  rezerwacje mogą naruszać zakaz reklamy notariuszy – w kodzie rezerwacje są już
  celowo neutralne. Nie budowałbym na tym przychodu bez opinii samorządu notarialnego.

## 6. Ryzyka i dźwignie

- **Przepustowość, nie cena, jest wąskim gardłem:** konto ma limit zapytań Bedrock
  ok. 5/min wspólny dla wszystkich kancelarii (`config.py`). Przy kilkunastu aktywnych
  kancelariach trzeba podnieść limit w AWS (Service Quotas), inaczej sprzedamy kredyty,
  których nie da się „wydać” w godzinach szczytu.
- **Zmiana modelu podnosi koszt strony.** Modele 4.7+ czytają obraz w wyższej
  rozdzielczości: ok. 20 700 tokenów obrazu na stronę zamiast 7 650 (policzone na tym
  kodzie) i nowy tokenizer (do 1,35 × tokenów). Nawet Opus 5.5 (4/20 USD) da stronę
  ok. 30% droższą. Po odblokowaniu modelu: kilkaset akcji i kalibracja przed zmianą cennika.
- **Dźwignie obniżenia kosztu** (do sprawdzenia na jakości odczytu, nie wdrożone):
  - pamięć podręczna promptu w rozmowie (kontekst sprawy idzie przy każdej turze;
    odczyt z cache kosztuje 10% ceny wejścia) – tura może potanieć o 40–60%,
  - dokładność „standardowa” dla dokumentów z warstwą tekstową (wypisy, KW),
  - tańszy model do rozmowy i podsumowania (Sonnet), Opus zostaje do odczytu skanów.
- **Kurs USD/PLN:** cennik w kredytach przelicza się sam (`PIECZAPP_KURS_USD`),
  ale wymaga restartu aplikacji. Przy wahaniu > 10% warto zaktualizować.
- **Założenia do potwierdzenia:** premia 10% za profil `eu.`, cena kredytu EasyMKW
  (przyjęte ~1,10 zł), koszty stałe (550 zł) – w kodzie są parametrami. Rzeczywistych kosztów
  z Cost Explorer i liczników tokenów z CloudWatch nie mogłem w tej sesji odczytać
  (wymagało ponownego zalogowania do AWS), dlatego profile tokenów to szacunek.

## 7. Wdrożenie krok po kroku

1. Wdrożyć bez zmiany parametru (tokenomia wyłączona): przez 2–4 tygodnie licznik
   zbiera prawdziwe koszty akcji. Podgląd: `GET /api/admin/tokenomia` → `kalibracja`
   i logi `tokenomia:` w CloudWatch.
2. Poprawić profile w `tokenomia.AKCJE`, jeśli kalibracja pokaże `ok: false`.
3. Ogłosić kancelariom cennik i plany (min. 30 dni przed – zmiana Regulaminu).
4. Parametr stosu `Tokenomia=true` (etap 3 wdrożenia). Istniejące kancelarie: pula planu
   przy najbliższej fakturze; do tego czasu można dopisać kredyty w panelu admina.


## 8. Druga runda: czego nie było w pierwszym projekcie

Przegląd całego kodu pod kątem „za co mogą płacić” i „gdzie stracimy pieniądze”.
Wszystko poniżej jest wdrożone i ma testy (`test_tokenomia.py`, `test_kontakt_klienta.py`,
`test_akademia.py`).

| Ryzyko / luka | Co by się stało | Rozwiązanie |
|---|---|---|
| Kredyty próbne w puli abonamentu | pierwsza faktura nadpisuje pulę – próbne znikają | osobna partia „proba”, ważna 30 dni |
| Nowe konto = nowe 150 kr | rejestracja jest samoobsługowa, można „farmić” | kredyty próbne raz na NIP (zapamiętany skrót, nie numer) |
| Dokupione „ważne 12 miesięcy” tylko w dokumentacji | obietnica bez pokrycia w kodzie, problem z Regulaminem | partie z datą ważności, wygasłe trafiają do historii, wydawane od najszybciej wygasającej |
| Dziesięć odczytów naraz | każdy przechodzi sprawdzenie salda osobno – przekroczenie debetu | rezerwacje kredytów na czas akcji |
| Publiczny kalkulator taksy | 1 500 tur/dobę × 2 kopie × ~0,11 zł ≈ do 10 tys. zł/mies. przy ruchu automatów | dzienny budżet (40 zł/proces), potem odesłanie do formularza bez modelu |
| Asystent w przeglądarce | zapętlony lub podmieniony pomocnik drenuje kredyty krokami | serwerowy limit 30 kroków na zlecenie |
| Ta sama KW pobierana kilka razy | notariusz płaci podwójnie za odświeżenie przed aktem | ta sama księga w tej samej sprawie w ciągu doby – bez opłaty |
| Limit osób w planie | pole w cenniku, niczego nie ograniczało | zaproszenie ponad limit planu – 402 z informacją o wyższym planie |
| Cena znana po fakcie | notariusz boi się kliknąć | `POST /api/kredyty/wycena` + flaga niskiego salda |
| Koszt KW | zakładałem 1,80 zł, w Finance You jest ~0,13 zł (Apify) | profil z prawdziwych stawek; cena 5 kr to cena za wartość, nie za koszt |

Ryzyka, których kod nie rozwiąże:
- **VAT i księgowość:** przedpłacone kredyty to w praktyce bon (MPV) – przychód przy
  wykorzystaniu albo wygaśnięciu. Operator jest fundacją zwolnioną z VAT, a Stripe Tax jest
  włączony – do potwierdzenia z księgową przed włączeniem pakietów.
- **Zmiana cennika:** kredyty kupione wcześniej powinny zachować cenę akcji przez okres
  wypowiedzenia (np. 30 dni) – zapisać w Regulaminie.
- **Przepustowość Bedrock** (patrz punkt 6) – nadal największe ryzyko sprzedaży.

## 9. Odsłonięcie kontaktu klienta

Zapytania ze strony notarai.pl (`wizyty.py`): kancelaria od razu widzi czynność, wartość,
termin i szacunek z kalkulatora, a telefon i e-mail klienta **po odsłonięciu**: najpierw
z puli planu (2/5/15/40 miesięcznie), potem 5 kr.

Zamknięte kanały, którymi kontakt wyciekał (każdy obchodziłby opłatę):
1. lista zapytań – kontakt ukryty, widać tylko, czy klient podał telefon/e-mail,
2. e-mail do kancelarii – bez telefonu i e-maila klienta,
3. treść wiadomości – numery telefonów (9–15 cyfr) i e-maile maskowane; kwoty („500 000 zł”) i daty zostają,
4. kalendarz – status „oddzwonię” i „umówione” wymaga odsłonięcia, bo wpis kalendarza niesie telefon.

Uczciwość wobec kancelarii i klienta:
- **duplikat bez opłaty** – ten sam klient (telefon/e-mail) odsłonięty w ostatnich 30 dniach,
- **reklamacja** do 7 dni (fałszywy kontakt, spam, sprawa nie do notariusza): zwrot kredytów
  albo miejsca w puli, najwyżej 5 w miesiącu,
- **SLA dla klienta** – zapytanie nieodsłonięte po 48 h: klient dostaje e-mailem publiczny
  kontakt kancelarii. Klient nie może czekać na telefon, który nie nadejdzie, bo kancelaria
  nie chciała zapłacić,
- **neutralność** – ta sama cena dla każdego zapytania, niezależnie od czynności i wartości
  (test `test_cena_nie_zalezy_od_czynnosci_ani_wartosci`). To opłata za usługę narzędzia,
  nie prowizja od klienta.

**Uwaga prawna:** płatność za kontakt do klienta jest najbliżej granicy zakazu pozyskiwania
klientów przez pośredników z Kodeksu Etyki Zawodowej Notariusza. Przed włączeniem
(`PIECZAPP_PLATNY_KONTAKT`, domyślnie aktywne razem z tokenomią) warto uzyskać opinię
samorządu notarialnego. Wyłączenie przywraca dawne zachowanie bez zmian w kodzie.

**Ekonomia:** przy realnej liczbie zapytań (8–40 miesięcznie) odsłonięcia dają 0–8 zł
miesięcznie na kancelarię. To nie jest źródło przychodu. Ich wartość to filtr jakości
zapytań i argument „zapytania z notarai.pl w cenie planu”. Rekomendacja: zostawić pulę
w planie jako korzyść, opłatę traktować jako hamulec przy dużym wolumenie, a nie jako biznes.

## 10. Akademia notarai (grywalizacja)

Założenie: notariusz to zawód zaufania publicznego – odznaki, rankingi i „serie dni”
odbierałby jako niepoważne, a codzienne serie przy nieregularnej pracy kancelarii budzą
poczucie winy i odpływ. Dlatego mechanika opiera się na **kompetencji i obowiązku**, nie na zabawie.

**Haczyk:** art. 4 AI Act wymaga od kancelarii (podmiotu stosującego AI) zapewnienia
kompetencji zespołu, a nasze Zasady AI w kancelarii (§ 3) to formalizują. Każdy zaliczony
moduł to jednocześnie wpis do zaświadczenia o szkoleniu (data, wersja modułu, wynik) i kredyty.
Notariusz dostaje dokumentację, którą i tak musi mieć.

| Element | Zasada behawioralna | Nagroda | Ochrona przed nadużyciem |
|---|---|---|---|
| 6 modułów (3–4 min, lekcja + 4 pytania) | kompetencja, krótkie porcje, natychmiastowa informacja zwrotna | 15–20 kr za moduł (100 kr na osobę), partia ważna 90 dni | odpowiedzi sprawdza serwer, 3/4 do zaliczenia, 10 min przerwy po nieudanej próbie, nagroda raz, tylko osoby z zespołu, max 6 osób |
| Ścieżka wdrożenia (6 kroków) | postęp na start (umowa = 1/6), gradient celu, zawsze nazwany następny krok | 100 kr po ukończeniu | kroki sprawdzane na faktach: odczyt, projekt, druga osoba *dołączyła*, pomocnik połączony |
| Moduł „Jak pracować taniej” | zgodność interesów | jak inne moduły | uczy dokładności standardowej dla PDF z tekstem, zbierania poprawek w jednej wiadomości |
| Polecenie (kod 8 znaków) | wzajemność, dowód społeczny wśród notariuszy | 200 kr dla obu stron | dopiero po pierwszej opłaconej fakturze poleconej kancelarii, nie dla tej samej firmy (NIP), max 10 rocznie |
| Premia stażowa | inwestycja, unikanie straty statusu | 5% puli od 6. okresu, 10% od 12. | tylko przy opłaconej fakturze, raz na fakturę |
| Postęp zespołu (dla właściciela) | przynależność bez rywalizacji | – | bez rankingu: kto ile modułów, do dokumentacji art. 4 |

Czego świadomie **nie** ma: publicznych odznak (mapa notariuszy i notarai.pl pozostają
neutralne – wyróżnienie byłoby reklamą), tablic wyników, odliczania, sztucznej presji,
zawstydzania („nie chcesz oszczędzać?”).

Koszt (symulacja, kredyt kosztuje nas ok. 0,27 zł kosztu AI):
- Akademia dla małej kancelarii (2 osoby + ścieżka) – 300 kr ≈ 80 zł,
- dla dużej (6 osób) – 700 kr ≈ 186 zł,
- polecenie – 400 kr ≈ 106 zł,
- premia stażowa w drugim roku – 112–718 zł rocznie zależnie od planu.

Wszystko zwraca się w pierwszym miesiącu marży najmniejszej kancelarii (test
`test_nagrody_zwracaja_sie_w_pierwszym_miesiacu`).

Uczciwy minus: moduł o oszczędzaniu, jeśli 30% stron przejdzie na dokładność standardową,
obniża nasz zysk brutto o ok. 9 kr na 100 stron (koszt AI −6 zł, przychód −15 kr). Płacimy
tym za zaufanie i mniejszy odpływ klientów; narzut ≥ 100% zostaje na każdej akcji.

API: `GET /api/akademia`, `POST /api/akademia/{modul}` `{"odpowiedzi": [..]}`,
`GET /api/akademia/zaswiadczenie`, `GET /api/akademia/zespol/postep` (właściciel).
Rejestracja przyjmuje `polecenie` (także z linku `/rejestracja?polecenie=KOD`).

## 11. Projekt zapisów do Regulaminu (do oceny prawnika)

1. Kredyty są jednostką rozliczeniową usługi; 1 kredyt w cenie katalogowej = 1 zł netto.
   Cennik czynności jest dostępny w aplikacji przed wykonaniem czynności.
2. Kredyty z puli abonamentu są ważne do końca okresu rozliczeniowego. Kredyty z pakietów
   – 12 miesięcy od zakupu. Kredyty z nagród i zwrotów – 90 dni, z polecenia – 180 dni,
   próbne – 30 dni. Najpierw wykorzystywana jest pula, potem kredyty wygasające najwcześniej.
3. Kredyty nie podlegają wymianie na pieniądze; niewykorzystane wygasają.
4. Czynność zakończona błędem nie obciąża kredytów. Saldo może zejść do −30 kr, żeby
   dokończyć rozpoczętą czynność; ujemne saldo pomniejsza kolejną pulę.
5. Zmiana cennika czynności – z 30-dniowym wyprzedzeniem; nie dotyczy kredytów już kupionych
   w tym okresie.
6. Odsłonięcie danych kontaktowych z zapytania jest usługą techniczną o stałej cenie,
   niezależnej od czynności i jej wartości. Reklamacja w 7 dni.
7. Nagrody Akademii i polecenia przysługują raz; Fundacja może je cofnąć przy nadużyciu
   (np. polecenie własnej firmy).
