# notarai.pl (SaaS) — co doszło i jak włączyć

## Nowe pliki
- `magazyn.py`      — pliki spraw: dysk (jak dotąd) albo dysk-cache + S3
- `autoryzacja.py`  — tokeny kancelarii + panel admina /api/admin/*
- `Dockerfile`      — kontener dla ECS Fargate (x86_64, użytkownik bez uprawnień roota)
- `infra/notarai-wdrozenie-iam.yaml` — CloudFormation: polityka dla tozsamosci, ktora wdraza stos ponizej (wdraza ja administrator konta, raz)
- `infra/notarai-s3.yaml` — CloudFormation: bucket S3 (szyfrowany, prywatny, wersjonowany, tylko TLS) + polityka IAM aplikacji (S3 + Bedrock we wszystkich regionach UE, bo profile `eu.` routują poza Frankfurt)
- `infra/notarai-budowanie.yaml` — CloudFormation: ECR (niezmienne tagi, skanowanie), bucket paczek źródeł, CodeBuild budujący obraz w AWS
- `infra/notarai-certyfikat.yaml` — CloudFormation: certyfikat ACM dla app.notarai.pl, walidacja DNS
- `infra/notarai-aplikacja.yaml` — CloudFormation: ECS Fargate + ALB z HTTPS, token admina generowany w Secrets Manager, role wykonawcza i zadania
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
| logowanie | brak | Bearer token per kancelaria |
| env | nic | PIECZAPP_MAGAZYN=s3, PIECZAPP_S3_BUCKET, PIECZAPP_MULTI=true, PIECZAPP_ADMIN_TOKEN |

## Uruchomienie SaaS

Konto AWS fbpl (127621462971), region eu-central-1, profil CLI `notarai-admin`.
App Runner nie przyjmuje nowych klientów od 30.04.2026, dlatego ECS Fargate.
Express Mode odpada, bo nie pozwala podnieść limitu bezczynności load balancera,
a odczyt skanów przez model trwa kilka minut. Docker lokalnie nie jest potrzebny.

0. Bucket spraw: stos `notarai-s3` (wdrożony 17.09.2026).
1. Budowanie i certyfikat:
   `aws cloudformation deploy --stack-name notarai-budowanie --template-file infra/notarai-budowanie.yaml --capabilities CAPABILITY_NAMED_IAM --tags projekt=notarai --profile notarai-admin --region eu-central-1`
   `aws cloudformation create-stack --stack-name notarai-certyfikat --template-body file://infra/notarai-certyfikat.yaml --parameters ParameterKey=Domena,ParameterValue=app.notarai.pl --tags Key=projekt,Value=notarai --profile notarai-admin --region eu-central-1`
   Potem dodaj w az.pl rekord CNAME walidacji z ACM (konsola ACM albo
   `aws acm describe-certificate`) i zostaw go na stałe - służy do odnawiania.
2. Obraz: `powershell -ExecutionPolicy Bypass -File infra\2-zbuduj-obraz.ps1`
   Pakuje tylko zacommitowany kod (`git archive HEAD`), tag = skrót commita.
3. Aplikacja: `powershell -ExecutionPolicy Bypass -File infra\3-wdroz-aplikacje.ps1`
   Wymaga certyfikatu ISSUED. Na końcu wypisuje cel CNAME dla app.notarai.pl.
4. Token admina: konsola AWS -> Secrets Manager -> `notarai/admin-token` ->
   Retrieve secret value. Wartość generuje AWS, nie ma jej w kodzie ani w logach.
5. Dodaj kancelarię:
   `curl -X POST https://app.notarai.pl/api/admin/kancelarie -H "Authorization: Bearer $ADMIN" -H "Content-Type: application/json" -d '{"nazwa":"Kancelaria X"}'`
   → odpowiedź zawiera token JEDEN RAZ. Przekaż kancelarii.
6. Nowa wersja aplikacji: commit, potem etap 2 i 3. Podmiana bez przestoju.
7. Kancelaria otwiera stronę i wkleja token w oknie ,,Dostęp kancelarii''.
   Token zostaje w localStorage tej przeglądarki i leci w nagłówku przy każdym
   żądaniu. ,,Wyloguj kancelarię'' w stopce paska bocznego go kasuje.
   W trybie lokalnym okno się nie pokazuje.

## Czego celowo NIE ruszałem
- `bedrock.py`, `walidacja.py`, `prompty.py`, `dokumenty.py` — zero zmian
- transkrypcja i asysta formularzy (Playwright) — funkcje stanowiska lokalnego,
  w kontenerze wyłączone (Dockerfile pomija te zależności)
- wymuszenie profilu `eu.` — bez zmian, dalej twarde

## Znane granice (uczciwie)
- Rejestr kancelarii w JSON (S3) — wystarczy do ~kilkudziesięciu kancelarii;
  przy większej skali przenieś do DynamoDB/RDS.
- Równoległy zapis tej samej sprawy z dwóch przeglądarek: ostatni wygrywa
  (wersjonowanie S3 pozwala odzyskać poprzednią wersję).
- Token kancelarii leży w localStorage przeglądarki: wystarczy dla stanowiska
  w kancelarii, ale nie wygasa sam. Przy szerszym gronie odbiorców warto przejść
  na sesje z terminem waznosci.
- Kontener w publicznej podsieci domyślnego VPC, bez NAT: wejście blokuje grupa
  bezpieczeństwa (tylko ruch z load balancera). Prywatne podsieci z NAT to
  osobny, stały koszt; warto przy większej skali.
- Jedna kopia aplikacji. Przy dwóch równoległych kopiach lokalny cache sprawy
  mógłby być nieaktualny względem S3 - przed skalowaniem w poziomie trzeba to
  rozwiązać.
