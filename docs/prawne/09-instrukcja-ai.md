# NOTARAI - INSTRUKCJA KORZYSTANIA Z FUNKCJI SZTUCZNEJ INTELIGENCJI

Wersja z dnia 24.10.2026.

Instrukcja, o której mowa w § 4 ust. 5 Regulaminu. Służy do zapewnienia
kompetencji w zakresie sztucznej inteligencji osobom korzystającym z notarai
w kancelarii (art. 4 rozporządzenia (UE) 2024/1689 - AI Act). Aplikacja
pokazuje ją każdej osobie przy pierwszym logowaniu (pkt 8).

## 1. Co robi model, a czego nie

notarai korzysta z modelu językowego Claude uruchomionego w Amazon Bedrock
w regionach Unii Europejskiej. Model:

- odczytuje treść skanów i plików i wypisuje dane potrzebne do czynności,
- wypełnia wzór aktu kancelarii odczytanymi danymi,
- odpowiada na pytania i wprowadza poprawki w rozmowie o sprawie,
- proponuje wartości do formularzy rejestrowych na podstawie treści aktu,
- w sekcji Klikamy prowadzi przeglądarkę w portalach rejestrów według
  polecenia użytkownika.

Model **nie** zna stanu prawnego sprawy poza dokumentami, które wgrasz. Nie
weryfikuje autentyczności dokumentów ani tożsamości osób. Nie ocenia
zdolności do czynności prawnych ani zgodności czynności z prawem. Wszystko,
co zwraca, jest propozycją, którą notariusz sprawdza z dokumentami
źródłowymi.

## 2. Typowe błędy modelu

1. **Pomylone cyfry.** Zamiana podobnych znaków (3 i 8, 1 i 7, 0 i O, 5 i S)
   w PESEL, numerach dowodów, numerach ksiąg wieczystych, numerach działek,
   kwotach i datach. Sumy kontrolne wychwytują część takich błędów w PESEL,
   NIP i numerach KW. Nie wychwytują ich w numerach działek, datach,
   kwotach ani numerach dokumentów tożsamości.
2. **Pismo odręczne i słaba jakość skanu.** Wpisy odręczne, pieczątki,
   przekreślenia i ciemne kopie są odczytywane gorzej. Model powinien wtedy
   oznaczyć niską pewność, ale nie zawsze to robi.
3. **Pomylenie osób.** Przy kilku stronach, małżonkach albo pełnomocnikach
   dane jednej osoby mogą trafić do innej, np. imiona rodziców albo adres.
4. **Odmiana i pisownia.** Błędna odmiana imion i nazwisk przez przypadki,
   utrata polskich znaków, nietypowe nazwiska „poprawione” na popularne.
5. **Uzupełnianie z domysłu.** Model ma instrukcję, by przy braku danych
   zostawiać znacznik zamiast zgadywać. Mimo to może podać wartość
   prawdopodobną, a nie wynikającą z dokumentu.
6. **Nieaktualne dokumenty.** Model nie wie, czy odpis z księgi wieczystej
   albo zaświadczenie jest aktualne. Odczytuje to, co jest na skanie.
7. **Zmiany w rozmowie.** Poprawka zgłoszona w rozmowie może zmienić także
   inne miejsca projektu albo pominąć któreś z miejsc, które powinna zmienić.
8. **Pominięte strony lub wpisy.** Przy dużych sprawach model może pominąć
   wpis, np. w dziale III lub IV księgi wieczystej.

## 3. Jak notarai pomaga wychwycić błędy

- Pola z błędną sumą kontrolną, niską pewnością odczytu albo bez danych są
  oznaczone czerwoną krawędzią na ekranie weryfikacji odczytu.
- Miejsca, których nie dało się wypełnić, zostają w projekcie jako
  `<<BRAK: nazwa pola>>`. Miejsca wymagające decyzji notariusza zostają jako
  `<<WYBOR: opis>>`.
- Propozycje wartości do formularzy pokazują cytat z aktu, z którego
  pochodzą.
- Plik projektu w Wordzie ma w metadanych informację, że powstał z użyciem
  AI.

Brak oznaczenia nie oznacza, że wartość jest poprawna.

## 4. Obowiązkowe sprawdzenie przed użyciem

Przed wykorzystaniem odczytu albo projektu notariusz lub upoważniony
pracownik:

1. porównuje z dokumentem źródłowym **każdy** numer: PESEL, numer i seria
   dokumentu tożsamości, numer księgi wieczystej, numer działki, NIP, REGON,
   KRS, numer rachunku,
2. porównuje imiona, nazwiska, imiona rodziców, adresy i daty,
3. sprawdza kwoty, cenę i sposób zapłaty, także zapisane słownie,
4. usuwa z projektu wszystkie znaczniki `<<BRAK>>` i `<<WYBOR>>`,
5. czyta projekt w całości, a nie tylko miejsca zmienione,
6. po każdej poprawce z rozmowy sprawdza ponownie cały projekt.

## 5. Klikamy i pomocnik

- Do portali rejestrów logujesz się samodzielnie. Pomocnik nie wpisuje
  niczego w pola haseł i PIN-ów. Nie przekazuj nikomu, także Fundacji,
  haseł ani kart do systemów urzędowych.
- Pomocnik rozpoznaje przyciski wysyłania, składania, podpisu, płatności
  i usuwania po ich opisie i ich nie klika. Rozpoznanie działa na podstawie
  nazwy przycisku i **może zawieść**, gdy portal nazwie przycisk nietypowo,
  np. „Dalej” na ostatnim kroku wniosku. Obserwuj okno przeglądarki
  i przerwij pracę, jeśli agent robi coś, czego nie oczekujesz.
- Agent nie przechodzi na strony spoza adresów, na które się zgodzisz, i
  wykonuje najwyżej 20 kroków na jedno polecenie.
- Przed wysłaniem lub podpisaniem czegokolwiek w portalu sprawdź samodzielnie
  wszystkie pola formularza.
- Wynik sprawdzenia w rejestrze zapisuje się w sprawie ze zrzutem ekranu.
  Zrzut pokazuje stan w chwili sprawdzenia.

## 6. Dane, które wgrywasz

- Wgrywaj wyłącznie dokumenty potrzebne do danej czynności.
- Nie wgrywaj dokumentów, które zawierają dane o zdrowiu, wyroki albo inne
  dane szczególnie chronione, jeżeli nie są potrzebne do czynności.
- Usuwaj sprawy z notarai po zakończeniu czynności albo w terminie
  ustalonym w kancelarii. notarai nie jest repertorium ani archiwum
  notarialnym.

## 7. Zgłaszanie problemów

Błędny odczyt, który nie został oznaczony, albo nieoczekiwane działanie
pomocnika zgłoś na kontakt@notarai.pl. Opisz problem bez danych osobowych
klientów: identyfikator sprawy, numer strony, rodzaj pola i rodzaj błędu.

## 8. Potwierdzenie zapoznania

Każda osoba potwierdza zapoznanie się z instrukcją w aplikacji, przy
pierwszym logowaniu, przyciskiem **Przeczytałam / przeczytałem**. Podpis
nie jest potrzebny. Data potwierdzenia jest zapisywana przy koncie, a
Właściciel widzi ją w oknie Zespół kancelarii. Po istotnej zmianie
instrukcji aplikacja prosi o ponowne potwierdzenie.
