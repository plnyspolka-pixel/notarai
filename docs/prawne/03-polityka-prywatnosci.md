# POLITYKA PRYWATNOŚCI NOTARAI

Wersja z dnia 08.11.2026.

Ta polityka dotyczy danych, które Fundacja przetwarza **jako administrator**:
danych użytkowników usługi, osób kontaktujących się z nami i odwiedzających
stronę notarai.pl.

Dane klientów kancelarii zawarte w sprawach (skany, akty, odczyty) Fundacja
przetwarza wyłącznie **w imieniu kancelarii**, na podstawie umowy
powierzenia. Ich administratorem jest notariusz, a informacje o tym
przetwarzaniu przekazuje kancelaria.

## 1. Administrator

Fundacja Krzewienia Edukacji Finansowej im. Pieczaka z siedzibą w Lublinie,
ul. Wilhelma Orlika Ruckemana 4/18, 20-244 Lublin, KRS 0001140846, NIP 9462747637, REGON 540280180
(dalej: **Fundacja**).
Kontakt w sprawach danych osobowych: kontakt@notarai.pl, listownie na adres
siedziby.

## 2. Jakie dane, w jakim celu i na jakiej podstawie

| Kogo dotyczy | Dane | Cel | Podstawa (RODO) | Jak długo |
|---|---|---|---|---|
| Użytkownicy usługi (notariusze, pracownicy kancelarii) | e-mail, imię i nazwisko (jeżeli podane), kancelaria, rola, daty zaproszenia i dołączenia, dane logowania (hasło przechowywane w postaci zabezpieczonej przez AWS Cognito) | założenie i prowadzenie konta, logowanie, zaproszenia, reset hasła | art. 6 ust. 1 lit. b (umowa z kancelarią - wobec notariusza) oraz lit. f (prawnie uzasadniony interes: obsługa kont pracowników kancelarii) | do usunięcia konta, a potem do 90 dni |
| Użytkownicy | adres IP, czas i rodzaj żądań, identyfikatory techniczne w dziennikach | bezpieczeństwo, wykrywanie nadużyć i awarii | art. 6 ust. 1 lit. f | 90 dni |
| Notariusz zawierający umowę, osoba wysyłająca formularz rejestracji | imię i nazwisko notariusza (notariuszy), nazwa i adres kancelarii, NIP, e-mail | zawarcie i wykonanie umowy, rozliczenia | art. 6 ust. 1 lit. b i c (przepisy podatkowe i rachunkowe) | czas umowy, następnie 5 lat od końca roku, w którym upłynął termin płatności podatku, oraz do przedawnienia roszczeń |
| Osoba akceptująca Regulamin i umowę powierzenia | data i godzina akceptacji, wersje dokumentów, e-mail, adres IP | wykazanie zawarcia umowy i umowy powierzenia (rozliczalność, art. 5 ust. 2 i art. 28 ust. 9 RODO) | art. 6 ust. 1 lit. c i f | czas umowy i 5 lat po jej zakończeniu |
| Użytkownicy | data potwierdzenia zapoznania się z instrukcją AI, data przyjęcia oceny skutków przez notariusza | wykazanie kompetencji w zakresie AI (art. 4 rozporządzenia (UE) 2024/1689) i dokumentacji kancelarii | art. 6 ust. 1 lit. c i f | do usunięcia konta albo kancelarii |
| Właściciel kancelarii opłacający abonament | e-mail płatnika, identyfikator klienta i subskrypcji w Stripe, status i daty płatności, faktury; danych karty Fundacja nie otrzymuje | prowadzenie abonamentu, rozliczenia | art. 6 ust. 1 lit. b i c | czas umowy, następnie 5 lat od końca roku, w którym upłynął termin płatności podatku |
| Notariusz kancelarii pokazywanej na mapie notariuszy (app.notarai.pl/notariusze) | nazwa kancelarii, imię i nazwisko notariusza (notariuszy), adres kancelarii oraz współrzędne wyznaczone z tego adresu | publiczna wyszukiwarka najbliższej kancelarii dla klientów | art. 6 ust. 1 lit. f (prawnie uzasadniony interes: informowanie o kancelariach korzystających z usługi; dane te są jawne także w rejestrze samorządu notarialnego); właściciel kancelarii może w każdej chwili wyłączyć publikację w aplikacji | do wyłączenia publikacji, wyłączenia kancelarii albo końca umowy |
| Osoby korzystające z mapy notariuszy | położenie ustalone przez przeglądarkę albo wskazane na mapie | wskazanie najbliższej kancelarii | nie jest przetwarzane przez Fundację: pozostaje w przeglądarce, odległości liczy strona lokalnie | - |
| Osoby piszące do nas | e-mail, imię i nazwisko, treść wiadomości | odpowiedź, obsługa reklamacji i zgłoszeń | art. 6 ust. 1 lit. f | do zakończenia sprawy, nie dłużej niż 3 lata |
| Odwiedzający stronę notarai.pl | adres IP, czas wizyty i dane techniczne przeglądarki w dziennikach serwera hostingu AZ.pl | wyświetlenie strony, bezpieczeństwo | art. 6 ust. 1 lit. f | zgodnie z zasadami dostawcy hostingu |

Podanie danych jest dobrowolne, ale bez adresu e-mail nie da się założyć
konta.

## 3. Pliki cookie

Strona notarai.pl nie używa plików cookie analitycznych ani reklamowych.
Aplikacja app.notarai.pl używa wyłącznie plików cookie i pamięci przeglądarki
niezbędnych do logowania i utrzymania sesji (w tym bezpiecznego pliku cookie
odnawiającego logowanie przez okres do 30 dni). Na ich użycie nie jest
wymagana zgoda.

## 4. Odbiorcy

1. Amazon Web Services EMEA SARL (Luksemburg) - hosting, logowanie, wysyłka
   e-maili z zaproszeniami i kodami, dzienniki; dane przechowywane we
   Frankfurcie.
2. AZ.pl Sp. z o.o. (Szczecin) - hosting strony notarai.pl, domena
   i skrzynka kontakt@notarai.pl.
3. Stripe Payments Europe, Limited (Dublin, Irlandia) - obsługa płatności
   kartą, subskrypcji i faktur. Stripe przetwarza dane płatnicze także jako
   odrębny administrator, na zasadach swojej polityki prywatności
   (stripe.com/pl/privacy). Dane karty podaje się bezpośrednio Stripe.
4. OpenStreetMap Foundation (Wielka Brytania) - wyznaczenie współrzędnych
   kancelarii z jej adresu (usługa Nominatim; otrzymuje wyłącznie adres
   kancelarii) oraz kafelki mapy, które przeglądarka osoby korzystającej
   z mapy notariuszy pobiera bezpośrednio z serwerów OpenStreetMap (widzą one
   jej adres IP, na zasadach polityki prywatności OSMF:
   osmfoundation.org/wiki/Privacy_Policy). Wielka Brytania jest objęta
   decyzją Komisji Europejskiej stwierdzającą odpowiedni stopień ochrony.
5. Organy publiczne, gdy wynika to z przepisów.

Dane użytkowników usługi są przechowywane w Europejskim Obszarze
Gospodarczym. AWS należy do grupy z siedzibą w USA i stosuje certyfikację
w ramach EU-U.S. Data Privacy Framework. Stripe może przekazywać dane
płatnicze do Stripe, Inc. w USA na podstawie EU-U.S. Data Privacy Framework
oraz standardowych klauzul umownych zatwierdzonych przez Komisję Europejską.

## 5. Twoje prawa

Masz prawo do: dostępu do danych, ich sprostowania, usunięcia, ograniczenia
przetwarzania, przenoszenia danych (gdy podstawą jest umowa) oraz sprzeciwu
wobec przetwarzania opartego na prawnie uzasadnionym interesie. Napisz na
kontakt@notarai.pl.

Masz prawo wnieść skargę do Prezesa Urzędu Ochrony Danych Osobowych,
ul. Stawki 2, 00-193 Warszawa.

## 6. Decyzje automatyczne

Fundacja nie podejmuje wobec użytkowników decyzji opartych wyłącznie na
zautomatyzowanym przetwarzaniu, w tym profilowaniu, wywołujących skutki
prawne lub podobnie istotnie wpływających.

## 7. Zmiany

O zmianach polityki informujemy na stronie, a użytkowników - e-mailem.
