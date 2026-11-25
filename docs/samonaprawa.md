# Samonaprawa notarai

System, który sam wykrywa błędy aplikacji na produkcji, naprawia je, wdraża
poprawkę i sprawdza, czy pomogła. Gdy nie pomogła, sam cofa poprawkę.
Właściciel nie musi czytać kodu: dostaje wiadomość po polsku, co się stało
i co kliknąć w aplikacji, żeby sprawdzić.

Decyzja właściciela z 23.11.2026, po błędzie „Sporządź projekt: Błąd modelu
(ParamValidationError)”. Decyzja z 25.11.2026: potok działa **w AWS (eu-central-1),
poza GitHub Actions i bez zależności od GitHuba w czasie działania**.

## Jak to działa

```
błąd u notariusza
  └─ samonaprawa.py: odcisk błędu + znacznik w CloudWatch (bez danych klientów)
       ├─ od razu: zdarzenie na domyślną szynę EventBridge (źródło notarai.samonaprawa)
       └─ co 30 minut: reguła EventBridge uruchamia przegląd znaczników (siatka bezpieczeństwa)
  └─ CodeBuild „notarai-samonaprawa” (stos notarai-samonaprawa), jedna naprawa naraz
       scripts/samonaprawa/potok.py:
       1. rekord błędu w DynamoDB „notarai-samonaprawa”: limity, eskalacja
       2. kod = paczka źródeł WERSJI URUCHOMIONEJ NA PRODUKCJI (S3), nie master
       3. agent naprawczy (Claude przez Bedrock, eu-central-1):
          przyczyna -> test, który odtwarza błąd -> poprawka -> wszystkie testy
       4. bramki (scripts/samonaprawa/bramki.py, bez zmian, deterministyczne)
       5. niezależny agent recenzent (widzi sam kod, nie rozumowanie)
       6. werdykt:
          auto   -> wdrożenie -> 20 min obserwacji
                    -> błąd wrócił albo przyszedł nowy? cofnięcie do poprzedniego tagu
          pr     -> patch w S3 + e-mail: czeka na zatwierdzenie (zatwierdz.py)
          odrzuc -> komentarz w rekordzie błędu; po 2 próbach eskalacja + e-mail
       7. poprawka z produkcji trafia do REJESTRU (DynamoDB), a potem, best effort,
          do repozytorium GitHub (patrz „Poprawka na produkcji a repozytorium”)
```

## Bramki: co musi spełnić poprawka, żeby weszła sama

| Bramka | Po co |
|---|---|
| Test regresji **oblewa** kod sprzed poprawki (pytest = 1) i **przechodzi** po niej | dowód, że poprawka naprawia ten błąd, a nie coś obok |
| Pełny zestaw testów zielony | nic innego się nie zepsuło (w tym walidacja zapytań do Bedrock przez SDK, `test_zgodnosc_sdk.py`) |
| Żadnych usuniętych testów ani `skip`/`xfail`/`except: pass` | agent nie może „naprawić” przez wyciszenie |
| Niezależny recenzent: `przepusc` | drugi agent szuka, co poprawka może zepsuć |
| Poza strefami zakazanymi | patrz niżej - tam zawsze decyduje właściciel |
| Najwyżej 10 plików i 400 linii, ryzyko „niskie” | automat tylko do wąskich napraw |
| Najwyżej 3 automatyczne wdrożenia na dobę | seria błędnych poprawek nie rozleje się po produkcji |
| Produkcja nie zmieniła się w trakcie naprawy | testy szły na tej samej wersji, na którą trafi poprawka (zmiana tagu = werdykt `pr`) |

Bramki uruchamiane są z kopii `scripts/samonaprawa/` z drzewa wersji produkcyjnej,
zrobionej PRZED uruchomieniem agenta, a te pliki (i `.github/`, `conftest.py`,
`test_samonaprawa.py`, testy potoku) są w strefie zakazanej, więc agent nie osłabi
własnej kontroli.

## Strefy (decyzja właściciela 23.11.2026)

- **Logowanie i płatności - całkowicie poza samonaprawą.** `autoryzacja.py`,
  `logowanie.py`, `rejestracja.py`, `urzadzenia.py`, `platnosci.py`,
  `tokenomia.py`: zmiana tam = odrzucenie, także na prośbę notariusza.
  Asystent nie przekazuje takich próśb - kieruje do zespołu notarai.
- **Treść prawna, taksa, dane osobowe - na prośbę notariusza automatycznie.**
  Notariusze odpowiadają za treść aktów; ich prośba wchodzi po bramkach bez
  czekania na właściciela. Poprawka błędu bez prośby - zatwierdzenie właściciela.
- **Zbudowane = włączone.** Agent podaje w raporcie `ustawienie` (klucz,
  wartość); po wdrożeniu aplikacja sama włącza je w kancelarii, która prosiła,
  i pokazuje „Twoja zmiana już działa”.
- **Zawsze zatwierdzenie właściciela:** sama samonaprawa, maskowanie logów
  i magazyn (RODO), infrastruktura (`infra/`, `Dockerfile`, `.github/`...).
  Pełna lista: `STREFY_*` w `bramki.py`.

## Skąd potok bierze kod (bez GitHuba)

1. Odczytuje z ECS (usługa `notarai` w klastrze `notarai`) tag obrazu uruchomionego
   na produkcji.
2. Pobiera paczkę `s3://<BucketZrodel stosu notarai-budowanie>/notarai/zrodla-<TAG>.zip`
   - dokładnie tę, którą wysyła `wdrozenie.yml` (`git archive`). Gdy paczki już nie ma,
   próbuje kopii w buckecie samonaprawy (`zrodla/<TAG>.zip`). Paczki budowania
   żyją teraz 90 dni (było 14), potok sam zapisuje kopię przy każdym uruchomieniu.
3. `git init` i commit BAZA. Bramki liczą różnicę względem BAZY, a poprawka jest
   `format-patch` względem BAZY.

Ponieważ baza to **to, co działa na produkcji**, zawiera już wcześniejsze poprawki
samonaprawy, które nie dotarły jeszcze do repozytorium. Kolejna poprawka nie wycofa
poprzedniej.

Agent pracuje w kopii drzewa. Potok **nie ufa jego katalogowi `.git`** (agent mógłby
wpisać do konfiguracji hak lub filtr, który wykonałby się u potoku): z kopii agenta
przenosi tylko pliki do czystego repozytorium, a testy bramek i recenzenta puszcza na
osobnych kopiach.

## Poprawka na produkcji a repozytorium (poprawka nie może zniknąć)

GitHub zostaje magazynem kodu, ale potok go nie potrzebuje. Żeby poprawka wdrożona przez
AWS nie zniknęła przy zwykłym wdrożeniu z GitHuba, działa **rejestr poprawek**:

1. Po udanym wdrożeniu poprawka dostaje wpis w DynamoDB (`pk=NAPRAWA`, status
   `do_zsynchronizowania`): patch `format-patch` względem BAZY w S3
   (`poprawki/<odcisk>/<czas>.patch`) i tag produkcyjny, na którym ją zbudowano.
   Wpisy nigdy nie są kasowane przy porażce. Cofnięcie ustawia `wycofana`, zapis w repozytorium
   `zsynchronizowane`.
2. **Strażnik w `wdrozenie.yml`** (`scripts/samonaprawa/straznik_poprawek.py`,
   krok „Poprawki samonaprawy jeszcze nie w master” przed budowaniem obrazu): listuje
   poprawki `do_zsynchronizowania` (tylko odczyt: `dynamodb:Query/GetItem` i
   `s3:GetObject` na `poprawki/*`), po kolei sprawdza `git apply --check --reverse`
   (jeśli przechodzi, poprawka już jest w kodzie z master, pomijamy), w przeciwnym razie
   `git apply --3way`, commit lokalny (bez pusha) i budowa obrazu z tego drzewa. Tag obrazu to
   `<sha12>-sn<skrót id poprawek>`, więc różni się od zwykłego. Gdy patch się **nie stosuje**:
   wdrożenie pada głośno (błąd w Actions) i przychodzi e-mail z notarai-alarmy
   po polsku. Zwykłe wdrożenie nigdy nie idzie po cichu bez poprawki.
3. **Zapis w repozytorium** (best effort, `synchronizacja.py`): po wdrożeniu i obserwacji,
   a przy porażce przy każdym przeglądzie co 30 minut, potok bierze token z sekretu
   `notarai/samonaprawa-github` (klucz `token`; brak lub „brak” = pomija), nakłada patch na
   aktualny master (API GitHub, bez protokołu git), tworzy gałąź
   `samonaprawa/<odcisk>-<czas>`, pull request z etykietą `samonaprawa` i scala go. Komunikat
   scalenia zawiera `[skip ci]`, żeby nie wyzwolić drugiego wdrożenia. Sukces = status
   `zsynchronizowane`, strażnik pomija poprawkę. Gdy się nie uda (brak tokenu, konflikt,
   scalenie odmówione): wpis zostaje, przychodzi jeden e-mail „poprawka jest na produkcji,
   ale nie zapisana w repozytorium” (kolejny po 24 godzinach). Poprawki są synchronizowane po
   kolei: po porażce pierwszej kolejne czekają.
4. Gdy GitHub nie działa, samonaprawa i tak działa. Poprawka na produkcji jest wtedy
   chroniona przez rejestr, ale **repozytorium jej nie ma**, dopóki synchronizacja nie
   zadziała. To jedyny ślad zależności od GitHuba.

Przypadek brzegowy: gdy w trakcie obserwacji ktoś wdrożył inną wersję, cofnięcie jest pomijane
(mail), a poprawka dostaje status `wycofana`. Trzeba ją obejrzeć ręcznie.

## Bezpieczeństwo i RODO

- Zgłoszenie zawiera tylko typ wyjątku, kod i komunikat AWS, miejsca w kodzie,
  wersję i endpoint, po `dziennik.maskuj()`. Treść wyjątków spoza AWS, treść
  spraw i identyfikatory kancelarii nie wychodzą z aplikacji. DynamoDB, S3 i logi
  też bez danych osobowych.
- Aplikacja ma tylko `events:PutEvents` na domyślną szynę. Zdarzenie jest wyłącznie
  wyzwalaczem: potok sam wylicza wszystko ze stanu w DynamoDB (aplikacja nie ma do niej
  dostępu), zatwierdzenie wymaga flagi w DynamoDB, a nie samego zdarzenia.
- Agent dostaje sesję AWS roli `notarai-samonaprawa-agent` (assume-role z polityką
  sesji: tylko `bedrock:InvokeModel`, `InvokeModelWithResponseStream`, `GetInferenceProfile`,
  `ListInferenceProfiles`; profile `eu.anthropic.*`, regiony UE), osobno dla agenta i recenzenta
  (limit godziny sesji). Proces agenta ma środowisko zbudowane od zera: bez poświadczeń roli
  CodeBuild, adresu poświadczeń kontenera, tokenów i sekretów. Gdy potok działa jako root,
  agent i testy bramek idą jako nieuprzywilejowany użytkownik `snagent`
  (`SN_AGENT_UZYTKOWNIK`) i nie przeczytają `/proc/<pid>/environ` potoku. Bramki puszczają
  testy napisane przez agenta w środowisku bez żadnych poświadczeń AWS.
- Rola potoku `notarai-samonaprawa-codebuild` ma najmniejsze uprawnienia (patrz niżej)
  i nie ma Bedrocka: modele tylko przez sesję agenta.
- Przeglądy nie czytają sekretów poza opcjonalnym tokenem do synchronizacji z repozytorium.

### Uprawnienia roli potoku

Logi własnej grupy; `logs:FilterLogEvents` na `/ecs/notarai` (znaczniki błędów) i
`logs:GetLogEvents` na logach budowania obrazu; S3: paczki `notarai/zrodla-*` w buckecie
źródeł i bucket poprawek; `codebuild:StartBuild/BatchGetBuilds` na `notarai-obraz`;
`ecr:DescribeImages` na `notarai`; CloudFormation (`DescribeStacks`, change sety) na stosie
`notarai-aplikacja` i odczyt `notarai-budowanie`; `iam:PassRole` wyłącznie dla
`notarai-cloudformation` (dla cloudformation.amazonaws.com); `ecs:DescribeServices` na
`notarai/notarai`, `ecs:DescribeTaskDefinition`; `sns:Publish` na `notarai-alarmy`;
`ssm:PutParameter/GetParameter` na `/notarai/samonaprawa/*`; DynamoDB `GetItem/PutItem/
UpdateItem/Query` na tabeli; `secretsmanager:GetSecretValue/DescribeSecret` tylko na
`notarai/samonaprawa-github`; `sts:AssumeRole` tylko na rolę agenta.

## Sterowanie

- **Wyłącznik / tryb:** parametr SSM `/notarai/samonaprawa/tryb` = `auto` (domyślnie, także
  gdy parametru nie ma) | `pr` (tylko poprawki do zatwierdzenia) | `wylaczona` (tylko zgłoszenia):
  `aws ssm put-parameter --name /notarai/samonaprawa/tryb --type String --overwrite --value pr --region eu-central-1`.
- **Model agenta:** parametr `/notarai/samonaprawa/model` (domyślnie `eu.anthropic.claude-opus-4-6-v1`, jak aplikacja).
- **Zgłoszenie ręczne** (np. ze zrzutu ekranu):
  `python scripts/samonaprawa/zglos.py "opis błędu słowami, bez danych klientów"`;
  przegląd od razu: `python scripts/samonaprawa/zglos.py --przeglad`.
- **Zatwierdzenie poprawki** (werdykt `pr`, e-mail „poprawka błędu czeka na decyzję”):
  `python scripts/samonaprawa/zatwierdz.py <odcisk>`. Ustawia flagę w DynamoDB i wysyła
  zdarzenie; potok nakłada patch na bieżącą wersję z produkcji, puszcza pełny zestaw testów,
  wdraża, obserwuje 20 minut i w razie nawrotu cofa. Ręcznie, bez skryptu:
  `aws dynamodb update-item --table-name notarai-samonaprawa --key '{"pk":{"S":"BLAD#<odcisk>"},"sk":{"S":"STAN"}}' --update-expression "SET zatwierdzone = :t" --expression-attribute-values '{":t":{"BOOL":true}}' --region eu-central-1`
  oraz `aws events put-events --entries file://zatwierdzenie.json` (wpis ze źródłem `notarai.samonaprawa`,
  typem `zatwierdzenie` i polem `ladunek_b64` = base64 z `{"zdarzenie":"zatwierdzenie","odcisk":"<odcisk>"}`).
  Odrzucenie: nic nie rób (patch wygasa w S3 po 90 dniach).
- **Podgląd:** DynamoDB `notarai-samonaprawa` (rekordy `BLAD#<odcisk>`: status, próby, historia
  komentarzy; `WDROZENIE`; `NAPRAWA` - rejestr poprawek), logi CloudWatch
  `/aws/codebuild/notarai-samonaprawa` (30 dni), w aplikacji `GET /api/admin/samonaprawa`
  (liczniki błędów w kontenerze). Postęp dla notariusza: parametr SSM `/notarai/samonaprawa/<odcisk>`.
- **Powiadomienia:** e-mail z tematu SNS `notarai-alarmy` (ten sam adres co
  alarmy), te same tematy i ton co dawniej. Niezależnie alarmy: `notarai-samonaprawa-bledy`
  (5+ błędów kodu w 5 minut) i `notarai-samonaprawa-potok-bledy` (uruchomienie potoku
  zakończyło się błędem lub przekroczeniem czasu).
- **Jedna naprawa naraz:** `concurrentBuildLimit: 1` projektu CodeBuild. Uruchomienie w trakcie
  innego jest wstrzymywane; reguły EventBridge ponawiają (do 6 godzin), a przegląd co 30 minut
  podejmie resztę. Zdublowane zdarzenie po naprawie jest rozpoznawane (czas zgłoszenia starszy niż
  zamknięcie rekordu) i pomijane.
- **Awaryjnie** `.github/workflows/samonaprawa.yml` zostaje jako ręczny `workflow_dispatch`
  (wyłączony: samonaprawa działa w AWS). Używa starej ścieżki z GitHub issues i nie widzi
  stanu DynamoDB, więc korzystaj z niego tylko, gdy AWS-owy potok jest niedostępny.

## Uruchomienie (jednorazowo, kolejność ma znaczenie)

1. Scal zmiany do `master` i poczekaj na zwykłe wdrożenie (obraz z potokiem i zmienionym
   szablonem aplikacji; wymaga wcześniej zaktualizowanego stosu `notarai-github`, bo strażnik
   czyta rejestr: `infra\4-polacz-github.ps1`).
2. Stos budowania (paczki źródeł 90 dni): `infra\2-zbuduj-obraz.ps1` (lub
   `aws cloudformation deploy --stack-name notarai-budowanie --template-file infra/notarai-budowanie.yaml --capabilities CAPABILITY_NAMED_IAM --region eu-central-1`).
3. Stos samonaprawy: `infra\6-wdroz-samonaprawe.ps1` albo
   `aws cloudformation deploy --stack-name notarai-samonaprawa --template-file infra/notarai-samonaprawa.yaml --capabilities CAPABILITY_NAMED_IAM --region eu-central-1`.
4. Opcjonalnie sekret z tokenem GitHub do zapisu poprawek w repozytorium:
   `infra\zapisz-sekret-samonaprawy.ps1` (bez niego poprawki są chronione rejestrem,
   a zapis w repozytorium jest do zrobienia ręcznie po mailu).
5. Test na żywo: `python scripts/samonaprawa/zglos.py --test` (patrz `docs/czeka-na-dostep.md`, NA-17).

Poprzedni stos `notarai-github` z rolą `notarai-github-samonaprawa` zostaje (rola dla ręcznego
workflow awaryjnego).

## Asystent kancelarii (prośby notariusza)

Przycisk „Asystent kancelarii” w aplikacji (`asystent_kancelarii.py`,
`POST /api/asystent-kancelarii`). Notariusz pisze po swojemu, co ma działać
inaczej, a asystent (Claude przez Bedrock, narzędzia Converse):
- od razu zmienia to, co da się ustawić: ustawienia ogólne
  (`ustawienia_kancelarii.OPISY_USTAWIEN`), zasady kancelarii, wbudowane kontrole;
  każda zmiana w dzienniku (plik kancelarii `asystent`), „cofnij” ją odwraca,
- czego nie da się ustawić - przekazuje do samonaprawy jako zgłoszenie ręczne
  (`samonaprawa.zglos_prosbe`, po anonimizacji; od razu zdarzeniem, a gdy nie dotrze,
  przez przegląd co 30 minut). Agent robi z prośby ustawienie tej kancelarii
  (domyślnie po staremu) i dopisuje je do `OPISY_USTAWIEN`, więc asystent od razu
  umie je przełączać,
- zmiany tylko dla notariusza (właściciela kancelarii); pracownik może pytać
  i zgłaszać prośby (limit 5 na dobę na kancelarię).

## Ograniczenia i niesprawdzone na żywo

- Automat naprawia błędy kodu (wyjątki). Błędy chwilowe AWS (limity, przeciążenie)
  tylko zlicza i alarmuje - na nie pomaga czekanie albo zmiana limitów, nie kod.
- Błąd merytoryczny bez wyjątku (np. zła treść aktu) nie wywoła samonaprawy -
  to zgłoszenie ręczne i zawsze strefa zakazana.
- Potok jest przetestowany jednostkowo (wszystkie wywołania zewnętrzne to atrapy); pierwszy
  przebieg na żywo to test z NA-17 (`zglos.py --test`). Nieweryfikowane do tego czasu:
  obraz CodeBuild `amazonlinux-x86_64-standard:5.0` z `python 3.12` i `nodejs 20`, dostępność
  `claude` dla użytkownika `snagent` (gdy nie, agent kończy bez raportu, więc werdykt `odrzuc`,
  bezpiecznie), zachowanie limitu `concurrentBuildLimit` (wstrzymanie vs kolejkowanie) i
  ponawianie przez EventBridge.
- Paczka źródeł wersji z produkcji musi istnieć w S3. Gdy produkcja stoi na wersji starszej niż
  90 dni i nie ma kopii, potok kończy się czytelnym błędem; wtedy wystarczy zwykłe wdrożenie.

## Kolejka zgloszen (25.11.2026)

CodeBuild odrzuca start, gdy projekt `notarai-samonaprawa` jest zajety (limit 1 rownolegle), wiec
zgloszenia nie trafiaja do niego wprost. Reguly EventBridge (zgloszenia, zatwierdzenia, przeglad)
wrzucaja je do kolejki SQS `notarai-samonaprawa-kolejka`, a funkcja Lambda
`notarai-samonaprawa-kolejka` startuje po jednym buildzie. Gdy potok jest zajety, start konczy sie
bledem i wiadomosc wraca do kolejki po 2 minutach; ponawianie trwa do 24 h (720 odbiorow), potem
wiadomosc laduje w `notarai-samonaprawa-martwe`. Alarmy (mail SNS `notarai-alarmy`): wiadomosc w
kolejce martwych (`notarai-samonaprawa-martwe-wiadomosci`) i zgloszenie czekajace w kolejce ponad
godzine (`notarai-samonaprawa-zaleglosc-kolejki`). Powtorzone zgloszenia tego samego bledu potok
i tak pomija (limit prob i data zamkniecia w DynamoDB), wiec zaleglosc nie powoduje wielokrotnych napraw.
`zglos.py --test` rowniez idzie przez kolejke.
