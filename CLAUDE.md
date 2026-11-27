# AWS Guidance

- Prefer the AWS MCP Server for AWS interactions — it provides sandboxed
  execution, observability, and audit logging. If unavailable, use the
  AWS CLI directly.
- Before starting a task, check whether a relevant AWS skill is available.
  Load the skill with `retrieve_skill` and prefer its guidance over
  general knowledge.
- When uncertain about specific AWS details (API parameters, permissions,
  limits, error codes), verify against documentation rather than guessing.
  State uncertainty explicitly if you cannot confirm.
- When creating infrastructure, prefer infrastructure-as-code (AWS CDK or
  CloudFormation) over direct CLI commands.
- When working with infrastructure, follow AWS Well-Architected Framework
  principles.
- Do not use em dashes in AWS resource names or descriptions. Use
  hyphens instead.

## Secret Safety

- MUST load the `aws-secrets-manager` skill first for any secret,
  credential, API key, token, or password task. MUST NOT call
  `secretsmanager get-secret-value` or `batch-get-secret-value`, and MUST
  NOT hit the Secrets Manager Agent daemon directly. MUST use
  `{{resolve:secretsmanager:secret-id:SecretString:json-key}}` with
  `asm-exec` so the secret resolves at runtime without entering context.

## Projekt: notarai (notarai.pl)

Wersja SaaS asystenta kancelarii notarialnej. Wywodzi się z projektu
pieczapp (stanowisko lokalne); identyfikatory w kodzie (moduły, zmienne
`PIECZAPP_*`) celowo pozostawiono, żeby nie rozjechać się z testami.

### Ograniczenia (RODO)
- Domyślny region: eu-central-1 (Frankfurt). NIE twórz zasobów poza UE.
- Dane osobowe klientów (PESEL, imiona, adresy) NIE mogą trafiać do logów
  CloudWatch, CloudTrail ani do komunikatów debugowania.
- Sekrety wyłącznie przez AWS Secrets Manager. Nigdy w kodzie ani w .env
  commitowanym do repozytorium. Token admina (`PIECZAPP_ADMIN_TOKEN`) w
  chmurze podpinaj jako referencję do sekretu, nie jako wartość w env.
- Modele Claude wywołuj przez Bedrock w eu-central-1, nie przez publiczne API.
- Przed utworzeniem zasobu przechowującego dane osobowe (bucket spraw,
  baza kancelarii) zapytaj o potwierdzenie.
- Obraz Dockera nie może zawierać `dane/` ani `.env` (pilnuje tego
  `.dockerignore`; nie usuwaj z niego tych wpisów).

### ElevenLabs: tylko silnik v3 lub nowszy (twarda reguła, 16.11.2026)
- Każda generacja głosu w ElevenLabs (lektor TTS, dialog, agenci rozmowni,
  projektowanie głosu, zamiana mowy) używa modelu v3 lub nowszego:
  `eleven_v4`, `eleven_v4_turbo`, `eleven_v3`, `eleven_v3_conversational`
  (projektowanie głosu: `eleven_ttv_v3`). NIGDY `eleven_multilingual_v2`,
  `eleven_flash_v2_5`, `eleven_turbo_v2_5` ani innych v1/v2 - także przy
  pracy przez konektor ElevenLabs, narzędzia MCP `fu` i skrypty.
- Gdy narzędzie albo model nie daje wyboru v3+, przerwij i zgłoś to,
  zamiast schodzić na niższy silnik. Domyślnie: lektor `eleven_v4`,
  agenci `eleven_v4_turbo`.

### Konwencje
- Zasoby nazywaj z prefiksem: notarai-
- Infrastrukturę definiuj jako kod (CloudFormation w `infra/`), nie przez
  konsolę i nie w Terraform.
- Zapytania do Bedrock muszą przechodzić walidację SDK z `requirements.txt`
  (`test_zgodnosc_sdk.py`, atrapa w `test_bedrock.py` waliduje przez
  `conftest.sprawdz_zgodnosc_z_api_bedrock`). Nowa ścieżka wywołania modelu
  dostaje test w `test_zgodnosc_sdk.py`; boto3 zawsze przypięte `==`.
- Tryb domyślny aplikacji to lokalny; tryb SaaS włączają zmienne opisane
  w `SAAS.md` i `.env.example`.

### Zadania czekające na dostęp (testy na żywo)
- Rejestr: `docs/czeka-na-dostep.md` (pozycje `NA-n`). Gdy użytkownik mówi,
  że jest dostęp (konto notariusza, środowisko testowe GIIF, portal MS itp.),
  zacznij od tej listy i prowadź test na żywo według kroków z pozycji.
- Każde nowe zadanie, którego nie da się skończyć bez dostępu z zewnątrz,
  dopisz tam jako kolejną pozycję; po zrobieniu oznacz `zrobione` z datą
  i commitem (nie usuwaj).

### Publikacja (bez FTP z ręki)
- Zmiany w `strona/` (notarai.pl) i `seo/` publikuje sam GitHub:
  `.github/workflows/strona.yml` po zielonych testach na `master` generuje
  katalog, blog i sitemap i wysyła na az.pl przez FTPS tylko zmienione pliki.
  Aplikację (`static/`, kod Pythona) wdraża `.github/workflows/wdrozenie.yml`.
- Gdy użytkownik prosi o zmianę strony lub frontendu: zrób zmianę, puść
  testy, commit, push i pull request do `master`; po scaleniu wszystko idzie
  na stronę samo. Nie uruchamiaj `infra\strona.ps1` ani FTP ręcznie, chyba
  że workflow nie działa (wtedy to wysyłka awaryjna).

## NotarAI 2.0 (katalog `v2/`, tor rozwojowy)

- Stan dla właściciela: `v2/STAN.md`. Architektura i moduły: `v2/README.md`.
- V2 jest osobne od V1: własne zależności (`v2/requirements.txt`), własne testy
  (`cd v2 && python -m pytest -q`), bez wdrożeń na produkcję i bez importu danych
  ani konfiguracji V1. Z V1 bierze wyłącznie kod reguł (`taksa.py`, `slownie.py`
  przez `v2/worker/domain.py`); zmieniając je, puść też testy V2. Decyzja właściciela
  27.11.2026: także `krz_portal.py` i `walidacja.py` (KRZ i numery KW/PESEL, tą samą drogą),
  a treść KW pobiera funkcja AWS `notarai-v2-rejestry` (stos w `infra/`) z `ekw.py` V1 bez zmian;
  token dostawcy zostaje w Secrets Manager, stanowisko woła funkcję swoim logowaniem.
- Dane prawdziwe (decyzja właściciela 27.11.2026): V2 obsługuje prawdziwe sprawy i dane osobowe;
  `ai.real_data_approved` domyślnie `true` i nadal nie da się go przełączyć z aplikacji. Zasady
  RODO z tego pliku (UE, brak danych w logach, sejf, pseudonimizacja dla modelu) obowiązują bez zmian.
- Każde wywołanie modelu w V2 idzie przez `v2/worker/inference.py` (polityka UE,
  pseudonimizacja, licznik). Nie wołaj Bedrock z innego miejsca i nie loguj treści.
- Zapis albo wysyłka w imieniu notariusza (decyzja właściciela 27.11.2026): wyraźne polecenie
  notariusza lub użytkownika („wyślij pocztę”, „wypełnij … i wyślij”) jest zatwierdzeniem; dodatkowe
  „Tak / Nie” tylko przy ustawieniu `confirm` albo gdy polecenie nie prosiło o tę czynność (np. samo
  „wypełnij”). Zawsze: zasady kancelarii (`check_*`) przed zapisem i wysyłką, pokazanie w rozmowie
  dokładnie tego, co wykonano, jedno wykonanie bez ponawiania po niepewnym wyniku. Zapis dokumentu
  nadal przez kontrakt Connect z odczytem kontrolnym.
- Stosy `notarai-v2-bedrock`, `notarai-v2-przekaznik`, `notarai-v2-kopia`, `notarai-v2-mowa`,
  `notarai-v2-pobieranie`, `notarai-v2-rejestry` istnieją w eu-central-1 (decyzje właściciela 27.11.2026). Zmieniaj je tylko przez szablony w
  `infra/`; `notarai-v2-kopia` przechowuje zaszyfrowane dane osobowe.
- Interfejs V2 to rozmowa (`v2/worker/chat.py`): nowe funkcje dodawaj jako polecenia
  zdaniem, bez tabel i formularzy. Polecenia zmieniające stan rozpoznaje kod, nie model;
  nieodwracalne wymagają potwierdzenia.
- Wypełnianie formularzy w V2 (decyzja właściciela 27.11.2026: priorytet programu): procedura
  z nagrania (`v2/worker/procedures.py`) daje wartości, a `v2/worker/autofill.py` wpisuje je sam
  na stronach (`web_fill.py`, przeglądarka NotarAI) i w programach Windows (`win_fill.py`,
  UI Automation). Wysłanie, złożenie, podpisanie albo zapis na stałe: na wyraźne polecenie (zob. wyżej,
  decyzja 27.11.2026) albo po zatwierdzeniu w czacie, zawsze związane ze stanem formularza z podglądu;
  jedno naciśnięcie, bez ponawiania po niepewnym wyniku.
- Mowa (nagrania procedur, notatki głosowe, stały nasłuch `v2/worker/listening.py`): decyzja
  właściciela 27.11.2026 - domyślnie w chmurze, wyłącznie Amazon Transcribe w eu-central-1
  (`v2/worker/cloud_speech.py`, bucket stosu `notarai-v2-mowa`): nagranie i wynik kasowane zaraz
  po odczycie tekstu, reguła cyklu życia kasuje resztę po dniu, organizacja ma politykę AI opt-out.
  Alternatywa lokalna (`v2/worker/transcribe.py`) zostaje jako ustawienie `speech.where`. Żadnych
  innych usług mowy; dźwięku nasłuchu nie zapisuj na stałe.
  Urządzenie o zakresie `listen` (mikrofon) wysyła tylko dźwięk: nie dawaj mu innych tras.
- Twarde zasady kancelarii (`v2/worker/rules.py`) to kod, nie polecenie dla modelu. Każda nowa
  ścieżka zapisu dokumentu albo wysyłki musi wywołać właściwe `check_*`. Nie dodawaj rodzaju
  zasady, którego kod nie umie sprawdzić.
- Zmiany w interfejsie (`v2/worker/pocket.*`, `admin.html`, `tunnel.js`) sprawdzaj
  w przeglądarce: `cd v2 && node tests/e2e/pocket.e2e.js python`.

## Secure Agent Factory (prototyp, bez wdrożenia produkcyjnego)

- Architektura i zasady: docs/agent-factory.md.
- **Polecenie dla Claude Code:** docs/claude-code-handoff-agent-factory.md. Przy pracach agentowych przeczytaj je w całości, realizuj kolejne etapy i testuj rezultaty.
- Nie korzystaj z danych klientów, sesji produkcyjnych ani sekretów. Nie omijaj zasad UE z tego pliku. Żadnych automatycznych wdrożeń na produkcję z Agent Factory (jedyny wyjątek w repozytorium: samonaprawa, sekcja niżej).

## Samonaprawa (decyzja właściciela 23.11.2026)

- Opis: `docs/samonaprawa.md`. Błąd na produkcji -> `samonaprawa.py` -> zdarzenie
  EventBridge -> CodeBuild `notarai-samonaprawa` (`scripts/samonaprawa/potok.py`) ->
  agent naprawczy -> bramki -> agent recenzent -> wdrożenie z AWS -> 20 min
  obserwacji -> cofnięcie poprzednim tagiem przy nawrocie. Działa bez GitHub Actions;
  poprawka trafia do repozytorium best effort, a do czasu zapisu nakłada ją straż
  w `wdrozenie.yml`. Stary `samonaprawa.yml` jest tylko ręcznym awaryjnym.
- Automatyczne wdrożenia na produkcję są dozwolone WYŁĄCZNIE przez potok AWS
  (stos `notarai-samonaprawa`, CodeBuild `notarai-samonaprawa`,
  `scripts/samonaprawa/potok.py`; bramki bez zmian) i WYŁĄCZNIE po bramkach `scripts/samonaprawa/bramki.py`: test
  regresji czerwony przed i zielony po poprawce, cały zestaw testów zielony,
  żadnych usuniętych ani wyciszonych testów, zgoda niezależnego recenzenta,
  limit 3 automatycznych wdrożeń na dobę, 2 próby na błąd, potem eskalacja.
- Strefy (decyzja właściciela 23.11.2026, lista w `bramki.py`):
  - logowanie i płatności (`autoryzacja`, `logowanie`, `rejestracja`,
    `urzadzenia`, `platnosci`, `tokenomia`): CAŁKOWICIE poza samonaprawą -
    zmiana tam = odrzucenie, nawet na prośbę notariusza; zmienia je tylko zespół,
  - treść prawna aktów, taksa, dane osobowe: na prośbę notariusza wchodzą
    automatycznie (to jego dziedzina); poprawka błędu bez prośby - pull request,
  - sama samonaprawa, maskowanie logów i magazyn (RODO), infrastruktura:
    zawsze pull request do właściciela.
- Zbudowane = włączone: zmiana zrobiona na prośbę notariusza włącza się sama
  w jego kancelarii po wdrożeniu (raport agenta `ustawienie`, aplikacja
  `asystent_kancelarii.odswiez_prosby`) - bez drugiego polecenia.
- Właściciel nie czyta kodu: każde powiadomienie (e-mail SNS, rekord
  w DynamoDB) mówi po ludzku, co się psuło, co naprawiono i co kliknąć w aplikacji.
- Wyłącznik: parametr SSM `/notarai/samonaprawa/tryb` = `auto` | `pr` | `wylaczona`.
- Zgłoszenia i znaczniki błędów bez danych osobowych (tylko
  `dziennik.opis_bledu` po `maskuj`). Agent działa na sesji AWS ograniczonej
  do Bedrock w UE, bez tokenu GitHub i bez dostępu do danych spraw.
- Asystent kancelarii (`asystent_kancelarii.py`): notariusz zmienia ustawienia
  zdaniem; każde nowe ustawienie kancelarii dostaje opis w
  `ustawienia_kancelarii.OPISY_USTAWIEN` (pilnuje tego test), żeby asystent
  umiał je przełączać. Prośby o zmiany programu idą do samonaprawy po anonimizacji.
- Przy pracy nad samonaprawą: nie osłabiaj bramek ani `test_samonaprawa.py`
  bez wyraźnej decyzji właściciela.

## Zakaz renderu na GitHub Actions (twarda reguła, 23.11.2026)
- NIC nie renderuje się ani nie wynajmuje GPU na GitHub Actions (także koder/vLLM): rolki studia, serial Komputerku /
  Kancelaria pod Siódemką, scenografia (Blender), klipy GPU, montaż, głosy,
  napisy wypalane w obrazie. Bez wyjątków i bez „jednorazowo”.
- Rendery idą wyłącznie przez Cloudflare: Worker `finyou-render`
  (`POST /zadanie`, kontener z montażem), a GPU (SaladCloud) zleca się spoza
  GitHuba przez bramę `salad-brama` lub Workera. Sekrety renderu żyją
  w Cloudflare (Worker secrets) i Supabase Vault, nie w sekretach GitHuba.
- Egzekwowanie:
  1. `tools/zakaz_renderu_gha.py` (workflow `zakaz-renderu-gha.yml`, każdy
     push na każdej gałęzi i każdy PR) blokuje workflow, który uruchamia
     ffmpeg, Blender, Remotion, ComfyUI, `ai-clip run/open`, fabrykę odcinków,
     montaż, generację głosu albo zleca render Cloudflare z GitHuba.
  2. Ścieżki renderu w kodzie wywołują strażnika na starcie i przerywają,
     gdy `GITHUB_ACTIONS=true` (notarai: `tools/zakaz_gha.py`; finyou: `services/ai-clip/zakaz-gha.mjs`).
- Sprawdzenie ręczne: `python3 -I tools/zakaz_renderu_gha.py` (zielone = OK).
  Gdy strażnik blokuje, przenieś pracę na Cloudflare; nie dopisuj wyjątku.
