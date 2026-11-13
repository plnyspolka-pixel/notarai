# CLAUDE — MISJA GŁÓWNA: NOTARAI SECRECY PROOF + ETHEREUM

**Gałąź robocza:** `wdrazamy-ethereum` — nie przełączaj się na `master` i nie wdrażaj na produkcję bez odrębnego polecenia.
**Polecenie właściciela:** Popchnij projekt autonomicznie tak daleko, jak pozwalają kod, testy i dostępne środowiska. Zostaw działający, przetestowany kod, wyniki testów i jednoznaczny raport tego, czego jeszcze nie można udowodnić. Nie kończ na analizie ani makietach.

## MISJA PRODUKTOWA

NotarAI ma pomagać kancelariom **wykazać zachowanie tajemnicy notarialnej**, a nie tylko obiecywać „bezpieczeństwo”. Opracuj `NotarAI Secrecy Proof` jako weryfikowalny, prywatny zestaw dowodów konfiguracji, integralności, polityk dostępu i przepływu informacji. Osobny `Ethereum Proof Engine` ma pozwalać weryfikować integralność i chronologię podpisanych dowodów poprzez zewnętrzne zakotwiczenie wyłącznie korzenia Merkle.

**Nie wolno twierdzić, że blockchain dowodzi „żaden człowiek nigdy nie widział danych”.** Wybierz precyzyjnie weryfikowalne twierdzenia: „dokument zaszyfrowano na kliencie kluczem niedostępnym operatorowi”, „ten konkretny podpisany build wykonywał taką politykę”, „nie było autoryzowanego dostępu w kompletnej, tamper-evident historii”, „zestaw danych był zakotwiczony do określonego bloku”. Bez niezależnych atestacji i pełnego pokrycia ścieżek dostępu nie wyświetlaj odznaki `Secrecy Verified`.

## PRIORYTET P0 — AUDYT ADVERSARIALNY I WERYFIKACJA REALNEGO STANU

1. Przeczytaj `CLAUDE.md`, `SAAS.md`, `SPEC.md`, `docs/ethereum-proof-engine.md`, `docs/NOTARAI-SECRECY-PROOF.md` i faktyczny kod. Ustal branch/commit i porównaj do `master`. Sprawdź kompletność implementacji, nie zakładaj, że komentarze = bezpieczeństwo.
2. Narysuj przepływ **każdego rodzaju** informacji poufnej: skan → upload → lokalny cache → OCR → Bedrock → rezultat → S3 → backup → pobranie → serwis → logi/metryki/monitoring. Uwzględnij administratora hosta, AWS IAM, operatorów pomocy, użytkowników kancelarii, przyznawanie uprawnień, integracje zewnętrzne, e-mail i dokumenty tymczasowe.
3. Sprawdź każdy endpoint i middleware: `autoryzacja.py`, `stanowiska.py`, `app.py`, `magazyn.py`, `teczka.py`, `dowody_ethereum.py`, `bedrock.py`, `dziennik.py`. Testuj obejścia przez alternatywne ścieżki, `..\/`, symlinki, URL-e z S3, token pomocnika i serwis. Szczególnie: czy podgląd receipt zawiera `payload`/salt/filename; czy serwis może czytać treść dowodu; czy personel bez prawa może wywołać `/api/dowody/*`.
4. Oddziel uprawnienia do *dokumentu*, do *dowodu* i do *potwierdzenia Ethereum*. Zasada najmniejszych uprawnień; prywatny receipt z nazwą pliku może być danymi objętymi tajemnicą. Zastosuj blokadę fail-closed, testy autoryzacji i negatywne.
5. Zbadaj zależności, sekrety, obrazy Docker, cache, lifecycle S3, SSE-KMS i IAM. Nie odczytuj wartości sekretów i nie umieszczaj ich w odpowiedziach/commitach. AWS region wyłącznie UE. Nie zmieniaj istniejących danych realnych kancelarii.

## PRIORYTET P1 — WYBÓR MODELU OCHRONY (IMPLEMENTUJ, NIE TYLKO OPISUJ)

Stwórz **dwa jawne, odmienne tryby** i w aplikacji wyświetlaj prawdziwe granice zaufania:

- **Sealed / Operator-Blind**: dokument szyfrowany *przed wysłaniem*, klucz kontroluje kancelaria, serwer NotarAI otrzymuje tylko ciphertext i nie może odszyfrować w zwykłej ścieżce. Przetwarzanie treści lokalnie/offline; instalowalny podpisany klient, nie sam modyfikowalny JS z serwera. Zaprojektuj odwołanie urządzenia, rotację klucza, odzyskiwanie przez kancelarię, bezpieczne współdzielenie w kancelarii, eksport i bezpieczne usunięcie. **Nie nazywaj tego zero-knowledge, dopóki nie dowiodłeś braku dostępu operatora do klucza i plaintextu we WSZYSTKICH ścieżkach.**
- **Private AI / AWS Bedrock**: wyraźnie ujawnij, że dane odszyfrowane trafiają do wywołania modelu i nie można tu udowodnić pełnej „operator-blind” ochrony. Sprawdź ustawienia modelu i retencji, logowania invocation, strumienie prompt/response, narzędzia modelu i usługi. Nie obiecuj braku dostępu ludzi poza zakresem rzeczywiście zweryfikowanym.

Zrób realne techniczne POC Sealed z WebCrypto/AES-GCM + envelope encryption, kluczem użytkownika nieeksportowalnym jeśli platforma na to pozwala, per-file DEK, salt/nonce, AAD wersjonowanym i sprawdzeniem integralności; lub lepszym, uzasadnionym wariantem. Nie wprowadzaj pseudo-kryptografii ani własnej wymiany kluczy. Repo jest Python/FastAPI, UI ma istniejące HTML/JS — dopasuj implementację do tej architektury. Nie przesyłaj plaintextu w NotarAI Sealed do Bedrock ani do nowych endpointów z szyfrowaniem.

## PRIORYTET P2 — SECRECY EVIDENCE CHAIN

1. Zdefiniuj versioned evidence schema (zdarzenia: konfiguracja szyfrowania, tożsamość/build klienta, przynależność do kancelarii, issuance/revocation uprawnień, operacje dostępu do klucza, próba dostępu do danych, wybór trybu AI, eksport, wyjątek incydentalny, wygenerowanie dowodu). Nie zapisuj treści dokumentu, PESEL, nazw plików ani surowych adresów/IP w publicznych rootach.
2. Spójne `canonical JSON`: porównaj Python `proof_engine.py` i TS `src/lib/proof-engine/crypto.ts` w Finance You. Obecne ręczne kanonikalizatory nie stanowią standardu międzyjęzykowego; rozważ RFC 8785 JCS z własną wersją protokołu, test vectors (UTF-8, liczby, Unicode, różne kolejności kluczy) i migrację istniejących receipt.
3. Dowody podpisuj przez odpowiedni nieeksportowalny klucz; buduj prywatny append-only/WORM log, replikację i udokumentowaną politykę retencji. Do Ethereum trafia tylko zbiorczy Merkle root (z losowo solonych commitments). Dziennik ma pozostać użyteczny także przy awarii RPC.
4. Zweryfikuj `proof_engine.py`, `dowody_ethereum.py`, testy — aktualnie `get /sprawy/{id}` ujawnia pełne `payload` i `salt` wszystkim dopuszczonym przez middleware; sprawdź, czy potrzebny jest bezpieczny mechanizm eksportu tylko do właściciela/notariusza.
5. Wbuduj `Privacy Evidence Report` (maszynowo weryfikowalny manifest, podpisy, hashe polityk i konfiguracji, wynik testu, weryfikator offline). Rozróżniaj `integrity`, `confidentiality controls`, `access history`, `onchain anchor`, `independent attestation`; każdy ma osobną flagę, źródło i ograniczenia.

## PRIORYTET P3 — REALNE TESTY I CERTYFIKACJA

- Unit + integration + end-to-end + fuzz/property-based + concurrency i awarie: zły token, rola sekretariat, operator serwisowy, inna kancelaria, odwołany klucz, zmodyfikowany payload, uszkodzona partia, przerwany upload, zrestartowana maszyna, wyłączony Internet/Bedrock/RPC, fałszywy receipt oraz reorg Ethereum.
- Testy bez prawdziwych aktów i danych osobowych; sprawdź brak wycieków do CloudWatch, plików temp, stacktrace, backupów i systemów telemetrycznych.
- Rozróżnij atestację AWS Nitro Enclaves od faktycznego przetwarzania Claude przez Bedrock: enclave chroni tylko zakres wykonywania wewnątrz enclave. Nie twórz wrażenia, że atestacja obejmuje wywołanie API modelu poza enclave.
- Przeanalizuj ochronę tajemnicy notarialnej (art. 18 PrNot), RODO, eIDAS2 i potencjalną kwalifikację usługi rejestru elektronicznego z prawnikiem; nie przedstawiaj POC jako QTSP.
- Uruchom dostępne CI, popraw błędy, sprawdź testy regresji. Zanotuj dokładne komendy, wyniki, brakujące dostępy. Dodaj osobny threat model STRIDE/LINDDUN i evidence-to-claim matrix.

## DEFINITION OF DONE

W tej gałęzi mają pozostać: (1) działający POC szyfrowania po stronie kancelarii, bez dostępu operatora do kluczy, albo uczciwy raport blokady z reprodukowalnym testem; (2) utwardzone dowodowe API, testy izolacji i praw dostępu; (3) versioned proof protocol i weryfikator; (4) minimalny interfejs raportu prywatności; (5) zielone testy CI, tam gdzie środowisko pozwala; (6) `docs/ETHEREUM-IMPLEMENTATION-STATUS.md` z tabelą DONE/IN PROGRESS/BLOCKED i niezależnymi dowodami wykonania. Nie fałszuj testów, nie ukrywaj kompromisów. Commity atomowe na tej gałęzi. Nie merge'uj do `master`, nie wysyłaj transakcji Mainnet, nie zmieniaj produkcji, certyfikatów, polityk IAM, nie twórz płatnych zasobów ani nie przesyłaj prawdziwych danych kancelarii bez wyraźnej zgody właściciela. W innych sprawach sam wybieraj rozsądne decyzje i koduj, bez zbędnych pytań.
