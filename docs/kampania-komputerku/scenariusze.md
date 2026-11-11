# „Komputerku…” — scenariusze odcinków (sezon 1)

Stan: 11.11.2026. Seria mikrofabuł 30–40 s, format główny 9:16, adaptacje 16:9 i 1:1.
Obsada i scenografia: `pakiet/05_biblia_produkcji/` (Helena, Marta, Basia, Kuba;
jeden pokój, ten sam plan). Każdy odcinek pokazuje **jedną istniejącą funkcję**
NotarAI na danych fikcyjnych i kończy się kontrolą człowieka.

## Szkielet każdego odcinka (stały rytm)

| Czas | Blok | Co widać | Źródło obrazu |
|---|---|---|---|
| 0–3 s | **Hak** | problem w jednym zdaniu, reakcja postaci | AI (kadr + ruch) |
| 3–10 s | **Kłopot** | wymiana 2–3 kwestii między postaciami | AI (mówiące postacie) |
| 10–13 s | **„Komputerku…”** | postać mówi polecenie; dymek + „Słucham…” | AI + grafika systemowa |
| 13–24 s | **Działanie** | „Już sprawdzam…” → prawdziwy ekran NotarAI | nagranie ekranu (dane testowe) |
| 24–31 s | **Kontrola** | notariusz przegląda wynik, „Projekt do weryfikacji” | AI + grafika systemowa |
| 31–35 s | **Puenta** | żart z charakterów, nie z prawa | AI |
| 35–38 s | **Outro** | `OUTRO_komputerku` + notarai.pl | plansza |

Warstwy stałe: oznaczenie „Treść wygenerowana przez AI” przez pierwsze 5 s,
znaczek „AI” do końca, logo w rogu, belki z imionami przy pierwszym pojawieniu
się postaci, napisy z czasów lektora.

Zasady treści (z biblii): nikt nie popełnia błędu prawnego dla żartu; program
nie podpisuje, nie wysyła i nie składa niczego sam; tylko fikcyjne dane (bez
PESEL, KW i nazwisk prawdziwych osób); funkcja głosowa pokazana tak, jak
faktycznie działa w wersji, z której nagrywamy ekran.

---

## Odc. 1 — „Księga nadawcza w pięć minut”

Funkcja: Przesyłki i korespondencja (`docs/przesylki.md`): dziennik
korespondencyjny, dziennik przesyłanych dokumentów, pocztowa książka nadawcza.

| # | Ujęcie | Kto | Kwestia / akcja |
|---|---|---|---|
| 1 | B, 85 mm | Basia | (nad stosem kopert) „Dwadzieścia trzy listy. Każdy do książki nadawczej. Ręcznie.” |
| 2 | A, plan ogólny | Kuba | „Pani Basiu, a gdyby tak… poprosić komputer?” |
| 3 | B | Basia | (spojrzenie znad okularów) „Kubusiu. Ten komputer drukuje od czasów Unii Lubelskiej.” |
| 4 | C, przez ramię | Marta | „Komputerku, przygotuj książkę nadawczą z dzisiejszych przesyłek.” → dymek, „Słucham…” |
| 5 | Ekran | — | „Już sprawdzam…” → lista przesyłek, wydruk książki nadawczej (dane testowe) |
| 6 | B | Basia | (przegląda wydruk) „Adresy się zgadzają. Numer pozycji… dalej po zeszłorocznej. Dobrze.” → „Projekt do weryfikacji” |
| 7 | A | Basia | (do drukarki) „Ale koperty dalej kleję ja.” |

## Odc. 2 — „Ile to będzie kosztowało?”

Funkcja: kalkulator taksy dla klientów (`docs/taksa.md`, `notarai.pl/kalkulator/`).

| # | Ujęcie | Kto | Kwestia / akcja |
|---|---|---|---|
| 1 | B | Kuba | (słuchawka przy uchu) „Piąty telefon dzisiaj: »ile kosztuje darowizna mieszkania?«” |
| 2 | B | Helena | „To zależy od wartości, od stopnia pokrewieństwa, od wypisów…” |
| 3 | B | Kuba | „…i od tego, czy pani rejent ma czas to policzyć.” |
| 4 | C | Marta | „Komputerku, wyślij klientowi link do kalkulatora i przygotuj wycenę do sprawdzenia.” |
| 5 | Ekran | — | kalkulator: opis sprawy zwykłym językiem → rozbicie: taksa, wypisy, PCC, opłaty, lista dokumentów |
| 6 | B | Helena | (okulary na nos) „Taksa maksymalna, nie ostateczna. Pokażę klientowi, ale stawkę ustalam ja.” |
| 7 | A | Kuba | „Czyli dzwonić będą tylko ci, co nie umieją kliknąć.” — Helena: „Czyli ty, Kubo.” |

## Odc. 3 — „Kto stoi po drugiej stronie?”

Funkcja: sprawdzenie stron na listach sankcyjnych i PEP (`docs/rejestry.md`, `docs/aml.md`).

| # | Ujęcie | Kto | Kwestia / akcja |
|---|---|---|---|
| 1 | A | Marta | „Jutro sprzedaż udziałów. Trzy spółki, siedem osób po stronie kupującego.” |
| 2 | B | Kuba | „Mam sprawdzić każdego na listach sankcyjnych? Ręcznie?” |
| 3 | C | Marta | „Komputerku, sprawdź strony aktu na listach sankcyjnych i PEP.” |
| 4 | Ekran | — | „Już sprawdzam…” → wyniki: brak trafień / jedno podobieństwo nazwiska do oceny |
| 5 | B | Helena | „Podobne nazwisko to nie ta sama osoba. Data urodzenia się nie zgadza — ale odnotowujemy, że sprawdziliśmy.” |
| 6 | Ekran | — | „Projekt do weryfikacji” — notatka do akt, decyzja po stronie notariusza |
| 7 | A | Kuba | (z ulgą) „A ja już szukałem w Google każdego po kolei.” — Basia: „Widziałam. Też tam jestem?” |

## Odc. 4 — „Wniosek do księgi wieczystej”

Funkcja: pakiet wniosku KW i repertorium C (`docs/ksiegi-i-giif.md`, `wnioski_kw.py`).
Ekran pokazuje **przygotowanie** danych do portalu; złożenie robi notariusz w systemie MS.

| # | Ujęcie | Kto | Kwestia / akcja |
|---|---|---|---|
| 1 | B | Kuba | „Akt podpisany. Teraz wniosek do KW… dwadzieścia pól do przepisania.” |
| 2 | B | Basia | „Z aktu na ekran, z ekranu do repertorium. Klasyka.” |
| 3 | C | Marta | „Komputerku, przygotuj dane wniosku KW z tego aktu.” |
| 4 | Ekran | — | „Już sprawdzam…” → pola wniosku wypełnione z aktu (dane testowe), podświetlone do sprawdzenia |
| 5 | B | Helena | (palcem po ekranie) „Udział jedna druga, nie jedna czwarta. Poprawiam.” → poprawka widoczna |
| 6 | Ekran | — | „Projekt do weryfikacji” → po złożeniu w portalu: wpis w repertorium C z numerem z systemu MS |
| 7 | A | Helena | „Komputer przepisuje. Czytam ja.” |

## Odc. 5 — „Klient przychodzi przygotowany”

Funkcja: teczka sprawy klienta (`docs/teczka-klienta.md`, `/przygotuj-sprawe/`).

| # | Ujęcie | Kto | Kwestia / akcja |
|---|---|---|---|
| 1 | A | Basia | „Pan Nowak (fikcyjny) na dziesiątą. Mówił, że »ma wszystkie papiery«.” |
| 2 | B | Helena | „Wszystkie papiery to zwykle połowa papierów.” |
| 3 | C | Marta | „Komputerku, pokaż teczkę, którą klient przygotował przed wizytą.” |
| 4 | Ekran | — | teczka: opis sprawy z czatu, wgrane dokumenty, lista braków |
| 5 | B | Marta | „Brakuje odpisu z księgi i zaświadczenia o niezaleganiu. Wysyłam mu listę od razu.” |
| 6 | Ekran | — | „Projekt do weryfikacji” — wiadomość do klienta czeka na kliknięcie Marty |
| 7 | A | Basia | „Pierwszy klient w historii, który przyjdzie z kompletem.” — Helena: „Zobaczymy.” |

## Odc. 6 — „Dziennik korespondencyjny po Nowym Roku”

Funkcja: księgi kancelarii — ciągła numeracja dzienników, poprawki bez usuwania
treści (`docs/przesylki.md`, § 1 ust. 5 i 7 rozporządzenia).

| # | Ujęcie | Kto | Kwestia / akcja |
|---|---|---|---|
| 1 | B | Kuba | „Nowy rok, nowy dziennik — zaczynam numerację od jedynki!” |
| 2 | B | Basia + Helena | (jednocześnie) „Nie.” |
| 3 | C | Marta | „Komputerku, dopisz dzisiejsze pismo z sądu do dziennika korespondencyjnego.” |
| 4 | Ekran | — | wpis z kolejnym numerem po zeszłorocznym; próba poprawki → historia „było: …” |
| 5 | B | Helena | „Dzienników nie prowadzi się w okresach rocznych. A poprawka nie wymazuje pierwotnej treści.” |
| 6 | Ekran | — | „Projekt do weryfikacji” |
| 7 | A | Kuba | (zapisuje w notatniku) „Nie… zaczynać… od… jedynki.” |

---

## Jak dopisać kolejny odcinek

1. Wybierz jedną funkcję, która **już działa** na `app.notarai.pl`.
2. Wypełnij `odcinek-szablon.json` (ujęcia, kwestie, postacie, czasy).
3. Przejdź siatkę kontrolną z `pakiet/05_biblia_produkcji/BIBLIA_WIZUALNA.md`
   (10 pytań) — zwłaszcza: czy ekran pokazuje tylko istniejącą funkcję i czy
   efekt zewnętrzny wymaga potwierdzenia notariusza.
4. Tekst przeczytać notariuszowi przed produkcją (merytoryka i etyka zawodowa).
