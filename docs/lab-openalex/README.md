# Laboratorium OpenAlex — stan wiedzy i kierunki

Część laboratorium agentowego (Agent Forge, koder na SaladCloud) odpowiedzialna
za **literaturę naukową**: co już wiadomo, co jest nowe, czego nie wiemy
i co z tego warto sprawdzić u siebie na wynajętym GPU.

Dwa kierunki:

1. **Bezpieczeństwo systemów informatycznych** — także bezpieczeństwo agentów
   AI i bezpieczeństwo z pomocą AI.
2. **Budowa, trening i serwowanie LLM oraz programowanie agentami** — na jednej
   karcie wynajmowanej na godziny.

## Co tu jest

| Plik | Co to |
|---|---|
| [STAN-WIEDZY.md](STAN-WIEDZY.md) | stan wiedzy na dzień wpisu: co wiadomo, z jaką pewnością, co z tego wynika dla nas |
| [KIERUNKI.md](KIERUNKI.md) | kolejne kierunki i eksperymenty laboratorium, z kosztem i miarą sukcesu |
| [GENEROWANIE-WIDEO.md](GENEROWANIE-WIDEO.md) | generowanie obrazów i wideo na otwartych modelach: workflow, agenci, powtórki, ocena (rejestry `media-*.jsonl`, M/N/Q, 100 prac) — pod ai-clip |
| `zrodla/*.jsonl` | rejestry prac (każda z identyfikatorem OpenAlex): `bezpieczenstwo` (S, 62), `llm-agenci` (L, 71), `trening-agentow` (T, 77), `praca-z-agentami` (P, 57), `zbiory-dla-agentow` (D, 85); `zbiory-danych` — rejestr dziedzinowy drugiej sesji |
| `weryfikacja/*.jsonl` | wynik weryfikacji rejestrów — także starszych, z gałęzi laboratorium |
| [radar.json](radar.json) | tematy obserwowane co tydzień |
| `radar/RRRR-MM-DD.md` | przeglądy nowych prac (do ręcznej selekcji) |

Narzędzia: `tools/lab_openalex/` (bez zależności, Python ≥ 3.10), testy
`tests/test_lab_openalex.py`.

## Zasady

- **Każda praca w rejestrze ma identyfikator OpenAlex** albo zweryfikowany
  numer arXiv. Pozycja „z pamięci modelu” nie wchodzi do rejestru.
- **Liczby tylko „według autorów”** i tylko ze streszczenia lub tekstu pracy.
  Wynik z pracy to hipoteza dla nas, nie fakt o naszym stosie — dopiero
  eksperyment według protokołu Agent Forge (te same zadania, ukryte testy,
  przedziały niepewności) mówi, czy działa u nas.
- **Rejestr przechodzi weryfikator przed użyciem**:

  ```bash
  python tools/lab_openalex/weryfikuj.py docs/lab-openalex/zrodla/bezpieczenstwo.jsonl --out docs/lab-openalex/weryfikacja/bezpieczenstwo.jsonl
  ```

  Werdykty: `potwierdzona`, `potwierdzona_arxiv` (OpenAlex jeszcze nie
  zaindeksował), `znaleziona_tytul`, `tytul_inny`, `niepewna`,
  `nie_znaleziona`. Wszystko poza dwoma pierwszymi ogląda człowiek.
- **Radar raz w tygodniu**: `python tools/lab_openalex/radar.py`. Radar tylko
  proponuje; do rejestru trafia to, co ktoś przeczytał i opisał „po co nam”.
- Bez danych klientów, bez kluczy w repo. Klucz OpenAlex jest opcjonalny
  (`OPENALEX_API_KEY`); bez niego jest darmowy budżet ok. 0,10 USD dziennie na
  adres IP, a pobranie pojedynczego rekordu nic nie kosztuje.

## Weryfikacja starszych rejestrów (17.11.2026)

| Rejestr | Pozycji | Wynik |
|---|---|---|
| `ai-coding-100-2026.jsonl` (gałąź `feature/agent-factory-learning-loop-20261116`) | 100 | wszystkie istnieją; 2 bez DOI arXiv w OpenAlex (numer poprawny), 1 jeszcze niezaindeksowana (jest na arXiv), 1 wydana pod nowym tytułem (SWE-Factory → „SWE Data Construction, Automatically!”, ACM PACMSE) |
| `academic-evidence.json` (gałąź `feature/frontier-engineering-lab-20261115`) | 24 | 22 prace istnieją (różnice tytułów to skróty); 2 to wpisy blogowe (METR, Princeton) — poza OpenAlex z definicji |

**Do poprawy w rejestrze 24 dowodów:** przy Self-HPO zapisano „61,0 → 69,5 na
SWE-bench Verified”, a streszczenie podaje średnią z trzech benchmarków
**57,8 → 64,8** (Qwen3.5-35B-A3B). Liczba z rejestru może pochodzić z tabeli
pracy — do sprawdzenia w PDF, zanim posłuży do decyzji.
