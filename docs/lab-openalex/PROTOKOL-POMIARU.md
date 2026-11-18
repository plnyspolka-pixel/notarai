# Protokół pomiaru (W4) — obowiązuje każdy eksperyment K/G/X

Dopisek do protokołu Agent Forge (`docs/agent-factory-research/experiments.md`).
Bez spełnienia tych punktów wynik ma status **NIEROZSTRZYGNIĘTY**, nie „wygrana”.

## 1. Jednostka i miara
- Miara główna: **koszt (USD) na przyjętą zmianę** = zmiana, która przeszła ukryte
  testy i przegląd. Koszt nieznany = `null`, nigdy 0.
- Jednostką niezależną jest **karta (zadanie)**, nie przebieg. Powtórzenia tej samej
  karty i ziarna jednej karty nie są niezależne.

## 2. Powtórzenia i przedziały (L057, L058; uwaga B7)
- 3–5 powtórzeń na kartę w każdym ramieniu; te same karty, te same ziarna w ramionach.
- Przy n < 100 kart **nie** używać przedziałów z CLT. Używać:
  - dla odsetka przyjęć: przedział **Clopper–Pearson** albo **Beta(1+s, 1+n−s)**;
  - dla porównania par ramion: **dokładny test znaków** na kartach, gdzie ramiona
    się różnią, oraz **bootstrap po klastrach kart** (losujemy karty, nie przebiegi);
  - implementacja: `tools/agent_factory/forge_research_stats.py`.
- Decyzja „ramię B lepsze” tylko, gdy **dolna granica** różnicy > 0 i ramię nie
  pogarsza żadnej bramki bezpieczeństwa.

## 3. Sędzia LLM (L059; Q5 z ACADEMIC_REVIEW)
- Sędzia tylko pomocniczo. Rozstrzyga test, CI albo człowiek.
- Jeśli sędzia jest użyty: losowa kolejność A/B, ≥ 2 powtórzenia, raport zgodności
  z człowiekiem na ≥ 30 przykładach (kappa) i **korekta odsetka** o czułość
  i swoistość sędzia-vs-człowiek (estymator Rogana–Gladena).

## 4. Uczciwe porównania
- Każdy wariant wieloagentowy porównujemy z **jednym agentem przy tym samym budżecie**
  tokenów i GPU-godzin (L050–L052).
- Silnik zapisany obok modelu: wersja vLLM, dtype/kwantyzacja, KV cache, kontekst,
  prefix caching, GPU (Silent Hyperparameter: do 16,6 pp różnicy). Źródło: manifest
  przebiegu kodera (`tools/agent_factory/koder/manifest.py`).
- HOLDOUT: karty młodsze niż dane treningowe, nieoglądane przy strojeniu.
  Trwała porażka rodziny zadań → nowy holdout albo eskalacja, nie strojenie pod grader.

## 5. Trening (T045, T046)
- Krzywa straty **nie jest** miarą sukcesu: po każdym checkpoincie regresja na
  ogólnym benchmarku kodu i na HOLDOUT (naiwne SFT zjadło 18,9 pkt HumanEval przy
  „zdrowej” stracie).
- Ponowny trening przy każdym **podwojeniu** przyjętych trajektorii.
- Weryfikator dobry w best-of-N nie musi być dobrą nagrodą RL (T025) — sprawdzić
  kontrolą „losowa nagroda” przed K7.

## 6. Nasze pomiary wygrywają z literaturą
- Gdy nasz pomiar przeczy rekomendacji z prac, obowiązuje pomiar — i zapisujemy go
  tutaj. Przykład (16.11.2026, learning-loop, 100 par dev): zwykłe polecenie
  **27/100** vs „ustrukturyzowany kontrakt” **13/100** przy +35–40% tokenów promptu.
  Wniosek: karty krótkie; rozbudowa szablonu tylko po A/B.

## 7. Zapis
- Każdy przebieg: manifest + rekord JSONL (bez promptów i treści plików), wynik
  w `docs/lab-openalex/wyniki/<eksperyment>-<data>.md` z: hipotezą, ramionami, n,
  przedziałami, decyzją, kosztem rzeczywistym z rachunku.
