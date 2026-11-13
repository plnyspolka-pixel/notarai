# Tokenomia notarai: koszty, kredyty, modele biznesowe

Stan na 13.11.2026. Kod: `tokenomia.py`, płatności: `platnosci.py` (przez Finance You), symulacja:
`scripts/symulacja_tokenomii.py`, testy: `test_tokenomia.py`, `test_platnosci.py`.

**Decyzja 13.11.2026: kredyty są jedynym sposobem zakupu (model B, sekcja 5).**
Abonament Stripe usunięty z aplikacji. Tokenomia domyślnie włączona
(`PIECZAPP_TOKENOMIA=true`; `false` tylko awaryjnie). Nowa kancelaria dostaje
150 kr startowych, potem kupuje pakiety przez Finance You (konto TPay Fundacji).
Szczegóły: sekcja 8.

## 1. Skąd biorą się koszty

Na każdą sprawę składają się trzy rodzaje kosztów:

| Koszt | Źródło | Rząd wielkości |
|---|---|---|
| **Zmienny, AI** | Bedrock, Claude Opus 4.6 w profilu `eu.`: 5 USD / 1 mln tokenów wejścia, 25 USD / 1 mln wyjścia, +10% za wnioskowanie geograficzne (założenie, `PIECZAPP_PREMIA_REGIONALNA`), kurs 3,70 zł | **ok. 22 zł na typową sprawę** (95% kosztów zmiennych) |
| **Zmienny, dane** | treść KW z EKW przez Finance You / Apify (płatny wynik) | ok. 1,80 zł za księgę (założenie, `PIECZAPP_KOSZT_EKW_ZL`) |
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
| Treść KW z EKW | księga | 1,80 zł | 1,80 zł | 1,80 zł | **4,5 kr** |
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
- Kolejność zużycia: najpierw kredyty startowe, potem dokupione (nie wygasają co miesiąc).
- Każde wywołanie modelu jest liczone (`bedrock._rozmowa` → `tokenomia.dolicz`),
  także w wątkach równoległego odczytu stron. Obok ceny zapisujemy rzeczywisty koszt.
  W logu: akcja, liczba wywołań, tokeny, koszt, kredyty. Zero danych osobowych.
- Portfel leży w obszarze administracyjnym S3 (`admin/kredyty/{kancelaria}.json`),
  zapis warunkowy (If-Match), więc dwie kopie aplikacji nie gubią pobrań. Działa też
  dla kancelarii, które trzymają pliki u siebie (to dane rozliczeniowe, nie sprawy).

API:
- `GET /api/kredyty` – saldo, startowe, dokupione, cennik (bez kosztów), pakiety z ceną
  do zapłaty, historia, zakupy, `moge_kupic`,
- `POST /api/kredyty/pakiet {"pakiet": "500"}` – zamówienie w Finance You, adres TPay (tylko właściciel),
- `POST /api/finyou/platnosc` – sygnał z Finance You (otwarty, nic nie przesądza),
- `GET /api/admin/sprzedaz?miesiac=RRRR-MM` – opłacone pakiety z numerami faktur,
- `GET /api/admin/tokenomia` – cennik z kosztami P50/P90, kalibracja z pomiarów,
  wynik miesiąca każdej kancelarii (kredyty, koszt, zrealizowany narzut),
- `POST /api/admin/kancelarie/{id}/kredyty {"kredyty": 250, "powod": "..."}` – ręczna korekta.

Płatności: patrz sekcja 8. Nowa kancelaria dostaje 150 kr startowych; kancelaria założona
przed tokenomią dostaje je przy pierwszej czynności.

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

> Wyniki w tabeli to symulacja z 08.11.2026 (model B liczony po cenie pakietu 500).
> Skrypt liczy teraz B jako najtańszy zestaw pakietów; od 13.11.2026 obowiązuje B.

### Model A: abonament z pulą kredytów + dokupowanie (porzucony 13.11.2026)

| Plan | Cena / mies. | Pula | zł / kr | Dla kogo |
|---|---:|---:|---:|---|
| Start | 290 zł | 300 kr | 0,97 | ~4 sprawy z AI, 2 osoby |
| Kancelaria | 600 zł | 700 kr | 0,86 | ~9 spraw, 6 osób (obecna cena w Stripe) |
| Pro | 1 500 zł | 1 875 kr | 0,80 | ~25 spraw, 20 osób |
| Kancelaria+ | 3 600 zł | 4 500 kr | 0,80 | ~60 spraw, 50 osób |

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
- **Założenia do potwierdzenia:** premia 10% za profil `eu.`, koszt KW u dostawcy
  (1,80 zł), koszty stałe (550 zł) – w kodzie są parametrami. Rzeczywistych kosztów
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


## 8. Zakup przez Finance You (TPay) i faktura (od 13.11.2026)

### Dlaczego przez Finance You

Sprzedawcą notarai i Finance You jest ta sama Fundacja (NIP 9462747637). Finance You
ma już jej konto TPay, weryfikację powiadomień w API TPay i automatyczne faktury
w KSeF. notarai nie ma więc osobnego konta TPay ani kluczy TPay: zakłada zamówienie
w Finance You tym samym tokenem partnera co treść KW (sekret `notarai/finyou`).

### Przepływ płatności

1. Właściciel w oknie „Kredyty” wybiera pakiet. notarai zapisuje zamówienie w portfelu
   (`zamowienia[numer]`: pakiet, kredyty, kwota, status `nowe`) i woła
   `POST {finyou}/api/public/partner-platnosci` z numerem `<kancelaria>:<numer>`,
   kwotą, nazwą pozycji faktury i danymi nabywcy (nazwa, e-mail właściciela, NIP, adres).
2. Finance You zapisuje zamówienie (`partner_credit_orders`), tworzy transakcję TPay
   (`hiddenDescription = NOTARAI:<id>`) i oddaje adres płatności. Przeglądarka idzie
   na TPay (BLIK, przelew, karta) i wraca na `/?kredyty=ok`.
3. TPay powiadamia wspólny webhook Finance You. Finance You pobiera transakcję z API
   TPay, sprawdza kwotę, oznacza zamówienie `paid` (raz), wystawia fakturę (KSeF),
   wysyła ją e-mailem nabywcy i „pinguje” `POST /api/finyou/platnosc`.
4. notarai na ping (albo przy otwarciu okna „Kredyty”, gdy ping zginie) czyta stan
   `GET {finyou}/api/public/partner-platnosci?zamowienie=...` tokenem partnera
   i dopisuje kredyty raz, gdy status `paid` i kwota, zapłata oraz liczba kredytów
   zgadzają się z zamówieniem. `refunded` odbiera kredyty (raz), `failed` zamyka zamówienie.

Ping jest otwarty i nic nie przesądza: fałszywy ping najwyżej wywoła odczyt stanu.

### Pakiety (ceny = kwoty do zapłaty, dopóki Fundacja jest zwolniona z VAT)

| Pakiet | Cena | zł / kr | ok. spraw |
|---|---:|---:|---:|
| 100 kr | 100 zł | 1,00 | 1 |
| 500 kr | 450 zł | 0,90 | 6 |
| 2 000 kr | 1 600 zł | 0,80 | 25 |

Kredyty startowe: **150 kr** (ok. dwie pełne sprawy: odczyt ~14 stron, zestawienie,
4 tury rozmowy, projekt, KW, formularz, kroki asystenta, przesyłka — test
`test_kredyty_startowe_wystarcza_na_przetestowanie_kazdej_funkcji`). Koszt AI dla
nas ok. 45 zł na kancelarię.

### VAT

Usługodawcą jest Fundacja Krzewienia Edukacji Finansowej, zwolniona podmiotowo
(art. 113 ust. 1 ustawy o VAT, Regulamin § 7). Dlatego `PIECZAPP_VAT=0` i cena
pakietu to kwota do zapłaty. Limit zwolnienia to 240 000 zł sprzedaży w roku
(od 2026 r.) — przy kilku średnich kancelariach (ok. 4 800 zł/mies. każda) limit
skończy się w ciągu roku. Wtedy: `StawkaVat=0.23` w stosie i zmiana Regulaminu
(§ 14, 14 dni).

### Faktura: nazwa pozycji

Kredyty to **bon jednego przeznaczenia** (art. 2 pkt 41 ustawy o VAT): w chwili
sprzedaży wiadomo, na jakie usługi (platforma notarai), gdzie (Polska) i według
jakiej stawki się je wymieni. Sprzedaż bonu jednego przeznaczenia jest
traktowana jak sprzedaż samej usługi (art. 8a ust. 1), więc fakturę wystawia się
po zapłacie, jako zwykłą fakturę (nie zaliczkową), a późniejsze zużywanie
kredytów nie wymaga już żadnych dokumentów.

Nazwa pozycji (`tokenomia.TYTUL_FAKTURY`):

> Bon jednego przeznaczenia - pakiet 500 kredytów na usługi platformy notarai
> (oprogramowanie w modelu SaaS dla kancelarii notarialnej)

Dopóki Fundacja jest zwolniona: stawka „zw”, adnotacja „Sprzedaż zwolniona z VAT na
podstawie art. 113 ust. 1 ustawy o podatku od towarów i usług”. Nie używać słów
„tokeny” ani „abonament” (pierwsze kojarzy się z kryptoaktywami, drugie
z usługą ciągłą, której już nie ma).

Fakturę wystawia automatycznie Finance You (moduł księgowy, KSeF) z nazwą pozycji
przysłaną przez notarai; stawkę bierze z ustawień podmiotu Fundacji (zwolnienie →
„zw”). Numer faktury wraca do notarai i widać go w oknie „Kredyty”. Panel `/admin` →
„Sprzedaż kredytów (CSV)” służy do uzgodnienia sprzedaży (nabywca, NIP, kwoty,
numer faktury, transakcja TPay). Do potwierdzenia z księgową: kwalifikacja
kredytów jako bonu jednego przeznaczenia.
