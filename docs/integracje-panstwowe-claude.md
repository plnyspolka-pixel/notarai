# Integracje państwowe NotarAI – zadania wdrożeniowe dla Claude'a

Stan: 25.11.2026. Zakres tego PR: bez zmian AWS, bez wysyłania pism,
bez zakupów komercyjnych, bez dostępu do danych chronionych. Nie wprowadzać
zmian ustawowych. Nie wykonywać rzeczywistych operacji w imieniu notariusza.

## Zasady
- NotarAI = integrator techniczny; każda zgoda produkcyjna i credential należą
  do indywidualnego uprawnionego notariusza, nigdy do ogólnego konta NotarAI.
- Logowanie podpisem kwalifikowanym potwierdza tożsamość, nie przyznaje dostępu
  do rejestrów. Weryfikacja zawodowa i zgoda organu osobno.
- Wspólny gateway tylko jeżeli przewidują go warunki konkretnego rejestru.
- Brak odczytu chronionych rejestrów przez model, brak pełnych PESEL i sekretów
  w logach, brak dostępu operatora, izolacja użytkowników i kancelarii.
- Podpis, wysyłka, opłata wymagają działania osoby uprawnionej. Nie obchodzimy
  logowania, zabezpieczeń, limitów ani wymagań portalowych.
- Publiczne odczyty ULDK/KRS/VAT w tym PR: testy syntetyczne, nie dowód działania live.
  Katalog informacyjny nie oznacza aktywnych integracji ani uprawnień.
- Nie duplikować istniejących KRZ, EKW, CRBR, GIIF ani mechanizmu czatu.
- W środowisku testowym wyłącznie dane przykładowe udostępnione przez instytucję.

## Zadania niezależne od AWS – P0

### GOV-01: RZNP, kontrakt i emulator (Claude)
Źródło: https://www.gov.pl/web/cyfryzacja/udostepnianie-danych-z-rejestru-zastrzezen-numerow-pesel
Pobrać ZIP 17.04.2024, sprawdzić aktualność względem strony, odczytać
rejestr-zastrzezen-proxy-contract.yml, dokumentację 2.0.8 i
rejestr-zastrzezen-proxy-2.0.8-stubs.jar. Zweryfikować pochodzenie, hash,
licencję i bezpieczeństwo JAR przed uruchomieniem w odizolowanym środowisku.
Nie commitować binariów ani materiałów objętych ograniczeniami; zapisać źródła
i sumy. Wygenerować klienta lub zaimplementować minimalny klient zgodny
z kontraktem. Zweryfikować nagłówki, request/response, daty i strefy czasowe,
wszystkie statusy, identyfikator zapytania, timeout i ograniczenia.
Testy kontraktowe na emulatorze: zastrzeżony, niezastrzeżony, błędny PESEL,
awaria, brak autoryzacji; awaria nigdy nie oznacza braku zastrzeżenia.
Przygotować formularz testowy (cc.wnioski@coi.gov.pl), wymagania i specyfikację
systemu. Nie wpisywać fikcyjnego IP. Produkcyjna zgoda/klucz indywidualne.
AC: test emulatora i dokumentacja dowodowa; brak realnego PESEL w testach;
adapter produkcyjny domyślnie wyłączony; żadnego współdzielenia kluczy.

### GOV-02: e-Doręczenia i Baza Adresów Elektronicznych (Claude)
Źródło: https://www.gov.pl/web/e-doreczenia/integracja-uslugi-e-doreczen-z-systemami-klasy-ezd
Pobrać aktualne załączniki, formularz INT, instrukcje X.509/JWT, kontrakty
API i scenariusze. Wniosek INT: test.edoreczenia@cyfra.gov.pl. Ustalić
certyfikaty systemu, zakres delegacji skrzynki, autoryzację właściciela,
zgłoszenie IP, wymagania produkcyjne i dostęp do BAE.
Zaimplementować klienta, listę skrzynek, wyszukanie adresata, przygotowanie
przesyłki, odbiór wiadomości i dowodów. Zapis szkicu oddzielić od wysyłki.
Obsłużyć ponowienia i idempotencję bez ryzyka podwójnej wysyłki.
Nie wykorzystywać zwykłego IMAP jako substytutu e-Doręczeń.
AC: oficjalne testy INT, brak realnych wysyłek, dowody i statusy zgodne
z kontraktem; testy krzyżowe izolacji kancelarii.

### GOV-03: indywidualna aktywacja rejestrów (Claude)
Wykorzystać Cognito jako istniejącą sesję, bez zastępowania logowania hasłem
w sposób niebezpieczny. Zaprojektować dodatkową weryfikację podpisem
kwalifikowanym: jednorazowy challenge, powiązany z sesją, użytkownikiem,
kancelarią, celem i TTL; ochrona przed replay, atomowe zużycie challenge.
Walidacja pełnej ścieżki zaufania UE, kwalifikowanego statusu certyfikatu,
odwołania, integralności i tożsamości; niezależne potwierdzenie statusu
zawodowego w wiarygodnym wykazie KRN. Nie akceptować samego pliku certyfikatu
ani samodzielnie podpisanego certyfikatu jako dowodu uprawnienia.
Nie modyfikować polityki Cognito ani nie tworzyć własnego QTSP.
Przygotować per-user per-service statusy: brak, wniosek przygotowany,
złożony, przyznany (udokumentowana decyzja), skonfigurowany, wygasły,
odwołany. Nie pozwalać użytkownikowi samodzielnie ustawić statusu „przyznany”.
Klucze i certyfikaty tylko w zaakceptowanym sejfie, nigdy w zwykłym JSON.
AC: testy replay, cross-tenant, podszycia, odwołania, demo, serwisu, braku
zgody, rotacji. Brak aktywacji chronionych adapterów bez wszystkich warunków.

### GOV-04: geodezja i wypisy (Claude)
Źródła: https://uldk.gugik.gov.pl/opis.html ; https://www.gov.pl/web/gugik/formularze
Sprawdzić live trzy publiczne adaptery tego PR wyłącznie na oficjalnych
przykładach lub publicznych identyfikatorach instytucji, dostosować parsery.
Dodać oficjalne WFS EGiB i RCN oraz WMS/KI miejscowych planów; walidacja
geometrii i źródła, brak pobierania danych chronionych. Rozróżniać dane
informacyjne od urzędowego wypisu/wyrysu. Ustalać właściwy powiat
z identyfikatora TERYT, korzystać z oficjalnego katalogu kontaktów.
Przygotować wniosek o wypis/wyrys (formularz właściwy dla urzędu, zakres,
podstawa prawna, dane wnioskodawcy, opłata); wysyłka dopiero po akceptacji.
Nie obiecywać automatycznego wystawiania we wszystkich powiatach.
GUGiK: potwierdzić istniejącą podstawę ZSIN i zakres usług; wpis publicznego
adresu IP na listę ULDK dopiero po ustaleniu IP. Nie mylić ZSIN z wydawaniem
urzędowych dokumentów przez starostę.
AC: oficjalny przykład działki + właściwy urząd; szkic formularza;
potwierdzenie użytkownika przed zewnętrznymi operacjami.

### GOV-05: stan cywilny (Claude)
Źródło: https://www.gov.pl/web/gov/uzyskaj-odpis-aktu-stanu-cywilnego-urodzenia-malzenstwa-zgonu
Wdrożyć przygotowanie wniosku o odpis urodzenia, małżeństwa, zgonu i
zaświadczenia, z wyborem uprawnionego wnioskodawcy i podstawy (np. interes
prawny, art. 95da Prawa o notariacie przy poświadczeniu dziedziczenia).
Wskazać istniejącą usługę gov.pl; rozróżnić automatyczne wydanie w przypadkach
kwalifikujących się od zwykłego postępowania. Nie deklarować, że notariusz ma
prawo automatycznie pobrać cudzy akt. Import oryginału elektronicznego,
weryfikacja pieczęci/podpisu oraz zachowanie oryginalnych bajtów.
Bezpośrednie API RSC z art. 45 ust. 3 Prawa o aktach stanu cywilnego
wyłącznie po potwierdzeniu istniejącego uprawnienia; w przeciwnym razie STOP.
AC: testy szkicu i importu na fikcyjnym dokumencie; brak wysyłki bez podpisu.

### GOV-06: mObywatel (Claude)
https://wspolpraca.mobywatel.gov.pl/
Odczytać aktualną dokumentację integratora, warunki dostępu, BackSystem,
certyfikaty, zakresy danych, testowe QR oraz procedurę zgłoszenia.
Dane przekazywane z woli klienta i w zakresie niezbędnym, nie ogólny
dostęp do państwowej bazy. AC: testowy przepływ QR, nonce, expiry, brak
ponownego użycia, walidacja odpowiedzi, brak danych w logach.

## P1 – po zdobyciu materiałów / potwierdzeniu podstaw
- GOV-07: PESEL, RDO, RDP – dokumentacja COI, zakres danych, Wniosek B,
  certyfikaty, sieć dedykowana, podmiot uprawniony i role. RSC i RDK jedynie
  kwalifikacyjne zapytania (bez postulowania zmian prawa). Przygotować
  kontraktowe adaptery dopiero po uzyskaniu prawdziwego WSDL/XSD/OpenAPI.
- GOV-08: Ministerstwo Sprawiedliwości – art. 36(4) ust. 8 ustawy o księgach
  wieczystych i hipotece, indywidualne wyszukiwanie wielokrotne; dokumentacja
  istniejących interfejsów, import wniosku wieczystoksięgowego, bez
  automatycznego podpisywania. Kontynuować NA-1, nie dublować adaptera EKW.
- GOV-09: KRN – ustalić, czy istnieje oficjalna integracja z Rejestrem
  Spadkowym, NORT, CREWAN i weryfikacją statusu. KRN jako właściciel systemu,
  kontakt techniczny RejNET dopiero w razie potrzeby. Nie zakładać istnienia API.
  Kontynuować NA-4; konto notariusza i podgląd tylko za zgodą i w granicach regulaminu.
- GOV-10: GIIF – kontynuować NA-2/NA-3; aktualne słowniki, podpis CAdES,
  szyfrowanie, REST, testowe UPO. Nie dublować istniejącego generatora XML.
- GOV-11: pozostałe publiczne usługi CEIDG, REGON, CRBR, rejestr zastawów,
  rejestry sankcyjne – oficjalne źródła, limity i ewentualne tokeny.
  Nie kupować dostępu komercyjnego w ramach tego zadania.

## Pisma – od integratora, nie jako wnioski o produkcyjne dane

Wspólny fragment:
> Występujemy wyłącznie jako producent i integrator oprogramowania NotarAI.
> Nie wnosimy o udostępnienie danych obywateli na własne potrzeby ani o nadanie
> nam uprawnień notariusza. Każdy notariusz wystąpi o dostęp indywidualnie,
> podpisze wymagane dokumenty i będzie korzystać wyłącznie z przyznanego zakresu.
> Prosimy o dokumentację, środowisko testowe i warunki techniczne wspólnej
> infrastruktury z indywidualną autoryzacją. Interesują nas wyłącznie
> rozwiązania dostępne na podstawie obowiązującego prawa.

| Adresat | Prośba / kanał |
| --- | --- |
| Ministerstwo Cyfryzacji + COI | RZNP, PESEL, RDO, RDP, kwalifikacja RSC/RDK, kontrakty, wspólna infrastruktura; formularz RZNP testowy e-mailem |
| e-Doręczenia | Formularz integratora INT na test.edoreczenia@cyfra.gov.pl |
| mObywatel | Zgłoszenie w Panelu Współpracy |
| Główny Geodeta Kraju | ZSIN i istniejące uprawnienia, publiczne interfejsy, centralna ścieżka wypisów; pismo ogólne |
| Ministerstwo Sprawiedliwości | Dokumentacja wyszukiwania KW i wniosków; pismo ogólne |
| KRN | Warunki integracji istniejących rejestrów; pismo techniczne |
| MSWiA | Warunki przyłączenia PESEL-NET – pozostawione do etapu infrastruktury |

Podstawy do weryfikacji przed wysłaniem: art. 2, 18, 80, 81, 85, 85a, 92 §4,
95da Prawa o notariacie; art. 23j i nast. oraz 46–51 ustawy o ewidencji
ludności; przepisy o ograniczonej teletransmisji ustawy o dowodach osobistych
i ustawy o dokumentach paszportowych; art. 45 Prawa o aktach stanu cywilnego;
art. 19c i 20h ustawy o informatyzacji; art. 24 i 24b Prawa geodezyjnego
i kartograficznego, §36 rozporządzenia EGiB; art. 36(4) ustawy o KW i hipotece.
Nie przedstawiać ogólnych obowiązków zawodowych jako automatycznej podstawy
do każdego API. Sprawdzić aktualne jednostki redakcyjne w ELI przed podpisem.

## Odłożone komercyjne (nie wdrażać teraz)
MGBI, KRData, Transparent Data, iMSiG, Rejestr.io, GetRegData/Apify, iAML;
GEOBID Geoportal 2, WebEWID, GIAP. Nie zmieniać obecnych adapterów komercyjnych
w ramach tego PR.

## AWS – świadomie poza zakresem
Weryfikacja EIP i rzeczywistej trasy wychodzącej z kontenera, oddzielenie
test/produkcja, lista dozwolonych IP, ewentualne MPLS, ochrona sekretów
i ocena 3×Zero. Nie podawać adresu load balancera jako adresu wychodzącego.
Nie tworzyć zasobów ani zmieniać konfiguracji w tym zadaniu.

## Zweryfikowane źródła integracyjne – 25.11.2026

- RZNP: aktualna strona udostępniania danych wskazuje dokumentację i stub 2.0.8; starsza strona ogólna wymienia 1.0.68. Przyjąć nowszą stronę jako punkt odniesienia, sprawdzić zawartość ZIP. Wniosek o klucz TEST można złożyć niezależnie od zgody produkcyjnej: cc.wnioski@coi.gov.pl. Nie jest wymagany pilotaż kancelarii do prac nad kontraktem.
- e-Doręczenia: https://www.gov.pl/web/e-doreczenia/interfejsy-api (aktualizacja 28.10.2026). UA API 3.0.8 dla INT i PROD; SE API 4.0.5 (również 3.0.11 i 2.0.9). Publiczny kontrakt UA: https://edoreczenia.poczta-polska.pl/wp-content/uploads/2026/05/uaapi_3.0.8.2.zip ; projekt techniczny https://edoreczenia.poczta-polska.pl/wp-content/uploads/2025/09/COI-Projekt-Techniczny-UA-API_5.27-1.pdf . INT: https://int.edoreczenia.gov.pl/dokumentacja , zgłoszenie integratora test.edoreczenia@cyfra.gov.pl. Pełne materiały INT po przyznaniu dostępu. Publiczny ZIP wskazany przez MC jako produkcyjny, nie zakładać identyczności wszystkich ustawień INT.
- GIIF: https://giif.mofnet.gov.pl/api/ — publiczne REST, mTLS, schematy, statusy i UPO. MF potwierdza wykorzystanie tego interfejsu w e-Notariuszu: https://podatki.gov.pl/enotariusz . Rozwijać istniejące giif.py, giif_xml.py, giif_xsd i zadania NA, nie tworzyć drugiego klienta obok nich.
- PESEL: https://www.gov.pl/web/gov/uzyskaj-dostep-do-rejestru-pesel ; RDO: https://www.gov.pl/web/gov/uzyskaj-dostep-do-rejestru-dowodow-osobistych . Dokumentacja techniczna przekazywana wskazanemu kontaktowi technicznemu. RDP: https://www.gov.pl/web/cyfryzacja/udostepnienie-danych-z-rejestru-dokumentow-paszportowych . Nie implementować z domniemanych endpointów.
- mObywatel: https://www.gov.pl/web/cyfryzacja/informacje-o-aplikacji-mobywatel oraz https://wspolpraca.mobywatel.gov.pl/ . Ścieżka integratora usługi przekazywania danych, zgoda klienta na przekazanie. Nie zakładać publicznego kontraktu bez uzyskania dokumentacji.
- REGON: https://api.stat.gov.pl/Home/RegonApi ; CEIDG: https://pliki.biznes.gov.pl/akademia/Hurtownia_danych/HD%20CEIDG%20-%20API%20v3%20HD%20-%20Dokumentacja%20dla%20integrator%C3%B3w%20v1.0.pdf . Zweryfikować aktualne wersje i ewentualne istniejące integracje przed implementacją.
- KW: https://eli.gov.pl/api/acts/DU/2024/1401/text.html ; KRN: https://www.krn.org.pl/rejestry-notarialne/crewan . Potwierdzono oficjalne procedury/systemy, nie odnaleziono publicznego kontraktu integracyjnego. To nie dowodzi, że interfejs nie istnieje.

ZIP RZNP oraz UA wskazane w oficjalnych źródłach, lecz zawartości nie pobrano w środowisku autora (brak obsługi ZIP przez przeglądanie, brak DNS w kontenerze). Pobrać w środowisku z dostępem do Internetu; nie odtwarzać kontraktów z domysłów.

Decyzja zakresowa: nie budować generatora pism, dodatkowego systemu korespondencji ani pilotażu w tym etapie. Skrypty audytowe pozostają pomocnicze poza runtime tylko na czas zebrania dowodów P0. Po wykorzystaniu rozważyć ich usunięcie, jeżeli nie będą potrzebne do powtarzalnych audytów. Nie modyfikować zadań AWS w trakcie pracy Claude'a.
