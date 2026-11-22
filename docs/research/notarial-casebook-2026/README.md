# NotarAI — źródłowy katalog realiów zawodu notariusza i spraw notarialnych

**Data kwerendy: 22 listopada 2026 r.**  
**Typ materiału: RESEARCH / FACT ONLY.** Bez postaci, odcinków, scenariuszy, dialogów, reklam ani analiz produktu.

## Zakres

| Plik | Liczba rekordów | Treść |
|---|---:|---|
| [01-orzecznictwo.md](01-orzecznictwo.md) | **68** | Sygnatury i odnośniki do SN, TK, SAOS: testamenty, spadki, ochrona osób niesłyszących i schorowanych, odmowa czynności, KW, pierwokup, dożywocie, odpowiedzialność |
| [02-instytucje-obciazenia-zmiany.md](02-instytucje-obciazenia-zmiany.md) | **36** | KRN, MS, MF, KAS, ELI: dane statystyczne, przerwy systemów, obowiązki, nowe schematy raportowania, taksa, interpelacje, projekty |
| [03-sprawy-karne-i-interwencje.md](03-sprawy-karne-i-interwencje.md) | **20** | Oficjalne komunikaty Policji, CBA i prokuratur o oszustwach, zatrzymaniach, aktach oskarżenia, wyroku i umorzeniu, z wyraźnym statusem |
| [04-przepisy-podstawowe.md](04-przepisy-podstawowe.md) | **37** | Artykuły i aktualne urzędowe teksty Prawa o notariacie, KC, KPC, KW i AML |

**Razem: 161 rekordów referencyjnych (124 rekordy orzecznictwa/zdarzeń/komunikatów + 37 przepisów).** Nie oznacza to 161 niezależnych spraw. Niektóre dokumenty odnoszą się do tego samego śledztwa lub orzeczenia. Zachować to rozróżnienie przy liczeniu zdarzeń.

## Główne obszary faktograficzne

1. Sprawy rodzinne i testamentowe: swoboda testowania, choroba, głuchota, odcisk palca, czynności w szpitalu lub poza kancelarią.
2. Ochrona uczestników czynności: weryfikacja tożsamości, zastrzeżony PESEL, obowiązek wyjaśnienia skutków czynności, odmowa.
3. Ryzyko transakcji: fałszywe pełnomocnictwa, nieprawidłowości w cenie i zapłacie, dożywocie, pierwokup, zabezpieczenia, KW.
4. Sądowa ocena dokumentów: brak załącznika, niekompletne żądanie, ograniczony zakres kognicji sądu KW, forma dokumentu.
5. Zmienność prawa i obowiązków: KRN, MS, KAS, GIIF, e-Doręczenia, CREWAN, taksa, projekty deregulacyjne.
6. Codzienność systemowa: raportowanie, wielokrotne czynności techniczne, niedostępność EKW i systemów ministerialnych.
7. Odpowiedzialność zawodowa i tajemnica: art. 18, 49, 80–87 Prawa o notariacie, nadzór i kontrola sądowa.

## Hierarchia źródeł

1. **ELI / Dziennik Ustaw** — źródło obowiązującego aktu prawnego w odpowiedniej wersji historycznej.
2. **SN / TK / SAOS** — treść rozstrzygnięcia, z wyszczególnieniem stanowisk uczestników, ustaleń i sentencji.
3. **Komunikat organu** (MS, MF, KAS, KRN, Policja, prokuratura, CBA) — potwierdza tylko informacje podane przez organ na dzień publikacji.
4. **Interpelacje, projekty ustaw i karty rządowe** — źródła o problemach zgłaszanych i postulatach, nie dowód obowiązywania projektu.
5. **Publikacje medialne** — mogą być pomocnicze; w tej wersji rejestru spraw karnych preferowano komunikaty urzędowe.

## Ograniczenia i kontrola jakości

- **Dane liczbowe** trzeba czytać zgodnie z definicją metryki; zbiorcze liczby czynności nie są średnią przypadającą na notariusza lub kancelarię.
- **Zarzut, akt oskarżenia, wyrok nieprawomocny, wyrok prawomocny i umorzenie** to różne stadia. Nie przypisywać winy przed prawomocnym rozstrzygnięciem. Komunikaty mogą nie ujmować późniejszych zdarzeń w sprawie.
- **SAOS** daje tekst rozstrzygnięcia, ale nie zawsze kompletną historię procesową lub informację o prawomocności. Sygnatury i linki są materiałem do dalszej lektury, a nie autoryzowanym opisem pełnych akt.
- **SN: strony zagadnień prawnych** mogą zawierać pytanie, a nie tezę uchwały. Odczytywać stan sprawy i datę rozstrzygnięcia.
- **Interpelacja** dokumentuje problem podniesiony przez parlamentarzystę, nie dowodzi skali lub jednolitości praktyki sądowej.
- **Duplikaty dokumentów**: P06/P07/P08/P10 — różne etapy rozległego śledztwa o lichwę mieszkaniową; P12/P13 — źródła tej samej sprawy. Nie liczyć jako niezależnych zdarzeń.
- Dokument ma wyłącznie charakter badawczy. Przed publikacją lub wykorzystaniem w komunikacji zewnętrznej potrzebny jest przegląd całości uzasadnień i ewentualnych nowszych rozstrzygnięć.
- Nie przenosić z orzeczeń wrażliwych danych prywatnych ani szczegółów pozwalających identyfikować osoby fizyczne; zachować prawo cytatu i warunki licencyjne źródeł.

## Checklista drugiego przebiegu (research, nie pisanie fabuły)

- [ ] Wybrać konkretny rekord i pobrać pełny tekst orzeczenia/komunikatu.
- [ ] Zapisać sąd/organ, sygnaturę, daty czynności oraz rozstrzygnięcia, podstawy prawne.
- [ ] Rozdzielić stan faktyczny ustalony przez sąd od twierdzeń stron, zarzutów i komentarzy.
- [ ] Sprawdzić sentencję, prawomocność, ewentualną kasację, uchylenie, nowe śledztwo, umorzenie.
- [ ] Ustalić stan prawny obowiązujący w chwili zdarzenia i dziś (Dz.U. + nowelizacje).
- [ ] Przy rozbieżnościach praktyki wskazać co najmniej **dwa konkretne orzeczenia**, zamiast twierdzić ogólnie „sądy orzekają inaczej”.
- [ ] Uzupełnić w kolejnej wersji pola: `verification_status`, `date_verified`, `judgment_final`, `source_count`, `related_ids`, `law_as_of`.

## Kryteria uznania tego PR za gotowy

- [x] Jedna gałąź i jeden PR wyłącznie na dokumentację.
- [x] Ponad 100 faktograficznych rekordów/źródeł z odsyłaczami.
- [x] Rozdzielenie orzecznictwa, komunikatów, aktów i postępowań karnych.
- [x] Linki do konkretnych sygnatur lub oficjalnych komunikatów.
- [x] Wyraźnie oznaczone etapy postępowań i brak założenia prawomocności.
- [x] Brak scenariuszy, kreacji bohaterów i materiału marketingowego.
- [ ] Pełny drugi przebieg fact-check 68 tekstów orzeczeń (na dalszy etap).
- [ ] Ustalenie prawomocności i nowszych rozstrzygnięć w każdej sprawie karnej (na dalszy etap).

## Aktualne teksty urzędowe / bramka prawna

- Prawo o notariacie: [Dz.U. 2026 poz. 614](https://eli.gov.pl/eli/DU/2026/614/ogl) i [nowela Dz.U. 2026 poz. 1099](https://eli.gov.pl/eli/DU/2026/1099/ogl), wejście w życie 19.11.2026.
- Kodeks cywilny: [Dz.U. 2026 poz. 795](https://eli.gov.pl/eli/DU/2026/795/ogl).
- KPC: [Dz.U. 2026 poz. 468](https://eli.gov.pl/eli/DU/2026/468/ogl).
- KW i hipoteka: [Dz.U. 2026 poz. 1066](https://eli.gov.pl/eli/DU/2026/1066/ogl).
- AML: [Dz.U. 2025 poz. 644](https://eli.gov.pl/eli/DU/2025/644/ogl) z późniejszymi zmianami.
- Taksa notarialna: [Dz.U. 2026 poz. 1370](https://eli.gov.pl/eli/DU/2026/1370/ogl), wejście w życie 05.11.2026.

## Wymóg nienaruszalny dla dalszych prac

To repozytorium źródeł, nie brief fabularny. W kolejnych sesjach **wyłącznie dopisywać lub weryfikować fakty i źródła**. Scenariusze i postacie są prowadzone niezależnie przez inny zespół/proces.
