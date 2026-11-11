# notarai - baza wiedzy asystenta głosowego

## Czym jest notarai
notarai (notarai.pl) to aplikacja dla kancelarii notarialnych - asystent kancelarii z AI.
Dostawca: Fundacja Krzewienia Edukacji Finansowej im. Pieczaka. Kontakt: kontakt@notarai.pl.
Działa w przeglądarce pod adresem app.notarai.pl. Każdy wynik to projekt - decyzje podejmuje notariusz.

Co robi dla kancelarii:
- Odczyt skanów (dowody, wypisy, odpisy z księgi wieczystej) i projekt aktu w Wordzie na własnym wzorze kancelarii. Pola niepewne, z błędną sumą kontrolną PESEL lub NIP albo bez danych są oznaczone na czerwono, braki zostają w tekście jako widoczne znaczniki.
- Poprawki zwykłym językiem ("dodaj pełnomocnika", "zmień sposób zapłaty").
- "Klikamy za Ciebie": pomocnik na Windows przechodzi formularze w portalach rejestrów w prawdziwej przeglądarce Chrome na komputerze kancelarii. Zatrzymuje się przed przyciskami wyślij, podpisz, zapłać, usuń; nie wpisuje haseł ani PIN-ów; działa tylko na zatwierdzonych stronach.
- Sprawdzenia w rejestrach (KRZ, księgi wieczyste, AML - listy sankcyjne i PEP, CRBR - beneficjenci rzeczywiści) zapisywane w sprawie ze zrzutem ekranu (ślad audytowy).
- Księgi kancelarii (repertorium A i inne), zgłoszenia GIIF, poświadczenia kopii ze zdjęcia lub skanu.
- Kalendarz kancelarii, telefony stron, zapytania klientów ze strony notarai.pl w panelu "Zapytania klientów".
- Rezerwacje B2B przez API i MCP dla biur nieruchomości, deweloperów i firm - tylko w kancelariach, które się na to zgodziły.
- Konta dla całego zespołu, sesja do 30 dni na zaufanym komputerze.

Czego notarai nie robi: nie tworzy dokumentu gotowego do podpisu bez sprawdzenia notariusza, nie loguje się za kancelarię do systemów urzędowych, nie składa, nie podpisuje i nie wysyła wniosków w imieniu kancelarii. Nie jest repertorium ani archiwum notarialnym.

## Cena i start
- Jeden abonament dla całej kancelarii: 600 zł miesięcznie. Fundacja jest zwolniona z VAT, więc 600 zł to cała kwota.
- Płatność kartą, co miesiąc z góry; faktura przychodzi e-mailem.
- 14 dni na wypróbowanie za darmo, bez karty płatniczej na start.
- Rejestracja samodzielnie na notarai.pl (przycisk "Załóż konto"). Umowę powierzenia przetwarzania danych i Regulamin akceptuje się przy rejestracji, bez papierów.

## Bezpieczeństwo i RODO (dla kancelarii)
- Dane wyłącznie w Unii Europejskiej: sprawy w AWS we Frankfurcie, model AI (Claude w Amazon Bedrock) w regionach UE: Frankfurt, Irlandia, Paryż, Sztokholm.
- Model niczego nie zapamiętuje: rejestrowanie wywołań w Bedrock wyłączone, AWS nie używa treści do trenowania.
- Opcja "pliki tylko u kancelarii" - sprawy zapisują się w folderze na komputerze kancelarii.
- Szyfrowanie AES-256, transmisja TLS, wersjonowanie plików, kopia zapasowa wygasa po 21 dniach.
- W logach nie ma PESEL, nazwisk, adresów ani treści dokumentów.
- Usunięcie sprawy od razu kasuje skany, odczyty i projekt.
- Role: kancelaria = administrator danych; Fundacja = podmiot przetwarzający (art. 28 RODO); AWS = dalszy podmiot przetwarzający. Zobowiązanie do tajemnicy w zakresie art. 18 Prawa o notariacie.
- Gotowa ocena skutków (DPIA) w aplikacji, wzór klauzuli informacyjnej i wpis do rejestru czynności przetwarzania.

## Dla klientów kancelarii (osób szukających notariusza)
- Na notarai.pl bezpłatnie: kalkulator kosztów czynności (taksa, wypisy, PCC, opłaty sądowe), wykaz kancelarii według miejscowości, mapa kancelarii i prośba o wizytę.
- Kwoty są szacunkowe - liczone według maksymalnych stawek z rozporządzenia o taksie notarialnej. Notariusz może przyjąć niższą taksę; dokładną kwotę potwierdza kancelaria.
- Kolejność kancelarii jest neutralna: pasma odległości i codzienna rotacja. Abonament ani konto w notarai nie dają lepszego miejsca. Zasady są publiczne (strona przejrzystości).
- Prośba o wizytę to prośba o kontakt - kancelaria oddzwoni albo potwierdzi termin. Niektóre kancelarie przyjmują rezerwację online konkretnej godziny; wtedy klient dostaje e-mail z potwierdzeniem i linkiem do odwołania (najpóźniej 2 godziny przed wizytą), a dzień wcześniej przypomnienie.
- Gdy klientowi wszystko jedno, która kancelaria: zapytanie trafia do kancelarii w miejscowości, a te, które się nim zajmą, zwykle odpowiadają w ciągu godziny.

## Podstawowe pojęcia (do wyjaśniania klientom, bez porad prawnych)
- Taksa notarialna: wynagrodzenie notariusza, maksymalne stawki określa rozporządzenie; do taksy dolicza się 23% VAT.
- PCC: podatek od czynności cywilnoprawnych, przy sprzedaży zwykle 2% wartości; pobiera go notariusz. Darowizna w najbliższej rodzinie zwykle bez PCC.
- Wypisy aktu: płatne kopie aktu dla stron i urzędów.
- Wniosek o wpis w księdze wieczystej składa notariusz; opłaty sądowe za wpis pobiera notariusz.
- Akt poświadczenia dziedziczenia (APD): u notariusza zamiast sprawy w sądzie, gdy spadkobiercy są zgodni; potrzebne m.in. odpis aktu zgonu i akty stanu cywilnego.
- I grupa podatkowa: małżonek, zstępni (dzieci, wnuki), wstępni (rodzice, dziadkowie), pasierb, rodzeństwo, ojczym, macocha, teściowie, zięć, synowa.
