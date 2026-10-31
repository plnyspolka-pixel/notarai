# REJESTR DOSTĘPÓW SERWISOWYCH DO TREŚCI SPRAW

Wersja z dnia 01.11.2026.

Prowadzi: Fundacja Krzewienia Edukacji Finansowej im. Pieczaka.
Osoba odpowiedzialna: Filip Robert Bielak, Prezes Zarządu.

Fundacja nie ma dostępu do treści spraw kancelarii (§ 5 ust. 3 umowy
powierzenia). Jedynym wyjątkiem jest dostęp serwisowy, który kancelaria sama
włącza w Usłudze (§ 5 ust. 4 umowy powierzenia, Załącznik nr 2 lit. D).
Ten dokument opisuje, jak taki dostęp jest rejestrowany.

## Zasady

1. Dostęp serwisowy włącza wyłącznie właściciel kancelarii w oknie
   „Zespół kancelarii”, na wybrany czas od 1 godziny do 7 dni. Może go
   w każdej chwili odwołać. Po upływie czasu dostęp wygasa samoczynnie.
2. Bez włączonego dostępu Fundacja nie ma żadnej drogi do treści spraw:
   panel administracyjny ich nie otwiera, a polityka magazynu zakazuje
   odczytu plików spraw wszystkim poza aplikacją i kopią zapasową.
   E-mail ani telefon z prośbą o pomoc nie otwierają dostępu - kancelaria
   musi go włączyć w Usłudze.
3. Z dostępu korzysta wyłącznie osoba z upoważnieniem w zakresie B
   (plik 06), zalogowana imiennie w panelu administracyjnym. Awaryjny token
   administratora nie otwiera dostępu serwisowego.
4. Osoba korzystająca z dostępu zagląda wyłącznie w to, czego dotyczy
   zgłoszenie kancelarii. Dostęp nie obejmuje zespołu, abonamentu,
   akceptacji dokumentów ani pomocnika kancelarii.
5. Awarie i naruszenia ochrony danych obsługuje się bez dostępu do treści
   spraw, na podstawie identyfikatorów, rozmiarów i dat plików oraz
   dzienników bez danych osobowych (§ 5 ust. 5 umowy powierzenia). Jeżeli to
   nie wystarcza, Fundacja prosi kancelarię o włączenie dostępu serwisowego.

## Rejestr

Rejestr prowadzi automatycznie aplikacja, w danych kancelarii. Dla każdego
włączenia zapisuje:

- kto z kancelarii włączył dostęp i kiedy,
- do kiedy dostęp miał trwać i czy został wcześniej odwołany (kiedy),
- kto z Fundacji z niego skorzystał (adres e-mail konta) i kiedy wszedł
  po raz pierwszy,
- zakres dostępu tej osoby: rodzaje danych (np. sprawy, kalendarz, osoby
  i telefony), otwarte sprawy (identyfikatory, które kancelaria widzi jako
  nazwy swoich spraw) oraz to, czy wprowadzała zmiany, czy tylko
  przeglądała.

Kancelaria widzi pięć ostatnich wpisów w oknie „Zespół kancelarii”.
W dziennikach aplikacji zostaje wyłącznie sam fakt włączenia, odwołania
i wejścia, z identyfikatorem kancelarii, bez adresów e-mail i bez treści
spraw. Wpisy usuwa się razem z danymi kancelarii po zakończeniu umowy.

## Przegląd

Raz w roku, przy przeglądzie środków bezpieczeństwa, sprawdza się, że:

1. panel administracyjny nadal nie otwiera spraw (testy automatyczne
   `test_serwis.py`, `test_autoryzacja.py`),
2. polityka bucketa spraw zawiera zakaz odczytu dla wszystkich poza rolą
   aplikacji i rolą kopii zapasowej, a w AWS CloudTrail nie ma
   nieuzasadnionych zmian tej polityki.
