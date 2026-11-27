# NotarAI — pakiet prawno-administracyjny: oficjalne integracje

Stan analizy: 25.11.2026. Wzory do uzupełnienia i podpisania przez właściwego
wnioskodawcę. Nie wysłano żadnego pisma. Bez zmian AWS, bez danych klientów,
bez dostępu produkcyjnego, bez dostawców komercyjnych.

## 1. Strategia i bramki

Cel: indywidualne uprawnienia notariuszy, jednokrotna budowa i — o ile
dopuszczalne — ocena wspólnej infrastruktury. Nie wnioskujemy o dane
obywateli dla producenta ani nowe kompetencje notariatu.

Dwie niezależne ścieżki, równolegle:
* DIP: żądanie istniejących informacji publicznych, nie opinii prawnej,
  kluczy, utworzenia dokumentacji czy przyznania dostępu. Wniosek może
  wysłać producent bez dostępu do AWS i bez kancelarii pilotażowej.
* TECH: zgłoszenie techniczne, testy i uzgodnienia. Formalne wnioski
  produkcyjne składa każdy uprawniony notariusz zgodnie z przepisami
  szczególnymi. Podpis kwalifikowany ≠ status notariusza ≠ zgoda organu.
* Trzecia ścieżka warunkowa: ustawa o otwartych danych i ponownym
  wykorzystywaniu informacji sektora publicznego, jeżeli potrzebujemy
  praw do ponownego wykorzystania określonego publicznego zasobu albo
  udostępnienia w tym celu. Nie dublujemy dostępnych otwartych usług.

Mocny argument: art. 13 ust. 2 pkt 1 ustawy o informatyzacji (Dz.U. 2026
poz. 1241) — równe traktowanie rozwiązań informatycznych w ustawowym
zakresie. Art. 13 ust. 2 pkt 2 lit. b i ust. 4 — testy akceptacyjne
z wyjątkiem ustawowym. Art. 13 ust. 5 — informacje o API, ale art. 14
ustawy nowelizującej z 25.07.2025 (Dz.U. poz. 1158) przewiduje okresy
przejściowe 50/72/48 miesięcy i wyjątki dla nowych/zmienianych systemów.
Nie twierdzić, że każdy organ już musi stworzyć API albo wydać dokumentację.
Nie opierać roszczenia wobec KRN wyłącznie na art. 13: zakres podmiotowy
ustawy o informatyzacji wymaga odrębnej oceny. DIP wobec KRN ma samodzielną
podstawę z art. 4 ust. 1 pkt 2 UDIP i własnych zasad BIP KRN.

Podstawy: art. 61 Konstytucji; art. 1, 2, 3 ust. 1 pkt 1, 4 ust. 1–3,
5, 6, 10, 13–17, 21 UDIP. Udostępnienie co do zasady do 14 dni od
otrzymania, przedłużenie z przyczyną i terminem do 2 miesięcy; wyjątek
dotyczący dodatkowych kosztów art. 15. Wniosek o informację prostą:
nie trzeba wykazywać interesu. Informacja przetworzona: szczególna istotność
dla interesu publicznego; sam interes komercyjny nie wystarczy.
Wniosek nie obejmuje podatności, sekretów, rzeczywistych poświadczeń,
danych osób, topologii wewnętrznej ani informacji ustawowo chronionych.
Nie każdy dokument IT jest informacją publiczną (WSA Lublin II SAB/Lu
154/25); dokumenty dotyczące rzeczywistych zasad wykonywania zadań
publicznych i zamawianych ekspertyz mogą nią być (NSA I OSK 2265/11).
Dostęp do dokumentu nie jest automatycznie licencją na jego publikację.

## 2. Co zrobić przed wysyłką

DIP można wysłać natychmiast po uzupełnieniu:
- pełna firma i dane podmiotu prowadzącego NotarAI, reprezentant, adres
  do odpowiedzi; nie utożsamiać nazwy produktu z osobą prawną;
- sprawdzić adres do doręczeń każdego adresata w aktualnej BAE, nie kopiować
  niesprawdzonych adresów z poprzednich rozmów; KRN: biuro@krn.org.pl,
  zgodnie z oficjalną stroną kontaktową; zachować wiadomość i dowód odbioru;
- wysłać osobno każde żądanie DIP, z tytułem i numerowanymi punktami;
- nie dołączać kodu, prywatnych dokumentów, danych klientów, IP ani
  deklaracji o wdrożonych zabezpieczeniach, których nie zweryfikowano;
- założyć rejestr: ID, adresat, tryb, data doręczenia, termin odpowiedzi,
  odpowiedzi na poszczególne punkty, dalsza czynność, dowód.

Przed zgłoszeniami testowymi: ustalić osobę techniczną, dane producenta,
nazwę i wersję systemu, oficjalne aktualne formularze, wymagane publiczne
IPv4 (zweryfikowany egress, nie adres LB), opis przepływu danych,
mechanizm separacji kancelarii/poświadczeń i dowody testów. Oddzielić
planowaną architekturę od stanu wdrożenia. Nie kupować sieci ani adresów
przed ustaleniem dopuszczalnego modelu. Przygotować zgodę kancelarii
pilotażowej (nie jest potrzebna do DIP), potwierdzenie statusu notariusza,
umowę powierzenia zgodną z art. 28 RODO, analizę art. 25, 32 i 35 RODO
(w tym ocenę konieczności DPIA), zasady tajemnicy z art. 18 Prawa o notariacie.
Dane testowe syntetyczne. Nie przesyłać klucza prywatnego podpisu notariusza.
Wnioski produkcyjne dopiero po spełnieniu przesłanek szczególnych.

## 3. Wzór wspólnego nagłówka i zakończenia dla pism DIP

**Wniosek o udostępnienie informacji publicznej – [temat]**

Na podstawie art. 2 ust. 1 w związku z art. 10 ust. 1 ustawy z dnia
6 września 2001 r. o dostępie do informacji publicznej wnoszę o
udostępnienie następujących istniejących informacji i dokumentów
pozostających w posiadaniu adresata:

[treść właściwego pisma z pkt 4–10]

Proszę o odpowiedź odrębnie na każdy punkt, w formie elektronicznej,
na [adres odpowiedzi]. Dokumenty proszę przekazać w istniejącym
formacie elektronicznym, w tym specyfikacje w formacie źródłowym,
jeżeli pozostaje on w posiadaniu adresata i podlega udostępnieniu.
W przypadku informacji już opublikowanej proszę o dokładny adres
strony lub pliku pozwalający odnaleźć odpowiedź na dany punkt.

Wniosek nie dotyczy danych obywateli, poświadczeń dostępowych,
informacji o podatnościach ani tworzenia nowych analiz, opinii prawnych
lub zestawień. Jeżeli dokument zawiera informacje chronione, proszę
udostępnić część jawną po wyłączeniu chronionych fragmentów, o ile
jest to prawnie i technicznie możliwe. Jeżeli informacja nie istnieje
lub nie jest w posiadaniu adresata, proszę wskazać to osobno dla
danego punktu. Jeżeli istnieją podstawy odmowy udostępnienia informacji
publicznej, proszę o rozstrzygnięcie w trybie art. 16 lub 17 ustawy,
odpowiednio do statusu adresata. W razie potrzeby przedłużenia terminu
proszę o zawiadomienie zgodnie z art. 13 ust. 2.

[Wnioskodawca, reprezentant, dane do odpowiedzi]

## 4. DIP-01 — Minister Cyfryzacji: dostęp notariuszy do SRP

1. Obowiązujące dokumenty określające kategorie uprawnionych podmiotów,
   zakresy dostępu i przesłanki weryfikacji dla notariuszy, odrębnie dla:
   RZNP, PESEL, RDO, RDP, RSC, RDK; w tym istniejące wytyczne
   dotyczące systemów własnych i pośredniczących.
2. Istniejące formularze, instrukcje i kryteria oceny wniosków oraz
   dokumentacji technicznej dla każdego z wymienionych rejestrów.
3. Czy w okresie 1.01.2024–25.11.2026 minister udzielił notariuszowi
   indywidualnego dostępu sieciowego do każdego z RSC, RDK i PESEL?
   Proszę o informację w zakresie posiadanych danych oraz kopię
   najnowszego istniejącego pozytywnego rozstrzygnięcia/zgody w każdej
   kategorii (po anonimizacji, jeżeli podlega udostępnieniu); w braku
   pozytywnego rozstrzygnięcia — najnowsze istniejące odmowne.
   Nie żądamy tworzenia statystyk ani przeglądu akt wszystkich spraw.
4. Istniejące dokumenty dotyczące dopuszczenia wspólnego systemu
   pośredniczącego dla wielu niezależnych uprawnionych podmiotów,
   zasad ponownego wykorzystania oceny tego samego systemu i
   indywidualnego wydawania/odwoływania poświadczeń.
5. Istniejące dokumenty określające model integratora mObywatela,
   tryby integracji z systemami kancelaryjnymi i zakresy danych
   przekazywanych z udziałem użytkownika, a także warunki testów.
6. Istniejące zasady dostępu do BAE przez systemy kancelaryjne,
   jeżeli nie są już ujęte w opublikowanej dokumentacji e-Doręczeń.

Podstawa szczególna dla kontekstu (nie roszczenie o dane): art. 85,
85a, 95da Prawa o notariacie; art. 23j, 23m i 46–51 ustawy o ewidencji
ludności; art. 45 Prawa o aktach stanu cywilnego; art. 19c i 20h
ustawy o informatyzacji. RSC/RDK — brak potwierdzonego uprawnienia,
nie traktować jako przesądzonego.

## 5. DIP-02 — Centralny Ośrodek Informatyki: technika

1. Wersje dokumentacji zewnętrznych interfejsów (OpenAPI/WSDL/XSD,
   instrukcje integracyjne, przykładowe odpowiedzi i testy akceptacyjne)
   dla RZNP, PESEL, RDO, RDP, RSC i RDK, w zakresie przewidzianym
   dla uprawnionych użytkowników lub integratorów; wskazać istniejący
   kanał uzyskania dokumentacji, której nie można udostępnić publicznie.
2. Aktualne, istniejące kryteria oceny systemu pośredniczącego,
   testy, wymogi adresów wychodzących, certyfikatów, identyfikacji
   użytkowników, izolacji i audytowalności — wyłącznie na poziomie
   wymogów dla zewnętrznego integratora.
3. Istniejące procedury dotyczące dostępu do INT, danych syntetycznych,
   emulatorów, rejestracji systemu i zmian wersji interfejsów.
4. Istniejące instrukcje opisujące, czy i jak ocenę techniczną
   przeprowadza się raz dla integratora czy oddzielnie dla każdego
   uprawnionego podmiotu; istniejące zasady podpinania kolejnych
   uprawnionych notariuszy.
5. Jeżeli dostęp do dokumentacji podlega odrębnej procedurze,
   proszę o jej istniejący regulamin, wzór i właściwy kanał.

Nie żądać dostępu do środowiska INT w trybie DIP — zgłosić równolegle
dedykowanym formularzem.

## 6. DIP-03 — Główny Geodeta Kraju: geodezja

1. Aktualne warunki i formularze dostępu do danych EGiB przez ZSIN,
   zakres dostępnych usług sieciowych i danych dla poszczególnych
   kategorii podmiotów, w tym dokumentacja interfejsów dla uprawnionych.
2. Czy od 1.01.2024 do 25.11.2026 zatwierdzono wniosek notariusza o
   dostęp do ZSIN? W zakresie posiadanych informacji proszę o kopię
   najnowszego zatwierdzenia lub, gdy takiego nie ma, istniejącego
   rozstrzygnięcia odmownego, z wyłączeniem danych chronionych.
3. Istniejące dokumenty określające możliwość korzystania z ZSIN przez
   uprawnione podmioty za pomocą wspólnego systemu pośredniczącego.
4. Istniejące wykazy usług publicznych ULDK, KIEG, EGiB WFS, RCN i innych
   przydatnych w czynnościach notarialnych, formaty, limity, warunki
   wpisu na listę zaufanych adresów IP i aktualność danych.
5. Istniejący wykaz powiatów udostępniających elektroniczne wypisy i
   wyrysy, w tym automatyczne wydawanie dokumentów opatrzonych
   kwalifikowaną pieczęcią, jeżeli taki wykaz jest prowadzony.
6. Istniejące standardy, procedury i dokumentacja centralnych usług
   zamawiania urzędowych wypisów/wyrysów lub istniejących wspólnych
   interfejsów powiatowych. Jeżeli takich usług nie ma, proszę o
   informację o tym fakcie, bez projektowania nowych rozwiązań.

Kontekst: art. 24 i art. 24b ustawy Prawo geodezyjne i kartograficzne;
§36 rozporządzenia EGiB. ZSIN to nie urząd wydający wypis; właściwość
starosty/prezydenta miasta i interes prawny w zakresie danych chronionych
należy oceniać osobno.

## 7. DIP-04 — Minister Sprawiedliwości: księgi wieczyste

1. Obowiązujące formularze i dokumenty określające uzyskanie przez
   notariusza zgód z art. 36(4) ust. 8 i 13 ustawy o KW i hipotece,
   w tym różnice między trybami, wymogi techniczne, opłaty i
   przydzielanie indywidualnych dostępów.
2. Istniejąca dokumentacja interfejsów zewnętrznych do wyszukiwania
   ksiąg i przekazywania wniosków wieczystoksięgowych przez notariuszy,
   w tym formaty importu wniosków, testy i instrukcje integracyjne.
3. Istniejące procedury dopuszczania systemów producentów zewnętrznych
   oraz warunki współdzielonej infrastruktury przy indywidualnych
   uprawnieniach notariuszy.
4. Istniejące dokumenty potwierdzające dopuszczenie takiej integracji
   przez producentów oprogramowania, jeżeli takie dokumenty istnieją;
   w razie ograniczeń proszę o część jawną.
5. Istniejąca dokumentacja oficjalnych interfejsów odczytowych KRZ i
   Rejestru Zastawów, jeżeli są udostępniane zewnętrznym podmiotom,
   oraz warunki korzystania z nich.

Kontekst: art. 92 §4 Prawa o notariacie; art. 36(4) ust. 8 i 13
ustawy o KW i hipotece. Zgoda na wyszukiwanie nie jest zgodą na API.
Przed produkcyjnym wnioskiem sprawdzić aktualne rozporządzenie CIKW.

## 8. DIP-05 — Krajowa Rada Notarialna: istniejące integracje

1. Obowiązujące uchwały i regulaminy dotyczące Rejestru Spadkowego,
   NORT, CREWAN, rejestru zarządców sukcesyjnych oraz modułu RZNP,
   w zakresie korzystania z nich przez notariuszy i systemy zewnętrzne.
2. Istniejące procedury, wymagania, testy, formularze i wzory umów
   regulujące dopuszczanie oprogramowania kancelaryjnego lub jego
   producenta do integracji z tymi systemami.
3. Czy którekolwiek z tych usług umożliwiają odczyt, import danych,
   przekazanie dokumentów lub pobranie potwierdzeń z oprogramowania
   zewnętrznego? Proszę o istniejącą dokumentację funkcji i interfejsów,
   w zakresie przeznaczonym dla podmiotów zewnętrznych.
4. Istniejące uchwały, porozumienia lub jawne postanowienia umów
   dotyczące integracji komercyjnego oprogramowania kancelaryjnego
   (nie umowy serwisowe niezwiązane z integracją), w tym kryteria
   dopuszczania innych producentów. Proszę o dokumenty aktualnie
   obowiązujące, nie o zestawienie wszystkich historycznych umów.
5. Istniejące dokumenty wyznaczające podmiot właściwy do uzgodnień
   technicznych i podmiot uprawniony do zatwierdzania integracji.
6. Istniejące zasady technicznej weryfikacji statusu zawodowego
   notariusza i aktualizacji tego statusu, o ile taki mechanizm
   udostępniono podmiotom zewnętrznym.

Podstawa DIP: art. 4 ust. 1 pkt 2 UDIP; BIP KRN:
https://bip.krn.org.pl/sposob-przyjmowania-i-zalatwiania-spraw
https://bip.krn.org.pl/rejestry-notarialne
Nie domagać się danych testamentów, aktów, haseł, PIN-ów czy certyfikatów.

## 9. DIP-06 — Minister Spraw Wewnętrznych i Administracji: PESEL-NET

1. Obowiązujące dokumenty określające warunki przyłączenia do PESEL-NET
   MPLS przez uprawnionych notariuszy, kategorie dopuszczalnych podmiotów,
   wzory porozumień i zasady przyłączenia.
2. Istniejące warunki dopuszczania wspólnej infrastruktury technicznej
   wykorzystywanej przez wielu indywidualnie uprawnionych użytkowników;
   zasady wykorzystania infrastruktury chmurowej, jeżeli takie zasady
   zostały przyjęte.
3. Istniejące procedury oceny, odbioru technicznego i obsługi kolejnych
   uprawnionych użytkowników, koszty i wymagania wobec wykonawców
   przyłącza w zakresie przeznaczonym dla wnioskodawców.
4. Istniejące dokumenty określające, czy dla poszczególnych usług
   stosuje się inne dopuszczalne sposoby połączenia.

Bez wniosku o topologię, adresy wewnętrzne, klucze czy zabezpieczenia
sieci. Nie utożsamiać adresu EIP z przyłączem MPLS.

## 10. DIP-07 — Minister Finansów / GIIF: raportowanie

1. Istniejąca aktualna dokumentacja dla zewnętrznego oprogramowania
   kancelaryjnego SI*GIIF i raportowania do Szefa KAS, schematy i słowniki,
   informacje o wersjach i procedurach pozyskiwania dokumentacji.
2. Istniejące zasady dostępu do środowiska testowego, testy akceptacyjne,
   procedury rejestracji podpisu i wymiany certyfikatów.
3. Istniejące instrukcje dotyczące komunikacji przez interfejs,
   identyfikacji przesyłek, urzędowych poświadczeń odbioru i błędów,
   w zakresie nieopublikowanym na stronie e-Notariusz.

Jeżeli aktualna dokumentacja jest dostępna przez zwykłe konto testowe,
najpierw założyć konto i nie eskalować bez potrzeby.

## 11. TECH – niezależne pismo wspólne

**Dotyczy: warunków integracji oprogramowania kancelaryjnego NotarAI**

Szanowni Państwo,

Rozwijamy oprogramowanie NotarAI przeznaczone do wspomagania wykonywania
ustawowych obowiązków notariuszy. Występujemy wyłącznie jako producent
i integrator techniczny. Nie ubiegamy się o produkcyjne uprawnienia do
danych obywateli dla producenta. Każdy notariusz będzie samodzielnie
wnioskował o dostęp, uzyska odrębne uprawnienia i będzie korzystał z nich
wyłącznie w zakresie wynikającym z przepisów oraz warunków właściwego organu.

Celem jest ograniczenie błędów identyfikacji stron i nieruchomości,
usprawnienie weryfikacji oraz realizacji obowiązków sprawozdawczych,
z zachowaniem tajemnicy notarialnej. Projektowany model zakłada
indywidualną identyfikację użytkownika, w tym potwierdzenie tożsamości
kwalifikowanym podpisem elektronicznym, niezależną weryfikację uprawnień
zawodowych, izolację kancelarii, rozdzielenie poświadczeń, minimalizację
danych i możliwość rozliczenia operacji. Przygotujemy dowody spełnienia
konkretnych wymogów technicznych w toku uzgodnień.

Prosimy o:
1. wskazanie istniejącego trybu dopuszczenia oprogramowania i właściwej
   dokumentacji dla producenta;
2. ustalenie możliwości jednokrotnej oceny wspólnej infrastruktury
   z indywidualną autoryzacją każdego notariusza, bez ograniczania
   kompetencji organu do badania wniosków indywidualnych;
3. wskazanie warunków udziału w testach na danych syntetycznych oraz
   kontaktu osoby/komórki właściwej do technicznych uzgodnień;
4. wskazanie, czy dostęp przez taki model jest dopuszczalny na podstawie
   obecnych przepisów i procedur; jeżeli nie, prosimy o wskazanie
   istniejącego alternatywnego modelu.

Wnosimy o stosowanie równoważnych kryteriów wobec rozwiązań
informatycznych w zakresie, w jakim zastosowanie ma art. 13 ust. 2 pkt 1
ustawy o informatyzacji. Nie oczekujemy tworzenia nowej usługi ani
zmiany prawa. Jesteśmy gotowi dostosować rozwiązanie do uzasadnionych
wymagań ochrony danych i bezpieczeństwa.

[Podpis reprezentanta producenta]

Załącznik tematyczny, zależnie od adresata (nie wysyłać jednej identycznej
paczki wszystkim):
- MC/COI: RZNP oraz kwalifikacja indywidualnej teletransmisji pozostałych
  pięciu rejestrów. RZNP: dedykowany wniosek testowy do cc.wnioski@coi.gov.pl,
  po wypełnieniu aktualnego formularza; oficjalna instrukcja dopuszcza
  system pośredniczący i adres IPv4 tego systemu.
- e-Doręczenia: zgłoszenie INT producenta EZD na test.edoreczenia@cyfra.gov.pl.
  Dodatkowo rozważyć odrębny tryb zewnętrznego systemu usługowego wyłącznie
  jeśli odpowiada funkcjonalności przekazania wniosku użytkownika.
- mObywatel: Panel Współpracy, https://wspolpraca.mobywatel.gov.pl/
- GGK: ZSIN (kwalifikacja dostępu), publiczne interfejsy, wypisy; oficjalny
  formularz dopiero dla uprawnionego wnioskodawcy.
- MS: ścieżka obu zgód wyszukiwawczych KW, e-wnioski.
- KRN: istniejące rejestry i warunki integracji, bez roszczenia do treści.
- MSWiA: wspólny model PESEL-NET, bez zamawiania przyłącza.
- MF/GIIF: testy istniejącego API (nie prosić o nowe API).

## 12. Eskalacja — dopiero po konkretnej odpowiedzi lub braku odpowiedzi

Dzień 0: doręczenie DIP i równoległe właściwe zgłoszenia techniczne.
Dzień 14: sprawdzić każdy punkt i czy nastąpiło prawidłowe zawiadomienie
z art. 13 ust. 2 (uwzględnić art. 15 i reguły obliczania terminów).
Brak odpowiedzi / odpowiedź pozorna: rozważyć krótkie wskazanie
nierozpoznanych punktów; nie jest to warunek skargi na bezczynność DIP.
Skarga do właściwego WSA za pośrednictwem zobowiązanego podmiotu (art. 21
UDIP, art. 3 §2 pkt 8 i art. 54 §1 PPSA); brak obowiązku ponaglenia
w klasycznej sprawie o informację publiczną — III SAB/Po 66/26.
Odmowa: ustalić, czy decyzja z art. 16/17, czy pismo o braku charakteru
publicznego, posiadania lub trybie szczególnym; odpowiednio odwołanie,
wniosek o ponowne rozpatrzenie (art. 17 ust. 2 dla podmiotu
niebędącego organem) lub skarga. Sprawdzić pouczenie, właściwość
i terminy przed wniesieniem. Skarga na decyzję co do zasady 30 dni,
odwołanie co do zasady 14 dni, z uwzględnieniem dopuszczalnej drogi
bez ponownego rozpatrzenia dla właściwych decyzji.
Nie skarżyć automatycznie każdego negatywnego stanowiska technicznego:
odmowa dokumentacji ≠ odmowa dostępu do rejestru ≠ brak API.
Jeżeli w grę wchodzi informacja przetworzona, najpierw ograniczyć
zakres; jeśli istnieje szczególnie istotny interes publiczny,
uzasadnić go realnymi faktami (np. powtarzalne obowiązki notariatu
i mierzalny wpływ na bezpieczeństwo obrotu), nie obiecywać nieudowodnionych
korzyści. Jeżeli organ wykazuje ograniczenie, żądać jawnej części,
nie próbować pozyskać informacji chronionych.

## 13. Źródła do kontroli przed wysyłką

- UDIP: https://eli.gov.pl/eli/DU/2001/1198/ogl
- Informatyzacja: https://eli.gov.pl/eli/DU/2026/1241/ogl
- Nowelizacja (art. 14): https://eli.gov.pl/eli/DU/2025/1158/ogl
- Prawo o notariacie: https://eli.gov.pl/eli/DU/2026/614/ogl
- RZNP: https://www.gov.pl/web/cyfryzacja/udostepnianie-danych-z-rejestru-zastrzezen-numerow-pesel
- Rejestry: https://www.gov.pl/web/cyfryzacja/jak-uzyskac-dostep-do-danych-z-rejestrow
- ZSIN: https://www.gov.pl/web/gugik/zintegrowany-system-informacji-o-nieruchomosciach-zsin
- Formularze: https://www.gov.pl/web/gugik/formularze
- e-Doręczenia EZD: https://www.gov.pl/web/e-doreczenia/integracja-uslugi-e-doreczen-z-systemami-klasy-ezd
- e-Doręczenia system usługowy: https://www.gov.pl/web/e-doreczenia/z-zewnetrznymi-systemami-uslugowymi
- KRN: https://krn.org.pl/kontakt
- e-Notariusz: https://podatki.gov.pl/enotariusz
- NSA I OSK 2265/11: https://orzeczenia.nsa.gov.pl/doc/BFC87465F2
- WSA II SAB/Lu 154/25: https://orzeczenia.nsa.gov.pl/doc/A470FA3319
- WSA III SAB/Po 66/26: https://orzeczenia.nsa.gov.pl/doc/A24369CCC0

Nie publikować w publicznym repozytorium wypełnionych wniosków,
odpowiedzi zawierających chronione informacje, poświadczeń ani danych
notariuszy. W repozytorium wyłącznie szablony i jawne odsyłacze.
