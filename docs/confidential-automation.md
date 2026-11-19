# NotarAI Confidential Automation — implementacja fundamentu (19.11.2026)

## Stan prac / zakres PR

Dodano opt-in moduły bez zmian działającej aplikacji, polityk produkcyjnych
ani migracji danych. Są to działające biblioteki i testy jednostkowe, **nie**
uruchomiona usługa produkcyjna:

1. `static/confidential-crypto.js`: szyfrowanie dokumentu w przeglądarce
   AES-256-GCM, indywidualny losowy DEK, AES AAD wiążący kancelarię, sprawę
   i dokument; RSA-OAEP-SHA256 pakuje DEK publicznym kluczem KMS.
   Wymagany przypięty (niezależnie potwierdzony) fingerprint klucza KMS.
2. `confidential/envelope.py`: ścisła walidacja formatu, kontrola AAD,
   bezpieczne błędy, deszyfrowanie wyłącznie przez wstrzyknięty moduł
   zwalniający klucz w poufnym środowisku.
3. `confidential/attested_kms.py`: jawny adapter AWS KMS Decrypt z
   `Recipient.AttestationDocument`; fail-closed, nie przyjmuje
   `Plaintext`. Zintegrowano także `confidential/nitro_unwrapper.py` i natywny
   `confidential/nsm_recipient.py` (AWS sample MIT-0), który generuje
   dokument NSM z `/dev/nsm` i otwiera CMS w pamięci guest.
   Wymaga wciąż zweryfikowania na rzeczywistym ECS Nitro Sandbox.
4. `confidential/form_engine.py`: zapora egress w Playwright,
   allowlista dokładnych originów, selektory tylko ze zweryfikowanego
   adaptera strony, walidacja wartości; podgląd bez wysyłki domyślnie.
   Wysłanie wymaga funkcji `approve`, która musi sprawdzać podpis
   użytkownika, związek z jobId/formId/digest i jednokrotność zgody.
   Nie ma domyślnej pozytywnej implementacji callbacka.
5. `confidential/demo_browser.py` i `test_confidential.py`:
   demo z fikcyjnym formularzem lokalnym i testy fail-closed.
6. `confidential/router.py`: zaszyfrowane dokumenty do S3 na ścieżce
   kancelarii, autoryzacja imiennego użytkownika SaaS, tylko z jawną
   flagą `PIECZAPP_CONFIDENTIAL_ENABLED=true`; domyślnie wyłączone.
7. `test_confidential_interop.py`: interoperacyjność szyfrowania
   WebCrypto (Node 22) z Python AES-GCM/RSA-OAEP.
8. `infra/notarai-confidential-task.yaml`: osobna definicja taska
   ECS Managed Instances / CONFIDENTIAL_SANDBOX. Wymaga gotowej polityki
   atestacji i KMS PCR17. CloudFormation celowo nie tworzy klastra,
   capacity provider, usługi ani zasobów z danymi klientów.

## Architektura docelowa (granice zaufania)

Kancelaria -> WebCrypto w przeglądarce -> JSON zaszyfrowanego dokumentu
-> magazyn opaque ciphertext -> Nitro Confidential Task (attestation)
-> KMS Decrypt z Recipient -> plaintext DEK tylko w guest
-> odszyfrowanie w pamięci -> dozwolony Playwright form adapter
-> podpis/akceptacja notariusza -> urząd / portal.

Dostawca NotarAI nie może mieć możliwości podstawienia własnego klucza RSA.
Zaufany fingerprint publicznego klucza musi zostać potwierdzony poza
zwykłą odpowiedzią serwera (np. wdrożony/pinowany przez kancelarię).
Klucz KMS wymaga osobnej kontroli zmian key policy; samo posiadanie ARN
klucza nie wystarcza. Operator może zmieniać kod aplikacji — atestacja
musi wiązać dokładny obraz i konfigurację w policy (PCR17).

**Zakres pojęcia Zero Knowledge:** szyfrowanie magazynu i
confidential-computing wobec operatora NotarAI. Treść będzie dostępna
wewnątrz autoryzowanego guest; portale urzędowe oraz Amazon Bedrock,
jeśli wywołamy model, otrzymają niezbędny plaintext. Nie nazywać tego
bezwarunkowo end-to-end Zero Knowledge wobec wszystkich podmiotów.

## AWS: co trzeba wykonać przed uruchomieniem

1. Zweryfikować dostępność ECS Managed Instances / Nitro Sandbox w
   eu-central-1 w konkretnym koncie, limitach i wspieranych typach EC2.
2. Przygotować odrębny obraz kontenera worker (Chromium + Playwright)
   z niewrażliwymi testami i zbudować jako image immutable digest.
   Pobrać natywne runtime/NSM narzędzia tylko ze sprawdzonego źródła.
3. Zintegrowany `NitroKMSUnwrapper` z dostawcą NSM/CMS przetestować
   na rzeczywistym confidential task, weryfikując PCR17, KMS Recipient,
   odpowiedź CMS oraz brak niechronionych ścieżek Decrypt. Kod oparto
   na oficjalnym przykładzie AWS (MIT-0), ale nie był jeszcze uruchamiany
   na sprzętowej infrastrukturze użytkownika.
4. Utworzyć osobny customer-approved key KMS RSA_3072 (ENCRYPT_DECRYPT).
   Publiczny SPKI oraz odcisk SHA-256 potwierdzić kancelarii.
   KMS **key policy**, nie tylko IAM task role, MUSI wymusić
   `kms:RecipientAttestation:PCR17` i
   `kms:RecipientAttestation:PCR8:ServiceName=ecs.amazonaws.com`.
5. Utworzyć capacity provider ECS Managed Instances z
   `nitroEnclavesEnabled=true`. Użyć awsvpc, dedykowanej grupy SG,
   z ograniczonym egress i bez ECS Exec/dostępu do logowania danych.
6. Z finalnego task definition wygenerować policy i PCR:
   `ecs-nitro-sandbox-genpolicy --task-definition task.json`
   oraz `ecs-nitro-sandbox-genpolicy --task-definition task.json --output pcrs`.
   Wstawić envelope i PCR17 do szablonu CloudFormation, upewnić się,
   że key policy ma warunek PCR17. Sprawdzić spójność przez `--check`.
7. Podłączyć transport ciphertext -> guest: przez uwierzytelniony
   kanał TLS, nie przez argumenty poleceń, logi, zmienne środowiskowe,
   nie przez niezaufany agent. Jeden job = jedna kancelaria i jawna zgoda.
8. Zbudować rejestr sprawdzonych adapterów portali, każda domena osobno.
   Zablokować zewnętrzne skrypty, iframe'y, otwarcia popupów, pobieranie
   plików, nieautoryzowany egress i nieznane redirecty.
9. Dodać kryptograficznie podpisywane (przez użytkownika) i nieodtwarzalne
   zgody na złożenie wniosku, z audytem jedynie metadanych/hash.
   Nie używać prostego parametru bool `approved=true` z API.
10. Włączyć Bedrock tylko w wyraźnie autoryzowanych zadaniach z profilem
    EU i Zero Data Retention; każda zawartość przekazana do modelu
    opuszcza guest. Zweryfikować retencję modelu, prompt cache i logi.
11. Zrobić testy live na fikcyjnych danych i dozwolonym formularzu.
    Nie włączać obecnie NotarAI SaaS w produkcji.

## Walidacja lokalna

- `python -m pytest -q test_confidential.py test_confidential_interop.py` (przy zależnościach
  z głównego requirements.txt).
- `python -m playwright install chromium`
- `python -m confidential.demo_browser`

## Oficjalna dokumentacja AWS (stan 19.11.2026)

- https://docs.aws.amazon.com/AmazonECS/latest/developerguide/ict-getting-started.html
- https://docs.aws.amazon.com/AmazonECS/latest/developerguide/ict-confidential-policy-configuration.html
- https://docs.aws.amazon.com/AmazonECS/latest/developerguide/ict-security-model.html
- https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-properties-ecs-taskdefinition-trustedexecutionconfiguration.html
- https://docs.aws.amazon.com/kms/latest/APIReference/API_Decrypt.html
- https://docs.aws.amazon.com/kms/latest/developerguide/conditions-nitro-enclave.html

## Kryteria odbioru produkcyjnego

- Złośliwa podmiana obrazu/attestation policy odmawia uwolnienia DEK.
- Operator S3 i administrator zwykłego kontenera nie otrzymują plaintext.
- Brak przypadkowego zapisu PESEL/treści w logach, screenach, nagraniach.
- Sfałszowana zgoda nie umożliwia submit; replay jest odrzucony.
- Próba egress do dowolnej domeny jest blokowana; również przez iframe,
  WebSocket, subresource, przekierowania i pobranie pliku.
- Degradacja AWS / timeout powoduje bezpieczne przerwanie zadania.
- Podpis i wysyłka do urzędu dopiero zgodnie z procedurą notarialną.

## Ograniczenia obecnego etapu

- Nie ma jeszcze połączenia API uploadu z kolejką zadań ani live-view guest.
- Brak podpisanej, odpornej na replay autoryzacji wysłania formularzy;
  tryb produkcyjny może jedynie przygotować podgląd (preview).
- Obraz zadania i capacity provider nie są utworzone ani wdrożone.
- Parser rzeczywistych aktów i gotowe adaptery urzędowych formularzy
  pozostają w istniejących modułach NotarAI i wymagają integracji.
- Dokument nie stwierdza wykonania testu produkcyjnego AWS.
