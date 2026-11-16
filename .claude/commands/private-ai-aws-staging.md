# Claude Code: AWS — uruchomienie izolowanego pilotażu Private AI (TYLKO staging)

**Cel:** zrealizować techniczny test end-to-end: podpisane żądanie AWS_IAM → API Gateway → Lambda w prywatnych podsieciach → Bedrock Runtime przez VPC Endpoint → metadane audytu w S3 Object Lock. Wyłącznie syntetyczny obraz i stały prompt. Nie łączyć z produkcyjnymi danymi NotarAI/Finance You.

**Repo i gałąź:** `plnyspolka-pixel/notarai`, `feature/private-ai-eu-gateway-20261116`, draft PR #40.
**Zależność:** draft `plnyspolka-pixel/finyou` PR #389 — NIE MERGE przed działającym zamiennikiem OCR.
**Punkt startowy:** `infra/private-ai-pilot.yaml`, `docs/private-ai/PILOT.md`, `docs/private-ai/REGION_EVIDENCE.md`, `private_ai/preflight.py`, `tools/private_ai/{make_fixture,build_pilot_zip,smoke_pilot}.py`, `private_ai_tests/`.
**Wykonuj pracę, commituj poprawki i dowody**, a nie tylko przygotowuj kolejny plan. Nigdy nie zamieszczaj poświadczeń, promptów klientów ani danych osobowych w repo/issue/CI.

## Granice bezpieczeństwa

- **Zakaz dotykania produkcji:** nie modyfikuj `app.notarai.pl`, konta produkcyjnego, istniejących VPC, IAM, DNS, bucketów, Fargate, RDS, płatności ani danych Finance You. Istniejąca rola deploymentu `notarai-github-wdrozenie` jest produkcyjna — nie używaj jej do pilotażu. Nie wywołuj workflow `wdrozenie.yml`.
- Uruchamiaj tylko na **oddzielnym koncie AWS staging**, w `eu-central-1`, wskazanym świadomie przez operatora. Nie zgaduj identyfikatora konta, regionu, roli ani VPC. Przed każdym wywołaniem mutującym porównaj `aws sts get-caller-identity` z zaakceptowanym account ID.
- Nie używaj stałych access key. Krótkotrwałe poświadczenia przez AWS SSO/Identity Center, zatwierdzoną rolę assume-role albo OIDC na osobnym koncie. Nie zmieniaj istniejących trust policy bez zgody.
- Etap READ ONLY i poprawki kodu możesz wykonać sam. **Tworzenie zasobów/kosztów, CloudFormation execute-change-set/deploy, uruchomienie płatnych modeli lub konfiguracja nowych uprawnień wymaga jawnej akceptacji operatora**, po podaniu planu zmian i szacunku kosztów. Bez akceptacji zatrzymaj się w oznaczonym punkcie i zapisz blokadę.
- Nie przesyłaj prawdziwych KW, aktów, skanów, danych pacjentów, dokumentów bankowych, wiadomości e-mail ani PESEL. Staging akceptuje tylko **dokładny hash syntetycznego PNG** oraz jeden ustalony prompt. Nie odblokowuj tej ochrony, żeby „test przeszedł”.
- Usługa przez zwykły HTTP API Gateway ma publiczny adres sieciowy zabezpieczony AWS_IAM; to **nie** jest prywatny endpoint klienta ani certyfikowana platforma. Endpoint Bedrock w VPC to inna warstwa.
- Zielone testy CI, prefiks `eu.`, TLS czy S3 Object Lock nie są samodzielnym dowodem rezydencji UE, pełnej poufności ani niepodważalnego audytu.

## A. Odkryj stan i sprawdź ryzyka — bez mutacji

1. Na gałęzi PR #40 uruchom pełne testy `python -m unittest discover -s private_ai_tests -v`, `python -m compileall -q private_ai`, `cfn-lint infra/private-ai-pilot.yaml`, i kontrolę CI. Nie zmieniaj master.
2. Sprawdź czy AWS CLI, boto3, cfn-lint i ważna sesja SSO są dostępne. Uruchom:
   ```bash
   aws sts get-caller-identity --output json
   aws configure list
   aws cloudformation validate-template --template-body file://infra/private-ai-pilot.yaml --region eu-central-1
   ```
   Pierwsze dwa polecenia sprawdzają bieżącą tożsamość; **nie traktuj istniejącego konta produkcyjnego jako staging**. CloudFormation validation jest odczytem, a nie deploymentem.
3. Uzyskaj od operatora/administratora **potwierdzone**: staging account ID, osobną rolę sesyjną, VPC ID, 2 prywatne subnet ID w różnych AZ, ich route table ID, regionalny S3 prefix list ID, rolę wywołującą IAM, bucket na kod Lambda, dozwolony profil modelu i maksymalny budżet.
4. Sprawdź konfigurację VPC i DNS: private subnets, `enableDnsHostnames`, `enableDnsSupport`; brak NAT/IGW/TGW/peering w trasach pilota; brak public IP; brak nieznanych endpointów i default routes; nie polegaj wyłącznie na nazwach „private”.
5. Zweryfikuj `GetInferenceProfile` i listę `models[].modelArn` dla dokładnego `ModelId`. Każdy docelowy region musi być zatwierdzonym regionem państwa UE, w szczególności nie `eu-west-2` (UK) i nie `eu-central-2` (Szwajcaria). Zbadaj ograniczenia i rzeczywistą dostępność modelu, uprawnienia Bedrock, wymagane profile, quotas oraz możliwość obsługi obrazów.
6. Uruchom istniejący preflight (przykład; podmień wszystkie identyfikatory):
   ```bash
   python -m private_ai.preflight \
     --expected-account <STAGING_ACCOUNT_ID> \
     --vpc-id <ISOLATED_VPC_ID> \
     --subnet-id <SUBNET_A> --subnet-id <SUBNET_B> \
     --route-table-id <RTB_A> --route-table-id <RTB_B> \
     --model-id <VERIFIED_EU_PROFILE_ID>
   ```
   Zapisz wyłącznie zredagowany raport wyników (bez tokenów, kont użytkowników, sekretów i payloadów). Negatywny preflight = **STOP**, nie obchodź kontroli.

## B. Przegląd i poprawki IaC przed wdrożeniem

Przejrzyj `infra/private-ai-pilot.yaml` i stosuj minimalne uprawnienia. Zweryfikuj szczególnie:

- `PilotApi` i `PilotRoute` wymagają faktycznego SigV4 AWS_IAM; bez domyślnych otwartych tras. `PilotPermission` ogranicza Lambda invoke do dokładnego API/method/path. Odrzuć direct Lambda invoke poza zatwierdzonym mechanizmem. Przetestuj rzeczywisty shape `requestContext.authorizer.iam.userArn` dla AWS HTTP API v2; nie zakładaj go wyłącznie z mocków.
- `WorkerSG` jest ograniczony do Bedrock Runtime VPC Endpoint:443 i regionalnego S3 prefix list:443, bez domyślnego `0.0.0.0/0` egress nawet **w czasie tworzenia**. Sprawdź po wdrożeniu `describe-security-groups`, Endpoint ENI i trasy. Jeśli szablon tworzy niepożądany egress, popraw przed wdrożeniem.
- Lambda ma prywatne podsieci, brak publicznych adresów, żadnego NAT, precyzyjne IAM i wymuszenie warunków SourceVpce/RequestedRegion. Docelowo zawęź `bedrock:InvokeModel` z `Resource: "*"` do profilu i underlying foundation model ARNs (wraz z cross-region). Nie wmawiaj, że obecny wildcard jest least privilege.
- S3 Object Lock COMPLIANCE + versioning + blokada public access + TLS + szyfrowanie + polityka zapisu via konkretny VPC endpoint. Zweryfikuj retention w AWS oraz zasadność okresu 30 dni z perspektywy operacyjnej i prawnej. Object Lock nie zastępuje KMS/HSM, niezależnego witness ani off-account backup.
- Ochrona kosztów: AWS Budgets/alarm kosztowy na staging, minimalne concurrency i log retention, identyfikowalne tagi owner/env/expiry; przygotuj plan usunięcia zasobów. Object Lock/Retain mogą uniemożliwić szybkie usunięcie części zasobów i naliczanie kosztów — sprawdź przed zatwierdzeniem.
- CloudTrail / CloudWatch / VPC Flow Logs z minimalizacją danych: **nigdy** log body, promptów, odpowiedzi, surowych dokumentów, authorization headers; przejrzyj API Gateway access logs i ewentualne Bedrock invocation logging, żeby wykluczyć payloady. Zdarzenia audytu muszą pochodzić od zaufanych komponentów.

Jeśli konkretne wymagania nie są spełnione, popraw kod, napisz regresyjne testy i commituj na PR #40. Żadnego automatycznego deploymentu z workflow testowego.

## C. Offline build i change-set (bez wykonania)

1. `python tools/private_ai/make_fixture.py` — wygeneruj wyłącznie geometryczny PNG i zapisz SHA-256 jako parametr `FixtureSha256`; sprawdź identyczność z `private_ai.synthetic.fixture_sha256()`.
2. `python tools/private_ai/build_pilot_zip.py` — zbuduj pakiet Lambda z allowlisty plików i oblicz jego SHA-256. Uruchom testy i sprawdź, że ZIP nie zawiera sekretów ani danych klienta.
3. Przygotuj listę parametrów: `VpcId`, `PrivateSubnetIds`, `PrivateRouteTableIds`, `S3PrefixListId`, `CallerRoleName`, `TenantId` (syntetyczny), `ModelId`, `FixtureSha256`, `PackageBucket`, `PackageKey`.
4. Oszacuj dzienny/miesięczny koszt, w szczególności **interface VPC endpoint (godziny + transfer), S3 Object Lock, CloudWatch, Lambda, API Gateway, Bedrock**. Utwórz opis planu i ocenę ryzyk. Nie podawaj fikcyjnych kosztów.
5. Po akceptacji kosztów i **osobnej akceptacji deployu** przygotuj upload kontrolowanego ZIP do *staging* bucket i CloudFormation change set, przedstaw operatorowi wynik `describe-change-set`. **Nie wywołuj execute-change-set ani deploy, zanim operator jawnie zaakceptuje ten konkretny zestaw zmian.**

## D. Test end-to-end po zgodzie na wykonanie

Po stworzeniu zasobów w zatwierdzonym stagingu:

```bash
python tools/private_ai/smoke_pilot.py \
  --api-url https://<API_ID>.execute-api.eu-central-1.amazonaws.com/v1/documents \
  --expected-account <STAGING_ACCOUNT_ID>
```

Uruchom test rolą `CallerRoleName` z najmniejszym zakresem `execute-api:Invoke`; zweryfikuj, że:
- syntetyczny PNG przechodzi i powstaje zdarzenie `authorized` przed inferencją i `completed` lub bezpieczny błąd;
- brak podpisu, obca rola/tenant, zły hash pliku i dodatkowy prompt są odrzucane przed Bedrock;
- awaria audytu blokuje inferencję; nie ma fallbacku do Internetu;
- profile Bedrock i destynacje odpowiadają zatwierdzonej liście UE, a Flow Logs / VPC endpoints / CloudTrail potwierdzają realną ścieżkę;
- endpoint nie zwraca dokumentów/sekretów w logach; tenant A nigdy nie może czytać danych B;
- weryfikacja Object Lock, dostępu do audytu, praw delete i dowodów retencji.

Nie używaj rzeczywistych dokumentów nawet w testach negatywnych. Nie „naprawiaj” błędów przez wyłączanie AWS_IAM, audytu, hash-pin, szyfrowania, VPC albo ograniczeń egress.

## E. Udokumentuj wynik i przekazanie użytkownikowi

Zapisz do `docs/private-ai/AWS_STAGING_EVIDENCE.md`:
- datę i commit, typ środowiska (staging), zredagowany identyfikator regionu/konta, artefakt SHA-256, model/profile i jego regiony docelowe;
- wynik READ-ONLY preflight, walidacji IaC, CI, kosztorys i plan zmian, numery runów oraz wynik smoke;
- twarde dowody rzeczywistego ruchu i uprawnień, bez danych osobowych i sekretów;
- co zrobiono, co **nie** jest potwierdzone, pozostające ryzyka i warunki rollback/cleanup;
- status osobno: `CODE_READY`, `AWS_PREFLIGHT_OK`, `CHANGESET_APPROVED`, `STAGING_DEPLOYED`, `LIVE_CANARY_OK`, `EGRESS_VERIFIED`, `AUDIT_VERIFIED`. Żaden status nie może być ustawiony „na wiarę”.

Jeżeli brak dostępu albo akceptacji, dopisz konkretną pozycję do `docs/czeka-na-dostep.md` i zakończ z listą potrzebnych działań operatora. **Nie merge PR #40/#389, nie wdrażaj produkcyjnie, nie deklaruj certyfikacji dla banków/szpitali.**

### Definition of done

**Pilot AWS done =** zatwierdzony, odizolowany staging; live SigV4 canary + wszystkie negatywne testy zielone; potwierdzone w AWS regiony docelowe modeli i brak otwartego egress; trwały audyt metadanych; udokumentowany koszt, rollback i artefakty dowodowe. Wszystko poza stagingiem pozostaje nienaruszone.
