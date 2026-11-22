# SEC-13 — [SEC-13] Niezależny audyt i bramka sprzedaży Zero Trust / Zero Operator / Zero Knowledge

**Status: PLANNED (NOT IMPLEMENTED).** P0 — finał; zależności: SEC-01 do SEC-12 oraz zewnętrzny audytor

## Zakres
1. Przygotuj formalny zakres audytu zewnętrznego: aplikacja, front-end, SDK, IAM/SCP, Nitro hardware, KMS custody, key release, source code chain, portal egress, LLM provider, tenant isolation, backup, legal hold.
2. Zdefiniuj zestaw dowodów akceptowanych przez kancelarię notarialną i technicznego audytora, oświadczenia operatora, zakres odpowiedzialności kustosza oraz brak wpływu operatora na aktualizację pomiarów KMS.
3. Oceń RODO, tajemnicę notarialną, role procesora/podprocesorów, region usług AI, ograniczenia marketingowe; certyfikacji nie twierdź, gdy jej nie ma.
4. Przygotuj prawdziwe teksty oferty/umowy: jasno wyliczone gwarancje i wyjątki. Jeśli nie ma pełnego kryptograficznego Zero Knowledge, użyj precyzyjnego 'confidential processing / brak jednostronnego dostępu operatora', nie bezwarunkowego 'nikt nie zna danych'.
5. Maszynowa bramka GO/NO-GO marketingu: wyłącznie kompletne aktualne signed evidence oraz formalne niezależne zatwierdzenie mogą zmienić status z NIE SPRZEDAWAĆ na DOZWOLONE W OKREŚLONYM ZAKRESIE.

## Kryteria odbioru
- [ ] Niezależna ocena bezpieczeństwa z wynikami i zaakceptowanym threat model.
- [ ] Weryfikowalne pakiety dowodowe i jawne ograniczenia claims przy różnych wariantach AI i egress.
- [ ] Dokumenty dla sprzedaży bez nieudowodnionej certyfikacji lub ścisłego Zero Knowledge.

## Instrukcja dla osobnej konwersacji
To **wyłącznie PR planistyczny**. Zrealizuj zadanie na istniejącej gałęzi tego PR, uzupełnij kod, testy, instrukcje i dowody w tym samym PR. Czytaj poprzednie #57, #60, #61, #62, #65 i odpowiednie SEC-nn; sprawdź aktualne SHA. Wszystkie SEC-nn bazują na #65 i nie wymagają edycji gałęzi pozostałych zadań. Jeśli potrzebna zmiana w pliku współdzielonym, udokumentuj integracyjne uzgodnienie i konflikt.
Zakres danych: wyłącznie syntetyczne pilot01/pilot02, EU eu-central-1, produkcja OFF, no-submit/no-sign. Nie dotykaj prawdziwych spraw, nie wynoś plaintext ani sekretów do CloudWatch/GitHub/proxy. Nie wykonuj AWS write bez autoryzowanych tożsamości i zgody kustosza. Wyniki CI != real hardware evidence. Kryteria: kod + testy odmowy + dokumentacja, niezależny dowód i jawne FAIL/BLOCKED. Bez automatycznej deklaracji 'Verified Zero Knowledge/Zero Operator Access'.
