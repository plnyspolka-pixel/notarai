# Koder – zlecanie pracy agentom na wynajętym GPU

> **23.11.2026: workflow `koder.yml` usunięty.** Runner GitHuba czekał na GPU do 2 h i palił minuty;
> wynajem GPU z GitHub Actions jest zakazany (CLAUDE.md, `tools/zakaz_renderu_gha.py`).
> Koder przechodzi na Cloudflare; do tego czasu push na `koder/*` niczego nie uruchamia.


Dwa tory pisania kodu w NotarAI:

- **koder** – otwarty model (Qwen3.8-27B) na karcie wynajmowanej na SaladCloud. Tani, pracuje
  w chmurze bez komputera operatora, dobry w małych, zamkniętych zadaniach z testem.
- **claude** – sesja Claude Code. Projektuje, dzieli pracę na karty, robi to, czego koder nie
  powinien dotykać, i przegląda wszystko, co koder oddał.

## Jak zlecasz

Mówisz Claude zwykłym zdaniem, co ma być zrobione. Resztę robi Claude:

1. **Dzieli** pracę na zadania i dla każdego pisze kartę w `docs/agent-tasks/kolejka/`.
2. **Przydziela tor** według reguły poniżej i sprawdza karty poleceniem
   `python tools/agent_factory/koder/karta.py lint`.
3. **Wypycha** gałąź `koder/<nazwa-paczki>`. Webhook GitHuba budzi Workera Cloudflare
   `notarai-koder` (sekcja „Gdzie to działa”): wynajem karty, model, zadania po trzy naraz,
   usunięcie karty. GitHub Actions nie bierze w tym udziału.
4. **Odbiera** wyniki z gałęzi `agent/<przebieg>-wyniki` (`WYNIKI.md`) i przegląda każdy diff
   z gałęzi `agent/<przebieg>-<id>`.
5. **Składa** przyjęte zmiany w jeden pull request do Twojej akceptacji. Zadania niezaliczone
   robi sam albo zwraca z pytaniem. Karty zadań tor `claude` wykonuje w zwykłej sesji.

Agent niczego nie scala, nie wdraża i nie ma żadnych kluczy.

## Gdzie to działa (od 23.11.2026: Cloudflare, nie GitHub Actions)

Twarda reguła właściciela: z GitHub Actions nic się nie renderuje i nie wynajmuje GPU
(`tools/zakaz_renderu_gha.py`). Dawny workflow `koder.yml` usunięto: runner czekał na kartę
do 2 h i palił minuty Actions.

```
push koder/* ──webhook──▶ Worker notarai-koder ──brama salad-brama──▶ SaladCloud: 1 karta
POST /start  ──token────▶  (Durable Object,       (klucz Salad zostaje   vLLM 127.0.0.1:8001
                            alarm co minutę,        w Workerze Finance     + agenci + ocena
                            cron co 5 min)          You)                   (wezel.py)
                ◀── GET /stan, GET /wyniki przez bramę kontenera Salad ──┘
                ──▶ gałęzie agent/* (API GitHuba albo odbierz.py), DELETE karty
```

- **Worker:** `https://notarai-koder.financeyou.workers.dev`, kod w
  `tools/agent_factory/koder/cloudflare/` (wdrożenie `npx wrangler@4 deploy` w tym katalogu,
  testy `node --test test/*.test.mjs`). Limity w `wrangler.jsonc`: `KODER_MAX_USD` (1,5),
  `KODER_MINUTES` (120), `KODER_PRIORITY` (`batch,high` - najpierw tańszy batch).
- **Węzeł:** grupa `finyou-ai-clip-koder-<czas>` (taką nazwę przepuszcza brama). Polecenie
  kontenera pobiera `wezel.py` z publicznego repo pod dokładnym SHA, stawia vLLM, instaluje
  mini-swe-agent, wykonuje `przebieg.sh` w trybie `KODER_TRYB=wezel` i wystawia paczkę wyników.
  Na węźle nie ma żadnych kluczy (ani Salad, ani GitHuba).
- **Izolacja bez Dockera** (na Salad nie da się uruchomić kontenera w kontenerze): repo zaufane,
  ukryte testy i wyniki w katalogach roota 0700; każdy agent jako osobny użytkownik bez
  uprawnień we własnej kopii bez `.git` i bez `ukryte/`; po agencie jego procesy są zabijane;
  ukryte testy uruchamia użytkownik `ocena`. Ruch agenta do sieci idzie na martwy pośrednik -
  to utrudnienie, nie zapora, dlatego na węzeł trafia wyłącznie publiczny kod.
- **Karta zawsze usunięta:** po odbiorze wyników od razu; po terminie (`KODER_DEADLINE`) przez
  alarm Workera; cron co 5 minut usuwa każdą grupę kodera po terminie albo osieroconą; strażnik
  bramy Finance You usuwa grupy po `AICLIP_DEADLINE`; sam węzeł kończy pracę po terminie.
- **Wspólna brama:** dopóki trwa render `finyou-ai-clip*`, koder czeka (do 45 min), żeby nie
  blokować renderu. Gdy Worker dostanie własny `SALAD_API_KEY` (z `notarai/salad`), działa
  wprost z api.salad.com na grupach `notarai-koder-*` i brama nie jest potrzebna.

### Uruchomienie i odbiór

```bash
# token: z public.render_tokens (zakres gpu:salad), w pliku poza repo; nigdy w czacie
H="x-webhook-secret: $(cat ~/.koder-token)"; U=https://notarai-koder.financeyou.workers.dev
curl -X POST -H "$H" -d '{"ref":"koder/paczka"}' $U/start   # albo {"sha":"…","karty":"a,b"}
curl -H "$H" $U/stan                                         # faza, Salad, postęp węzła, koszt
curl -X POST -H "$H" $U/stop                                 # natychmiast usuń kartę
KODER_TOKEN_PLIK=~/.koder-token python3 tools/agent_factory/koder/odbierz.py <przebieg> --push
```

`odbierz.py` jest potrzebny, dopóki Worker nie ma `GITHUB_TOKEN`; z tokenem Worker sam
zakłada gałęzie `agent/<przebieg>-<id>` i `agent/<przebieg>-wyniki` (faza `wypychanie`).

### Do zrobienia przez właściciela (raz)

1. **Webhook** (wymaga admina repo): wygeneruj sekret (`openssl rand -hex 32`), zapisz go
   w Secrets Manager jako `notarai/koder-webhook` (eu-central-1) i wgraj do Workera:
   `npx wrangler@4 secret put GITHUB_WEBHOOK_SECRET` (nadpisuje tymczasowy). Potem w GitHubie
   Settings → Webhooks → Add webhook: Payload URL
   `https://notarai-koder.financeyou.workers.dev/github`, Content type `application/json`,
   Secret = ta sama wartość, zdarzenie „Just the push event”. Worker odpowie na `ping`.
   Bez webhooka działa ręczny `POST /start`.
2. **Token GitHuba dla Workera** (opcjonalnie, żeby gałęzie zakładał sam): fine-grained PAT
   tylko na `plnyspolka-pixel/notarai`, uprawnienie Contents: Read and write, potem
   `npx wrangler@4 secret put GITHUB_TOKEN` w `tools/agent_factory/koder/cloudflare/`.
3. **Własny klucz Salad** (opcjonalnie): `SALAD_API_KEY` z `notarai/salad` przez
   `asm-exec` do `wrangler secret put SALAD_API_KEY` (wartość nie trafia do kontekstu ani
   logów) oraz `SALAD_ORG` w `wrangler.jsonc` na organizację z tego sekretu.

### Przebieg próbny (23.11.2026)

`cf-20261123t2233h`: 3 karty (`walidacja-regon`, `nazwy-max-dlugosc`, `taksa-kwota-kropki`),
**3 z 3 zaliczone** (widoczny test + ukryte testy), RTX 5090; batch nie dał węzła w 15 min,
więc Worker przeszedł na high. Od utworzenia karty do usunięcia 14 min, górna granica kosztu
0,14 USD (pierwsza próba `cf-20261123t2146h` padła na braku gita w obrazie, karta usunięta
od razu, do 0,28 USD - głównie pobieranie obrazu). Zero minut GitHub Actions.

## Karta zadania

```markdown
---
id: taksa-wypis-granice
tor: koder
zakres:
  - taksa.py
  - test_taksa.py
sprawdzenie: python -m pytest -q test_taksa.py
kroki: 40
---
# Koszt wypisu: odrzucaj ujemną liczbę stron

Co jest teraz, co ma być, na jakim przykładzie widać różnicę, czego nie ruszać.
```

Dobra karta dla kodera odpowiada na cztery pytania bez zgadywania: **gdzie** (plik, funkcja),
**co ma się zmienić** (zachowanie przed i po, najlepiej na przykładzie wejście → wynik),
**po czym poznać koniec** (test), **czego nie ruszać**. Wzór: `docs/agent-tasks/SZABLON.md`.

**Dlaczego karta jest krótka:** w naszym pomiarze na 100 parach zwykłe polecenie dało 27/100,
a „ustrukturyzowany kontrakt” 13/100 przy +35–40% tokenów (gałąź learning-loop, 16.11.2026).
Sekcji nie dokładamy bez pomiaru A/B (`docs/lab-openalex/PROTOKOL-POMIARU.md` w laboratorium).

## Reguła przydziału: koder czy Claude

Zadanie idzie do **kodera**, gdy spełnia wszystkie warunki:

| Warunek | Dlaczego |
|---|---|
| Najwyżej 4 pliki, wskazane z nazwy | mały model gubi się w szukaniu po całym repo |
| Jest test `pytest`, który rozstrzyga wynik | bez testu nie ma jak odebrać pracy automatycznie |
| „Co” jest przesądzone, zostaje tylko „napisz” | decyzje projektowe to praca Claude i Twoja |
| Nie wymaga sieci, kluczy, przeglądarki ani żywych systemów | robotnik jest odcięty od świata |
| Nie dotyka obszarów zastrzeżonych | patrz niżej |
| Jest ich co najmniej kilka naraz | start karty to ok. 25 minut i 0,25 USD przed pierwszym zadaniem |

Zadanie zostaje u **Claude**, gdy zachodzi którykolwiek punkt:

- obszary zastrzeżone: logowanie i uprawnienia, płatności i tokenomia, dane osobowe i ich
  przetwarzanie, AML/GIIF i księgi notarialne, teksty prawne, infrastruktura AWS i workflowy,
  wywołania modeli i prompty (lista plików: `ZASTRZEZONE` w `karta.py`);
- zmiana przechodzi przez kilka modułów albo wymaga decyzji o architekturze;
- przyczyna błędu jest nieznana i trzeba jej szukać;
- wynik ocenia się okiem (wygląd strony, tekst dla klienta) albo na żywym systemie;
- wymaganie jest niejasne i trzeba dopytać;
- zadanie jest pojedyncze i pilne – Claude zrobi je szybciej, niż wstanie karta.

Pierwsze trzy warunki i obszary zastrzeżone pilnuje kod: karta z torem `koder`, która je łamie,
nie przejdzie `karta.py lint` i workflow ją pominie.

## Kiedy wynik kodera jest zaliczony

Automatycznie, wszystkie naraz: agent zakończył sam (`Submitted`), test z karty przechodzi
w świeżym kontenerze bez sieci, **ukryte testy przechodzą**, coś zostało zmienione i nic poza
zakresem karty.

Dodatkowe bramki (od 17.11.2026):
- **Karta otwarta** (tytuł albo punkt od „popraw”, „zrefaktoruj”, „ulepsz”, „uporządkuj”…) musi
  mieć `## Kryteria akceptacji` z 1–3 punktami, inaczej nie przejdzie `karta.py lint` (W7).
- **„Zmiana niepotrzebna”** to dozwolony wynik, liczony osobno (`niepotrzebna`), jeśli agent
  niczego nie zmienił, a testy, także ukryte, przechodzą na niezmienionym kodzie. Inaczej
  odrzucenie z powodem `niepotrzebna_niepotwierdzona`.
- **Nowa zależność:** diff z importem spoza stdlib, repozytorium i `requirements.txt` jest
  odrzucany (`nowa_zaleznosc`, miara K5 w `WYNIKI.md`), bo modele zmyślają nazwy paczek (S051).
- **Dziennik:** każde zadanie zostawia wiersz w `dziennik.jsonl` z manifestem silnika (model,
  vLLM, dtype, kwantyzacja, kontekst, prefix caching, GPU, sha uprzęży, sha karty, skrót
  ukrytych testów) i powodami decyzji. Bez promptów i treści plików; koszt nieznany = `null`.

### Ukryte testy (od 17.11.2026)

Agenci zgłaszają jako ukończone ok. 70% zadań, które faktycznie się nie udały, a gdy widzą
testy, potrafią się do nich dopasować (laboratorium OpenAlex, `docs/lab-openalex/STAN-WIEDZY.md`,
działy C2 i D2). Dlatego każdą kartę toru `koder` Claude pisze razem z katalogiem
`docs/agent-tasks/ukryte/<id>/`, którego agent nie widzi (kopia dla agenta powstaje bez niego
i bez `.git`):

| `rodzaj:` w karcie | Co Claude dokłada do `ukryte/<id>/` | Warunek przed startem agenta | Zaliczenie |
|---|---|---|---|
| `zmiana` (domyślny) | `test_*.py` – testy zachowania docelowego, inne przypadki niż w treści karty; opcjonalnie `*.patch` | ukryte testy **oblewają** kod bazowy | ukryte testy przechodzą |
| `refaktor` | `test_*.py` + co najmniej jedna łatka `*.patch` zmieniająca zachowanie | ukryte testy przechodzą na bazie, a **oblewają** każdą łatkę | ukryte testy przechodzą |
| `testy` | co najmniej jedna łatka `*.patch` z celowym błędem w module | łatki dają się nałożyć | test z karty **oblewa** każdą łatkę |

Łatki to „test sabotażu”: celowo złe rozwiązanie, które musi zostać odrzucone. Karta, która nie
przejdzie warunku przed startem, jest wadliwa – agent jej nie dostaje (oszczędza czas GPU),
a karta wraca do Claude. Logika: `tools/agent_factory/koder/ukryte.py`; lokalnie bez Dockera:
`KODER_OCENA=lokalnie python tools/agent_factory/koder/ukryte.py przed <karta> <katalog>`.

W `WYNIKI.md` jest kolumna „Ukryte” i licznik **fałszywych sukcesów** (agent zgłosił koniec,
widoczny test zielony, ukryte czerwone) – to miara W6 dla każdego modelu.
Niezaliczone zadanie nie jest ponawiane na GPU – przechodzi do Claude.
Zaliczone i tak czyta Claude przed złożeniem pull requesta: test mówi, że działa, nie że jest dobrze.

## Koszty i miara

- Karta RTX 5090: 0,25 USD/h w priorytecie batch (0,60 USD/h high), naliczane od pobierania
  modelu. Limity w `tools/agent_factory/koder/cloudflare/wrangler.jsonc`: `KODER_MINUTES`,
  `KODER_MAX_USD`; po terminie węzeł wyłącza się sam nawet bez Workera. Batch może zostać
  przerwany przez Salad - wtedy przebieg kończy się terminem, a niezaliczone karty wracają.
- Pierwsza próba (16.11.2026): 5 zadań, 5 oddanych, 4 z 4 sprawdzanych zaliczone, 52 minuty
  karty, ok. 0,52 USD. To za mało na wniosek o jakości.
- Miarą jest **koszt przyjętej zmiany** (USD karty ÷ liczba zmian przyjętych po przeglądzie),
  nie cena tokenu. Wyniki każdego przebiegu zostają w `docs/agent-tasks/wyniki/<przebieg>/`.

## Ograniczenia

- Węzły Salad to cudze komputery poza UE: do kodera trafia wyłącznie kod z tego publicznego
  repozytorium i dane syntetyczne. Nigdy `dane/`, `.env`, dane klientów.
- Największa karta Salad ma 32 GB, stąd model 27B w 4 bitach. Większe modele wymagają innego
  dostawcy.
- Brama Salad ucina żądanie po 100 s, więc odpowiedź modelu jest ograniczona do 4096 tokenów,
  a tryb „myślenia” modelu jest wyłączony.
- Na węźle agent ma technicznie dostęp do internetu (patrz izolacja wyżej); ukryte testy
  leżą w publicznym repo, więc to pomiar, nie sejf.
