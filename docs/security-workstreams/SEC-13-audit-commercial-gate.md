# SEC-13 — [SEC-13] Niezależny audyt i bramka sprzedaży Zero Trust / Zero Operator / Zero Knowledge

**Status: PLANNED (NOT IMPLEMENTED).** P0 — finał; zależności: SEC-01 do SEC-12 oraz zewnętrzny audytor

## Zakres
1. Przygotuj formalny zakres audytu zewnętrznego: aplikacja, front-end, SDK, IAM/SCP, Nitro hardware, KMS custody, key release, source code chain, portal egress, LLM provider, tenant isolation, backup, legal hold.
2. Zdefiniuj zestaw dowodów akceptowanych przez kancelarię notarialną i technicznego audytora, oświadczenia operatora, zakres odpowiedzialności kustosza oraz brak wpływu operatora na aktualizację pomiarów KMS.
3. Oceń RODO, tajemnicę notarialną, role procesora/podprocesorów, region usług AI, ograniczenia marketingowe; certyfikacji nie twierdź, gdy jej nie ma.
4. Przygotuj prawdziwe teksty oferty/umowy: jasno wyliczone gwarancje i wyjątki. Jeśli nie ma pełnego kryptograficznego Zero Knowledge, użyj precyzyjnego 'confidential processing / brak jednostronnego dostępu operatora', nie bezwarunkowego 'nikt nie zna danych'.
5. Maszynowa bramka GO/NO-GO marketingu: wyłącznie kompletne aktualne signed evidence oraz formalne niezależne zatwierdzenie mogą zmienić status z NIE SPRZEDAWAĆ na DOZWOLONE W OKREŚLONYM ZAKRESIE.

## Mierzalne kryteria zakończenia — SEC-13

- [ ] **K1.** **12 etapów poprzedzających:** bramka GO/NO-GO czyta wyniki SEC-01…SEC-12; 12/12 ma wskazany HEAD commit, status implementacji, niezależny artefakt dowodowy, status LIVE/NOT-LIVE i datę ważności; brak któregokolwiek krytycznego dowodu => `NO-GO`.
- [ ] **K2.** **Niezależny audyt:** istnieje podpisana przez faktycznie niezależnego audytora ocena obejmująca workload IAM/SCP, KMS custody, GitHub release, sprzęt Nitro, eksfiltrację, izolację tenant, frontend i AI/LLM; raport zawiera datę, zakres, ograniczenia, listę 0 otwartych niezaakceptowanych ustaleń krytycznych i wysokich.
- [ ] **K3.** **E2E przed ofertą:** raport z SEC-12 zawiera 2 sukcesy fikcyjnych kancelarii, minimum 12 odmów przeciwnika i 4 scenariusze awaryjne, 0 nieautoryzowanych decrypt i 0 finalnych submit; hardware i podpis kustosza są aktualne.
- [ ] **K4.** **RODO/tajemnica notarialna:** rejestr procesorów/podprocesorów, regiony AWS/LLM, umowy powierzenia, retencja, odtwarzanie i transfery transgraniczne mają przegląd prawny, datę oraz osobę akceptującą; brak akceptacji = `NO-GO`.
- [ ] **K5.** **Treści handlowe kontrolowane:** powstają odrębne precyzyjne opisy Zero Trust, Zero Operator Access i ograniczonego ZK z wyjątkami i źródłami dowodów; testy automatyczne odrzucają hasła „certyfikowany”, „nikt nigdy nie widzi” lub „100% zero knowledge” bez odpowiadających niezależnych dokumentów.
- [ ] **K6.** **Automatyczna bramka odmowy:** testy obejmują minimum 8 scenariuszy `NO-GO`: brak dowodu, expired, bad signature, klucz custody operator-controlled, dowód jedynie mock/CI, wyciek do LLM poza Nitro, nieudany egress test oraz otwarta podatność krytyczna/wysoka. `GO` wyłącznie po niezależnym podpisanym potwierdzeniu wszystkich wymaganych warunków.

**Docelowy test do dopisania:** `python -m pytest -q test_confidential_commercial_gate.py` — 0 failed, 0 pominiętych testów odmowy.

### Wspólny warunek zamknięcia
- [ ] Zielone CI dla aktualnego HEAD SHA, wynik testów, podpisana opinia zewnętrzna i zanonimizowany raport `docs/security-evidence/SEC-13.md` z linkami do źródeł dla każdego K1–K6.
- [ ] Każde K1–K6 ma `PASS/FAIL/BLOCKED`, datę i właściciela. Zewnętrzny audyt i realny KMS/Nitro nie mogą być zastąpione pozytywnym wynikiem testów mock.
- [ ] Nie otwieraj sprzedaży obietnicy ZK/ZOA bez dowodów; AUTO nadal no-submit/no-sign i żadnych produkcyjnych danych w testach.


## Instrukcja dla osobnej konwersacji
To **wyłącznie PR planistyczny**. Zrealizuj zadanie na istniejącej gałęzi tego PR, uzupełnij kod, testy, instrukcje i dowody w tym samym PR. Czytaj poprzednie #57, #60, #61, #62, #65 i odpowiednie SEC-nn; sprawdź aktualne SHA. Wszystkie SEC-nn bazują na #65 i nie wymagają edycji gałęzi pozostałych zadań. Jeśli potrzebna zmiana w pliku współdzielonym, udokumentuj integracyjne uzgodnienie i konflikt.
Zakres danych: wyłącznie syntetyczne pilot01/pilot02, EU eu-central-1, produkcja OFF, no-submit/no-sign. Nie dotykaj prawdziwych spraw, nie wynoś plaintext ani sekretów do CloudWatch/GitHub/proxy. Nie wykonuj AWS write bez autoryzowanych tożsamości i zgody kustosza. Wyniki CI != real hardware evidence. Kryteria: kod + testy odmowy + dokumentacja, niezależny dowód i jawne FAIL/BLOCKED. Bez automatycznej deklaracji 'Verified Zero Knowledge/Zero Operator Access'.
