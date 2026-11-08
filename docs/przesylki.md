# Przesyłki i korespondencja

Widok **Przesyłki i korespondencja** (menu „Narzędzia”) zastępuje papierowe
prowadzenie dwóch ksiąg notarialnych i pocztowej książki nadawczej.

## Podstawa prawna

Rozporządzenie Ministra Sprawiedliwości z 12.04.1991 r. w sprawie prowadzenia
ksiąg notarialnych oraz przekazywania na przechowanie dokumentów sądom
rejonowym (t.j. Dz.U. 2018 poz. 2039):

- § 1 ust. 1 pkt 4 i 5: dziennik przesyłanych dokumentów i dziennik
  korespondencyjny to **dwie osobne księgi**. W aplikacji leżą w dwóch
  osobnych plikach i każda ma własną numerację.
- § 5 ust. 1: do dziennika przesyłanych dokumentów wpisuje się wnioski
  i pisma przesyłane z urzędu sądom i innym organom państwowym.
- § 5 ust. 2: do dziennika korespondencyjnego wpisuje się inne pisma,
  wysyłane i wpływające.
- § 1 ust. 5: tych dzienników **nie** prowadzi się w okresach rocznych, więc
  numeracja pozycji biegnie dalej po Nowym Roku.
- § 1 ust. 6: księgi mają być oprawione, a strony ponumerowane. Stąd wydruk
  PDF z numeracją stron, którą kolejny wydruk kontynuuje.
- § 1 ust. 7: poprawka nie może usuwać treści pierwotnej. Wpisów nie
  kasujemy: poprawka trafia do historii pozycji i do rubryki „Uwagi” na
  wydruku („było: …”), a anulowana pozycja jest przekreślona.

Rozporządzenie nie podaje wzoru rubryk. Kolumny wydruku są zdefiniowane
w `przesylki.py` (`KOLUMNY`) i łatwo je dopasować do wzoru używanego
w danej izbie notarialnej.

## Jak się z tego korzysta

1. Dodaj pozycję: data, nr repertorium, adresat i adres, sposób przesłania.
   Adres urzędu podpowiada się z poprzednich wpisów.
2. Zaznacz pozycje i wydrukuj **koperty** (DL, C5, C6, C4): nadawca w lewym
   górnym rogu, adresat w prawej dolnej części, napis „POLECONY” i „ZA
   POTWIERDZENIEM ODBIORU”.
3. Wydrukuj **pocztową książkę nadawczą** na dany dzień. Zestawienie obejmuje
   listy polecone z obu dzienników, a w uwagach ma odsyłacz do pozycji
   (DPD 12, DK 4).
4. Po powrocie z poczty wpisz **numery nadania** z naklejek w tabeli. Czytnik
   kodów kreskowych działa jak klawiatura: numer i Enter zapisują pozycję,
   a kursor przechodzi do następnej.
5. Po otrzymaniu zwrotki wpisz datę doręczenia. Link „śledź” otwiera status
   przesyłki na stronie Poczty Polskiej.
6. Co jakiś czas wydrukuj księgę do oprawy (A4 poziomo, nagłówek tabeli na
   każdej stronie, numer strony w stopce).

Dane nadawcy (nazwa i adres kancelarii) ustawia się raz, na dole widoku.

## Poczta Polska: umowa i nadawanie z aplikacji

Okno „Poczta Polska” w widoku Przesyłki prowadzi kancelarię przez trzy kroki
(`poczta_polska.py`).

1. **Wniosek o umowę.** Umowy z Pocztą nie da się zawrzeć przez API: zawiera
   ją przedstawiciel handlowy. Aplikacja wypełnia wniosek danymi z rejestracji
   w notarai i proponuje trzy sposoby wysłania:
   - PDF do podpisu,
   - gotowy e-mail do Poczty (kontakt@poczta-polska.pl),
   - oficjalny formularz sprzedażowy Poczty z treścią prośby w schowku.

   Prośba obejmuje: przesyłki polecone z potwierdzeniem odbioru, konto
   w Elektronicznym Nadawcy z dostępem do WebAPI, EPO (opcjonalnie) i
   wyłączenie wymuszonej zmiany hasła dla konta WebAPI. Dokumentacja WebAPI
   mówi, że takie ustawienie zmienia tylko Poczta.
2. **Umowa.** Przedstawiciel się odzywa, podpisane oryginały wracają pocztą
   (Poczta sprawdza firmę w BIG), a potem przychodzi e-mail z loginem
   i hasłem. Kancelarie podają, że trwa to 3–6 tygodni.
3. **Połączenie.** Kancelaria wkleja login i hasło. Aplikacja sprawdza je
   jedną próbą (metoda `hello`), bo kilka błędnych prób blokuje konto. Potem:
   - zapisuje login i hasło w AWS Secrets Manager (`notarai-poczta-<kancelaria>`),
   - pobiera urzędy nadania i karty umowy.

   Hasło nigdy nie wraca do przeglądarki.

Po połączeniu, w tabeli wpisów:

- **Nadaj w e-Nadawcy** (`getGuid` + `addShipment`): numer nadania wpisuje się
  do księgi sam, jako uzupełnienie, a nie poprawka;
- **Etykiety z kodem** (`getPrintForParcel`, ADDRESS_LABEL);
- **Wycofaj z bufora** (`clearEnvelopeByGuids`);
- **Wyślij zbiór na pocztę** (`sendEnvelope`), a zaraz po nim książka nadawcza
  z Poczty (`getOutboxBook`). e-Nadawca przyjmuje zbiór tylko z przesyłek
  dodanych tego samego dnia, więc aplikacja pilnuje tego przed wysłaniem;
- **Sprawdź doręczenia** (`getEPOStatus`): daty doręczeń z EPO trafiają do
  księgi;
- **Zmień hasło automatycznie** (`changePassword`): nowe hasło zapisuje się
  w sejfie przed wywołaniem Poczty, więc nie ginie przy awarii.

WebAPI: SOAP 1.1, HTTP Basic, adresy z dokumentacji WebAPI w97:

- produkcja: `https://e-nadawca.api.poczta-polska.pl/websrv/`
- integracja: `https://int-e-nadawca.api.poczta-polska.pl/websrv/` (osobny
  login od Poczty; do wyboru w kroku 3 jako „środowisko testowe”).

Bez połączenia nadal działają koperty, papierowa książka nadawcza, eksport
CSV do e-Nadawcy i link „śledź”.

Wdrożenie: rola zadania ECS dostała politykę `sekrety-poczty-polskiej`
(Secrets Manager, tylko `notarai-poczta-*`) w `infra/notarai-aplikacja.yaml`.
Trzeba zaktualizować stos, zanim pierwsza kancelaria się połączy.

## Dane osobowe

Adresatami bywają osoby fizyczne. Dzienniki leżą w obszarze kancelarii
(`kancelarie/{id}/dziennik_*.json`, w S3 szyfrowane, w UE). Nazwy ani adresy
nie trafiają do logów. Kancelaria, która trzyma pliki u siebie, nie ma tego
widoku, bo serwer nie zapisuje jej danych.
