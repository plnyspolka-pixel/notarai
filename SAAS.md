# notarai.pl (SaaS) — co doszło i jak włączyć

## Nowe pliki
- `magazyn.py`      — pliki spraw: dysk (jak dotąd) albo dysk-cache + S3
- `autoryzacja.py`  — logowanie per osoba, panel admina /api/admin/*, dostęp serwisowy /api/serwis
- `aml_listy.py`, `aml_dopasowanie.py`, `aml.py` — listy sankcyjne (UE, ONZ, MSWiA) i PEP (Sejm, KPRM, Wikidata) pobierane do aplikacji, dopasowanie liczone u nas, decyzje notariusza w śladzie audytowym (docs/rejestry.md)
- `crbr.py`         — beneficjenci rzeczywiści spółki z oficjalnej bramki CRBR Ministerstwa Finansów
- `Dockerfile`      — kontener dla ECS Fargate (x86_64, użytkownik bez uprawnień roota)
- `infra/notarai-wdrozenie-iam.yaml` — CloudFormation: polityka dla tozsamosci, ktora wdraza stos ponizej (wdraza ja administrator konta, raz)
- `infra/notarai-s3.yaml` — CloudFormation: bucket S3 (szyfrowany, prywatny, wersjonowany, tylko TLS) + polityka IAM aplikacji (S3 + Bedrock we wszystkich regionach UE, bo profile `eu.` routują poza Frankfurt)
- `infra/notarai-budowanie.yaml` — CloudFormation: ECR (niezmienne tagi, skanowanie), bucket paczek źródeł, CodeBuild budujący obraz w AWS
- `infra/notarai-certyfikat.yaml` — CloudFormation: certyfikat ACM dla app.notarai.pl, walidacja DNS
- `infra/notarai-aplikacja.yaml` — CloudFormation: ECS Fargate + ALB z HTTPS, token admina generowany w Secrets Manager, role wykonawcza i zadania
- `infra/notarai-repozytorium.yaml` — CloudFormation: dawne repozytorium kodu w CodeCommit (nieaktualne od 07.11.2026, kod jest na GitHub: https://github.com/plnyspolka-pixel/notarai)
- `infra/wyslij-kod.ps1` — wysyła zacommitowane zmiany na GitHub (przepina `origin` ze starego CodeCommit, jeśli trzeba)
- `infra/notarai-logowanie.yaml` — CloudFormation: logowanie użytkowników (Amazon Cognito)
- `logowanie.py` — logowanie, pierwsze hasło, odzyskiwanie hasła, sprawdzanie tokenu tożsamości
- `stanowiska.py` — stanowisko osoby w zespole (notariusz / aplikant / sekretariat): co może zrobić w sprawach; serwer odmawia 403, UI chowa przyciski. Nadaje właściciel w oknie „Zespół kancelarii”. Osoba bez stanowiska i właściciel mają pełne uprawnienia.
- `korespondencja.py` — poczta e-mail do spraw: IMAP (TLS) albo katalog .eml, propozycje przypisania, pliki sprawy, ustalenia ze źródłem (sekcja „Poczta e-mail do spraw”)
- `scripts/demo_odcinek01.py` — fikcyjne dane demo i lokalny serwer z kontami 4 ról do nagrania odcinka 01 (`docs/odcinek-01-luki.md`)
- `infra/2-zbuduj-obraz.ps1`, `infra/3-wdroz-aplikacje.ps1` — etapy wdrożenia jednym poleceniem
- `test_magazyn.py`, `test_autoryzacja.py` — 10 testów (cały zestaw: 204 przechodzą, 1 pominięty)

- `poswiadczenia.py` + `static/poswiadczenia.html` — poświadczenie kopii: zdjęcie z telefonu
  albo skan z kopiarki (PDF, także kilka dokumentów w jednym skanie) → opis do repertorium A
  (krótka treść czynności, liczba stron, cechy dokumentu do klauzuli, taksa § 13 pkt 2/3).
  Strona `/poswiadczenia`, API `POST /api/poswiadczenia/opis` (wymaga logowania). Pliki tylko
  w katalogu tymczasowym na czas odczytu, nic nie zapisujemy ani nie logujemy. Model:
  `PIECZAPP_POSWIADCZENIA_MODEL` (domyślnie `eu.anthropic.claude-sonnet-4-6`, tylko profil `eu.`).
  Dodatkowo: projekt klauzuli poświadczenia (taksa netto, VAT, podstawa § 13, cechy dokumentu)
  z drukiem, automatyczna numeracja Rep. A i miejscowość (ustawienia w przeglądarce, bez danych
  klientów), nasłuch folderu kopiarki w Chrome/Edge (File System Access API: nowy skan jest
  odczytywany sam i przenoszony do podfolderu `odczytane`; na serwerze nic nie zostaje).

## Zmienione (minimalnie)
- `config.py` — `SPRAWY` wyliczane per kancelaria (PEP 562); tryb lokalny = stare ścieżki
- `app.py`    — middleware + router admina, `/zdrowie`, utrwalanie do S3 po zapisach,
                pobieranie z S3 przed odczytem, lista spraw odporna na restart kontenera

## Tryby
| | lokalny (domyślny) | SaaS |
|---|---|---|
| pliki | dane/sprawy (bez zmian) | S3: kancelarie/{id}/sprawy/{id}/ |
| logowanie | brak | Bearer token logowania (Cognito) per osoba |
| env | nic | PIECZAPP_MAGAZYN=s3, PIECZAPP_S3_BUCKET, PIECZAPP_MULTI=true, PIECZAPP_ADMIN_TOKEN |

## Uruchomienie SaaS

Konto AWS fbpl (127621462971), region eu-central-1, profil CLI `notarai-admin`.
Sesja profilu odnawia się sama: `aws login` zapisuje token odświeżający, a CLI
wymienia poświadczenia automatycznie, dopóki ten token jest ważny (wg
dokumentacji AWS do 90 dni). Logowanie w przeglądarce powtarzasz dopiero,
gdy skrypt poprosi. Skrypty etapu 2 i 3 sprawdzają sesję na starcie i wypisują
gotowe polecenie logowania, zamiast wywalać się błędem AWS.
App Runner nie przyjmuje nowych klientów od 30.04.2026, dlatego ECS Fargate.
Express Mode odpada, bo nie pozwala podnieść limitu bezczynności load balancera,
a odczyt skanów przez model trwa kilka minut. Docker lokalnie nie jest potrzebny.

0. Bucket spraw: stos `notarai-s3` (wdrożony 17.09.2026).
   Kod: GitHub, https://github.com/plnyspolka-pixel/notarai (gałąź `master`).
   Nowe stanowisko: `git clone https://github.com/plnyspolka-pixel/notarai.git`.
   Wysyłka zmian: `powershell -ExecutionPolicy Bypass -File infra\wyslij-kod.ps1`.
   Do 07.11.2026 kod był w AWS CodeCommit (stos `notarai-repozytorium`);
   historia została przeniesiona 1:1 (te same skróty commitów, więc tagi
   obrazów w ECR dalej odpowiadają commitom). CodeCommit nie przyjmuje już
   zmian, stos można usunąć, gdy nikt z niego nie korzysta.
1. Budowanie i certyfikat:
   `aws cloudformation deploy --stack-name notarai-budowanie --template-file infra/notarai-budowanie.yaml --capabilities CAPABILITY_NAMED_IAM --tags projekt=notarai --profile notarai-admin --region eu-central-1`
   `aws cloudformation create-stack --stack-name notarai-certyfikat --template-body file://infra/notarai-certyfikat.yaml --parameters ParameterKey=Domena,ParameterValue=app.notarai.pl --tags Key=projekt,Value=notarai --profile notarai-admin --region eu-central-1`
   Potem dodaj w az.pl rekord CNAME walidacji z ACM (konsola ACM albo
   `aws acm describe-certificate`) i zostaw go na stałe - służy do odnawiania.
2. Obraz: `powershell -ExecutionPolicy Bypass -File infra\2-zbuduj-obraz.ps1`
   Pakuje tylko zacommitowany kod (`git archive HEAD`), tag = skrót commita.
3. Aplikacja: `powershell -ExecutionPolicy Bypass -File infra\3-wdroz-aplikacje.ps1`
   Wymaga certyfikatu ISSUED. Na końcu wypisuje cel CNAME dla app.notarai.pl.
4. Panel administratora: https://app.notarai.pl/admin. Stały administrator
   to parametr stosu `Administratorzy` (domyślnie plnyspolka@gmail.com, kilka
   adresów po przecinku). Jego konto zakłada się samo przy pierwszym otwarciu
   panelu po wdrożeniu - zaproszenie z hasłem tymczasowym przychodzi e-mailem,
   potem logujesz się hasłem, sesja trzyma 30 dni. Kolejnych administratorów
   dodajesz w panelu (sekcja Administratorzy). Token z Secrets Manager
   (`notarai/admin-token`) zostaje wyłącznie na awarię: „Wejdź tokenem awaryjnym”.
5. Dodaj kancelarię: w panelu /admin wpisz nazwę kancelarii i e-mail
   notariusza, wybierz miejsce na pliki. Jeden przycisk zakłada kancelarię,
   konto właściciela i wysyła zaproszenie. Właściciel zaprasza swój zespół
   sam (pasek boczny -> Zespół kancelarii). W panelu też: ponowne wysłanie
   zaproszenia, rola właściciela, wyłączenie i włączenie kancelarii. Panel
   nie otwiera spraw: administrator zaprasza tylko pierwszego właściciela,
   a do spraw wchodzi wyłącznie przez dostęp serwisowy, który właściciel
   kancelarii sam włącza w oknie Zespół kancelarii (umowa powierzenia § 5
   ust. 4). Gdy jest włączony, w karcie kancelarii pojawia się przycisk
   „Otwórz sprawy (dostęp serwisowy)”.
6. Nowa wersja aplikacji: push na `master` (albo merge pull requesta na GitHubie).
   Po zielonych testach workflow `.github/workflows/wdrozenie.yml` sam buduje
   obraz i podmienia aplikację, bez przestoju i bez logowania do AWS. Postęp:
   zakładka Actions w repozytorium. Ręcznie: Actions -> „NotarAI - wdrozenie
   na app.notarai.pl” -> Run workflow (na `master`).
   Jednorazowo trzeba to włączyć (zalogowany jako administrator konta):
   `powershell -ExecutionPolicy Bypass -File infra\4-polacz-github.ps1 -Profil notarai-admin`
   Skrypt zakłada stos `notarai-github` (`infra/notarai-github.yaml`):
   dostawcę OIDC GitHuba i dwie role. `notarai-github-wdrozenie` przyjmuje
   wyłącznie GitHub Actions z gałęzi `master` tego repozytorium; nie ma kluczy
   dostępu, poświadczenia żyją godzinę. Zmiany w zasobach wykonuje rola
   `notarai-cloudformation`, ograniczona do zasobów `notarai-*` stosu aplikacji.
   GitHub zmienia tylko tag obrazu; pozostałe parametry stosu (certyfikat,
   sekrety, e-mail, cena) zostają z poprzedniego wdrożenia. Etap 2 i 3 z
   komputera dalej działają: są potrzebne, gdy dochodzi nowy sekret
   (np. `notarai/stripe`) albo zmieniasz parametr, np. liczbę kopii czy cenę.
   Bezpieczeństwo: każdy, kto może pushować na `master`, wdraża na produkcję.
   Warto włączyć w GitHubie ochronę gałęzi `master` (Settings -> Branches)
   z wymogiem zielonych testów.
7. Logowanie użytkowników (opcjonalne, ale zalecane):
   `aws cloudformation deploy --stack-name notarai-logowanie --template-file infra/notarai-logowanie.yaml --capabilities CAPABILITY_NAMED_IAM --tags projekt=notarai --profile notarai-admin --region eu-central-1`
   Potem etap 3 jeszcze raz - skrypt sam wykryje stos i poda aplikacji dane puli.
   Konta zakłada administrator:
   `curl -X POST https://app.notarai.pl/api/admin/uzytkownicy -H "Authorization: Bearer $ADMIN" -H "Content-Type: application/json" -d '{"email":"notariusz@kancelaria.pl","kancelaria":"kancelaria-x"}'`
   Użytkownik dostaje e-mail z hasłem tymczasowym i ustawia własne przy pierwszym logowaniu.
   Hasła przechowuje Cognito; aplikacja ich nie zapisuje.
8. Wspólnego tokenu kancelarii już nie ma (usunięty 31.10.2026): dawał
   pełny dostęp do spraw temu, kto go miał, także administratorowi, który go
   wydawał. Do spraw wchodzi się tylko logując się adresem e-mail.

## Czego celowo NIE ruszałem
- `bedrock.py`, `walidacja.py`, `prompty.py`, `dokumenty.py` — zero zmian
- transkrypcja i asysta formularzy (Playwright) — funkcje stanowiska lokalnego,
  w kontenerze wyłączone (Dockerfile pomija te zależności)
- wymuszenie profilu `eu.` — bez zmian, dalej twarde

## Rok bez opieki

Co utrzymuje się samo:
- **Awaria kontenera albo całej strefy dostępności.** Działają dwie kopie
  w różnych strefach, load balancer omija chorą, ECS odtwarza brakującą.
- **Certyfikat TLS.** ACM odnawia go sam, dopóki rekord walidacyjny CNAME
  zostaje w az.pl. Bieżący jest ważny do kwietnia 2027.
- **Sesja wdrożeniowa.** Nie ma wpływu na działanie aplikacji; kontenery
  korzystają z roli IAM, nie z Twojego logowania.
- **Miejsce i koszty magazynu.** Stare wersje plików kasują się po 90 dniach,
  paczki źródeł po 14, logi po 90, w rejestrze obrazów zostaje ostatnie 15.

Co zgłosi się mailem (temat SNS `notarai-alarmy`, trzeba potwierdzić subskrypcję):
- brak choćby jednego zdrowego kontenera,
- spadek poniżej zadanej liczby kopii, czyli utrata redundancji,
- błędy 5xx aplikacji, np. gdyby model w Bedrock został wycofany,
- błędy 5xx samego load balancera,
- 80 procent miesięcznego budżetu i prognoza jego przekroczenia.

Czego żadna automatyka nie załatwi:
- **Przedłużenie domeny notarai.pl** w az.pl i pozostawienie rekordów DNS.
- **Ważna karta płatnicza** na koncie AWS. Nieopłacone konto to przestój.
- **Aktualizacje bezpieczeństwa obrazu.** Rok bez przebudowy to rok bez łatek
  Pythona i systemu. Warto przebudować obraz raz na kwartał, nawet bez zmian
  w kodzie: etap 2 i 3.
- **Cykl życia modelu.** `eu.anthropic.claude-sonnet-4-5` jest aktywny.
  Gdy zostanie wycofany, alarm błędów 5xx to wykryje, ale podmiana modelu
  w `config.py` wymaga człowieka.

## Jakość odczytu skanów

- **Warstwa tekstowa ma pierwszeństwo.** Gdy PDF został wygenerowany
  elektronicznie (wypis, zaświadczenie, wydruk KW), aplikacja bierze tekst
  wprost z pliku i zaznacza modelowi, że jest dokładny. Skany bez tekstu idą
  jako obraz.
- **Rozmiar obrazu dobierany do modelu.** Modele od wersji 4.7 wzwyż czytają
  dłuższy bok do 2576 px, starsze do 1568 px. Wysyłanie więcej nic nie daje,
  bo model i tak pomniejszy obraz, a koszt rośnie.
- **Gęste strony dzielone na dwie zachodzące części**, każda w pełnej
  rozdzielczości. Podwaja szczegół na skanach i pismie ręcznym. Nie dzielimy
  stron, które i tak mieszczą się w limicie.
- **Powyżej 20 obrazów w żądaniu** obowiązuje ostrzejszy limit rozmiaru
  (2000 px). Aplikacja sama schodzi z rozdzielczości, zamiast dostać odmowę
  z API: najpierw rezygnuje z dzielenia stron, potem z obrazów dla stron
  mających dokładny tekst, na końcu zmniejsza wszystkie strony.
- **Model: `eu.anthropic.claude-opus-4-6-v1`.** W porównaniu na tych samych
  fragmentach strony (trzy odczyty na model) Opus 4.6 odczytał wszystko
  bezbłędnie 3/3, Sonnet 4.6 0/3 - mylił numer repertorium i cyfrę PESEL.
- **Modele 4.7+ są zablokowane na koncie fbpl przez AWS.** Umowy dla
  `opus-4-7`, `opus-4-8`, `sonnet-5` i `opus-5` są zaakceptowane i mają status
  AVAILABLE, ale wywołanie zwraca „not available for this account" także dla
  konta głównego. Odblokowanie wymaga zgłoszenia do AWS Support albo działu
  sprzedaży. Po odblokowaniu wystarczy zmienić `PIECZAPP_MODEL`: rozmiar
  obrazu podniesie się sam, a parametr `temperature` zostanie pominięty,
  bo nowsze modele go odrzucają.

## Kredyty za czynności (tokenomia)

Koszt każdej czynności z modelem jest liczony z tokenów (`tokenomia.py`), a ceny
w kredytach wynikają z kosztu z narzutem co najmniej 100%. Włącza parametr stosu
`Tokenomia=true` (zmienna `PIECZAPP_TOKENOMIA`); bez niego koszty są tylko liczone.
Cennik, plany, symulacja i trzy modele biznesowe: `docs/tokenomia.md`.

## Pliki w chmurze albo u kancelarii

Kancelaria dostaje pole `przechowywanie` przy zakładaniu konta: `chmura`
(domyślnie) albo `u-klienta`. Zmiany w trakcie nie ma świadomie - zostawiałaby
sprawy w dwóch miejscach naraz.

Przy `u-klienta`:
- serwer nie zapisuje niczego; `magazyn.utrwal_sprawe()` odmawia zapisu,
- przeglądarka pracuje na punktach `/api/odczyt`, `/api/projekt`, `/api/rozmowa`,
  które przetwarzają dane w katalogu tymczasowym i kasują go zawsze,
- sprawy trafiają do folderu wskazanego przez notariusza: układ plików
  identyczny jak w chmurze (sprawa.json, odczyt.json, rozmowa.json,
  kontekst.txt, wzor.*, skany/, projekt.docx, projekt.txt),
- folder pamięta się między uruchomieniami; wymaga Chrome albo Edge,
- sprawdzenia w rejestrach są w tym trybie ukryte, bo zapisują ślad w sprawie
  po stronie serwera,
- za kopie zapasowe odpowiada kancelaria - znika wersjonowanie z S3.

## Poczta e-mail do spraw (korespondencja.py)

Okno „Poczta do przypisania”: notarai czyta skrzynkę kancelarii i dla każdej
wiadomości proponuje sprawę (sygnatura, numer KW, adres nadawcy/adresata znany
w sprawie, odpowiedź w wątku już przypisanym, nazwiska stron) — z uzasadnieniem
i pewnością. **Nic nie trafia do sprawy bez kliknięcia „Przypisz do sprawy”.**
Po przypisaniu `.eml` i załączniki są w „Plikach sprawy” (z nadawcą, datą,
tematem i rolą nadawcy), a metadane w `{sprawa}/korespondencja.json`.

Ustalenia z treści wyciąga model (Bedrock, eu-central-1) osobnym kliknięciem
(uprawnienie `sprawy_ai`). Ustalenie ma źródło: kto napisał, jaka jest jego rola
(strona / kupujący / pełnomocnik / osoba kontaktowa / bank / inny) i czy relacjonuje
cudze stanowisko („mama się zgadza”). **Ustalenia nie zmieniają pól odczytu ani
projektu** — w „Weryfikacji odczytu” pojawia się tylko komunikat, np. „W korespondencji:
1.12 (Paweł Nowak — osoba kontaktowa, 9.11). Brak potwierdzenia: Irena Nowak
(sprzedająca).”, a projekt nadal ma w tym miejscu `<<BRAK>>`.

Konfiguracja skrzynki (okno „Poczta do przypisania” → „Ustawienia skrzynki”,
uprawnienie `kancelaria`): serwer IMAP, port (993, TLS), użytkownik, folder.
Skrzynka otwierana tylko do odczytu (`BODY.PEEK[]` — wiadomości nie zmieniają
stanu „przeczytana”).
- **Chmura:** hasło zapisuje się wyłącznie w AWS Secrets Manager jako
  `notarai-skrzynka-<kancelaria>` (polityka `sekrety-skrzynki-pocztowej`
  w `infra/notarai-aplikacja.yaml`, region eu-central-1). Nie wraca do przeglądarki,
  nie trafia do S3 ani do logów. Wymaga ponownego wdrożenia stosu aplikacji.
- **Lokalnie:** zmienna `PIECZAPP_SKRZYNKA_HASLO` ustawiana w sesji (nie w `.env`
  w repozytorium).
- Microsoft 365 / Gmail (OAuth): interfejs dostawcy (`nowe`, `pobierz`) jest gotowy,
  dojdzie jako kolejna klasa obok `DostawcaImap`.
- Logi: tylko identyfikatory, liczby i statusy — bez tematów, treści, adresów i nazwisk.
- Test na żywo z prawdziwą skrzynką: `docs/czeka-na-dostep.md` (NA-9).

Demo (dane fikcyjne, domena `.test`):

    python scripts/demo_odcinek01.py przygotuj --dane dane/demo-odcinek01
    python scripts/demo_odcinek01.py serwer --dane dane/demo-odcinek01 --haslo 'Demo-Odc01!' \
        --atrapa-modelu 3 --skrzynka-demo scripts/demo_odcinek01_skrzynka

## Znane granice (uczciwie)
- Listy sankcyjne i PEP leżą jako migawki JSON w S3 (`<prefiks>/admin/listy_aml/`), a indeks
  buduje się w pamięci każdej kopii aplikacji (sekundy). Odświeża je wątek w tle co 6 h;
  obie kopie mogą to robić równolegle, zapis jest idempotentny. Wikidata bywa
  przeciążona (429) - importer ponawia, a stara migawka zostaje.
- Rejestr kancelarii w JSON (S3) — wystarczy do ~kilkudziesięciu kancelarii;
  przy większej skali przenieś do DynamoDB/RDS.
- Równoległy zapis tej samej sprawy z dwóch przeglądarek: ostatni wygrywa
  (wersjonowanie S3 pozwala odzyskać poprzednią wersję).
- Kontener w publicznej podsieci domyślnego VPC, bez NAT: wejście blokuje grupa
  bezpieczeństwa (tylko ruch z load balancera). Prywatne podsieci z NAT to
  osobny, stały koszt; warto przy większej skali.
- Dwie kopie aplikacji. Przed odczytem sprawy każda porównuje znacznik wersji
  z ETagiem pliku w S3 i odświeża swoją pamięć podręczną, gdy druga kopia
  zapisała zmianę. Nadal obowiązuje zasada: przy równoczesnym zapisie tej samej
  sprawy z dwóch miejsc ostatni wygrywa.
