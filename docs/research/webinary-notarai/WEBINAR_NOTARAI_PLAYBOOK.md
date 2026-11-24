# NOTARAI — webinar dla notariuszy: szczegółowy playbook (24.11.2026)

Dokument produkcyjno-badawczy. Nie stanowi potwierdzenia wdrożenia funkcji. Powiązany z FULLTEXT_EVIDENCE_REVIEW_2026-11-24.md w tym katalogu.

## 1. Strategia: jaką zmianę oferuje NotarAI?

**Nazwa:** „Od skanu do projektu aktu — AI w kancelarii pod kontrolą notariusza”.

**Obietnica dla odbiorcy:** „Zobaczysz, jak uporządkować dokumenty sprawy, przenieść dane do projektu Word i wykryć niepewność bez rezygnowania z kontroli notariusza. Całość na całkowicie fikcyjnych dokumentach”.

**Właściwa postawa:** transparentny warsztat fachowy, a nie telezakupy. Nie sprzedawaj „automatu do podpisywania aktów” ani „zastępstwa dla notariusza”. Konkretnym produktem jest przewidywalny proces przygotowania **projektu**, walidacja i jawna kontrola niepewnych danych. Główny outcome marketingowy = jakościowa prośba o indywidualne demo na syntetycznej sprawie, NIE sam klik w reklamę.

**Jedno CTA:** „Umów indywidualny pokaz na fikcyjnej sprawie podobnej do spraw, które obsługuje Twoja kancelaria”.

**Ograniczenia z repo NotarAI:** podstawowy proces importu wzoru/skanów, odczytu, walidacji i projektu DOCX. Nie mówić o 3xZERO (#96), czacie głównym (#125), publicznym demo (#122), Virtual Employee (#64), integracjach z RejNET, Polskim EKW czy dodatkach Word/OpenOffice (#127) jako o funkcjach już dostępnych na produkcji, dopóki nie są osobno potwierdzone.

## 2. Dwie persony jednocześnie

| Rola | Chce wiedzieć | Najlepszy dowód |
|---|---|---|
| Notariusz/zarządzający, decydent | Czy nie naruszę tajemnicy? Kto odpowiada za błędy? Jaki koszt i kontrola? | Celowe wykrycie błędu, human-in-the-loop, proces przetwarzania danych, przejrzysty pilot |
| Aplikant / pracownik kancelarii, operator | Czy mniej przepisuję? Czy korzysta z mojego wzoru? Czy działa w Wordzie? | Demonstracja od pliku źródłowego do edytowalnego projektu DOCX |

Nie wykluczaj żadnej z grup. Persony te są hipotezami lokalnymi, nie wynikiem badania populacji polskich notariuszy.

## 3. Scenariusz 60 minut

Czas to propozycja redakcyjna, nie „idealna” liczba udowodniona eksperymentem. Pytania i aktywizacja wynikają z badań uczenia się, nie potwierdzonego wzrostu sprzedaży.

| Czas | Zadanie | Dokładne wykonanie | Aktywność i miara |
|---|---|---|---|
| 00–02 | Otwarcie | Pokaż 3 fikcyjne dokumenty na ekranie. Obiecaj jeden kompletny proces i celowo błędne pole. Podkreśl, że nie zastępuje to notariusza. | Obecność live |
| 02–05 | Kontrakt | Zapowiedz 3 cele: ekstrakcja, kontrola braku, projekt DOCX. Daj znać, co będzie nagrywane. | Pretest zrozumienia |
| 05–09 | Problem kancelarii | Pokaż ręczne przechodzenie między załącznikami, odpisywanie i poprawki — jako scenariusz, bez wymyślonych statystyk. | Ankieta: co najbardziej przeszkadza? |
| 09–12 | Proces | Pięć etapów: źródło → odczyt → walidacja → człowiek → projekt. Oddziel projekt od czynności notarialnej. | Uczestnik umie opowiedzieć kroki |
| 12–15 | Fikcyjna sprawa | Trzy dokumenty demonstracyjne; skan z rozbieżnością kwoty i brak jednego źródła. | Quiz nr 1: co wymaga weryfikacji? |
| 15–21 | Import i odczyt | Wgranie plików do izolowanego demo albo wyraźnie oznaczonego nagrania. Pokazanie odczytu i źródeł pól. | Czytelność i sukces testu technicznego |
| 21–27 | Walidacja i „stop” | Rozbieżność w kwocie/numerze lub pole brakujące. System nie może zgadywać. | Quiz nr 2: trzy możliwe działania |
| 27–33 | Korekta i projekt Word | Operator weryfikuje źródło, poprawia wartość lub zostawia brak, generuje i otwiera edytowalny projekt DOCX. | Quiz nr 3: jakie kroki pozostają ludziom? |
| 33–37 | Ścieżka kontroli | Notariusz zatrzymuje błędny projekt, wskazuje punkt nieprzekraczalny. Uczciwie omawia ograniczenia. | Posttest |
| 37–44 | Bezpieczeństwo danych | Mapa: dokument → aplikacja → Bedrock i S3 w określonym trybie → kopie/logi/retencja/uprawnienia. Weryfikacja dokumentów umownych, bez absolutnych twierdzeń. | Pytania i obiekcje |
| 44–49 | Wdrożenie i koszt | Minimalny pilot na syntetycznych danych, role, narzędzia i rzeczywisty model kredytowy według wersji wdrożonej; zero zmyślonego ROI. | Ocena bariery adopcji |
| 49–57 | Q&A | Realne pytania, prawo do sceptycyzmu, bez ujawniania nazwisk ani danych spraw. | Klasyfikacja pytań |
| 57–60 | Synteza i CTA | Co AI może robić / czego nie robi; jedno CTA do indywidualnego pokazu i opis następnego kroku. | Kwalifikowana prośba o demo |

**Wersja dla bardzo zajętego notariusza (25 min):** 0–3 kontekst/odpowiedzialność; 3–15 demonstracja z błędem; 15–20 bezpieczeństwo/cena; 20–25 Q&A/CTA. Wersja warsztatowa (75 min) rozwija quiz i ocenę projektu.

## 4. Gotowe kwestie prowadzącego

### Powitanie
> Dzień dobry. Zamiast prezentacji o tym, jak AI odmieni świat, pokażę Państwu jedną fikcyjną sprawę kancelaryjną. Zobaczymy przejście od dokumentów do projektu w Wordzie, a także sytuację, kiedy maszyna nie może sama rozstrzygnąć rozbieżności. Wszystkie dane na ekranie są syntetyczne. Nie pokażę automatu zastępującego notariusza — pokażę pomocniczy proces, nad którym notariusz zachowuje kontrolę.

### Przejście do problemu
> Są czynności wymagające niezależnej oceny prawnej, zbadania woli stron i odpowiedzialności notariusza. I są czynności polegające na odnalezieniu, porównaniu i przeniesieniu danych z dokumentów. Właśnie tę drugą grupę chcemy usprawniać. Zobaczmy, gdzie pojawiają się braki i pomyłki, które można wykryć przed sporządzeniem ostatecznego dokumentu.

### Zapowiedź demo
> Na ekranie jest celowo fikcyjny komplet dokumentów. Jeden z nich zawiera różnicę, którą uczestnicy mogą znaleźć wcześniej niż system. Proszę zwrócić uwagę nie tylko na to, ile pól uda się odczytać, ale też co stanie się z polem, do którego nie mamy wiarygodnego źródła.

### Moment wykrycia problemu
> Mamy niezgodne dane. Co powinna zrobić pomocna aplikacja: wybrać najbardziej prawdopodobną wartość, pominąć problem czy wyraźnie zatrzymać projekt do sprawdzenia? Oczywiście to trzecie. W kancelarii ważniejsze jest rozpoznanie granicy pewności niż efektowna odpowiedź udzielona za wszelką cenę.

### Projekt i odpowiedzialność
> Zobaczyli Państwo projekt dokumentu. Nie jest to akt gotowy do podpisu. Nawet prawidłowo wyglądający numer czy kwota nie dowodzi poprawności materialnoprawnej. Notariusz sprawdza treść, źródła i skutki czynności — i zachowuje decyzję.

### Bezpieczeństwo
> W przypadku dokumentów kancelarii samo słowo „chmura w Europie” nie wystarcza. Pytania muszą być konkretne: kto może odczytać zawartość, gdzie wykonywana jest analiza, co trafia do logów, jak działają kopie i kiedy dane znikają. Oddzielę właściwości działającej wersji od tych, które dopiero rozwijamy.

### Koszty
> Nie podam dziś obietnicy w rodzaju „zaoszczędzą Państwo połowę etatu”, bo nie znam procesu ani wolumenu Państwa kancelarii. Pokaz pilotażowy może zmierzyć czas przygotowania materiałów, liczbę koniecznych poprawek oraz czas kontroli projektu. Dopiero wtedy warto policzyć korzyść netto, uwzględniając koszty i dodatkowe ryzyka.

### Zakończenie
> Najważniejsze, co chciałem pokazać, to różnica między automatyzacją pracy przygotowawczej a automatyzacją odpowiedzialności. Jeśli chcą Państwo sprawdzić to w swoim typie czynności, proponuję indywidualny pokaz na syntetycznych dokumentach. Bez przesyłania realnych aktów i bez zobowiązania do wdrożenia. Wystarczy wybrać termin i rodzaj sprawy.

## 5. Scenariusz fikcyjnej sprawy: najważniejszy rekwizyt webinaru

**Wybór:** przykładowa czynność dotycząca lokalu mieszkalnego. Użyj wzoru DOCX, skanu dowodu dokumentu oraz drugiego dokumentu z celowo niespójną kwotą lub brakującym polem. Na każdej stronie duży znak „FIKCYJNE DANE — DEMO”.

**Zasady:** nie używać prawdziwych aktów, skanów dowodów, adresów osób, prawdziwych KW/PESEL ani numerów telefonów. Syntetyczne numery mają być jednoznacznie demonstracyjne. Nie wolno przypadkowo wykonać prawdziwego zapytania do rejestru. Nie wyświetlać w streamie cookies, tokenów, adresów zaplecza ani danych kancelarii testującej.

**Przebieg demonstracji:**
1. „Tak wygląda punkt wejścia”: wzór DOCX i fikcyjne załączniki.
2. Operator importuje dane do jawnie oznaczonego środowiska demo.
3. Odczyt: oddzielenie „wartość ze źródła” od „wartość zaproponowana”.
4. Walidacja: syntetyczna rozbieżność. Podkreśl czerwony znacznik i źródło.
5. Decyzja uczestników: A zgaduj, B żądaj źródła, C ukryj brak.
6. Korekta po wiarygodnym źródle; pozostawienie innych braków.
7. Projekt DOCX: człowiek kontroluje cały dokument, także terminologię i skutki prawne.
8. Zakończenie na widocznym statusie „projekt do przeglądu”, bez podpisu lub wysyłki.

**Brak działającej funkcji?** Zamiast udawać live, pokaż prawdziwy, oznaczony materiał z zarejestrowanego testu i wskaż ograniczenie. Nagranie powinno odpowiadać istniejącej, audytowanej funkcji. Gdy nie ma wiarygodnego demonstratora — NO GO.

## 6. Mapa prezentacji: 18 ekranów

| Ekran | Nagłówek | Co widać | Co mówi prowadzący |
|---|---|---|---|
| 1 | Od skanu do projektu | nazwa webinaru + jeden syntetyczny dokument | obietnica |
| 2 | Co pokażemy, czego nie | projekt / kontrola vs nie automatyczna czynność | granice |
| 3 | Ile kroków ma sprawa? | pięć etapów procesu | oddzielenie czynności |
| 4 | Gdzie tracimy czas? | wybór trudności | ankieta |
| 5 | Kto odpowiada? | operator vs notariusz | podział kompetencji |
| 6 | Komplet fikcyjnych plików | 3 widoczne załączniki | orientacja |
| 7 | Znajdź brak | jedno pytanie | pierwsza aktywizacja |
| 8 | Import | żywy ekran lub jawne nagranie | źródło |
| 9 | Dane odczytane | lista pól i znaczniki | walidacje |
| 10 | Tu system nie zgaduje | niezgodność i źródła | drugi quiz |
| 11 | Człowiek poprawia | korekta na podstawie źródła | kontrola |
| 12 | Projekt Word | podgląd, wyraźny status projektu | efekt |
| 13 | Granice odpowiedzialności | zakres AI vs notariusz | ryzyko |
| 14 | Dane i bezpieczeństwo | faktyczny przepływ danych dla konkretnej wersji | transparentność |
| 15 | Bezpieczny start | pilot na danych fikcyjnych | wdrożenie |
| 16 | Koszty i wsparcie | rzeczywisty aktualny cennik i warunki | ekonomia bez obietnic |
| 17 | Trudne pytania | krótka lista obiekcji | Q&A |
| 18 | Jeden następny krok | link do umówienia indywidualnego demo | CTA |

**Slajdy:** jeden główny punkt uwagi na ekranie; duże zbliżenia pól; bez czytania tekstu 1:1, nadmiaru ruchu i tablicy funkcji. Kamera prowadzącego powinna ustąpić miejsca demonstracji. Nie ma udowodnionej „idealnej” liczby slajdów.

## 7. Dwanaście trudnych pytań i rzetelne odpowiedzi

1. **„Czy AI pisze już gotowe akty?”** Nie. Może przygotować projekt do sprawdzenia; pełna czynność wymaga decyzji notariusza.
2. **„Co z halucynacjami?”** Pokaż brak, wymóg źródła, korektę, odmowę zgadywania; kontrola sumy kontrolnej nie wystarcza do potwierdzenia prawdziwości.
3. **„Czy zna aktualne prawo?”** Nie opierać decyzji na samej odpowiedzi modelu; podstawę prawną i stan faktyczny weryfikuje prawnik/notariusz.
4. **„Kto ma dostęp do akt?”** Tylko odpowiedź z dokumentacji bieżącego wdrożenia, ról, szyfrowania, uprawnień operatora i audytów; nie obiecywać „zero operator access” przed niezależną weryfikacją.
5. **„Czy dane zostają w UE?”** Dokumentacja mówi o trybach Bedrock eu. i S3 w eu-central-1, ale region konkretnego przepływu oraz podwykonawców należy zweryfikować; nie wyciągać z jednego regionu uniwersalnej gwarancji.
6. **„A tajemnica notarialna i RODO?”** Wymaga oceny konkretnego przepływu i umowy powierzenia; RODO nie sprowadza się do checkboxa czy szyfrowania.
7. **„Czy można użyć własnego szablonu Word?”** Podstawowy produkt wykorzystuje wzory DOCX; zakres zgodności danego wzoru trzeba sprawdzić na kopii fikcyjnej.
8. **„RejNET lub Notaris?”** Virtual Employee jest pracą rozwojową; nie twierdzić, że działa, dopóki adapter nie przejdzie testów i wdrożenia.
9. **„Księgi wieczyste?”** Numer i jego suma kontrolna to nie aktualna treść rejestru; adapter EKW w otwartym PR nie dowodzi produkcyjnego działania.
10. **„A jeśli program się zawiesi?”** Zachowujemy źródłowe pliki i tradycyjny sposób pracy, nie akceptujemy niepełnego projektu; pokaż realny kanał wsparcia, bez fikcyjnego SLA.
11. **„Ile zarobię/zaoszczędzę?”** Nie obiecywać wartości bez pomiaru na próbie spraw, kosztu przeglądu i błędów. Mierzyć czas kompletnego procesu, nie czas AI.
12. **„Ile kosztuje?”** Model kredytowy jest opisany w repo, ale uczestnikowi pokazać wyłącznie aktualny i potwierdzony cennik, warunki rezygnacji i sposób obsługi zapytań.

## 8. Komunikacja, rejestracja, przypomnienia

**Strona zapisu:** tytuł, data/czas, 3 konkretne umiejętności, informacja o syntetycznych danych, formularz „imię + e-mail + rola (opcjonalnie) + pytanie (opcjonalne)”. Zgoda marketingowa wyraźnie odrębna; zapis nie jest automatycznie zgodą na późniejszy marketing. Nie zbierać danych klientów kancelarii. Informacja o nagraniu, retencji i sposobie zgłaszania pytań bez ujawniania danych osobowych.

**Komunikacja przed:** potwierdzenie rejestracji z linkiem, przypomnienie organizacyjne w granicach właściwej podstawy prawnej, agenda i brak marketingowego nadużycia. Masowa wysyłka cold email/SMS/telefonów może naruszać art. 398 PKE; korzystać z prawidłowych zgód lub innych zgodnych z prawem kanałów.

**Komunikacja po:** pomocniczy materiał edukacyjny i odpowiedzi na pytania w zakresie zgody/celu; odrębny marketingowy follow-up tylko z należytą podstawą. Uczestnik ma prawo nie rezerwować pokazu. Nagranie webinaru może zawierać głosy i pytania, trzeba jasno określić, co jest nagrywane i jak będzie udostępnione.

## 9. Zespół i checklista przed transmisją

**Prowadzący:** zna język pracy kancelarii, nie wypowiada niezweryfikowanych obietnic, rozumie podstawy kontroli prawnej.

**Operator techniczny:** widzi sygnał, dźwięk, aktywny ekran; bez przyznania uprawnień do realnych kancelarii. Ma jawnie oznaczone nagranie zapasowe i procedurę natychmiastowego zatrzymania udostępniania.

**Moderator:** odczytuje pytania bez ujawnienia danych, pomaga w quizie, filtruje przypadkowe dane wrażliwe w czacie i informuje o zasadach.

- D-7: audyt produktu, ceny i bezpieczeństwa; zatwierdzenie jednego syntetycznego zestawu dokumentów.
- D-2: kompletna próba z nagraniem, uchem słuchacza, niezależna kontrola fikcyjnej sprawy.
- D-1: wersja awaryjna, brak prywatnych okien, zamknięte powiadomienia, kontrola napisów i dostępności.
- D-0 45 min wcześniej: mikrofon, kamera, echo, ekran w telefonie, ankieta, link CTA i operator pytań.
- W trakcie awarii: otwarcie powiedz „to oznaczone nagranie demonstracyjne”; nie podmieniaj po cichu.
- Po wydarzeniu: ustal faktyczne pytania, usterki, wskaźniki i możliwe nieporozumienia w komunikacji.

**Stop transmisji bez dyskusji:** ujawnienie rzeczywistych danych/sekretów, dostęp do produkcyjnego konta, fałszywe przedstawienie nierozwiniętej funkcji jako wdrożonej, brak jasnej ścieżki weryfikacji wyniku, brak zgodności transmisji z ustalonym zakresem.

## 10. Pomiar, analityka i testy

Rozdziel:
- **Wejście:** obejrzenia strony → rzeczywiste rejestracje → obecni live i replay.
- **Wiedza:** ten sam problem o niepewnym polu przed pokazem i analogiczny po; oddziel samoocenę satysfakcji.
- **Handel:** liczba kwalifikowanych uczestników → prośby o demo → *faktycznie odbyte* rozmowy → bezpieczne piloty → użycie i retencja po 30/90 dniach.
- **Bezpieczeństwo:** zero rzeczywistych dokumentów klientów w publicznym webinarze, odnotowane błędne obietnice i pytania wymagające korekty.

**Główna metryka:** dobrowolna, kwalifikowana prośba o indywidualny pokaz na jednego **kwalifikowanego, rzeczywistego uczestnika**. Definicja kwalifikacji przed zbieraniem danych (np. pracuje w kancelarii notarialnej i ma udział w decyzji lub praktycznym użyciu). Nie dzielić przez wszystkie kliknięcia i nie mieszać odbiorców reklamy ze zweryfikowanymi kancelariami.

**Test 1:** wezwanie oparte na czasie pracy vs oparte na granicy kontroli — metryka: kwalifikowane uczestnictwo, nie sam CTR.

**Test 2:** demonstracja jednego fikcyjnego błędu z aktywnym pytaniem vs demonstracja tego samego błędu bez interakcji — metryka: poprawne rozumienie granic, dopiero potem demo request.

**Test 3:** krótkie 25 min vs 60 min — metryka: wiedza i odbyte indywidualne pokazy w 30 dni, z uwzględnieniem początkowej motywacji i źródła ruchu. Nie twierdzić, że to eksperyment przyczynowy bez randomizacji.

**Przy małej próbie:** podawać licznik, mianownik, segment, przedziały niepewności, utraconych do obserwacji i ryzyko selekcji. Nie interpretować 2 rezerwacji jako dowodu wielkiej skuteczności.

## 11. GO / NO-GO — warunki dopuszczenia webinaru

1. Wyłącznie fikcyjne i opisane dokumenty, testowe konta, zero realnych KW/PESEL.
2. Funkcjonalność poparta sprawdzoną wersją, a nie tylko otwartymi PR.
3. Notariusz wyraźnie odpowiada za weryfikację oraz ostateczną treść.
4. Odpowiedzi o bezpieczeństwie podparte zatwierdzoną dokumentacją i zakresem.
5. Mikrofon i zrozumiały obraz działają, przygotowana jest jawna wersja awaryjna.
6. Dokumentacja prawna procesu zapisu i nagrania, komunikacja zgodna z art. 398 PKE.
7. Jasny, jeden dobrowolny CTA bez manipulacji i sztucznego niedoboru.
8. Ustalona uprzednio miara sukcesu; zapisujemy także brak efektu i problemy.

## 12. Związek ze źródłami

Szczegółowa bibliografia i metody: FULLTEXT_EVIDENCE_REVIEW_2026-11-24.md. Badania wspierają **przejrzystość, interakcję, dobrą jakość dźwięku, pokazywanie kontroli i zgodność z potrzebami odbiorców**; nie ma przeprowadzonego RCT potwierdzającego, że ten 60-minutowy scenariusz to „idealny webinar” dla polskich notariuszy. To konkretny projekt do pilotażu i udoskonalania.
