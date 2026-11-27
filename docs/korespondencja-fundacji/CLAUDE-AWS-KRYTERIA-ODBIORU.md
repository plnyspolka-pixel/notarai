# P0 — polecenie dla Claude'a: dowody AWS do korespondencji NotarAI

Data: 25.11.2026. Właściciel infrastruktury: Claude; odbiorca dokumentacji: osoba przygotowująca korespondencję w PR #139. Powiązanie z zadaniami D01–D06/GOV w PR #137. **To jest kontrakt odbioru, nie deklaracja, że zabezpieczenia działają.** Nie trzeba czekać na pilotaż kancelarii. Dane do RZNP/INT oddaj w pierwszej kolejności, niezależnie od audytu 3×Zero. Nie wykonuj wysyłek ani operacji w rejestrach urzędowych. Zakres zmian infrastruktury i kosztów uzgodnij z właścicielem; w ramach tego dokumentu dozwolony jest audyt odczytowy oraz bezpieczne testy syntetyczne. Nie zamieszczaj rzeczywistych IP, identyfikatorów infrastruktury, danych osobowych, tajemnic, pełnych polityk IAM i materiału kryptograficznego w publicznym repo, PR, CI ani komentarzach.

## A. Priorytet P0: stałe publiczne IPv4 — dane do formularzy

### A1. Inwentaryzacja rzeczywistego wdrożenia
Ustal, z jakiego komponentu faktycznie wychodzi połączenie HTTP/TLS do danego rejestru (nie z frontendu). Dla RZNP, e-Doręczeń INT, ULDK oraz innych przyszłych adapterów osobno opisz: środowisko TEST/PROD, release i SHA commita/obrazu, usługę wykonawczą, region, wszystkie AZ, VPC/subnety, tablice routingu, NAT/EIP lub broker/proxy, Internet Gateway, ewentualny IPv6, trasę awaryjną. Uwzględnij workery, zadania kolejki, VM, kontenery, Lambda, fallbacki oraz usługi poza AWS, jeśli wykonują połączenia. Nie zakładaj technologii na podstawie IaC.

Jeżeli stałego wyjścia jeszcze nie ma, oznacz BLOKER. Zaproponuj najprostszy wariant (np. prywatna podsieć + NAT/EIP albo dedykowany broker egress, zależnie od aktualnej architektury). Pokaż koszt miesięczny, HA i ryzyko pojedynczego punktu awarii. Wdrożenie według osobnego polecenia właściciela; po nim wykonaj pomiary. Nie wymuszaj jednej wspólnej adresacji, jeśli urzędowy formularz dopuszcza wiele adresów i HA wymaga więcej.

### A2. Dowód IP, a nie sama konfiguracja
- Odczytaj konfigurację EIP, NAT, routing oraz powiązania podsieci (np. DescribeAddresses, DescribeNatGateways, DescribeRouteTables, DescribeSubnets; odpowiedniki dla faktycznej architektury). Ustal trwałość alokacji adresu po restarcie/wymianie komponentu.
- Z każdej rzeczywistej ścieżki egress wykonaj minimalne zapytanie IPv4 do zaufanego endpointu diagnostycznego (np. https://checkip.amazonaws.com), tym samym klientem/siecią/proxy co adapter; nie wysyłaj sekretów. Jeśli routing jest zależny od domeny, dodatkowo wykaż, że dla domeny rejestru obowiązuje dokładnie ta sama ścieżka, bez nieautoryzowanego wywoływania API rejestru.
- Co najmniej dwa pomiary na ścieżkę, przed i po bezpiecznej wymianie/redeploy w środowisku testowym. Dla produkcji nie wymuszaj awarii ani restartu bez osobnej zgody; potwierdź przy normalnej wymianie lub oznacz brak dowodu. Sprawdź wszystkie AZ, repliki, alternatywny egress oraz retry/failover. Brak możliwości pomiaru = NIEZWERYFIKOWANE, nie PASS.
- Sprawdź, czy przy awarii broker/NAT nie przełącza na losowy publiczny adres. Jeżeli urząd wymaga listy dozwolonych IP, wyjście alternatywne poza nią ma być blokowane. Potwierdź IPv4 (nie DNS, ALB, CloudFront ani adres ingress); nie wpisuj adresów prywatnych.
- W prywatnym raporcie dołącz minimalne wyniki CLI/API oraz log pomiarów z UTC, identyfikatorem komponentu i ścieżką. Wskaż, które adresy są przeznaczone do wpisania do konkretnego formularza, a które nie.

### A3. Plik 01_EGRESS_IP.csv — format obowiązkowy
Kolumny:
`service;environment;runtime;release_sha;aws_region;az;egress_type;ipv4;allocation_persistent;route_evidence_id;probe_before_utc;probe_after_utc;probe_evidence_id;failover_ipv4s;fail_closed;form_field;status;blocker`
Jeden wiersz na każdą możliwą ścieżkę i IP. Dodatkowo podsumowanie **RZNP TEST: dokładna lista IPv4 do skopiowania; RZNP PROD: osobno; INT: osobno, jeśli wymagane; ULDK: osobno**. Jeżeli środowiska współdzielą adres, jawnie to oznacz, wyjaśnij izolację i sprawdź dopuszczalność. Bez przykładowych IP, bez pustych pól oznaczonych jako pozytywny wynik.

AC-A: każdy wymagany adres potwierdzony konfiguracją i rzeczywistym pomiarem, wszystkie ścieżki zinwentaryzowane, trwałość i zachowanie awaryjne udokumentowane. Wynik może być częściowy per środowisko; nie blokuj przekazania sprawnego TEST przez niegotowy PROD.

## B. Formularze i opis integratora (P0, nie czeka na pełny audyt)

1. Pobierz z oficjalnej strony aktualny wniosek RZNP oraz instrukcję. Zapisz URL, datę pobrania, wersję i SHA-256. Rozróżnij TEST/PROD oraz system pośredniczący. Wypełnij tylko pola techniczne potwierdzone dowodami. Przygotuj TEST jako pierwsze; nie twierdź, że Fundacja ma indywidualne uprawnienia notariusza. PROD tylko na potwierdzonej podstawie, z właściwym uprawnionym podmiotem.
2. Pobierz bieżący załącznik 2a INT dla integratora systemu klasy EZD i instrukcję 1a. Nie myl z formularzem 2b podmiotu, dostawcy kwalifikowanego lub ZSU. Sprawdź wymagane pola i format certyfikatów, IP tylko jeśli rzeczywiście wymagane, nazwę i wersję systemu, kontakt techniczny i tryb autoryzacji. Nie twórz fikcyjnych certyfikatów ani kontaktów.
3. Dla ULDK potwierdź aktualną procedurę wpisu adresu na listę zaufanych. ZSIN/SRP/PESEL-NET/mObywatel: ustal dokładne wymagania techniczne i podmiot uprawniony; nie składaj wniosków produkcyjnych ani nie zamawiaj przyłączy. Brak podstawy prawnej lub zgody jest oddzielnym blokerem, nie problemem AWS.
4. Dostarcz **02_MAPA_POL_FORMULARZY.csv**: `service;environment;official_form_version;page_or_section;exact_field_label;verified_value;source_evidence_id;owner;status;missing_reason`. Każde pole formularza: dane AWS, dane Fundacji/reprezentanta, dane notariusza lub N/D z uzasadnieniem. Osobno 02_SPECYFIKACJA_INTEGRATORA.md (edytowalna, plus PDF): nazwa NotarAI, wersja, operator, schemat pośredniczący, granice zaufania, izolacja kancelarii, autoryzacja indywidualna, szyfrowanie, logi, audyt i awaria, mechanizm odwołania dostępu. Rola prawna i kontakt do potwierdzenia przez Fundację, nie przez AWS.

AC-B: aktualne oryginalne formularze i kompletna mapa pól technicznych, z potwierdzonymi wartościami i źródłem; pola prawne/kontaktowe do zatwierdzenia oznaczone, bez podpisywania za kogokolwiek. Przekazać edytowalne formularze i PDF do wglądu. Oficjalne druki, nie nasz zamiennik.

## C. Faktyczna architektura i przepływ danych (P1)

Dostarcz 03_PRZEPLYW_DANYCH.md + diagram edytowalny (Mermaid/Draw.io) i PDF. Pokaż faktyczną drogę dokumentu/PESEL/treści promptu i odpowiedzi: przeglądarka/telefon/wtyczka/VM → API → procesor/worker/enklawa → bazy, obiekty, OCR/ASR/TTS, modele, integracje, backupy, logi i monitoring. Uwzględnij dostawców zewnętrznych, błędy, kolejki i DLQ, cache, analitykę, wsparcie oraz eksporty. Rozdziel diagram produkcyjny od planowanego.

03_INWENTARZ.csv: `component;environment;provider;service;region;data_category;plaintext_boundary;encryption_in_transit;encryption_at_rest;key_controller;retention_days;backup_region;delete_procedure;operator_access;evidence_id;status`. Retencja N/D tylko z uzasadnieniem; nie myl retencji danych klientów z przechowywaniem treści przez model. Udowodnij wszystkie faktyczne regiony, w tym replikacje, DR, inference profiles i egress do usług poza AWS. Wszelkie wyjątki od deklarowanej lokalizacji EU oraz dostęp poza EU pokaż jawnie, nie jako spełniony warunek.

AC-C: pełna mapa usług i granic danych porównana z konfiguracją wdrożenia oraz kodem; brak nieudokumentowanych procesorów, ścieżek i kopii albo jawna lista niezgodności.

## D. Bedrock / AI — brak retencji, treningu i nieuprawnionego dostępu (P1)

Z rzeczywistych konfiguracji i kodu ustal wszystkie modele, API/endpointy, wersje, dostawców, profile inference, projekty, regiony i fallbacki, także poza Bedrock (OCR, głos, embeddings, agent tools). Rozróżnij Bedrock od bezpośredniego API Anthropic. Nie opieraj się na marketingowych opisach produktu.

- Dla Bedrock odczytaj GetAccountDataRetention, GetProject (jeżeli używany), GetFoundationModel/GetInferenceProfile, GetModelInvocationLoggingConfiguration w zakresie faktycznie użytych regionów/profili. Skorzystaj z istniejącego skryptu w #137, jeżeli zgodny z aktualnym SDK. Ustal efektywną retencję (projekt → konto → domyślna modelu) i obsługę trybu none. Gdy model wymaga retencji, udokumentuj odrzucenie lub niezgodność zamiast przepięcia na inny niezatwierdzony model. Weryfikuj również Responses API store=false/tryb none, jeżeli jest używane, cache, narzędzia stanowe, tracing i treść błędów.
- Zapisz aktualne warunki dostawcy dla konkretnej usługi/modelu: trening, retencja, wyjątki abuse monitoring, dostęp człowieka, procesorzy i lokalizacja. Źródło, data, zakres umowny. Brak retencji po stronie dostawcy nie dowodzi braku logów po stronie aplikacji.
- Dla wszystkich fallbacków sprawdź, że nie obchodzą polityki EU, retencji i dopuszczonych modeli. Testy syntetyczne z unikalnym nieszkodliwym znacznikiem: normalny request, błąd, retry, fallback; sprawdź, czy znacznik pojawił się w logach/traces/cache/S3/DB wbrew polityce. Brak możliwości obserwacji = ograniczenie dowodu. Test nie dowodzi samodzielnie braku retencji u dostawcy. Nie używaj dokumentów kancelarii.
- 04_MODELE_RETENCJA.csv: `model;provider;api;project;source_region;destination_regions;effective_retention;logging;store;cache;training_terms;human_access_terms;fallback;evidence_ids;status`.

AC-D: kompletna inwentaryzacja z dowodami efektywnej konfiguracji i warunków dla każdego modelu, wymuszenie bezpiecznej odmowy przy niezgodnym modelu, brak niezatwierdzonych fallbacków. Każde odstępstwo opisane. Nie nazywać ZDR dowodem absolutnego braku dostępu człowieka.

## E. 3×Zero — dowody realnych właściwości, nie slogan (P1)

1. Zero Trust: role tenant/użytkownik/operator, rzeczywiste IAM i SCP, zasady dostępu do produkcji, sesje, MFA, ewentualne logowanie podpisem i niezależne potwierdzanie statusu zawodowego. Dowód separacji kancelarii, najmniejszych uprawnień, izolacji demo, uprawnień narzędzi AI. Nie twierdzić, że sam podpis przyznaje prawo do rejestru.
2. Zero Knowledge / poufność operatora: pokaż, gdzie i kiedy plaintext istnieje (w tym dostawca inference), kto kontroluje klucze, skąd są wydawane, kto może zmienić kod, politykę klucza i proces odzyskiwania. Jeżeli architektura opiera się na Nitro Enclaves/NitroTPM, pokaż właściwą technologię, rzeczywisty uruchomiony komponent, wersję obrazu, pomiary PCR stosowne do tej technologii, łańcuch atestacji, weryfikację świeżości i powiązania klucza publicznego z atestacją. Nie utożsamiaj VM, sandboxu lub flagi Nitro z enklawą. Jeżeli KMS uczestniczy, wykaż warunki RecipientAttestation, sposób zwracania klucza do atestowanego środowiska oraz kto może zmienić politykę/grant, rolę i dozwolone pomiary. Sam KMS ani encryption at rest nie dowodzi niezdolności operatora do odszyfrowania. Jeśli zamiast KMS zastosowano inną architekturę kluczy, opisz ją zgodnie z faktem.
3. Zero Operator Access: przeanalizuj cały łańcuch uprawnień, w tym administratora AWS/root, deployment/CI, możliwość podmiany obrazu, kodu web, rozszerzenia, certyfikatów i konfiguracji, logi, backup, break-glass, recovery, SSM/exec, support i dostawców. Pokaż, jakie działania są kryptograficznie niemożliwe, jakie blokuje polityka, a jakie nadal możliwe. Rozróżnij ochronę przed zwykłym operatorem od złośliwego administratora platformy. Nie deklaruj niemożliwości tam, gdzie operator może zmienić kod i odebrać dane.
4. Testy negatywne wyłącznie na syntetycznych danych i odizolowanym środowisku: między tenantami (API, obiekty, DB, zadania/eksport), konto demo/serwis/operator, nieuprawnione odszyfrowanie, niezatwierdzony pomiar, replay/wygaśnięcie atestacji, błędne uprawnienia, rotacja/odwołanie, backup/recovery, awaria klucza/atestacji (fail closed), niezgodny fallback AI i ścieżka logowania. Jeśli test uprzywilejowanego operatora nie może być bezpiecznie wykonany, zaznacz NIEZWERYFIKOWANE i granice wniosku; nie próbuj podnosić uprawnień ani odczytywać rzeczywistych danych.
5. 05_SECURITY_MANIFEST.json oraz 05_TESTY_3ZERO.csv: wersja/release, hash obrazu, data UTC, środowisko, claim, test ID, expected, actual, evidence_id, wynik, ograniczenie. Raport nie jest certyfikatem, audytem niezależnego podmiotu ani gwarancją zachowania tajemnicy notarialnej.

AC-E: dla każdej tezy osobny dowód i test adekwatny do zagrożenia; rozróżnienie stanu wdrożonego, planowanego i niezweryfikowanego. FAIL przy ujawnieniu treści nieuprawnionemu operatorowi/tenantowi albo możliwości obejścia zadeklarowanej bariery bez ujawnionego ograniczenia. Nie podpisywać pozytywnej tezy, której nie da się obronić.

## F. Pakiet do KRN/MS i dokumentacja RODO (P1)

06_ZALACZNIK_KRN_MS.md + PDF: techniczna argumentacja do TECH-12/13, oparta na dowodach A–E, z tabelą `teza;stan;dowod;ograniczenie`. Uwzględnij rolę notariusza, granice dostępu, przetwarzanie pomocnicze, przepływ danych, szyfrowanie, kontrolę kluczy, retencję, działania awaryjne, wersję i datę. Wyraźnie oddziel zakres przyszły od aktualnego. Dołącz materiał do DPIA, art. 25/28/32/35 RODO, listę podprocesorów, dostępne warunki DPA/AWS i procedurę incydentów. Nie udzielaj opinii prawnej, nie podpisuj dokumentów za Fundację, nie twierdź, że KRN zatwierdziła system. Jeżeli zakres dowodowy jest częściowy, przygotuj uczciwą wersję warunkową. PDF do urzędu nie ma zawierać pełnych IP infrastruktury, sekretów, konfiguracji eksploatacyjnych ani danych klientów, poza polami rzeczywiście wymaganymi przez konkretny formularz.

## G. Format przekazania i bramka odbioru

Oddaj jeden prywatny pakiet ZIP (lub najpierw ZIP A+B, potem uzupełnienie C–F), z indeksem SHA-256 plików:
- 00_PODSUMOWANIE_I_BLOKERY.md — decyzja per procedura i per teza; dokładna lista rzeczy do uzupełnienia przez Fundację, Claude'a, urząd lub notariusza; nie blokować DIP.
- 01_EGRESS_IP.csv + dowody sieciowe.
- 02_MAPA_POL_FORMULARZY.csv, 02_SPECYFIKACJA_INTEGRATORA.md/PDF, oryginalne i roboczo uzupełnione formularze.
- 03_PRZEPLYW_DANYCH.md/PDF, diagram, 03_INWENTARZ.csv.
- 04_MODELE_RETENCJA.csv + dowody i źródła umowne.
- 05_SECURITY_MANIFEST.json, 05_TESTY_3ZERO.csv, raport testów.
- 06_ZALACZNIK_KRN_MS.md/PDF, dokumentacja RODO i podprocesorów.
- 07_INDEKS_DOWODOW.csv: `evidence_id;claim_or_field;source;utc;environment;release_sha;method;artifact_path;sha256;status;limitation`.
- 08_STATUS_PROCEDUR.csv: `procedure;requirement;status;evidence_ids;missing;owner;next_step`.

Statusy: PASS (dowód spełnia AC), FAIL (niezgodność), BLOKER (brak warunku uniemożliwiający konkretną procedurę), NIEZWERYFIKOWANE (brak dowodu), N/D (uzasadnione). Nie utożsamiać zielonych testów mock, kodu IaC, screenshotu konsoli ani pojedynczego adresu IP z dowodem kompletności. W publicznym PR tylko zredagowany status, identyfikator wersji pakietu i niesensytywne wyniki; pełny pakiet przez prywatny kanał uzgodniony z właścicielem. Jeśli takiego kanału nie ma, zgłoś BLOKER przekazania zamiast publikacji. Nigdy nie zamieszczaj sekretów nawet w prywatnym ZIP; ogranicz dane i zabezpiecz dostęp. Zweryfikuj SHA-256 i możliwość otwarcia artefaktów po przekazaniu.

**Najpierw oddaj A+B.** W PR #139 odbiorca ma móc bez domysłów skopiować wartości do aktualnych druków, przygotować specyfikację i odblokować formalne zgłoszenia TEST. C–F służą późniejszej udokumentowanej ocenie bezpieczeństwa, nie są warunkiem wysłania DIP ani warunkowych TECH-12/13. Żadnego dokumentu nie oznaczać jako wysłanego; akceptację prawną i podpis pozostawić Fundacji/notariuszowi.

## Źródła referencyjne (sprawdzone 25.11.2026)

- RZNP: https://www.gov.pl/web/cyfryzacja/udostepnianie-danych-z-rejestru-zastrzezen-numerow-pesel
- INT EZD: https://www.gov.pl/web/e-doreczenia/integracja-uslugi-e-doreczen-z-systemami-klasy-ezd
- ULDK: https://uldk.gugik.gov.pl/opis.html
- Bedrock: https://docs.aws.amazon.com/bedrock/latest/userguide/data-retention.html ; https://docs.aws.amazon.com/bedrock/latest/APIReference/API_GetAccountDataRetention.html ; https://docs.aws.amazon.com/bedrock/latest/userguide/model-invocation-logging.html ; https://docs.aws.amazon.com/bedrock/latest/userguide/inference-responses-api.html
- Nitro/KMS: https://docs.aws.amazon.com/kms/latest/developerguide/cryptographic-attestation.html ; https://docs.aws.amazon.com/enclaves/latest/user/connect-enclave-kms.html
