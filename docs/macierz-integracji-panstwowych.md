# Macierz integracji państwowych NotarAI — jedyne miejsce aktualizacji statusów

**Stan bazowy: 25.11.2026.** PR #137, przed scaleniem; audyt repo na 857b211.
Cel: oficjalne połączenia bez zmiany prawa, bez nowych płatnych pośredników, z indywidualnymi uprawnieniami notariuszy. Fundacja występuje jako integrator. Pilotaż odłożony, nie jest warunkiem researchu ani wystąpień integratora.

## Jak czytać i utrzymywać tabelę

- **Dokumentacja:** D0 = nie znaleziono kontraktu; D1 = oficjalna procedura/źródło, nie pełny kontrakt; D2 = kontrakt wskazany lub opisany w źródłach, pliki niezweryfikowane w tej sesji; D3 = kontrakt dostępny w repo albo faktycznie odczytany i sprawdzony. D2 nie znaczy gotowy klient.
- **Kod:** K0 = brak adaptera; K1 = szkic/formularz lub częściowy moduł; K2 = kod w repo. K2 nie oznacza wdrożenia. **TEST:** T0 = brak potwierdzenia; T1 = testy syntetyczne; T2 = oficjalne INT/emulator z wynikiem; T3 = test produkcyjny z uprawnieniem. **PROD:** P0 = niezweryfikowana aktywacja/dostęp; P1 = potwierdzona aktywacja z dowodem. Brak dowodu nigdy nie staje się P1.
- Przy każdej zmianie dopisz datę, źródło i commit/dowód do dziennika poniżej; zmień tylko właściwe pole. Dane historyczne i rozbieżności nie są nowym odkryciem. Nie usuwaj starych ustaleń bez podania przyczyny.
- Przed rozpoczęciem zadania przeczytaj tę macierz, następnie istniejący kod i wskazane zadanie. Szczegóły techniczne pozostają w dokumentacji niżej. Nie twórz drugiego klienta, panelu ani generatora bez konkretnego uzasadnienia.
- Wspólny adres IP tylko na warunkach organu. Indywidualna autoryzacja, izolacja kancelarii, brak pełnego PESEL w logach, brak prawdziwych danych w INT, żadnej rzeczywistej wysyłki bez akceptacji. Nie publikować sekretów, IP infrastruktury, danych klientów ani decyzji imiennych. Dowody prywatne: w macierzy wyłącznie status i niesensytywny identyfikator.
- Źródła poniżej zebrano z istniejących ustaleń repo (16.09, 07.11, 25.11.2026); link nie jest dowodem ponownego pobrania ani bieżącej dostępności. Do implementacji wymagane sprawdzenie aktualnej wersji kontraktu. Szczegóły sporne oznaczono jawnie.

## Macierz A — tożsamość, stan cywilny, czynności notarialne

| ID / system | Instytucja, zakres | Kontrakt / protokół (znane) | Dostęp / INT | Kod i status | Następny konkretny krok / zadanie |
|---|---|---|---|---|---|
| RZNP-API — zastrzeżenia PESEL | MC/COI; aktualny i historyczny status | D2 REST OpenAPI, ZIP 17.04.2024, stub 2.0.8, `rejestr-zastrzezen-proxy-contract.yml`; wcześniejszy opis 16.09: X-API-KEY, allowlista IP, ścieżki statusu — niepotwierdzone w aktualnym YAML. [RZNP] | TEST: wniosek cc.wnioski@coi.gov.pl; PROD: indywidualne uprawnienie i klucz | K0/T0/P0; jest inwentaryzator ZIP, nie klient | Pobrać i zahashować faktyczny ZIP, porównać kontrakt ze starszym opisem, test emulatora; GOV-01 |
| RZNP-KRN — moduł KRN | KRN; sprawdzenie zastrzeżenia | D1 portal Rejestry Notarialne, certyfikat notariusza; API integratora niepotwierdzone [KRN] | Konto notariusza; warunki automatyzacji do ustalenia | K1/T0/P0; `formularze/rejestry_notarialne_pesel.yaml` | NA-4, GOV-09; nie dublować RZNP-API |
| PESEL | MC/COI; dane z rejestru | D1 teletransmisja; kontrakt przekazywany kontaktowi technicznemu [PESEL] | Indywidualne przyznanie zakresu; PESEL-NET/MPLS i certyfikaty do potwierdzenia | K0/T0/P0 | Uzyskać WSDL/XSD/specyfikację i warunki przyłączenia; GOV-07 |
| RDO | MC/COI; dowody osobiste | D1 teletransmisja; kontrakt niepozyskany [RDO] | Indywidualna zgoda, zakres i sieć do potwierdzenia | K0/T0/P0 | Dokumentacja COI, bez fikcyjnych endpointów; GOV-07 |
| RDP | MC/COI; dokumenty paszportowe | D1 oficjalna procedura [RDP] | Zakres ograniczonej teletransmisji i dostęp do potwierdzenia | K0/T0/P0 | Wniosek/specyfikacja, GOV-07 |
| RSC | MC/COI; rejestr stanu cywilnego | D1 procedura, brak kontraktu; art. 45 ust. 3 wymaga kwalifikacji | Nie zakładać ogólnego prawa notariusza do API | K0/T0/P0 | Ustalić podstawę prawną i rzeczywisty zakres, inaczej używać odpisów; GOV-05/07 |
| RDK | MC/COI; dane kontaktowe | D1 procedura; brak kontraktu [RDK] | Podmiot i zakres uprawnienia niepotwierdzone | K0/T0/P0 | Pytanie kwalifikacyjne, bez implementacji; GOV-07 |
| ODPIS-USC | USC; odpis urodzenia, małżeństwa, zgonu | D1 istniejąca usługa gov.pl [USC] | Wniosek uprawnionej osoby / interes prawny; nie ogólny odczyt | K0/T0/P0 | Przygotowanie wniosku tylko jeśli potrzebne; import oryginału i weryfikacja pieczęci; GOV-05 |
| STAN-CYW | USC; zaświadczenie o stanie cywilnym | D1 usługa gov.pl [USC] | Wnioskodawca i podstawa zgodne z warunkami usługi | K0/T0/P0 | Zweryfikować zakres, użyć istniejącej usługi; GOV-05 |
| MOBYW | MC/COI; przekazanie danych przez klienta | D1 Panel Współpracy, BackSystem/QR do weryfikacji [MOB] | Ścieżka integratora i zgoda klienta; szczegóły testu niepozyskane | K0/T0/P0 | Uzyskać aktualną dokumentację, zakresy i certyfikaty; GOV-06 |
| CREWAN | KRN; repozytorium elektronicznych wypisów | D1 istniejący system; publicznego kontraktu nie znaleziono [KRN] | Uprawnienie notariusza, podpis; warunki integracji nieznane | K0/T0/P0 | Uzgodnić oficjalny import/wysyłkę i potwierdzenia; GOV-09 |
| SPADKOWY | KRN; rejestracja i wyszukiwanie czynności spadkowych | D1 portal, kontrakt integracyjny nieznany [KRN] | Publiczne wyszukiwanie w określonym zakresie; rejestracja dla uprawnionych | K0/T0/P0 | Ustalić rozdzielnie odczyt i zapis; GOV-09 |
| NORT | KRN; rejestr testamentów | D1 portal, kontrakt nieznany [KRN] | Dostęp zawodowy, warunki KRN | K0/T0/P0 | Ustalić warunki i autoryzację; GOV-09 |
| RU | KRN; Rejestr Użytkowników (zakres/status zawodowy do potwierdzenia) | D0 brak zweryfikowanego kontraktu | Nie przyjmować, że dostępny zewnętrznie | K0/T0/P0 | Ustalić zakres i źródło weryfikacji notariusza; GOV-03/09 |
| ZARZAD-SUKC | Właściwy rejestr / KRN; czynności dotyczące zarządu sukcesyjnego | D0 ustalić właściwy system i interfejs | Niepotwierdzone | K0/T0/P0 | Najpierw potwierdzić, czy potrzebna odrębna integracja; GOV-09 |

## Macierz B — nieruchomości i przedsiębiorcy

| ID / system | Instytucja, zakres | Kontrakt / protokół (znane) | Dostęp / INT | Kod i status | Następny konkretny krok / zadanie |
|---|---|---|---|---|---|
| ULDK | GUGiK; identyfikacja działki, lokalizacja | D2 HTTP GET, GetParcelById, GetParcelByIdOrNr, `result`; [ULDK] | Publiczne; warunki limitów/IP do sprawdzenia | K2/T1/P0 `rejestry_panstwowe.py`, router, UI, czat; geometria jeszcze niepobierana | Test oficjalnego przykładu, następnie geometria tylko jeśli potrzebna; GOV-04 |
| EGIB | GUGiK/powiat; ewidencja gruntów | D2 publiczne WFS/WMS/KIEG, nie wypis; [GEO] | Dane jawne bez indywidualnego klucza wg warunków; właściciele niepubliczni | K0/T0/P0 | Sprawdzić capabilities i zakres; nie pobierać danych chronionych; GOV-04 |
| RCN | GUGiK/powiat; ceny transakcyjne | D1 publiczne usługi i Geoportal, zakres/WFS do sprawdzenia [GEO] | Dostępność zależna od publikacji; nie gwarantować kompletności | K0/T0/P0 | Potwierdzić aktualne warstwy/format i użyteczność; GOV-04 |
| MPZP | Gminy/GUGiK; planowanie | D1 WMS/KI i publikacje gmin, wersja do sprawdzenia [GEO] | Publiczne, nie gwarantować aktualności/kompletności | K0/T0/P0 | Wskazać źródło planu i datę, nie zastępować zaświadczenia; GOV-04 |
| ZSIN | GGK; zintegrowana informacja o nieruchomościach | D1 formularze i kwalifikacja uprawnienia [GEO] | Zakres dla notariusza niepotwierdzony | K0/T0/P0 | Pytanie o uprawnienie i kontrakt; GOV-04 |
| WYPIS-EGIB | Powiat/prezydent miasta; urzędowy wypis i wyrys | D1 oficjalny wniosek, nie centralne publiczne API [GEO] | Właściwy urząd, podstawa, opłata | K0/T0/P0 | Wskazać właściwy urząd i istniejący formularz, nie budować uniwersalnego generatora; GOV-04 |
| EKW-TRESC | MS; aktualna treść KW | D1 portal po pełnym KW; publicznego API nie znaleziono. Starszy test 02.11: serwer 403 | Publiczny portal; wcześniejsze komercyjne alternatywy istnieją, nie rozbudowywać | K2/T0/P0 `ekw.py`, Finance You/Apify jako istniejąca ścieżka, nie oficjalne API | Uzgodnić oficjalny dostęp; nie usuwać działającego kodu ani obchodzić ochrony; GOV-08 |
| EKW-SZUKAJ | MS; wielokrotne wyszukiwanie KW | D1 procedura indywidualna; brak kontraktu [KW] | Decyzja i uprawnienie notariusza; art. 36(4) ust. 8 do weryfikacji | K0/T0/P0 | Uzyskać dokumentację i warunki; GOV-08 |
| EKW-WNIOSEK | MS; wniosek wieczystoksięgowy | D1 portal zalogowany; import XML niepotwierdzony | Konto, podpis notariusza | K1/T0/P0 `wnioski_kw.py`, YAML szkic, Rep. C | NA-1: sprawdzić import/selektory w trybie podglądu; GOV-08 |
| KRS | MS; odpis aktualny | D2 REST `api-krs.ms.gov.pl/api/krs/OdpisAktualny/{KRS}`, P/S, JSON [KRS] | Publiczne | K2/T1/P0 `rejestry_panstwowe.py` + UI/czat | Test publicznego przykładu; nie zakładać kompletności danych reprezentacji |
| VAT | MF; wykaz podatników | D2 REST `wykazpodatnikowvat.mf.gov.pl/api/search/nip/{NIP}`, data, requestId [VAT] | Publiczne, limity do weryfikacji | K2/T1/P0 `rejestry_panstwowe.py` + UI/czat | Test na instytucji, zapisać identyfikator odpowiedzi |
| CEIDG | MRiT; działalność gospodarcza | D2 API HD v3, dokumentacja [CEIDG] | Token i aktualne limity do ustalenia | K0/T0/P0 w nowym module; sprawdzić repo przed pisaniem | Potwierdzić brak istniejącego klienta, dostęp i kontrakt; GOV-11 |
| REGON | GUS; dane podmiotu | D2 BIR1, dokumentacja [REGON] | Klucz/API i wersję środowiska testowego potwierdzić | K0/T0/P0 w nowym module; sprawdzić istniejące integracje | GOV-11; nie dublować KRS/CEIDG |
| CRBR | MF; beneficjenci rzeczywiści | D2 istniejący SOAP 1.2, ApiPrzegladoweCRBR/2022/12/01, operacja PobierzInformacjeOSpolkachIBeneficjentach [CRBR] | Publiczne wg ustalenia 07.11 | K2/T0/P0 `crbr.py` | Zweryfikować obecny endpoint i wynik, nie budować drugiego klienta |
| KRZ | MS; zadłużenie i upadłość | D1 publiczny portal, brak znalezionego oficjalnego API [KRZ]; wcześniejszy 403 spoza przeglądarki | Portal jawny; regulamin/automatyzacja do sprawdzenia | K2/T0/P0 `krz.py`, dowód z przeglądarki | Ustalić oficjalny kanał; ręczna ocena wyniku, nie obchodzić zabezpieczeń |
| RZASTAW | MS; rejestr zastawów | D0 publiczny kontrakt nieustalony | Procedura do zbadania | K0/T0/P0 | Tylko jeśli konkretny proces kancelarii wymaga; GOV-11 |

## Macierz C — komunikacja, raportowanie, AML i infrastruktura

| ID / system | Instytucja, zakres | Kontrakt / protokół (znane) | Dostęp / INT | Kod i status | Następny konkretny krok / zadanie |
|---|---|---|---|---|---|
| ED-UA | MC/COI/operator; wiadomości, załączniki, dowody | D2 UA API 3.0.8; publiczny ZIP uaapi_3.0.8.2 i projekt techniczny 5.27; [ED] | INT: test.edoreczenia@cyfra.gov.pl, dokumentacja INT po dostępie; certyfikaty X.509/JWT wg procedury; delegacja skrzynki | K0/T0/P0, brak potwierdzonego klienta | Pobrać ZIP, potwierdzić różnice INT/PROD; odbiór przed wysyłką, idempotencja; GOV-02 |
| ED-SE/BAE | MC/COI; wyszukanie adresu | D2 SE API 4.0.5, także 3.0.11/2.0.9 wg notatki 25.11 [ED] | INT i zakres BAE do potwierdzenia | K0/T0/P0 | Uzyskać kontrakt SE i warunki wyszukiwania; GOV-02 |
| GIIF/KAS | MF; SI*GIIF/e-Notariusz, raporty | D3 XSD 14250 i 14252 w repo; generator 14250. D2 publiczny opis REST /api/rest2018, CAdES + CMS, UPO; pełny kontrakt i słowniki do sprawdzenia [GIIF] | Konto test.giif.mofnet.gov.pl, certyfikaty, szczegóły mTLS do potwierdzenia | K1/T1/P0 `giif.py`, `giif_xml.py`, `giif_xsd/`; przygotowanie XML, nie potwierdzona wysyłka | NA-2/3/6, GOV-10; słowniki, test statusu R/UPO, potwierdzić aktualny schemat i termin; nie dublować generatora |
| AML-SANKCJE | UE/ONZ/MSWiA; listy finansowe | D2 XML UE FSF, ONZ XML, MSWiA HTML; OFAC opcjonalny [AML] | Publiczne źródła, warunki ponownego użycia do sprawdzenia | K2/T0/P0 `aml_listy.py`, `aml_dopasowanie.py`, `aml.py` | Kontrola świeżości, kompletności i warunków; istniejący kod |
| AML-PEP | Sejm/KPRM i inne; stanowiska PEP | D2 API Sejmu, HTML KPRM; Wikidata pomocnicza, nie urzędowa [AML] | Publiczne, luki pokrywa oświadczenie klienta i ocena notariusza | K2/T0/P0 istniejący AML | Nie deklarować pełnego screeningu PEP; sprawdzić aktualność źródeł |
| AUTORYZACJA | NotarAI / organy; indywidualny dostęp | D1 projekt Cognito + podpis kwalifikowany, status zawodowy niezależnie | Zgoda konkretnego organu, osobny zakres, rotacja/odwołanie | K1/T0/P0 istniejąca autoryzacja; brak dowodu pełnej aktywacji rejestrów | GOV-03; użyć istniejących mechanizmów, nie tworzyć QTSP |
| AWS/3ZERO | NotarAI/AWS; dowody dla organów | D1 zadania P0 D01–D06, audyt Bedrock, manifest; nie certyfikacja | Claude: rzeczywiste odczyty AWS; EIP/egress, regiony, retencja, izolacja i atestacja niepotwierdzone tutaj | K1/T0/P0 skrypty pomocnicze, brak potwierdzenia konfiguracji produkcyjnej | [P0] — Claude realizuje; nie dublować i nie zmieniać AWS w tym PR |

## Źródła techniczne — indeks, nie kopie dokumentacji

- [RZNP] [MC: udostępnianie danych](https://www.gov.pl/web/cyfryzacja/udostepnianie-danych-z-rejestru-zastrzezen-numerow-pesel), [ZIP wskazany w notatce](https://www.gov.pl/attachment/e9b8d838-ebdc-4fd7-a254-83f101d991b9), [starsza dokumentacja 16.09](https://www.gov.pl/attachment/5781564b-68dd-4982-9898-5741694a9c67). Różne wersje 1.0.68 / 2.0.8: nie uznawać za ten sam kontrakt. ZIP niepobrany w tej sesji.
- [KRN] [BIP](https://bip.krn.org.pl/rejestry-notarialne), [PESEL](https://krn.org.pl/aktualnosci/zastrzezenie-numeru-pesel-co-warto-wiedziec-przed-wizyta-u-notariusza), [Rejestry Notarialne](https://www.rejestry-notarialne.pl/).
- [PESEL] https://www.gov.pl/web/gov/uzyskaj-dostep-do-rejestru-pesel
- [RDO] https://www.gov.pl/web/gov/uzyskaj-dostep-do-rejestru-dowodow-osobistych
- [RDP] https://www.gov.pl/web/cyfryzacja/udostepnienie-danych-z-rejestru-dokumentow-paszportowych
- [RDK] https://www.gov.pl/web/cyfryzacja/udostepnianie-danych-z-rejestru-danych-kontaktowych
- [USC] [odpis](https://www.gov.pl/web/gov/uzyskaj-odpis-aktu-stanu-cywilnego-urodzenia-malzenstwa-zgonu), [zaświadczenie](https://www.gov.pl/web/gov/uzyskaj-zaswiadczenie-o-stanie-cywilnym).
- [MOB] https://wspolpraca.mobywatel.gov.pl/
- [ULDK] https://uldk.gugik.gov.pl/opis.html
- [GEO] [Geoportal](https://mapy.geoportal.gov.pl/), [formularze GGK](https://www.gov.pl/web/gugik/formularze), [wypis/wyrys](https://www.gov.pl/web/gov/uzyskaj-wypis-i-wyrys-z-ewidencji-gruntow-i-budynkow).
- [KW] [EKW](https://ekw.ms.gov.pl/), [ustawa](https://eli.gov.pl/api/acts/DU/2024/1401/text.html); zob. NA-1.
- [KRS] https://prs.ms.gov.pl/krs/ ; https://api-krs.ms.gov.pl/
- [VAT] https://wykazpodatnikowvat.mf.gov.pl/api
- [CEIDG] [dokumentacja HD v3](https://pliki.biznes.gov.pl/akademia/Hurtownia_danych/HD%20CEIDG%20-%20API%20v3%20HD%20-%20Dokumentacja%20dla%20integrator%C3%B3w%20v1.0.pdf).
- [REGON] https://api.stat.gov.pl/Home/RegonApi
- [CRBR] https://crbr.podatki.gov.pl/ ; szczegóły SOAP: [rejestry.md](rejestry.md).
- [KRZ] https://krz.ms.gov.pl/
- [ED] [MC interfejsy API](https://www.gov.pl/web/e-doreczenia/interfejsy-api) (wg notatki 28.10.2026), [procedura INT](https://www.gov.pl/web/e-doreczenia/integracja-uslugi-e-doreczen-z-systemami-klasy-ezd), [INT](https://int.edoreczenia.gov.pl/dokumentacja), [UA ZIP](https://edoreczenia.poczta-polska.pl/wp-content/uploads/2026/05/uaapi_3.0.8.2.zip), [projekt techniczny](https://edoreczenia.poczta-polska.pl/wp-content/uploads/2025/09/COI-Projekt-Techniczny-UA-API_5.27-1.pdf). ZIP niepobrany; wersja źródłowa do potwierdzenia.
- [GIIF] [REST](https://giif.mofnet.gov.pl/api/), [INT](https://test.giif.mofnet.gov.pl), [e-Notariusz](https://podatki.gov.pl/enotariusz); [szczegóły](ksiegi-i-giif.md). Stary opis NA-3 mówi o dokumentacji za logowaniem; nowszy wskazuje publiczny opis. Nie utożsamiać opisu z pełnym kontraktem i dostępem do słowników.
- [AML] [dotychczasowa dokumentacja](rejestry.md#listy-sankcyjne-i-pep-ustawa-aml).
- [P0] [zadania Claude](CLAUDE-P0-pakiet-dowodowy-do-pism.md), [audyt Bedrock](audyt-bedrock-dowody.md).

## Dokumenty wykonawcze (nie konkurencyjne macierze)

[Zadania GOV](integracje-panstwowe-claude.md) — zakres i kryteria akceptacji.
[Zadania NA](czeka-na-dostep.md) — testy po przyznaniu dostępu.
[Ustalenia historyczne](rejestry.md) — szczegółowe badania z września/listopada.
[GIIF i KW](ksiegi-i-giif.md) — istniejąca implementacja i schematy.
[Projekty pism](pakiet-pism-rejestry-panstwowe.md) — osobny tor, nie oznacza doręczenia.
Nie duplikować zadań GOV/NA. Zmianę statusu integracji zapisywać tutaj; szczegóły implementacji w odpowiednim dokumencie.

## Dziennik decyzji i zmian

| Data | Zakres | Ustalenie / dowód |
|---|---|---|
| 16.09.2026 | RZNP, KRZ | Historyczne ustalenia w rejestry.md, nie odkrycie z 25.11. |
| 07.11.2026 | EKW, CRBR, AML | Istniejące moduły i źródła; nie tworzyć ponownie. |
| 25.11.2026 | ULDK, KRS, VAT | PR #137, 3f8e8c1: 6/6 kontroli CI zakończone sukcesem w poprzedniej weryfikacji. Nie jest to test live. 22aa29b wspólna walidacja czatu i adapterów, nowsze CI sprawdzić osobno. |
| 25.11.2026 | RZNP, ED, GIIF, pozostałe | 857b211: uzupełniony indeks źródeł w zadaniach GOV; ZIP-y niepobrane, nie deklarować nowych klientów. |
| 25.11.2026 | Zakres | Użytkownik: bez pilotażu na tym etapie, bez zbędnych generatorów i dublowania kodu. Claude wykonuje zadania P0. Macierz jest punktem wejścia dla dalszej pracy. |

**Kryterium realnego postępu:** nowy pozyskany kontrakt / przyznany dostęp / działający adapter / test oficjalnego środowiska / zweryfikowana produkcja. Ponowne znalezienie linku już w tabeli to nie postęp. Jeśli nie ma żadnego nowego faktu, napisać wprost „brak zmiany”.
