# notarai.pl (SaaS) — co doszło i jak włączyć

## Nowe pliki
- `magazyn.py`      — pliki spraw: dysk (jak dotąd) albo dysk-cache + S3
- `autoryzacja.py`  — logowanie per osoba, panel admina /api/admin/*, dostęp serwisowy /api/serwis
- `Dockerfile`      — kontener dla ECS Fargate (x86_64, użytkownik bez uprawnień roota)
- `infra/notarai-wdrozenie-iam.yaml` — CloudFormation: polityka dla tozsamosci, ktora wdraza stos ponizej (wdraza ja administrator konta, raz)
- `infra/notarai-s3.yaml` — CloudFormation: bucket S3 (szyfrowany, prywatny, wersjonowany, tylko TLS) + polityka IAM aplikacji (S3 + Bedrock we wszystkich regionach UE, bo profile `eu.` routują poza Frankfurt)
- `infra/notarai-budowanie.yaml` — CloudFormation: ECR (niezmienne tagi, skanowanie), bucket paczek źródeł, CodeBuild budujący obraz w AWS
- `infra/notarai-certyfikat.yaml` — CloudFormation: certyfikat ACM dla app.notarai.pl, walidacja DNS
- `infra/notarai-aplikacja.yaml` — CloudFormation: ECS Fargate + ALB z HTTPS, token admina generowany w Secrets Manager, role wykonawcza i zadania
- `infra/notarai-repozytorium.yaml` — CloudFormation: repozytorium kodu w CodeCommit (eu-central-1) i dostęp do niego dla stanowiska
- `infra/notarai-logowanie.yaml` — CloudFormation: logowanie użytkowników (Amazon Cognito)
- `logowanie.py` — logowanie, pierwsze hasło, odzyskiwanie hasła, sprawdzanie tokenu tożsamości
- `infra/2-zbuduj-obraz.ps1`, `infra/3-wdroz-aplikacje.ps1` — etapy wdrożenia jednym poleceniem
- `test_magazyn.py`, `test_autoryzacja.py` — 10 testów (cały zestaw: 204 przechodzą, 1 pominięty)

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
   Kod: stos `notarai-repozytorium` (CodeCommit). Po wdrożeniu:
   `pip install git-remote-codecommit`, potem
   `git remote add origin codecommit::eu-central-1://pieczapp@notarai`
   i `git push -u origin master`. Historia przestaje zależeć od jednego dysku.
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
6. Nowa wersja aplikacji: commit, potem etap 2 i 3. Podmiana bez przestoju.
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

## Znane granice (uczciwie)
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
