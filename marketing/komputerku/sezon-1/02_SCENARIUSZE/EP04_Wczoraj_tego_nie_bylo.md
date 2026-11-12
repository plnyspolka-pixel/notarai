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
