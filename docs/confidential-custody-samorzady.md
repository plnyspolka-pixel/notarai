# NotarAI Confidential: samorządy i organy nadzoru jako kustosz albo weryfikator

**Status: analiza i koncepcja. Żadnych zmian w AWS, żadnych wdrożeń, żadnych rozmów z instytucjami.**
Data: 22.11.2026. Dotyczy pomysłu właściciela z 22.11.2026 oraz architektury z
`docs/confidential-independent-custody.md`, `docs/confidential-custody-release.md`,
`docs/confidential-external-custody-launch.md` (PR #61, #62, #65).

## 1. Wniosek w skrócie

**Kierunek, w którym budujemy (decyzja właściciela z 22.11.2026): pkt 5.7.** Dostęp do treści
ma zależeć od algorytmu, a nie od zaufania do osoby lub instytucji: klucz zostaje u klienta,
klient sam sprawdza atestację enklawy z publicznym rejestrem, a enklawa przyjmuje zlecenia
tylko od kluczy poświadczonych podpisem kwalifikowanym notariusza. Warianty z kustoszem
(5.2-5.5) są etapem przejściowym i tłem analizy.

1. **Nie wręczać klucza kustosza żadnemu samorządowi ani organowi nadzoru.** Kustosz może
   zmienić politykę klucza KMS, czyli technicznie może sobie przyznać `kms:Decrypt`. Organ,
   który ma jednocześnie taki klucz i ustawowe prawo żądania dokumentów, staje się zagrożeniem
   dla tajemnicy, a nie jej gwarantem. Ustawodawca idzie w odwrotną stronę: tajemnica
   notarialna, adwokacka i radcowska nie ustaje nawet wobec organu ochrony danych (pkt 3.6).
2. **„Czy chcą, czy nie chcą” nie działa technicznie ani prawnie.** Konta AWS nie da się
   skutecznie przekazać podmiotowi, który go nie przyjął. Klucz bez aktywnego opiekuna oznacza
   w praktyce, że kontrolę zachowuje NotarAI, czyli brak niezależności (pkt 4.2).
3. **KRN i KRS to nie są organy, które badają tajemnicę.** U notariuszy kontrolę wykonują
   Minister Sprawiedliwości (przez prezesów sądów) i rady izb notarialnych, nie KRN. KRS nie
   bada tajemnicy sędziowskiej; ma tylko wąski nadzór nad danymi osobowymi w sądach
   apelacyjnych (pkt 3).
4. **To, czego właściciel naprawdę chce (każdy może sprawdzić nienaruszalność, bez wglądu
   w treść), daje publiczny rejestr przejrzystości, nie klucz.** Rejestr nie wymaga zgody
   żadnej instytucji i można go zbudować od razu (pkt 5.1).
5. **Instytucje mają sens w roli weryfikatora albo świadka**, czyli z dostępem tylko do
   dowodów. To wymaga ich zgody i rozmów (pkt 6.2).
6. **Na stronie wolno pisać tylko o tym, co jest publicznie sprawdzalne**, bez nazw instytucji,
   które się nie zgodziły (pkt 6.3).
7. **Podmiot powiązany z właścicielem operatora (osobiście, rodzinnie, kapitałowo) nie jest
   niezależnym kustoszem cudzych kluczy**, nawet jeśli właściciel go nie prowadzi i nie
   kontroluje. Może być kustoszem własnych danych i miejscem pilota technicznego (pkt 5.5).

## 2. Dwie role, których nie wolno mylić

| | Kustosz | Weryfikator | Świadek |
|---|---|---|---|
| Co ma | administrację konta custody: `kms:PutKeyPolicy`, klucz podpisujący wydania | odczyt: polityka klucza, granty, CloudTrail, rejestr | własny klucz podpisu, którym kontrasygnuje wpisy rejestru |
| Co może zepsuć | wszystko: dopisać nieatestowany `Decrypt`, zatwierdzić złośliwy obraz, zablokować usługę | nic w systemie | nic w systemie; może odmówić podpisu, co jest widoczne |
| Odpowiedzialność | realna, umowna i deliktowa; ciągły dyżur operacyjny | za rzetelność własnej oceny | za własny podpis |
| Kompetencje | zespół z AWS, MFA, procedury, całodobowa reakcja | umiejętność uruchomienia narzędzia lub zlecenia audytu | minimalna |
| Czy widzi treść | nie powinien, ale **może sobie ten dostęp nadać** | nie | nie |

Istotny szczegół obecnego projektu: podpis kustosza pod wydaniem jest ważny najwyżej 48 h
(domyślnie 24 h), a bez ważnego podpisu runner nie uruchomi zadania Nitro
(`docs/confidential-custody-release.md`, `docs/confidential-external-custody-launch.md`).
Kustosz to więc nie depozytariusz koperty w sejfie, tylko uczestnik procesu, który podpisuje
co dobę lub przy każdym wydaniu. Rada samorządu zawodowego zbierająca się na posiedzeniach
nie jest w stanie pełnić takiej funkcji.

## 3. Kto faktycznie bada i egzekwuje tajemnicę zawodową

Przepisy poniżej przeczytano 22.11.2026 w tekstach ujednoliconych Kancelarii Sejmu
(api.sejm.gov.pl). Przy każdym akcie podano datę stanu tekstu. Rzeczy niepotwierdzone są
zebrane w pkt 3.8.

### 3.1 Notariusze

[Prawo o notariacie](https://api.sejm.gov.pl/eli/acts/DU/1991/91/text/U/D19910091Lj.pdf)
(t.j. Dz.U. 2026 poz. 614, 1099; tekst na 21.08.2026).

- **Tajemnica: art. 18.** § 1 obowiązek, § 2 trwa po odwołaniu, § 3 ustaje przy zeznaniach
  przed sądem, a gdy ujawnienie zagraża dobru państwa albo ważnemu interesowi prywatnemu,
  zwolnić może **Minister Sprawiedliwości**; § 4 wyjątki (AML, schematy podatkowe, k.s.h.).
- **Nadzór: art. 42 § 1.** Minister Sprawiedliwości „osobiście, za pośrednictwem prezesów
  sądów apelacyjnych lub sądów okręgowych albo przez wyznaczone osoby”.
- **Nadzór samorządowy: art. 44.** Wykonuje go **rada izby notarialnej** (nie KRN) przez
  wizytatorów; wizytacja każdej kancelarii co najmniej raz na 4 lata; protokół trafia do
  Ministra.
- **Uprawnienia nadzoru: art. 45.** Wgląd w czynności notarialne, żądanie wyjaśnień,
  zarządzanie usunięcia uchybień, żądanie wszczęcia postępowania dyscyplinarnego.
- **Dyscyplina: art. 50, 53, 58, 63a.** Sądy dyscyplinarne izb notarialnych, Wyższy Sąd
  Dyscyplinarny, kasacja do Sądu Najwyższego. Wniosek o wszczęcie składa Minister
  Sprawiedliwości lub rada właściwej izby. KRN ma tylko prawo kasacji (art. 63a § 1).
- **Krajowa Rada Notarialna: art. 40.** Zadania reprezentacyjne, opiniodawcze i uchwałodawcze:
  m.in. regulamin wewnętrznego urzędowania kancelarii (§ 1 pkt 1), wypowiadanie się w sprawie
  zasad etyki (pkt 7), wybór rzecznika dyscyplinarnego (pkt 5). **Brak kompetencji kontrolnej
  wobec pojedynczego notariusza i wobec jego dostawców IT.** Realna dźwignia KRN jest
  normatywna: regulamin urzędowania kancelarii i stanowiska.
- **RODO: art. 78b i 78c.** Art. 15 ust. 1 i 3, art. 18 i 19 RODO stosuje się tylko w zakresie
  nienaruszającym tajemnicy; art. 78c: tajemnica **nie ustaje**, gdy ujawnienia żąda Prezes
  UODO.

### 3.2 Adwokaci

[Prawo o adwokaturze](https://api.sejm.gov.pl/eli/acts/DU/1982/124/text/U/D19820124Lj.pdf)
(t.j. Dz.U. 2024 poz. 1564 ze zm., ostatnio 2026 poz. 1290; tekst na 19.10.2026).

- **Tajemnica: art. 6.** Wszystko, o czym adwokat dowiedział się w związku z udzielaniem
  pomocy prawnej; bez ograniczenia w czasie; **nie można zwolnić** co do faktów poznanych
  przy udzielaniu pomocy prawnej lub prowadzeniu sprawy (ust. 3); wyjątek AML (ust. 4).
- **Samorząd: art. 3 ust. 1 pkt 3 i 5** (nadzór nad przestrzeganiem przepisów o wykonywaniu
  zawodu, etyka); **art. 36**: wizytacje kancelarii prowadzi **okręgowa rada adwokacka**.
- **Minister Sprawiedliwości: art. 14** (zaskarżanie uchwał do SN), **art. 90 ust. 2**
  (polecenie wszczęcia dochodzenia; część o postępowaniu przed sądem dyscyplinarnym utraciła
  moc wyrokiem TK K 4/08), ust. 2a (prawa strony).
- **Dyscyplina: art. 80, 91, 91a.** Sąd dyscyplinarny izby adwokackiej, Wyższy Sąd
  Dyscyplinarny, kasacja do SN (strony, Minister Sprawiedliwości, RPO, Prezes NRA).
- **RODO: art. 16a i 16b** (brzmienie od 17.10.2026). Tajemnica nie ustaje, gdy ujawnienia
  żąda „organ nadzorczy, którego sprawa dotyczy” w rozumieniu art. 4 pkt 22 RODO.

### 3.3 Radcowie prawni

[Ustawa o radcach prawnych](https://api.sejm.gov.pl/eli/acts/DU/1982/145/text/U/D19820145Lj.pdf)
(t.j. Dz.U. 2024 poz. 499 ze zm., ostatnio 2026 poz. 731, 846; tekst na 8.10.2026).

- **Tajemnica: art. 3 ust. 3-6** (konstrukcja jak u adwokatów).
- **Samorząd: art. 22(1).** **Rada okręgowej izby** kontroluje i ocenia wykonywanie zawodu
  przez wizytatorów. **Art. 5 ust. 3**: nadzór Ministra Sprawiedliwości nad samorządem
  „w zakresie i formach określonych ustawą”.
- **Dyscyplina: art. 64 i nast.** Okręgowe sądy dyscyplinarne, Wyższy Sąd Dyscyplinarny,
  rzecznicy dyscyplinarni i Główny Rzecznik Dyscyplinarny (art. 42); Minister może polecić
  wszczęcie dochodzenia; kasacja do SN (strony, Minister, RPO, Prezes KRRP).
- **RODO: art. 5a-5d** (po nowelizacji 2026 poz. 731). Art. 5b jak art. 16b u adwokatów.

### 3.4 Sędziowie i pytanie o KRS

[Prawo o ustroju sądów powszechnych](https://api.sejm.gov.pl/eli/acts/DU/2001/1070/text/U/D20011070Lj.pdf)
(tekst na 16.09.2026) i
[ustawa o KRS](https://api.sejm.gov.pl/eli/acts/DU/2011/714/text/U/D20110714Lj.pdf)
(t.j. Dz.U. 2024 poz. 1186; tekst na 4.09.2024).

- **Tajemnica: art. 85 p.u.s.p.** Zwolnić może Minister Sprawiedliwości (§ 3).
- **Dyscyplina: art. 110, 112, 112b, 114.** Sądy dyscyplinarne przy sądach apelacyjnych
  i Sąd Najwyższy (Izba Odpowiedzialności Zawodowej); oskarżycielami są Rzecznik Dyscyplinarny
  Sędziów Sądów Powszechnych, jego zastępcy oraz ewentualnie Rzecznik Dyscyplinarny Ministra
  Sprawiedliwości. Czynności wyjaśniające podejmuje się m.in. na żądanie Ministra, prezesów
  i kolegiów sądów oraz **KRS** (art. 114 § 1).
- **KRS: art. 3 ustawy o KRS.** Ocena kandydatów na sędziów, wnioski do Prezydenta, zbiór
  zasad etyki i czuwanie nad nim, opinie. **KRS nie orzeka i nie prowadzi kontroli tajemnicy.**
- **Jedyna styczność KRS z ochroną danych: art. 175dd § 1 p.u.s.p.** Nadzór nad
  przetwarzaniem danych osobowych przez sądy: rejonowe - prezes sądu okręgowego, okręgowe -
  prezes sądu apelacyjnego, **apelacyjne - KRS**.

**Ocena: KRS nie jest właściwym adresatem.** Nie bada tajemnicy, nie ma żadnych kompetencji
wobec dostawców, a sądy to inny model wdrożenia (administratorem jest sąd, system kupuje się
w zamówieniu publicznym, nadzór nad danymi sprawują prezesi sądów). Jeżeli kiedyś powstanie
produkt dla sądów, rozmówcą będą Ministerstwo Sprawiedliwości jako dysponent systemów oraz
prezesi sądów, a nie KRS.

### 3.5 Lekarze

[Ustawa o zawodach lekarza i lekarza dentysty](https://api.sejm.gov.pl/eli/acts/DU/1997/152/text/U/D19970152Lj.pdf),
[ustawa o prawach pacjenta i RPP](https://api.sejm.gov.pl/eli/acts/DU/2009/417/text/U/D20090417Lj.pdf)
(oba teksty na 2.07.2026),
[ustawa o izbach lekarskich](https://api.sejm.gov.pl/eli/acts/DU/2009/1708/text/U/D20091708Lj.pdf)
(tekst na 20.07.2023),
[ustawa o działalności leczniczej](https://api.sejm.gov.pl/eli/acts/DU/2011/654/text/U/D20110654Lj.pdf).

- **Tajemnica: art. 40** ustawy o zawodach lekarza; **art. 13-14** ustawy o prawach pacjenta.
- **Izby lekarskie:** art. 5 ustawy o izbach (etyka, piecza nad wykonywaniem zawodu);
  art. 52b ustawy o zawodach lekarza: **okręgowa izba lekarska** wizytuje praktyki zawodowe,
  z wglądem do dokumentacji medycznej. Odpowiedzialność zawodowa: art. 53 ustawy o izbach;
  okręgowy i Naczelny Rzecznik Odpowiedzialności Zawodowej, okręgowe sądy lekarskie, Naczelny
  Sąd Lekarski, kasacja do SN (art. 95: strony, minister zdrowia, Prezes NRL).
- **Rzecznik Praw Pacjenta:** postępowanie wyjaśniające (art. 50), praktyki naruszające
  zbiorowe prawa pacjentów (art. 59), kara do 500 000 zł (art. 68).
- **Minister Zdrowia i organ rejestrowy:** kontrola podmiotów (art. 111 i 118 ustawy
  o działalności leczniczej).
- **Różnica istotna dla produktu:** tu dostawca IT jest związany tajemnicą **z mocy ustawy**.
  Art. 24 ust. 2 pkt 2 i ust. 3 ustawy o prawach pacjenta obejmuje osoby utrzymujące system
  teleinformatyczny z dokumentacją, a ust. 6 podmiot przetwarzający z umowy powierzenia.
  U notariuszy, adwokatów i radców takiego przepisu nie znaleziono; dostawca jest związany
  umownie i jako podmiot przetwarzający.

### 3.6 Wspólne: prawo karne i ochrona danych

- **[Kodeks karny](https://api.sejm.gov.pl/eli/acts/DU/1997/553/text/U/D19970553Lj.pdf)
  art. 266** (t.j. Dz.U. 2026 poz. 1342). § 1: ujawnienie wbrew ustawie **lub przyjętemu
  zobowiązaniu**, do 2 lat, ściganie na wniosek pokrzywdzonego (§ 3). § 2: funkcjonariusz
  publiczny, do 3 lat, z urzędu. Notariusz jest funkcjonariuszem publicznym (art. 115 § 13
  pkt 3). § 1 obejmuje też dostawcę, który przyjął zobowiązanie do poufności.
- **Prezes UODO** nadzoruje administratora (kancelarię) i podmiot przetwarzający (NotarAI),
  ale nie przełamuje tajemnicy zawodowej (art. 78c, 16b, 5b powyżej).
- **Wniosek z tego zestawu przepisów:** ustawodawca konsekwentnie odmawia organom nadzoru
  dostępu do treści objętej tajemnicą, nawet organowi ochrony danych. Klucz deszyfrujący
  w rękach organu nadzoru byłby technicznym obejściem tej zasady.

### 3.7 Zestawienie

| Zawód | Kontrola w kancelarii lub praktyce | Dyscyplina | Organ centralny samorządu | Nadzór państwa |
|---|---|---|---|---|
| Notariusz | rada izby notarialnej; prezesi sądów w imieniu MS | sąd dyscyplinarny izby, WSD, SN | KRN: regulamin, etyka, opinie | MS (art. 42) |
| Adwokat | okręgowa rada adwokacka | sąd dyscyplinarny izby, WSD, SN | NRA | MS, wąsko (art. 14, 90) |
| Radca prawny | rada okręgowej izby | okręgowy sąd dyscyplinarny, WSD, SN | KRRP | MS, wąsko (art. 5 ust. 3) |
| Sędzia | prezesi sądów (nadzór administracyjny) | sądy dyscyplinarne przy SA, SN | KRS: etyka, żądanie czynności | MS |
| Lekarz | okręgowa izba lekarska, organ rejestrowy | okręgowy sąd lekarski, NSL, SN | NRL | MZ, RPP |

Praktyczna konsekwencja: realne kompetencje kontrolne mają organy **okręgowe**, nie krajowe.
Pierwszym rozmówcą w notariacie powinna być rada izby notarialnej, a KRN w sprawach
standardów i etyki.

### 3.8 Czego nie udało się potwierdzić

- **Izba Odpowiedzialności Zawodowej SN.** Przepisy nadal ją wskazują; w prasie były projekty
  jej likwidacji i reformy dyscyplinarek sędziowskich. Losu tych projektów nie ustalono.
- **Status i skład KRS** jest przedmiotem sporu ustrojowego; nowelizacja ze stycznia 2026 r.
  miała zostać zawetowana 19.02.2026 (tylko wyciąg z wyszukiwarki). Tekst ustawy o KRS
  w API Sejmu ma stan na 4.09.2024.
- **Prawo o notariacie od 19.11.2026:** według jednego źródła prasowego weszła zmiana
  dotycząca elektronicznych wypisów. Tekst ujednolicony ma stan na 21.08.2026.
- **Stanowisko KRN lub izb o chmurze, dostawcach IT lub AI:** nie znaleziono. To nie dowodzi,
  że nie istnieje; strony krn.org.pl nie przeszukano systematycznie.
- **Etyka i rekomendacje samorządów** (tylko wyciągi z wyszukiwarki, bez lektury pełnych
  tekstów): nowy § 23e Zbioru Zasad Etyki Adwokackiej o narzędziach AI (uchwała NRA 41/2026),
  rekomendacje KIRP o AI (2025), art. 12 i 24-26 Kodeksu Etyki Lekarskiej, przewodniki CCBE
  (2025, 2026).
- **Z pamięci, bez sprawdzenia w tej sesji:** art. 186 Konstytucji, art. 55 ust. 3 RODO
  (organ nadzorczy nie nadzoruje sądów w ramach wymiaru sprawiedliwości), art. 4 pkt 7-8
  i art. 28 RODO, art. 180 § 2 k.p.k., połączenie funkcji Ministra Sprawiedliwości
  i Prokuratora Generalnego, przepisy o nieuczciwych praktykach rynkowych i nieuczciwej
  konkurencji (pkt 6.3).
- **eIDAS:** brak kwalifikowanej usługi zaufania polegającej na kustodii cudzych kluczy
  szyfrujących przyjęto wstępnie, na podstawie fragmentów art. 3 pkt 16 po zmianie 2024/1183.
  Listy dostawców w rejestrze NCCert nie pobrano.
- **RODO a dane zaszyfrowane bez klucza:** wyrok TSUE C-413/23 P (4.09.2025) i wytyczne
  EROD 01/2025 znane tylko ze streszczeń. Nie znaleziono stanowiska wprost o podmiocie
  przetwarzającym, który nie ma klucza.

## 4. Krytyczna ocena pomysłu

### 4.1 Co w pomyśle jest trafne

- Niezależność kustosza od operatora to rzeczywisty brak obecnej architektury i warunek
  uczciwej deklaracji (kryterium 1 w `docs/confidential-independent-custody.md`).
- Intuicja „weryfikacja bez wglądu w treść” jest poprawna i wykonalna, ale realizuje ją
  dowód publiczny, a nie posiadanie klucza.
- Samorząd zawodowy jako strona potwierdzająca ma dużą wartość dla zaufania klientów.

### 4.2 Wręczenie klucza komuś, kto go nie chce

- **Technicznie:** konto AWS ma właściciela (adres e-mail konta root, MFA, płatnik, strona
  umowy z AWS). Dopóki instytucja nie przejmie tych elementów, właścicielem pozostaje ten,
  kto konto założył, czyli NotarAI. Wysłanie komuś danych logowania niczego nie zmienia.
- **Dowodowo:** klucz bez aktywnego opiekuna to albo klucz, którego polityki nikt nie
  pilnuje, albo klucz, nad którym faktyczną kontrolę ma operator. W obu przypadkach nie
  jest spełnione założenie niezależnego kustosza. Niezależność wymaga podmiotu, który
  **aktywnie odmawia**, gdy coś się nie zgadza.
- **Operacyjnie:** podpis wydania wygasa po 24-48 h. Kustosz, który nie podpisuje, zatrzymuje
  usługę dla wszystkich kancelarii.
- **Prawnie i wizerunkowo:** publiczne przypisanie instytucji roli, której nie przyjęła, to
  ryzyko zarzutu wprowadzania w błąd oraz niemal pewne publiczne zaprzeczenie ze strony tej
  instytucji. To zamyka drogę do późniejszej współpracy.

### 4.3 Instytucja jako kustosz, nawet za zgodą

- **Brak kompetencji operacyjnych.** Samorządy nie mają zespołów administrujących kontami
  chmurowymi ani dyżurów. Błąd w polityce klucza albo utrata dostępu obciążałaby samorząd
  odpowiedzialnością wobec wszystkich kancelarii.
- **Brak podstawy ustawowej.** Katalogi zadań (np. art. 40 Prawa o notariacie) nie obejmują
  prowadzenia infrastruktury kluczy dla komercyjnego dostawcy. Organ działa w granicach
  swoich zadań; do sprawdzenia przez prawnika, czy mógłby taką rolę przyjąć umownie.
- **Konflikt ról.** Organ, który prowadzi wizytacje i wnioskuje o dyscyplinę, miałby
  techniczną możliwość odszyfrowania akt. Dla Ministra Sprawiedliwości konflikt jest
  najostrzejszy: to on zwalnia notariusza i sędziego z tajemnicy i inicjuje postępowania
  dyscyplinarne. Dla adwokatów i radców dochodzi tajemnica obrończa, chroniona właśnie przed
  państwem.
- **Jeden kustosz dla wielu zawodów** tworzy pojedynczy punkt nacisku: jedna decyzja
  administracyjna lub jeden incydent dotyczy wszystkich tajemnic naraz.
- **Odzyskiwanie i utrata.** Przy `DeletionPolicy: Retain` klucz przetrwa usunięcie stosu, ale
  utrata dostępu administracyjnego (zmiana kadencji, odejście jedynej osoby znającej
  procedurę, utrata MFA) blokuje zmiany polityki, czyli każde nowe wydanie. Zaplanowane
  usunięcie klucza przez pomyłkę oznacza trwałą utratę dostępu do dokumentów.
- **RODO.** Podmiot zdolny do nadania sobie dostępu do danych trzeba ująć w analizie ryzyka
  i w umowach. Jego rola (odrębny administrator, podmiot przetwarzający, żaden z nich)
  zależy od tego, kto decyduje o celach; wymaga opinii prawnej i wpisu w DPIA.

### 4.4 Czy niezależność od operatora w ogóle wymaga instytucji publicznej

Nie. Wymaga podmiotu, który jest (a) organizacyjnie niezależny od NotarAI, (b) operacyjnie
zdolny, (c) rozliczalny umownie i (d) sam nie ma interesu w dostępie do treści. Organ nadzoru
spełnia (a), nie spełnia (b) i (d). Kancelaria lub izba jako kustosz własnych danych spełnia
(a) i (d). Komercyjny powiernik spełnia (a)-(c), a (d) trzeba zabezpieczyć umową i tym, że
szyfrogram leży w innym koncie niż klucz.

## 5. Warianty techniczne dowodu

Kolejność od najprostszego. Warianty się uzupełniają.

### 5.1 Publiczny rejestr przejrzystości (rekomendowany pierwszy krok)

**Co to jest.** Publiczny dziennik tylko do dopisywania, w którym każdy wpis jest podpisany
i połączony skrótem z poprzednim. Wpis wydania zawiera: commit źródeł, digest obrazu
`@sha256`, PCR17, ARN i wersję definicji zadania, SHA-256 polityki klucza KMS, ARN klucza,
podpis kustosza (ECDSA P-256, już zaimplementowany w `confidential/release_approval.py`)
i znacznik czasu. Osobne wpisy: dokumenty atestacji Nitro z rzeczywistych uruchomień.
Klucz publiczny kustosza i jego odcisk publikowane kilkoma niezależnymi kanałami.

**Dlaczego każdy może to sprawdzić.** Dokument atestacji Nitro to COSE_Sign1 podpisany
łańcuchem certyfikatów do publicznego certyfikatu głównego AWS Nitro Attestation PKI; AWS
publikuje ten certyfikat i jego odcisk, a weryfikacja jest możliwa offline
([dokumentacja AWS](https://docs.aws.amazon.com/enclaves/latest/user/verify-root.html)).
Certyfikaty w łańcuchu są krótkotrwałe, więc dokument trzeba weryfikować względem chwili
wystawienia; stąd potrzeba wiarygodnego znacznika czasu przy wpisie (np. kwalifikowany
znacznik czasu, który jest uznaną usługą zaufania).

**Co dowodzi.**
- Kustosz zatwierdził dokładnie tę kombinację kodu, obrazu, pomiaru i polityki, w tym czasie.
- Dokument atestacji pochodzi z prawdziwego środowiska Nitro o podanych pomiarach.
- Historii nie zmieniono po cichu (pod warunkiem, że ktoś niezależny przechowuje kopie
  nagłówków dziennika).
- Przy odtwarzalnej kompilacji: opublikowany kod źródłowy daje dokładnie ten obraz.

**Czego nie dowodzi.**
- Że polityka klucza jest taka **teraz**; to wymaga odczytu z konta kustosza (5.2).
- Że kustosz jest organizacyjnie niezależny od operatora.
- Że kod nie wypuszcza treści dozwolonym kanałem (wyniki, logi, ruch wychodzący). To wymaga
  przeglądu kodu i testów eksfiltracji.
- Że konkretna sesja klienta trafiła do zatwierdzonego środowiska, chyba że atestacja
  zawiera wartość losową (nonce) podaną przez klienta albo klient szyfruje do klucza,
  którego odcisk sam sprawdził w rejestrze.

**Kto może korzystać.** Każdy: klient, notariusz, izba, organ nadzoru, dziennikarz, badacz.
Bez konta AWS i bez zgody NotarAI. Dla osób nietechnicznych potrzebne jest narzędzie
„sprawdź” działające lokalnie w przeglądarce oraz niezależne implementacje weryfikatora.

**Wzorce.** Dzienniki typu Sigstore Rekor; publiczny dziennik pomiarów w Apple Private Cloud
Compute, gdzie urządzenie klienta szyfruje wyłącznie do węzłów obecnych w dzienniku
(opis znany z wyciągów wyszukiwarki). Ten drugi wzorzec jest docelowy: przeglądarka
notariusza odmawia wysyłki, jeśli atestacja nie zgadza się z rejestrem.

### 5.2 Weryfikatorzy z rolą tylko do odczytu

**Co to jest.** Rola IAM w koncie kustosza i w koncie operatora ograniczona do
`kms:DescribeKey`, `kms:GetKeyPolicy`, `kms:ListGrants`, `ecs:DescribeTaskDefinition` oraz
odczytu CloudTrail. To dokładnie zakres, którego używa już
`scripts/verify_confidential_operator_boundary.py`.

**Co dowodzi.**
- Stan bieżący polityki klucza i brak grantów w chwili odczytu.
- Historię zmian polityki (zdarzenia `PutKeyPolicy`, `CreateGrant`).
- Że odszyfrowania następowały z atestacją: CloudTrail przy `Decrypt` zapisuje pomiary
  z dokumentu atestacji, w tym PCR8 i PCR17
  ([dokumentacja AWS](https://docs.aws.amazon.com/kms/latest/developerguide/ct-nitro-enclave.html)).
  Weryfikator może więc policzyć odszyfrowania z niezatwierdzonym pomiarem; powinno ich być
  zero.

**Czego nie dowodzi.** Tego, co działo się między odczytami, jeśli dziennik CloudTrail nie
jest chroniony przed kustoszem i kopiowany na zewnątrz; poprawności kodu; niezależności
kustosza.

**Kto może korzystać.** Wskazane podmioty: izba, audytor działający dla izby, klient
korporacyjny. Instytucja nie musi mieć własnych kompetencji AWS, jeśli zleci odczyt
audytorowi albo dostanie okresowe podpisane migawki publikowane w rejestrze 5.1.

**Uwaga o danych.** CloudTrail nie zawiera treści dokumentów, ale zawiera metadane: czas,
rolę, identyfikator kancelarii. Z liczby i pory odszyfrowań da się wnioskować o aktywności
kancelarii. Weryfikator instytucjonalny powinien dostawać widok zagregowany albo
pseudonimizowany; wymaga wpisu w DPIA.

### 5.3 Wielopodpis m-z-n dla zmian polityki klucza

**Stan faktyczny.** KMS nie ma natywnego kworum dla `kms:PutKeyPolicy`. Usługa Multi-party
approval obejmuje tylko AWS Backup i AWS Payment Cryptography
([dokumentacja AWS](https://docs.aws.amazon.com/mpa/latest/userguide/what-is.html)).
Kworum w CloudHSM nie dotyczy polityk KMS. Zewnętrzny magazyn kluczy (XKS) pozwala zbudować
własną autoryzację, ale obsługuje tylko klucze symetryczne, a projekt używa RSA_3072.

**Wykonalna konstrukcja.**
1. Jedyną tożsamością z `kms:PutKeyPolicy` jest zautomatyzowana rola w koncie kustosza, która
   stosuje zmianę wyłącznie wtedy, gdy manifest zmiany ma m z n poprawnych podpisów
   (np. 2 z 3: kustosz operacyjny, audytor, przedstawiciel samorządu).
2. Poświadczenia awaryjne konta (root, MFA) są podzielone i zdeponowane, tak aby pojedyncza
   osoba nie mogła ominąć kworum; każde ich użycie jest widoczne w CloudTrail i w rejestrze.
3. Ten sam próg podpisów obowiązuje w bramce uruchomienia (`check_release()`), czyli runner
   wymaga k z n podpisów pod wydaniem.

**Co dowodzi.** Żadna pojedyncza strona, w tym kustosz, nie zmieni polityki ani nie
zatwierdzi wydania sama.

**Czego nie dowodzi.** Braku zmowy m stron; uczciwości właściciela konta (root pozostaje
zaufaniem szczątkowym); poprawności kodu automatu, który sam wymaga audytu i wpisu
w rejestrze.

**Kto może korzystać.** Sygnatariusze bezpośrednio; wszyscy pozostali pośrednio przez
rejestr, w którym widać, kto podpisał każdą zmianę.

**Ocena udziału samorządu.** Możliwy tylko za zgodą i tylko jako jeden z n, nigdy jako
podpis wymagany bezwzględnie. Podpis wymagany bezwzględnie daje prawo weta nad każdym
wydaniem i zatrzymuje poprawki bezpieczeństwa, gdy sygnatariusz jest niedostępny.

### 5.4 Kustosz komercyjny, samorząd jako świadek

**Co to jest.** Kustoszem jest podmiot na umowie: firma audytorska lub bezpieczeństwa,
dostawca usług zaufania, wyspecjalizowany powiernik. Samorząd nie ma żadnych uprawnień
w systemie; dostaje własny klucz i kontrasygnuje wpisy rejestru albo tylko otrzymuje
powiadomienia o każdej zmianie.

**Co dowodzi.** Niezależny, rozliczalny umownie podmiot zatwierdził wydanie; świadek je
widział. Brak kontrasygnaty świadka jest publicznie widoczny.

**Czego nie dowodzi.** Podpis świadka nie jest certyfikacją ani oceną bezpieczeństwa.
Niezależność kustosza komercyjnego jest ograniczona tym, że płaci mu NotarAI; trzeba ją
wzmocnić umową (zakaz przyjmowania poleceń operatora co do polityki klucza, obowiązek
publikacji odmów, kara umowna, ubezpieczenie OC, okres wypowiedzenia z procedurą przekazania).

**Uwaga o słowie „kwalifikowany”.** Nie potwierdzono istnienia kwalifikowanej usługi zaufania
polegającej na przechowywaniu cudzych kluczy szyfrujących (pkt 3.8). Dostawca usług zaufania
może być kustoszem na zwykłej umowie, a status kwalifikowany dotyczy wtedy tylko jego
znaczników czasu i pieczęci użytych w rejestrze. Nie wolno pisać „kwalifikowany kustosz”.

**Kto może korzystać.** Każdy, przez rejestr.

### 5.5 Klient jako kustosz własnego klucza

Przewidziany już w `docs/confidential-independent-custody.md` („klient z własnym kontem
AWS”). Kancelaria albo izba notarialna dla swoich członków utrzymuje konto z kluczem.
Najczystszy model z punktu widzenia tajemnicy, bo klucz ma ten, kto jest nią związany.
Wykonalny dla dużych kancelarii i ewentualnie izb, niewykonalny dla małej kancelarii bez
obsługi IT. Wart zaoferowania jako opcja, nie jako model domyślny.

### 5.6 Porównanie

| Wariant | Wymaga zgody instytucji | Kto korzysta z dowodu | Główna słabość |
|---|---|---|---|
| 5.1 Rejestr publiczny | nie | każdy | nie pokazuje stanu bieżącego konta |
| 5.2 Weryfikator do odczytu | tak, jeśli ma nim być instytucja | wskazane podmioty | metadane w CloudTrail |
| 5.3 Wielopodpis m-z-n | tak | sygnatariusze, pośrednio każdy | złożoność, automat do audytu |
| 5.4 Kustosz komercyjny i świadek | tylko dla świadka | każdy | kustosza opłaca operator |
| 5.5 Klient jako kustosz | nie | dany klient | wymaga kompetencji po stronie klienta |
| 5.7 Bez kustosza treści (docelowy) | nie | każdy, a klient dla każdej swojej sesji | duża zmiana w kodzie; zależy od oprogramowania klienta |

### 5.7 Kierunek docelowy: bez kustosza treści

Kustosz jest potrzebny tylko dlatego, że dziś klucz dokumentu jest szyfrowany do klucza KMS,
a o dostępie decyduje polityka tego klucza. Jeżeli klucz nigdy nie opuszcza klienta inaczej
niż zaszyfrowany do konkretnej, sprawdzonej enklawy, nie ma polityki, którą ktoś mógłby
zmienić. Konstrukcja składa się z trzech elementów.

**A. Klucz u klienta.** Klucz kancelarii powstaje i zostaje na urządzeniu notariusza (magazyn
kluczy rozszerzenia przeglądarki lub pomocnika, docelowo sprzętowy). Kopia zapasowa: drugi
klucz albo podział na części między osoby z kancelarii.

**B. Klient sprawdza enklawę.** Enklawa generuje klucz jednorazowy i uzyskuje dokument
atestacji, który go zawiera. Oprogramowanie klienta weryfikuje: podpis i łańcuch certyfikatów
AWS Nitro, obecność pomiaru w publicznym rejestrze wydań (5.1), własną wartość losową (nonce)
w dokumencie. Dopiero wtedy szyfruje klucz dokumentu do klucza enklawy. Przy niezgodności
klucz nie jest wysyłany.

**C. Enklawa sprawdza klienta przez podpis kwalifikowany.** Podpis kwalifikowany nie szyfruje
(klucz na karcie lub u dostawcy służy tylko do podpisu), więc nie zastępuje elementu A.
Rozwiązuje natomiast pytanie, skąd enklawa wie, że zlecenie pochodzi od notariusza:

1. Notariusz jednorazowo podpisuje kwalifikowanie oświadczenie wiążące klucz urządzenia
   z kancelarią. Operator nie może podstawić cudzego klucza.
2. Codzienne zlecenia podpisuje klucz urządzenia (bez PIN-u przy każdym dokumencie). Zlecenie
   wskazuje pomiar enklawy, zadanie i okres ważności. To także sposób na pracę w tle, gdy
   notariusz jest offline.
3. Dodanie urządzenia i odzyskanie dostępu wymagają podpisu kwalifikowanego, więc nie ma
   ścieżki „operator resetuje dostęp”.
4. Podpis kwalifikowany jest równoważny własnoręcznemu, więc każde przetworzenie jest
   oświadczeniem notariusza, który osobiście odpowiada za tajemnicę.

Operator pośredniczy w przesyłaniu, ale nie może udawać ani enklawy (B), ani notariusza (C).

**Co dowodzi.** Treść może odszyfrować wyłącznie kod o pomiarze z publicznego rejestru,
i wyłącznie na zlecenie klucza poświadczonego przez notariusza. Nie istnieje strona, która
może to zmienić jednostronnie.

**Czego nie dowodzi.**
- Poprawności kodu. Rejestr i odtwarzalna kompilacja sprawiają, że każdy może go przeczytać
  i porównać; nie zastępują przeglądu.
- Wiarygodności sprzętu i podpisu AWS, który jest korzeniem konstrukcji.
- Braku wycieku dozwolonym kanałem (wyniki, logi, ruch wychodzący).
- Uczciwości oprogramowania klienta, jeśli pochodzi od operatora bez niezależnej kontroli.
  Weryfikator musi być w rozszerzeniu lub pomocniku, w wydaniach podpisanych, odtwarzalnych
  i wpisanych do rejestru, a nie w kodzie strony pobieranym przy każdym wejściu.

**Kto może korzystać z dowodu.** Każdy z rejestru (jak w 5.1); dodatkowo sam klient ma dowód
dla każdej własnej sesji, bo to jego oprogramowanie podjęło decyzję o wydaniu klucza.

**Rola instytucji.** Żadnej władzy nad kluczem. Sensowna rola to przechowywanie niezależnych
kopii nagłówków rejestru, żeby operator nie mógł pokazać różnym klientom różnych wersji.

**Problemy do rozwiązania.**
- Certyfikat kwalifikowany potwierdza tożsamość osoby, nie zawód. Powiązanie z notariuszem
  wymaga urzędowego wykazu; nie sprawdzono, czy jest dostępny maszynowo.
- Certyfikat zawiera dane osobowe (imię, nazwisko, zwykle identyfikator oparty na PESEL).
  Podpisów kwalifikowanych nie wolno publikować w rejestrze ani zapisywać w logach;
  weryfikacja wyłącznie w enklawie.
- Enklawa nie ma ruchu wychodzącego do dostawców certyfikatów, więc potwierdzenie ważności
  (OCSP lub CRL) i znacznik czasu dostarcza klient razem z poświadczeniem.
- Lista zaufanych dostawców musi być w mierzonym obrazie i aktualizowana przez wydania.
- Wymiana certyfikatu co 2-3 lata wymaga ponownego poświadczenia klucza urządzenia.
- Wielu użytkowników w kancelarii (zastępca, asesor, pracownicy): delegacja podpisana przez
  notariusza, z zakresem i terminem.
- Podpisy w chmurze dostawcy, karty i czytniki różnią się integracją; do sprawdzenia na
  prawdziwym sprzęcie.
- Odrzucono wyprowadzanie klucza szyfrującego z podpisu pod stałym tekstem: działa tylko dla
  części algorytmów, a wymiana certyfikatu oznaczałaby utratę dokumentów.
- Odrzucono zamrożenie polityki klucza KMS jako rozwiązanie docelowe: właściciel konta
  prawdopodobnie może odzyskać dostęp przez wsparcie AWS (niezweryfikowane).

**Co trzeba przestawić w kodzie (przegląd z 22.11.2026, bez zmian w kodzie).**

| Miejsce | Stan dziś | Zmiana |
|---|---|---|
| `static/confidential-crypto.js` | szyfruje klucz dokumentu do klucza publicznego KMS, sprawdza tylko odcisk tego klucza | szyfrowanie do klucza enklawy po weryfikacji atestacji; przeniesienie do rozszerzenia |
| `rozszerzenie/` | brak kodu poufnego przetwarzania | weryfikator atestacji i rejestru, magazyn klucza kancelarii, podpisywanie zleceń |
| `confidential/nsm_recipient.py` | atestacja z `nonce: None`, `user_data: None`, odbiorcą jest KMS | nonce klienta i powiązanie z sesją w `user_data`; odbiorcą jest klient |
| `confidential/envelope.py` | koperta wymaga `kms_key_arn` i klucza opakowanego RSA | nowa wersja koperty z odbiorcą-enklawą; stara zostaje na okres przejściowy |
| `confidential/attested_kms.py`, `nitro_unwrapper.py` | jedyna droga do klucza dokumentu | ścieżka przejściowa; docelowo poza obiegiem dokumentów |
| `confidential/worker.py`, `dispatch.py`, `job_ledger.py` | zadanie jednorazowe z kolejki, bez udziału klienta | sesja z klientem albo zadanie w tle na podstawie podpisanego zlecenia |
| `confidential/signed_approval.py` | zgody Ed25519; rejestr kluczy w DynamoDB wypełniany osobną procedurą | korzeniem rejestru staje się poświadczenie podpisem kwalifikowanym, weryfikowane w enklawie |
| brak | brak weryfikacji podpisów kwalifikowanych (XAdES/CAdES/PAdES) i listy zaufania | nowy moduł w obrazie enklawy |
| `confidential/private_egress.py` | zamknięty ruch wychodzący | bez zmian; ważność certyfikatów dostarcza klient |
| `confidential/release_approval.py`, `operator_boundary.py`, `pilot_preflight.py` | bramki kustosza dla ścieżki KMS | zostają dla ścieżki przejściowej; podpisy wydań zasilają rejestr |
| brak | brak rejestru przejrzystości i odtwarzalnej kompilacji | nowe |

**Etapy.**
0. Rejestr przejrzystości i narzędzie weryfikacji (5.1). Niezależne od reszty.
1. Atestacja z nonce klienta i weryfikator w rozszerzeniu, równolegle do ścieżki KMS.
2. Poświadczenie klucza urządzenia podpisem kwalifikowanym; rejestr kluczy przestaje zależeć
   od operatora.
3. Wydanie klucza dokumentu bezpośrednio enklawie; KMS znika z obiegu dokumentów.
4. Podpisane zlecenia dla zadań w tle i delegacje dla pracowników kancelarii.

Do etapu 3 potrzebny jest kustosz ścieżki KMS. Na pilota: kancelaria pilotażowa jako kustosz
wyłącznie własnych danych (5.5), na danych syntetycznych.

**Do weryfikacji przed projektem szczegółowym:** okres ważności certyfikatów w dokumencie
atestacji i wynikające z niego ograniczenia sesji; sposób dostarczenia atestacji klientowi
(enklawa nie przyjmuje połączeń przychodzących); czy cały obecny przepływ zadań da się
przestawić bez utraty funkcji.

## 6. Rekomendacja

### 6.1 Co zrobić najpierw (bez udziału instytucji)

1. Przyjąć rozdział ról z pkt 2 i zrezygnować z koncepcji „klucz dla KRN”. Przyjąć pkt 5.7
   jako kierunek docelowy i budować etapami tam opisanymi.
2. Zaprojektować i zbudować rejestr przejrzystości (5.1) wraz z narzędziem weryfikacji
   offline. Podpis wydań i weryfikator już istnieją; brakuje publikacji, łańcucha wpisów,
   znaczników czasu, zapisu dokumentów atestacji i odtwarzalnej kompilacji.
3. Kustosz na okres przejściowy: kancelaria pilotażowa jako kustosz wyłącznie własnych danych
   (5.5), na danych syntetycznych. Konto AWS zakłada i opłaca kancelaria, na własny adres
   i z własnym MFA, poza organizacją AWS operatora; operator nie zna haseł, nie ma roli
   administratora i nie podpisuje wydań w jej imieniu. Dla pozostałych kancelarii kustosz
   pozostaje pytaniem otwartym do czasu etapu 3 z pkt 5.7 (`docs/czeka-na-dostep.md`, NA-16).
4. Rozstrzygnąć kwestię 24-48 h ważności podpisu: albo kustosz ma automat podpisujący po
   świeżej weryfikacji obu kont, albo ważność trzeba inaczej związać z niezmiennością
   konfiguracji. To decyzja projektowa do osobnego przeglądu bezpieczeństwa.
5. Zlecić opinię prawną: rola kustosza w RODO, podstawa umowna poufności dostawcy wobec
   kancelarii, dopuszczalność przyjęcia roli świadka przez samorząd.

### 6.2 Co wymaga rozmów z instytucjami

Kolejność według realnych kompetencji i szansy na odpowiedź:

1. **Wybrana rada izby notarialnej** (wykonuje nadzór z art. 44). Prośba: uwagi do modelu
   i ewentualnie rola weryfikatora do odczytu przy pilocie w jednej kancelarii z tej izby.
2. **KRN** (art. 40 § 1 pkt 1, 4 i 7). Prośba o stanowisko co do korzystania z narzędzi
   chmurowych przy zachowaniu tajemnicy. Nie prosić o patronat ani o klucz.
3. **Prezes UODO.** Przy okazji DPIA; ewentualnie pytanie o ocenę modelu, w którym podmiot
   przetwarzający nie ma klucza.
4. **Przy kolejnych zawodach:** okręgowa rada adwokacka i NRA, rada OIRP i KRRP, okręgowa
   izba lekarska i NRL. Dla lekarzy dodatkowo uwzględnić ustawową tajemnicę dostawcy
   (art. 24 ustawy o prawach pacjenta) i Rzecznika Praw Pacjenta.
5. **Minister Sprawiedliwości:** wyłącznie informacyjnie. Żadnych uprawnień w systemie.
6. **KRS:** nie dotyczy.

Każdej instytucji proponować najpierw rolę najlżejszą: odbiorca powiadomień o zmianach,
potem weryfikator do odczytu, potem świadek z własnym podpisem. Rola współsygnatariusza m-z-n
dopiero wtedy, gdy instytucja sama o nią poprosi i wskaże zespół.

### 6.3 Co wolno uczciwie napisać na stronie

Obowiązują ograniczenia z `docs/confidential-independent-custody.md`: do czasu audytu
i testów na żywo nie wolno twierdzić, że operator nie może odczytać dokumentów.

**Wolno, gdy dana rzecz faktycznie działa:**
- „Publikujemy rejestr wydań: digest obrazu, pomiar środowiska i skrót polityki klucza. Każdy
  może je zweryfikować naszym otwartym narzędziem lub własnym.”
- „Klucze szyfrujące znajdują się na koncie prowadzonym przez [nazwa kustosza], niezależnym
  od NotarAI” - dopiero po zawarciu umowy i za zgodą kustosza na użycie nazwy.
- „Tajemnicę notarialną reguluje art. 18 Prawa o notariacie; nadzór nad notariuszami
  sprawują Minister Sprawiedliwości i rady izb notarialnych” - jako informacja o prawie,
  bez sugestii związku z produktem.
- „Projekt architektury i dokumentacja dowodów są publiczne” z linkiem.

**Nie wolno:**
- „Pod nadzorem KRN”, „zatwierdzone przez”, „zgodne z wymogami izby”, „certyfikowane”,
  logotypy samorządów, wspólne zdjęcia sugerujące partnerstwo.
- „Klucze przekazaliśmy Krajowej Radzie Notarialnej” ani „KRN może w każdej chwili sprawdzić”,
  jeśli KRN tej roli nie przyjęła.
- „Zaprosiliśmy X do nadzoru” z nazwą instytucji, zanim odpowie. Zaproszenie bez odpowiedzi
  działa jak sugestia udziału.
- „Kwalifikowany kustosz” (pkt 5.4), „nikt nie ma dostępu”, „zero knowledge”.

Powód poza uczciwością: klienci to zawodowi prawnicy, a przypisanie instytucji roli, której
nie przyjęła, może być oceniane jako wprowadzające w błąd oznaczenie usługi (podstawy prawne
do potwierdzenia przez prawnika, pkt 3.8).

**Wartość marketingowa bez instytucji.** Publiczny, sprawdzalny rejestr jest mocniejszym
argumentem niż patronat: konkurencja może kupić opinię, ale nie może udawać dowodu, który
każdy weryfikuje sam. Udział samorządu jako świadka warto dodać później, gdy będzie
prawdziwy.

## 7. Otwarte pytania do właściciela

1. Rozstrzygnięte 22.11.2026: kierunek docelowy to pkt 5.7; kustoszem pilota jest kancelaria
   pilotażowa dla własnych danych.
2. Kto ma być kustoszem ścieżki KMS dla pozostałych kancelarii do czasu etapu 3: podmiot
   komercyjny na umowie, czy wstrzymujemy się z innymi kancelariami do etapu 3?
8. Gdzie ma mieszkać klucz kancelarii i weryfikator: rozszerzenie przeglądarki, pomocnik,
   czy oba? Od tego zależy zakres etapu 1.
9. Czy kancelaria pilotażowa udostępni prawdziwy podpis kwalifikowany do testu etapu 2
   (`docs/czeka-na-dostep.md`, NA-17)?
3. Czy rejestr przejrzystości ma być w pełni publiczny od pierwszego dnia, w tym z kodem
   źródłowym części działającej w Nitro (warunek odtwarzalnej kompilacji)?
4. Czy masz istniejący kontakt w którejś izbie notarialnej lub w KRN, od którego można zacząć
   rozmowę nieformalnie?
5. Czy opcja „klient jako kustosz własnego klucza” ma wejść do oferty dla dużych kancelarii?
6. Kolejność zawodów po notariuszach: adwokaci i radcowie (model prawny prawie identyczny)
   czy lekarze (inny reżim, ustawowa tajemnica dostawcy, inny regulator)?
7. Czy zlecić opinię prawną z pkt 6.1 ppkt 5 przed rozmowami z instytucjami?
