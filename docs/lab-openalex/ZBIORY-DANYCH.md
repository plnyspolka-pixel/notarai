# Zbiory danych z OpenAlex — co jest, czego brak, po co nam

Stan na 17.11.2026. Rejestr: [zrodla/zbiory-danych.jsonl](zrodla/zbiory-danych.jsonl)
(26 pozycji), weryfikacja: [weryfikacja/zbiory-danych.jsonl](weryfikacja/zbiory-danych.jsonl)
— **26/26 potwierdzone** przez `weryfikuj.py` (DOI istnieje, tytuł zgodny).

Poziom dowodu: **metadane z OpenAlex**. Nikt jeszcze nie pobrał żadnego zbioru,
nie sprawdził licencji ani zawartości. Każda pozycja ma `licencja:
do_sprawdzenia` i `dane_osobowe: do_sprawdzenia`.

## Czym są „zbiory danych” w OpenAlex

Typ `dataset` to głównie depozyty z repozytoriów danych badawczych: Zenodo,
Harvard Dataverse, Figshare, Mendeley Data, ICPSR, IEEE DataPort, Hugging Face,
polskie RepOD i repozytoria uczelni (UW, UJ, AGH). Zwykle są to **pakiety
replikacyjne** konkretnych prac (dane + kod), rzadziej duże korpusy.

Z Polski jest ok. 10 tys. takich depozytów (Zenodo 3,4 tys., RepOD 1,3 tys.,
repozytorium UJ 318, UW 227). Duże znane zasoby (np. SAOS, PolEval, NKJP)
występują w OpenAlex głównie jako **artykuły**, nie jako `dataset` — szuka się
ich przez prace, które je opisują.

## Co znaleźliśmy, według kierunku

| Kierunek | Pozycji | Najcenniejsze | Do czego |
|---|---|---|---|
| NotarAI — prawo | 5 | anotacje klauzul w polskich umowach NDA; legislacja PL 1989–2025 | test ekstrakcji klauzul; test „prawo na dzień X” |
| Finance You — kredyt | 5 | dane Ganong–Noel („dlaczego nie spłacają hipotek”), Fuster–Willen (rata a niespłacanie) | mechanizmy ryzyka przy zastawie, sens restrukturyzacji w windykacji |
| Finance You — nadużycia | 2 | FalsID (podrobione dokumenty), FLUXSynID (syntetyczne twarze) | KYC bez danych prawdziwych osób |
| Finance You — nieruchomości | 2 | protokół walidacji przestrzennej AVM | jak uczciwie sprawdzić automatyczną wycenę |
| Marketing z AI | 4 | ujawnianie AI w reklamie; cyfrowy rzecznik a zaufanie inwestorów | decyzja o awatarach w rolkach i w komunikacji z inwestorami |
| ai-clip — mowa i wideo | 4 | nEMO (emocje polskiej mowy), AI-SPEAK (słowiańska synchronizacja ust) | niezależne mierniki tonu i sync w bramce akceptacji |
| Agenci — ocena | 2 | QualDeltaBench (LLM jako sędzia kodu), 10 tys. przebiegów agenta | kalibracja sędziego i wykrywanie obchodzenia zadań bez GPU |
| Web Factory | 2 | Sketch2Code, strony produktowe Klarny | testy generatora i agentów przeglądarkowych |

## Prace powiązane (nie zbiory, ale wskazują dane)

- Dadas i in. 2024, *A support system for the detection of abusive clauses in B2C
  contracts*, Artificial Intelligence and Law — [W4400048050](https://openalex.org/W4400048050).
  Klauzule niedozwolone po polsku (OPI PIB): wprost dotyczy umów pożyczek
  Finance You i przeglądu umów w NotarAI. **Najpierw ustalić, czy dane są
  udostępnione.**
- Rejestracja badania na OSF: staleness legal LLM na polskim benchmarku „as-of”
  — [W7213290963](https://openalex.org/W7213290963). Ten sam problem co „prawo
  na dzień X”.
- *Annotated Surrogate Retrieval for Polish Statutory Law* (arXiv 2608.30929) —
  [W7204944872](https://openalex.org/W7204944872). Wyszukiwanie przepisów po polsku.
- *Polish Court Ruling Classification Using Deep Neural Networks* (Sensors 2022)
  — [W4220736205](https://openalex.org/W4220736205).

## Czego w OpenAlex NIE ma (luki)

- **Ceny i transakcje nieruchomości w Polsce**: 5 wyników, żaden użyteczny.
  Źródła są poza OpenAlex: RCiWN (Rejestr Cen i Wartości Nieruchomości), BaRN NBP,
  GUS/BDL, AMRON-SARFiN. Trzeba je oceniać osobno (licencja, koszt, RODO).
- **Polskie dane o zadłużeniu i windykacji gospodarstw domowych**: brak. Poza
  OpenAlex: BIK/BIG (płatne raporty), HFCS (badanie EBC, dostęp na wniosek),
  raporty KNF i UOKiK.
- **Polska synchronizacja ust i mowa w wideo**: brak polskiego zbioru, jest
  serbski. To przemawia za własnym, małym zbiorem testowym z naszych klipów
  (zgoda aktorów/głosów jest już w obsadzie).
- **Księgi wieczyste, akty notarialne**: brak i nie należy się spodziewać
  (dane osobowe). Do testów zostają dokumenty syntetyczne.

## Zasady użycia

1. Zbiór trafia do eksperymentu dopiero po sprawdzeniu licencji w samym
   repozytorium (Zenodo/Figshare podają ją na stronie depozytu). „Publicznie
   dostępny” nie znaczy „wolno komercyjnie”.
2. Zbiór z danymi osobowymi (twarze, głos, dane kredytobiorców) — tylko po
   ocenie RODO; w laboratorium wyłącznie zbiory syntetyczne lub zanonimizowane.
3. Liczby z pakietów replikacyjnych to wynik autorów na ich rynku. U nas służą
   do przeniesienia **metody** (np. protokół walidacji AVM), nie wartości.
4. Pobieranie zbiorów — osobno, do katalogu poza repo, każdy w osobnym
   katalogu; repo przechowuje tylko metadane.

## Następne kroki

1. Sprawdzić licencje i zawartość pięciu najważniejszych: klauzule NDA (PL),
   Ganong–Noel, ujawnianie AI w reklamie, nEMO, QualDeltaBench.
2. Ustalić u autorów (Dadas i in., OPI PIB), czy zbiór klauzul niedozwolonych
   jest dostępny.
3. Radar co tydzień obejmuje teraz sześć tematów `zbiory-danych` (pole `typ:
   dataset` w [radar.json](radar.json)).
4. Ocenić źródła spoza OpenAlex (RCiWN, BaRN, HFCS) jako osobny wpis.
