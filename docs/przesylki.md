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

## Poczta Polska

Teraz:

- eksport zaznaczonych listów poleconych do CSV (UTF-8, separator `;`) do
  importu w aplikacji **Elektroniczny Nadawca**. Szablon importu (przypisanie
  kolumn) ustawia się w e-Nadawcy raz. Kolumna `identyfikator_nadawcy` niesie
  odsyłacz do pozycji w dzienniku;
- link do śledzenia przesyłki (`emonitoring.poczta-polska.pl`).

Następny krok wymaga umowy z Pocztą Polską i konta e-Nadawca z dostępem do
WebAPI. Dopiero z nim można:

- pobierać numery nadania z puli kancelarii przed wyjściem na pocztę,
- drukować etykiety z kodem kreskowym zamiast naklejek z okienka,
- wysyłać elektroniczną książkę nadawczą (zbiór przesyłek) zamiast papierowej,
- pobierać statusy doręczeń i daty z elektronicznego potwierdzenia odbioru.

Login i hasło do WebAPI trzymamy w AWS Secrets Manager, nigdy w kodzie ani
w `.env`.

## Dane osobowe

Adresatami bywają osoby fizyczne. Dzienniki leżą w obszarze kancelarii
(`kancelarie/{id}/dziennik_*.json`, w S3 szyfrowane, w UE). Nazwy ani adresy
nie trafiają do logów. Kancelaria, która trzyma pliki u siebie, nie ma tego
widoku, bo serwer nie zapisuje jej danych.
