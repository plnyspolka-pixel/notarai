# NotarAI 2.0: co działa i co wymaga decyzji

Stan na 27.11.2026. NotarAI 2 to wersja produkcyjna (decyzja właściciela): obsługuje prawdziwe sprawy
i dane osobowe kancelarii, w UE, w zaszyfrowanym sejfie na komputerach kancelarii.

## Co działa (sprawdzone testami)

| Obszar | Co robi | Jak sprawdzone |
| --- | --- | --- |
| Sejf | Dokumenty i wersje zaszyfrowane na komputerze kancelarii, osobny klucz na dokument, sprawy | testy automatyczne |
| Odzyskiwanie | Kod odzyskiwania do wydruku, plik kopii, odtworzenie na nowym komputerze, wymiana klucza | ćwiczenie „komputer przepadł” w testach |
| Kopie bez pamiętania | Raz na dobę kopia na wskazany dysk i (po włączeniu) poza kancelarię | testy automatyczne |
| Dziennik dostępu | Kto i kiedy czytał albo zapisał dokument; wykrywa zmianę wpisów | testy automatyczne |
| Asystent sprawy | Pytania do dokumentów i projekt aktu; zapis dopiero po zatwierdzeniu dokładnej treści | testy + przeglądarka |
| Ochrona danych w AI | PESEL, NIP, REGON, dowód, KW, rachunek, telefon, e-mail i wskazane osoby zastępowane znacznikami | testy + próba na żywo z Bedrock w UE |
| Blokada AI | Tylko modele UE, sprawdzenie na koncie, że treść wywołań nie jest zapisywana | testy + próba na żywo |
| Taksa | Liczy program (ten sam silnik co w V1), nie model | testy automatyczne |
| Edycja w Wordzie | Otwórz do edycji, zapisz do sejfu jako kolejną wersję, kopia robocza znika z dysku | testy, w tym prawdziwy LibreOffice |
| Rozmowa zamiast formularzy | Jedno okno czatu w Pocket i w panelu; polecenia zdaniem, potwierdzenia przyciskiem | testy + przeglądarka |
| Kafelki | Pulpit ustawiany przez notariusza: narzędzia z katalogu i własne, przeciąganie, chowanie; domyślnie pusty | testy + przeglądarka |
| Poczta | Thunderbird (wprost z plików), klasyczny Outlook, folder .eml; tylko odczyt, wiadomość do sprawy jednym zdaniem | testy na plikach Thunderbirda; Outlook na atrapie |
| Samodzielne wypełnianie | „wypełnij …” na stanowisku wpisuje dane w formularz na stronie albo w programie Windows, naciska „Dalej”, pokazuje zrzut i stan każdego pola; wysyła dopiero po „Wyślij teraz” | testy na prawdziwym formularzu w Chromium + przeglądarka; okno Windows w CI |
| Notatki głosowe | Mikrofon w Pocket, pliki z dyktafonu i komunikatorów; mowę przepisuje Amazon Transcribe we Frankfurcie strumieniem (kilka sekund, nagranie nigdzie nie zapisywane), zapasowo trybem wsadowym; okno nie czeka | testy; strumień sprawdzony do etapu logowania w usłudze, pełna próba na stanowisku z kontem w grupie `notarai-v2` |
| Gdzie są dane | „gdzie są dane”: mowa na tym komputerze (pasek pobierania modelu) albo we Frankfurcie bez zapisu; kopia sejfu we Frankfurcie wyłączona / co godzinę / co 6 h / raz na dobę, trzymana 30 dni / rok / bez usuwania | testy |
| Dyktowanie: diagnostyka i druga droga | Bez logowania stanowiska dyktowanie nie startuje i mówi „Zaloguj”; błąd strumienia widać w rozmowie; gdy strumień nie działa, po ■ całe nagranie idzie drugą drogą (bucket we Frankfurcie); „sprawdź mowę” sprawdza po kolei ustawienie, logowanie, dostęp, strumień i drugą drogę | testy (2.5.1) |
| Okno programu po restarcie i aktualizacji | Okno na tym komputerze wchodzi samo (lokalne, jednorazowe wejście tylko dla strony z tego komputera; telefon, drugie stanowisko i inne strony go nie dostaną); ekran „Kod panelu” zostaje tylko awaryjnie | testy (2.5.2) |
| Druk kodu odzyskiwania | Drukuje osobny arkusz z samym kodem dużą czcionką, niezależnie od układu okna (wcześniej wychodziła pusta kartka) | testy (2.5.2) |
| Agent komputera | Polecenie zdaniem wykonywane na komputerze: pliki z dysku, poprawki w Wordzie, programy Windows, strony w przeglądarce NotarAI; kroki widać w rozmowie; wysłanie, podpis, zapłata, usunięcie tylko na wyraźne polecenie, inaczej Tak/Nie; AI nie pisze już „nie mam dostępu do komputera” | testy (2.6.0) |
| Agent komputera: start z każdego zdania | 2.6.0 uruchamiała agenta tylko, gdy zdanie zaczynało się od kilku czasowników; w pozostałych przypadkach asystent odpowiadał tekstem, a przy wybranej sprawie pisał „nie mam dostępu do przeglądarki”. Teraz zdanie mówione („dobra, słuchaj, wejdź mi na stronę…”) rozpoznaje kod, a resztę oddaje agentowi sam asystent, także przy wybranej sprawie i w sprawie bez dokumentów | testy + 20 prób na żywo z modelem we Frankfurcie (2.6.1) |
| Agent widzi ekran | Gdy okno programu nie pokazuje pól, agent robi zrzut ekranu, klika w punkt i pisze z klawiatury. Zrzut idzie do asystenta we Frankfurcie tak, jak go widać (nazwisk na obrazie nie da się zamienić na znaczniki); każde spojrzenie widać w rozmowie; „wyłącz zrzuty ekranu agenta” | testy + próba na żywo z modelem na narysowanym oknie (2.7.0); na prawdziwym Windows: NA-20 |
| Wiersz poleceń | Agent uruchamia pojedynczy program z argumentami (np. narzędzie `cli-anything-…`, `winapp`, własny wiersz poleceń programu) i czyta, co wypisał. Bez cmd, PowerShella, skryptów i narzędzi systemowych kasujących dane; polecenie ze słowem „delete/send/sign” tylko na wyraźną prośbę; „wyłącz wiersz poleceń agenta”. Narzędzi CLI-Anything i WinApp program sam nie instaluje | testy (2.7.0); na Windows: NA-20 |
| Komputer z telefonu | Telefon zleca pracę na komputerze kancelarii po zgodzie danej na komputerze: „pozwól telefonowi Telefon sterować komputerem” albo „dodaj telefon z dostępem do komputera”; cofnięcie działa od razu | testy (2.7.0) |
| Mapa programu | Agent zapamiętuje ekrany, pola i przyciski programów i stron, po których chodził, oraz drogę do funkcji; przy następnym zadaniu ma mapę od pierwszego kroku. „poznaj program RejNET” robi samo rozpoznanie bez zapisywania czegokolwiek; „co wiesz o programie …”, „zapomnij program …”. W mapie nie ma wartości pól ani numerów | testy (2.8.0); na prawdziwym RejNET: NA-20 |
| Dłuższe zadania | Jeden przebieg do 80 kroków (było 24, co kończyło zwykłe zadanie w połowie); po limicie przycisk „Kontynuuj” wznawia pracę od miejsca przerwania | testy (2.8.0) |
| Programy Windows czytane w całości | W oknie programu (np. RejNET) agent widzi nie tylko pola i przyciski, ale też menu, zakładki, drzewa, listy oraz otwarte menu i okna dialogowe; po nich nawiguje i z nich buduje mapę programu | testy na atrapie (2.8.0); na prawdziwym RejNET: NA-20 |
| Starsze programy (Delphi) czytane po polach | Gdy nowszy interfejs Windows nie pokazuje pól programu, agent czyta to samo okno klasycznie: pola, listy, przyciski, menu główne i zakładki; pola bez podpisu dostają numer i agent raz ustala na zrzucie, które jest którym. Zrzut ekranu jest dozwolony dopiero po odczycie okna, a klik w punkt jest cofany, gdy przycisk ma nazwę. W dzienniku widać sposób: [pola okna] albo [ZRZUT EKRANU] | testy na atrapie programu Delphi (2.8.1); na prawdziwym RejNET: NA-20 |
| Sesja uczenia do 45 minut | Nagranie procedury trwa do 45 minut (było 5), z licznikiem czasu; głos jest nagrywany osobno, więc da się go przepisać także z długiego nagrania; do nauki idzie do 20 ujęć ekranu i cały komentarz | okno stanowiska w przeglądarce z podstawionym ekranem i mikrofonem; przepisanie długiego nagrania przez Transcribe: NA-20 |
| Okienko z pytaniem na wierzchu | Gdy agent ma pytanie, potrzebuje logowania albo zgody, w prawym górnym rogu ekranu pojawia się małe okienko ponad innymi oknami z dokładnym pytaniem i przyciskami odpowiedzi (przy pytaniu także pole na własne słowa); odpowiedź trafia do rozmowy i praca rusza dalej; „wyłącz okienko z pytaniem agenta” | testy + cały obieg w przeglądarce; samo wyświetlenie ponad oknami Windows: NA-20 |
| KRZ bez podawania PESEL | „sprawdź KRZ Jagiełło”: program sam szuka aktu (sprawy w sejfie, potem pliki w folderze aktów i na dysku), odczytuje strony z numerami PESEL i proponuje, kogo sprawdzić (nazwisko, PESEL zamaskowany, skąd wziął); bez udziału modelu | testy |
| Agent nie zabiera ekranu | Program kancelaryjny zostaje pod Twoimi oknami: agent czyta i wypełnia pola, naciska przyciski i menu, robi zrzut okna i klika w punkt bez wyciągania okna na wierzch, bez ruchu myszy i bez klawiatury. Gdy jakiegoś kroku nie da się tak zrobić, pyta o zgodę „na chwilę” i zaraz oddaje Twoje okno. Uruchamiany program nie przejmuje klawiatury | testy na atrapach; na prawdziwym Windows i RejNET: NA-20 |
| Bez kręcenia się w kółko | Powtórzony odczyt tego samego okna bez żadnej zmiany jest cofany; trzy takie same kroki z tym samym wynikiem (albo ten sam cykl kilku kroków trzy razy) zatrzymują pracę i agent pyta, co dalej | testy |
| Dziennik pracy agenta | Każda praca zostawia plik w folderze `dziennik-agenta`: krok, program, nazwa pola lub przycisku, czy się udało, czas; bez wpisywanych wartości, nazwisk i numerów. „dziennik agenta” pokazuje ostatnie prace: ile kroków, błędów, co się powtarzało | testy |
| Coraz krótsza droga | Po udanej pracy program zapamiętuje, co po kolei nacisnął i wypełnił (same nazwy), jako sprawdzoną drogę dla tej czynności; następnym razem idzie nią od razu, a gdy uda się krócej, zostaje krótsza | testy na atrapie; na prawdziwym RejNET: NA-20 |
| Okienko z pytaniem: dźwięk i miejsce | Okienko jest większe, na środku u góry ekranu (w rogu bywało częściowo schowane) i przychodzi z sygnałem dźwiękowym, powtarzanym kilka razy, póki nie odpowiesz; „wyłącz dźwięk pytania agenta” | testy; dźwięk i położenie na Windows: NA-20 |
| Listy rozwijane i skutek kliknięcia | Listę rozwijaną agent ustawia wartością (program czyta jej pozycje bez rozwijania); po każdym kliknięciu dostaje wykaz tego, co się w oknie pojawiło, zmieniło i zniknęło, więc nie zgłasza „nie reaguje”, gdy coś zadziałało. Czytane są też okna dialogowe i otwarte listy tego samego programu | testy na atrapach; na prawdziwym RejNET: NA-20 |
| Dyktowanie ze zrozumieniem | Po zakończeniu dyktowania asystent czyta tekst jeszcze raz i zapisuje to, co miałeś na myśli: przekręcone nazwy programów („w rynecie” → RejNET), skróty (KRZ, KW), zająknięcia i wtrącenia, interpunkcja. Liczby, daty i kwoty muszą zostać takie, jak usłyszane, inaczej zostaje tekst dosłowny. Pod polem widać, co usłyszano dosłownie; „wyłącz poprawianie dyktowania” | testy + próba na żywo z modelem we Frankfurcie |
| Ekran logowania | Gdy program albo strona pokazuje pole hasła lub PIN-u, agent staje i prosi w rozmowie o zalogowanie; po „Zalogowałem się, kontynuuj” pracuje dalej | testy + okno stanowiska w przeglądarce (2.8.0) |
| Dziennik czynności na żywo | W trakcie pracy agenta rozmowa pokazuje każdy krok z godziną: co dokładnie robi (okno, pole, przycisk, wpisywana wartość), po co, i osobno wynik z czasem trwania; po zakończeniu zwija się do „Dziennik czynności (n)” | testy + okno stanowiska w przeglądarce (2.8.0) |
| Praca w tle | Strony agent otwiera i wypełnia w oknie przeglądarki trzymanym poza ekranem; okno wychodzi na wierzch do logowania, podpisu i na „pokaż przeglądarkę”; na koniec w rozmowie jest obraz przygotowanej strony. Programy Windows (nie strony) są obsługiwane w ich własnych oknach | testy + próba na prawdziwym Chromium z oknem (Linux); na Windows: NA-20 (2.8.0) |
| Logowanie i podpis zostają u notariusza | Agent nie klika logowania certyfikatem, nie wpisuje PIN-u ani hasła, nie podpisuje i nie płaci, także na polecenie: przygotowuje, pokazuje okno i czeka na „…, kontynuuj” | testy (2.8.0) |
| Chrome albo Edge | „używaj Chrome” / „używaj Edge”; każda przeglądarka w osobnym profilu NotarAI, gdy wybranej nie ma, program bierze drugą | testy (2.7.0); uruchomienie Chrome na Windows: NA-20 |
| Ikona | Ikona NotarAI na pulpicie, w menu Start i w instalatorze; stare skróty dostają ją same po aktualizacji | 2.6.0 |
| Konta i uprawnienia | Notariusz zdaniem: „dodaj osobę adres”, „zablokuj/odblokuj adres”, „adres nie może wysyłać poczty”, „konta”; nowa osoba dostaje e-mail z hasłem; uprawnienia wspólne dla stanowisk, sprawdzane kodem | testy + funkcja AWS notarai-v2-zespol (2.6.1) |
| Polecenia programu z rozmowy | AI zna polecenia programu (konta, stanowiska, kopie, telefon, poczta, kalendarz, rejestry…) i wykonuje je liniami „POLECENIE:” przez zwykłą ścieżkę z uprawnieniami; czynności odbierające coś (zablokuj, usuń, cofnij…) tylko jako przycisk do potwierdzenia; zdania o koncie/stanowisku dla sekretariatu rozpoznaje kod | testy (2.7.2) |
| Sprawa rozpoznawana sama | Bez wybierania sprawy: KW, KRZ i pytania trafiają do sprawy rozpoznanej po numerze księgi, PESEL albo nazwisku strony; gdy żadnej nie ma, wynik idzie do nowej sprawy nazwanej po numerze; foldery techniczne (procedury, styl, zasady) nie są na liście spraw | testy (2.7.3) |
| KRZ w tle | KRZ sprawdzany na krz.ms.gov.pl w osobnej przeglądarce bez okna (KRZ nie ma API); gdy w tle się nie uda, przycisk „Sprawdź w oknie przeglądarki”; księgi wieczyste zawsze przez API (funkcja notarai-v2-rejestry) | testy (2.7.3), na żywo do sprawdzenia |
| Agent pyta i się uczy | Gdy utknie (krok „pytanie” albo 3 błędy z rzędu, liczone kodem), pyta notariusza z 2-4 opcjami; odpowiedź (przycisk albo zdanie) wznawia pracę i od razu daje lekcję „📘 Nauczyłem się: …”; po pracy z błędami program sam proponuje wniosek do potwierdzenia; potwierdzone lekcje „komputer” trafiają do każdego następnego zadania agenta | testy (2.8.3) |
| Stop dla agenta | „stop”, „przerwij”, „zatrzymaj” przerywają każdą pracę agenta przed następnym krokiem i kasują „Kontynuuj”; zamknięcie okna stanowiska zatrzymuje agenta od razu (oraz po 150 s bez okna); programy i strony pomocy zdalnej/pulpitu zdalnego zablokowane kodem; agent nie uruchamia drugiej kopii działającego programu | testy (2.8.4) |
| KRZ w prawdziwym oknie i podgląd | KRZ blokuje przeglądarki bez okna: sprawdzanie idzie w przeglądarce NotarAI z oknem poza ekranem; w oknie NotarAI podgląd strony na żywo (KRZ i kroki agenta na stronach) i przycisk „Pokaż okno przeglądarki”; przy błędzie prawdziwa przyczyna zamiast „przeglądarka nie odpowiedziała” | testy (2.9.0), na żywo do sprawdzenia |
| KRZ przez Apify | KRZ najpierw przez Apify (osoba fizyczna i przedsiębiorca naraz, funkcja AWS), przeglądarka NotarAI tylko gdy Apify nie odpowie: wtedy każdy ruch opisany w rozmowie i obraz strony co sekundę; KW: Apify, potem Finance You; zamiast „Pracuję nad tym” bieżąca czynność | testy (2.9.1); Apify na żywo do sprawdzenia |
| Kalendarz z notarai.pl | Ten sam kalendarz w 2.0 i w wersji webowej, w obie strony, co 2 minuty i na „synchronizuj kalendarz”: terminy z sieci przychodzą, zmiany i usunięcia w sieci się powtarzają, nowe i usunięte tutaj idą do sieci; kolizję godzin zgłasza raz, termin zostaje w 2.0. Wymaga wdrożenia zmiany logowania wersji webowej (master) | testy |
| Kalendarz w oknie | Lewy pasek: miesiąc z zaznaczonymi dniami z terminami, dziś wyróżnione, kliknięcie dnia pokazuje jego terminy, „+ Dodaj termin” wpisuje wybraną datę | przeglądarka |
| Dyktowanie na żywo | 🎤: tekst pojawia się w polu wiadomości w trakcie mówienia (Transcribe we Frankfurcie, strumieniem, bez zapisu nagrania); ✕ anuluje, ■ zatrzymuje do poprawki, ↑ wysyła | testy + przeglądarka (z atrapą usługi mowy) |
| Kalendarz | Terminy zdaniem („termin w piątek 10:00 akt Kowalski”, „co mam jutro”), daty czyta kod; plan dnia na powitanie; terminy z podsłuchanych rozmów oznaczone „?”; zaszyfrowane w sejfie | testy + przeglądarka |
| Pliki w czacie | Spinacz, przeciągnij i upuść, wklej (Ctrl+V); od razu „Streść” i „Sprawdź błędy”; DOCX, PDF z tekstem, TXT, e-mail; nagrania przepisuje | testy + przeglądarka |
| Przewodnik pierwszego uruchomienia | 13 kroków w czacie: rozpoznanie komputera, pokaz możliwości, kod odzyskiwania (obowiązkowy, nie da się pominąć), logowanie, gdzie dane, kopia, folder aktów (okno Windows), nauka stylu, poczta, czynności „pokaż raz, potem automat”, pierwszy akt, Pocket na telefonie, mikrofony; krok zalicza się dopiero, gdy jest naprawdę zrobiony | testy + przeglądarka |
| Powitanie Pocket | Na nowym telefonie: dodanie do ekranu głównego (Android: przycisk instalacji, iPhone: instrukcja Safari), mikrofon, pliki, kalendarz | przeglądarka |
| Aktualizacje bez dużego instalatora | Program sam sprawdza co 6 h `aktualizacja.json` pod adresem pobierania, pobiera paczkę z kodem (setki KB), sprawdza rozmiar i SHA-256, rozpakowuje obok i podmienia przy następnym starcie (albo „Uruchom ponownie i zaktualizuj” w czacie). Nowe biblioteki = komunikat o pełnym instalatorze. Nieudana podmiana przywraca poprzednią wersję | testy; publikacja: paczka i opis z wydania GitHub do bucketu `notarai-v2-pobieranie` (opis jako ostatni) |
| Pierwszy ekran: rozpoznanie komputera | Poczta, Word/LibreOffice, przeglądarki, programy kancelaryjne (RejNET i in.), podpis kwalifikowany, programy urzędowe, foldery z aktami; przy każdym „Podłącz” | testy (na Windows: NA-20) |
| Pokaz możliwości | 14 kroków z ikoną, przykładem rozmowy i „Spróbuj”: kalendarz, dyktowanie, akty, pliki, EKW, KRZ, wnioski, programy kancelaryjne, poczta, taksa, telefon, nasłuch, zasady, bezpieczeństwo; także na telefonie | testy + przeglądarka |
| Poczta w oknie | Skrzynka jako lista, załączniki do sprawy z „Streść”/„Sprawdź błędy”, odpowiedź (projekt od asystenta, dyktowanie) otwierana w Outlooku/Thunderbirdzie do wysłania przez notariusza | testy (na żywo: NA-20) |
| Księgi wieczyste (EKW) | „sprawdź KW …” albo numer z dokumentów sprawy; funkcja AWS `notarai-v2-rejestry` uruchamia `ekw.py` z V1 (Apify; Finance You po dodaniu sekretu), token w Secrets Manager; wynik w tle do sprawy, porównanie z dokumentami | testy; funkcja sprawdzona na żywo (walidacja numeru), pobranie prawdziwej księgi: NA-20 |
| KRZ | „sprawdź strony w KRZ”: PESEL z dokumentów sprawy, `krz_portal.py` z V1 w przeglądarce NotarAI, zrzuty do sprawy, PESEL maskowany | testy (portal na żywo: NA-20) |
| Mądre uczenie | Z poprawek aktu asystent wyciąga 1-3 ogólne zasady stylu kancelarii (do potwierdzenia), dokładne poprawki zostają jako materiał; wielkie litery, interpunkcja i literówki nie są lekcjami (w dyktowaniu poprawiane po cichu); co trzy odpowiedzi na maile asystent opisuje styl odpowiedzi kancelarii | testy |
| Tryb uczenia | Widoczny przycisk 📘; lekcje z poprawek aktów, poprawek dyktowania (od razu poprawia kolejne dyktowanie), odpowiedzi na maile, „zapamiętaj:” i „to było źle:”; lista „czego się nauczyłeś”, usuwanie, wyłącznik; bez nazwisk i liczb, zaszyfrowane | testy + przeglądarka |
| Program mówi, co robi | W trakcie pracy kroki na żywo pod wiadomością („Rozumiem: pytanie o sprawę…”, „Czytam dokumenty (4)”, „Pytam asystenta we Frankfurcie…”), potem zwinięte „Jak to zrobiłem”; po odpowiedzi „Proponuję dalej” z 1-3 przyciskami | testy + przeglądarka |
| Polecenie = zatwierdzenie | „wyślij pocztę”, „odpowiedz na mail 2: …”, „wypełnij … i wyślij” wykonują się od razu (decyzja właściciela); „pytaj o potwierdzenie” przywraca „Tak / Nie”; zasady kancelarii (np. godziny wysyłki) sprawdzane zawsze | testy |
| Proponuję teraz | 2-3 następne kroki z tego, co widzi program: terminy, braki w sprawie (KW, KRZ, projekt aktu), poczta, lekcje do potwierdzenia, zaległa kopia; na powitanie i w lewym pasku | testy + przeglądarka |
| Kilka stanowisk w kancelarii | Każde stanowisko ma nazwę (krok przewodnika; widać, skąd polecenie i wiadomość). „połącz drugie stanowisko” daje kod, „dołącz do kancelarii …” łączy; co 5 s wymiana zmian w sieci kancelarii (port 47321), zaszyfrowana kluczem kancelarii (AES-GCM, okno czasu, bez powtórzeń): dokumenty, kalendarz, lekcje, wiadomości, usunięcia; równoległa edycja = osobny dokument „(konflikt)” | testy na dwóch stanowiskach w jednym procesie; na dwóch prawdziwych komputerach: NA-21 |
| Komunikator zamiast Gadu-Gadu | „napisz do Sekretariat: …”, „wiadomości”; termin w wiadomości proponowany do kalendarza; nowe wiadomości w „Proponuję teraz” | testy |
| Drukarki i podgląd ekranu | „drukarki” (oba stanowiska), „wydrukuj umowa w gabinecie”; „pokaż ekran Sekretariat” tylko po „zezwól na podgląd ekranu” na tamtym komputerze | testy (druk i zrzut ekranu Windows: NA-21) |
| Drukarki i skanery sieciowe | „znajdź drukarki”: urządzenia ogłaszające się w sieci (mDNS: IPP, eSCL/AirScan) i zainstalowane w Windows na każdym stanowisku; „nazwij drukarkę … jako Sekretariat” (nazwy wspólne dla stanowisk); „wydrukuj umowa na drukarce Sekretariat” (IPP bez sterownika, DOCX przez Worda do PDF); „zeskanuj na skanerze Gabinet [w kolorze] [z podajnika]” do sprawy jako PDF | testy na atrapach; wykrywanie sprawdzone tu bez urządzeń; na żywo: NA-21 |
| Mikrofony całej kancelarii | „mikrofony”: ostatnie notatki i stenopisy z mikrofonów wszystkich stanowisk | testy |
| Tryb serwisowy | „popraw program: …” / „zmień program: …”: prośba bez nazwisk (wszystkich stron), numerów i e-maili → zdarzenie `notarai.v2.serwis` (stos `notarai-v2-serwis`) → kolejka dla potoku samonaprawy i e-mail do właściciela; „moje zgłoszenia”; „Twoja zmiana już działa”, gdy aktualizacja zamyka zgłoszenie | testy; droga w AWS sprawdzona na żywo (zdarzenie → kolejka i e-mail). Etap 2: potok samonaprawy robi zmianę V2 i publikuje aktualizację - do zrobienia |
| Szata graficzna | Kolory, czcionka Montserrat (w programie, bez internetu) i sygnet jak notarai.pl | przeglądarka |
| Program na pulpicie | Ikona „NotarAI” otwiera własne okno (bez paska adresu, bez logowania kodem), worker działa w tle i startuje z Windows; odświeżenie okna nie rozłącza | testy + budowa i próba instalatora w CI Windows |
| Twarde zasady kancelarii | Zasady ustawiane zdaniem („zasada: …”), pilnowane przez kod przy zapisie projektu, zapisie z Worda, wysyłce formularza i zmianie ustawień; małe okienko „Zasady kancelarii” w nagłówku | testy + przeglądarka |
| Styl kancelarii | „naucz się stylu kancelarii” czyta akty na dyskach stanowiska (DOCX, ODT, RTF, TXT) i zapamiętuje powtarzalne sformułowania i układ, bez danych klientów; projekty piszą tymi sformułowaniami | testy na fikcyjnym dysku |
| Stały nasłuch | Mikrofony (tablet, telefon, komputer) sparowane jako „mikrofon”; stenopis odczytanego aktu trafia do sprawy, z rozmów i telefonów powstają notatki z terminem i kontaktem | testy + przeglądarka (zastępczy mikrofon) |
| Uczenie przez pokazanie | Nagranie ekranu z komentarzem zamienia się w procedurę do zatwierdzenia; dla sprawy powstają wartości do każdego pola z przyciskiem „Kopiuj” | testy + przeglądarka + próba na żywo z Bedrock |
| Telefon w kancelarii | Pocket w przeglądarce, uprawnienia odczyt/zapis i per sprawa | przeglądarka |
| Telefon poza kancelarią | Parowanie kodem QR, szyfrowanie od telefonu do komputera, klucz nie opuszcza telefonu | przeglądarka przez lokalny przekaźnik |
| Panel stanowiska | Kod odzyskiwania, kopie, urządzenia, logowanie do AI, dziennik, zużycie | przeglądarka |

## Instalator

Pobieranie bez logowania (stos `notarai-v2-pobieranie`: prywatny bucket w eu-central-1 + CloudFront, tylko plik
instalatora, żadnych danych kancelarii):
https://daw6bv5zhb6ck.cloudfront.net/NotarAI-V2-Setup-x64.exe

Najnowszy przetestowany instalator z CI (po zalogowaniu na GitHubie):
https://github.com/plnyspolka-pixel/notarai/releases/download/notarai-v2-podglad/NotarAI-V2-Setup-x64.exe

CI podmienia plik na GitHubie przy każdej udanej budowie; pod adresem CloudFront plik podmienia się ręcznie
(`aws s3 cp NotarAI-V2-Setup-x64.exe s3://notarai-v2-pobieranie-<konto>/`), bo GitHub nie ma kluczy AWS.

## Jak się tego używa

Asystent to ten sam czat: bez wybranej sprawy odpowiada na pytania ogólne, z wybraną sprawą na podstawie jej
dokumentów. Nie ma osobnego włączania AI; jeśli stanowisko nie jest zalogowane do NotarAI, formularz
logowania pojawia się w czacie.

Jedno okno rozmowy, w Pocket i w panelu stanowiska. Piszesz zwykłym zdaniem, bez tabel i formularzy:

- „nowa sprawa kowalski-2026”, „dokumenty”, „otwórz umowa”
- „strony: Jan Kowalski, Anna Nowak” (zapamiętane w sejfie dla sprawy, na każdym urządzeniu)
- „kto jest sprzedającym?”, „przygotuj umowę sprzedaży lokalu”
- „policz taksę od sprzedaży lokalu za 500 tys.”
- w panelu: „zrób kopię”, „kod odzyskiwania”, „dodaj telefon tylko do odczytu dla sprawy kowalski-2026”,
  „cofnij telefon”, „kto czytał umowa?”, „otwórz umowa w Wordzie”, „zapisz do sejfu”,
  „wyłącz pseudonimizację”, „włącz dostęp spoza kancelarii”

- kafelki: „narzędzia”, „dodaj kafelek Taksa”, „dodaj kafelek Pełnomocnictwo KW: przygotuj pełnomocnictwo…”, „ukryj kafelki”
- poczta (panel): „połącz pocztę”, „poczta”, „maile od Kowalskiego”, „dodaj mail 2 do sprawy”
- procedury: „nagraj procedurę Wniosek o wpis w KW” (panel), potem na każdym urządzeniu „wypełnij wniosek o wpis w KW”

### Twarde zasady kancelarii

Notariusz pisze w panelu np. „zasada: każdy akt musi zawierać „Notariusz pouczył strony…””, „zasada: nigdy
„Szanowny Panie””, „zasada: wysyłka tylko w dni robocze od 8 do 15”, „zasada: przed wysłaniem pole
„PESEL wnioskodawcy” musi być wypełnione”, „zasada: pseudonimizacja zawsze włączona”. Program przyjmuje tylko
zasady, które umie sprawdzić kodem; inne odrzuca i mówi dlaczego, zamiast udawać, że ich pilnuje. Model widzi
wymagane sformułowania, żeby projekt był od razu zgodny, ale o zapisie i wysyłce decyduje sprawdzenie w kodzie.

### Stały nasłuch

1. W panelu: „włącz nasłuch” (z potwierdzeniem i przypomnieniem o obowiązku informacyjnym RODO).
2. „dodaj mikrofon Sekretariat”, „dodaj mikrofon Gabinet”: kod albo QR otwiera na tablecie lub telefonie ekran
   mikrofonu. Urządzenie zostaje na ładowarce; przesyła fragmenty z dźwiękiem, ciszy nie wysyła.
3. Mowę przepisuje Amazon Transcribe we Frankfurcie (nagranie kasowane zaraz po przepisaniu). Rozmowa, która pokrywa się z aktem w którejś sprawie, staje się
   stenopisem tej sprawy; pozostałe (wizyty, telefony słyszane w pokoju) stają się notatkami w sprawie
   „sekretariat” z podsumowaniem, terminem i kontaktem. Dźwięk nie jest przechowywany.
4. „nasłuch”, „wstrzymaj nasłuch”, „wznów nasłuch”, „notatki z rozmów”, „stenopisy”.

### Jak notariusz pracuje z formularzami

1. Raz na każdy rodzaj wniosku pokazuje go programowi: „nagraj procedurę Wniosek o wpis w KW”.
2. Dla każdej sprawy pisze w panelu „wypełnij wniosek o wpis w KW”. Program bierze dane z dokumentów
   sprawy, sam otwiera stronę albo znajduje okno programu, wpisuje wartości, sprawdza każde pole
   odczytem i zatrzymuje się przed wysłaniem.
3. Notariusz czyta zrzut wypełnionego formularza w czacie (albo sam formularz na ekranie) i dotyka
   „Wyślij teraz”. Jeśli w międzyczasie coś zmienił w formularzu, program pokaże go jeszcze raz.

Na stronach program używa własnego okna przeglądarki (Edge z osobnym profilem): notariusz loguje się
tam raz do portali i logowanie zostaje. W programach Windows działa przez to samo, z czego korzystają
czytniki ekranu, więc nie potrzeba osobnej integracji z każdym programem.

### Jak działa łączenie z dowolnym programem

Zamiast osobnej integracji dla każdego programu i każdej strony urzędowej notariusz pokazuje czynność raz:
włącza nagrywanie, wypełnia formularz (najlepiej na przykładowej sprawie) i mówi, co wpisuje i dlaczego. Z kilku ujęć ekranu
i komentarza powstaje procedura (pole, skąd wartość, powód), którą notariusz poprawia i zatwierdza. Dla kolejnych
spraw program przygotowuje gotowe wartości do skopiowania. Wpisuje albo wkleja je notariusz, więc działa to
w każdym programie i nic nie zostaje wysłane bez jego wiedzy. Samodzielne klikanie w programach to następny,
osobny krok (niżej).

Polecenia zmieniające stan rozpoznaje program według stałych sformułowań, nie model. Rzeczy
nieodwracalne (cofnięcie urządzenia, porzucenie zmian, nowy kod) wymagają potwierdzenia przyciskiem.
Pseudonimizacja jest ustawieniem kancelarii: domyślnie włączona, wyłączasz ją jednym zdaniem.

## Co jest utworzone w AWS (eu-central-1, 27.11.2026, za zgodą właściciela)

| Stos | Co zawiera | Dane |
| --- | --- | --- |
| `notarai-v2-bedrock` | logowanie stanowisk do AI; dostęp tylko dla kont z grupy `notarai-v2` | żadnych |
| `notarai-v2-przekaznik` | przekaźnik dla telefonu: `wss://qj7nel6in9.execute-api.eu-central-1.amazonaws.com/v1` | identyfikatory połączeń, 3 godziny |
| `notarai-v2-kopia` | bucket `notarai-v2-kopie` na kopie poza kancelarią | zaszyfrowane kopie, klucz ma tylko kancelaria |

Żeby kancelaria mogła używać AI, jej konto trzeba dodać do grupy `notarai-v2` w puli logowania.
Adresy tych usług instalator wpisuje sam (`installer/preset.json`); wszystko pozostaje wyłączone,
dopóki notariusz tego nie włączy.

## Czego nie dało się sprawdzić stąd

- Instalator Windows i usługa Windows: zmieniłem je, ale testy Windows uruchamia dopiero GitHub po otwarciu pull requesta.
- Przekaźnik w AWS: stos działa, funkcja przyjęła prawdziwy podpis stanowiska i odrzuciła fałszywy oraz powtórzony;
  pełnej próby telefon–przekaźnik–stanowisko stąd nie wykonałem, bo to środowisko nie przepuszcza WebSocket.
  Uruchom z własnego komputera: `python tests/live_relay.py wss://qj7nel6in9.execute-api.eu-central-1.amazonaws.com/v1`.
- Logowanie stanowiska przez Cognito: przetestowane na atrapie; próba na żywo wymaga konta w grupie `notarai-v2`.
- Outlook: napisany pod klasycznego Outlooka i sprawdzony na atrapie; na prawdziwym Outlooku nie był uruchomiony.
  Nowy Outlook nie ma interfejsu automatyzacji, tam zostaje folder z plikami .eml.
- Rozpoznawanie mowy: domyślnie chmura (Amazon Transcribe, eu-central-1), strumieniem: tekst po kilku sekundach.
  Tryb wsadowy (zapas, gdy sieć blokuje strumień) sprawdzony na żywo: ok. 1,5-2 min na notatkę. Strumienia
  stąd nie dało się sprawdzić do końca (to środowisko nie ma poświadczeń stanowiska); kod dochodzi do usługi
  we Frankfurcie i dostaje odmowę wyłącznie z powodu brakującego logowania. Koszt ok. 0,10 zł za minutę nagrania. Do chmury potrzebne jest zalogowanie
  stanowiska kontem z grupy `notarai-v2`. Wariant lokalny (`faster-whisper`, model 0,5 GB) można włączyć
  ustawieniem `speech.where = lokalnie`, ale obciąża komputer kancelarii.
- Wypełnianie programów Windows: test na prawdziwym oknie WinForms działa w CI na Windows; programów
  kancelaryjnych (np. RejNET) nie sprawdzałem, bo nie mam do nich dostępu.
- Nagrywanie ekranu: sprawdzone w Chromium na zastępczym obrazie ekranu, nie na prawdziwym pulpicie Windows.
- Microsoft Word: przetestowane z LibreOffice; z Wordem mechanizm jest ten sam (plik i blokada `~$`), ale nie był uruchomiony.

## Do sprawdzenia na miejscu (nasłuch)

- Jakość rozpoznawania mowy z mikrofonu w pokoju zależy od sprzętu; dobry mikrofon konferencyjny na biurku
  zamiast mikrofonu tabletu wyraźnie pomaga. Rozmowy telefonicznej program słyszy tylko stronę kancelarii,
  chyba że rozmowa idzie przez głośnik.
- Model „small” na zwykłym procesorze przepisuje mniej więcej w czasie rzeczywistym; przy kilku mikrofonach
  naraz kolejka może rosnąć w ciągu dnia i nadrabiać po godzinach.
- Obowiązek informacyjny (RODO, art. 13) i zgoda zespołu na nagrywanie w pokojach: decyzja i wzór informacji
  po stronie kancelarii.

## Decyzje dla właściciela

1. **Strona Pocket pod `notarai.pl/pocket/`**: pull request #155 do `master`; po scaleniu publikuje ją
   workflow strony. Po zmianach w Pocket na tej gałęzi trzeba odświeżyć pliki: `python tools/export_pocket.py`.
2. **Prawdziwe dane**: nadal zablokowane. Warunki zwolnienia blokady są w README („Release gates”).

## Co zostaje do zrobienia

- Maskowanie danych na zrzutach ekranu wysyłanych przy nauce procedury.
- Próba wypełniania na prawdziwym programie kancelaryjnym i prawdziwym portalu (z kontem testowym;
  patrz `docs/czeka-na-dostep.md`).
- Podpis instalatora i kanał aktualizacji (wymaga certyfikatu do podpisu kodu).
- RejNET i inne programy kancelarii przez automatyzację okien (wymaga dostępu do środowiska testowego; patrz `docs/czeka-na-dostep.md`).
- Rozliczanie zużycia AI po stronie NotarAI (dziś licznik jest lokalny, na stanowisku).
- Niezależny przegląd bezpieczeństwa przed pierwszymi prawdziwymi danymi.


## Dane prawdziwe: co musi zrobić kancelaria (decyzja z 27.11.2026)

Program przetwarza dane klientów wyłącznie w UE (Frankfurt), w zaszyfrowanym sejfie na komputerze, a do
modelu AI wysyła je po pseudonimizacji. Po stronie kancelarii jako administratora danych zostaje:
- umowa powierzenia przetwarzania z AWS (DPA AWS, akceptowana w koncie) i z Finance You / Apify dla treści KW,
- wpis w rejestrze czynności przetwarzania (AI w UE, przepisywanie mowy, kopie we Frankfurcie, KW, KRZ),
- obowiązek informacyjny dla klientów, zwłaszcza przy stałym nasłuchu i nagrywaniu rozmów,
- ocena skutków (DPIA) dla nasłuchu i automatycznego przetwarzania, jeśli inspektor ochrony danych uzna ją za potrzebną.
