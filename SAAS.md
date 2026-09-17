# notarai.pl (SaaS) — co doszło i jak włączyć

## Nowe pliki
- `magazyn.py`      — pliki spraw: dysk (jak dotąd) albo dysk-cache + S3
- `autoryzacja.py`  — tokeny kancelarii + panel admina /api/admin/*
- `Dockerfile`      — kontener dla App Runner / ECS
- `infra/notarai-s3.yaml` — CloudFormation: bucket S3 (szyfrowany, prywatny, wersjonowany, tylko TLS) + polityka IAM aplikacji (S3 + Bedrock we wszystkich regionach UE, bo profile `eu.` routują poza Frankfurt)
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

## Uruchomienie SaaS (skrót)
1. `aws cloudformation deploy --stack-name notarai-s3 --template-file infra/notarai-s3.yaml --capabilities CAPABILITY_NAMED_IAM --region eu-central-1 --profile pieczapp` → bucket + polityka IAM (bucket trzyma dane osobowe: decyzja świadoma)
2. `docker build -t notarai .` → obraz (`.dockerignore` wyklucza `dane/` i `.env`); wypchnij do ECR
3. App Runner: obraz z ECR, port 8000, rola instancji z polityką z kroku 1,
   env z sekcji wyżej (`PIECZAPP_ADMIN_TOKEN` jako referencja do Secrets Manager, nie wartość). Sonda zdrowia: `/zdrowie`.
4. Dodaj kancelarię:
   `curl -X POST https://.../api/admin/kancelarie -H "Authorization: Bearer $ADMIN" -H "Content-Type: application/json" -d '{"nazwa":"Kancelaria X"}'`
   → odpowiedź zawiera token JEDEN RAZ. Przekaż kancelarii.
5. Kancelaria otwiera stronę i wkleja token w oknie ,,Dostęp kancelarii''.
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
