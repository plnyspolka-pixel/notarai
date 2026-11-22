# NotarAI — minimalna alternatywa dla kustosza (prototyp kryptograficzny)

## Decyzja: uproszczenie zamiast kolejnego systemu custody

Wariant docelowy **bez oddzielnego konta kustosza** i bez nowych usług:

1. **Pozostają**: AES-256-GCM dokumentu, izolowany Nitro guest, S3 ciphertext,
   SQS, istniejący `PreviewJobLedger`, podpisane potwierdzenie pochodzenia
   dokumentu (`SEC-03`), blokada automatycznego wysyłania formularzy.
2. **Zmiana**: DEK jest szyfrowany do **publicznego klucza RSA kancelarii**,
   nie do KMS kontrolowanego przez AWS operatora. Klucz prywatny klienta nie
   trafia do NotarAI. To osobna wersja koperty; istniejącego formatu v2
   nie nadpisujemy i nie prowadzimy automatycznej migracji danych.
3. Przy uruchomieniu zadania niezależnie dostarczony klient kancelarii
   weryfikuje świeżą, prawdziwą atestację Nitro, sprawdza zatwierdzony
   digest obrazu/PCR i klucz publiczny odbiorcy; dopiero potem lokalnie
   odszyfrowuje DEK i szyfruje go do **ephemeralnego RSA guest**.
4. Powstaje jedno upoważnienie na `job_id`, identyfikatory dokumentu,
   `envelope_sha256`, klucz odbiorcy i maksymalnie 15 min. OAEP label
   kryptograficznie wiąże te metadane. Nie wprowadzamy osobnego signera
   ani rozproszonego rejestru kustosza; dokument nadal musi przejść
   podpisaną kontrolę pochodzenia z SEC-03.
5. Nitro odbiera tylko kopertę + upoważnienie, kontroluje podpisany origin,
   tożsamość zadania i wersję, otwiera DEK prywatnym kluczem w pamięci
   enclave, robi **jedynie preview** i kończy proces. Bez nowego operator
   KMS decrypt. Żaden sekret nie powinien pozostawać po restarcie.

## Co świadomie odrzucamy z MVP

- Shamir 2/3: **niepotrzebny** dla zwykłych zadań; opcjonalny później przy
  odzyskiwaniu klucza właściciela. Na start zaszyfrowany eksport klucza
  w procedurze kancelarii, bez kopii u operatora; utrata kopii oznacza
  nieodwracalną utratę danych.
- MPC, FHE, ZKP, serwer podpisujący, drugi AWS account, DDB custody ledger,
  perpetual offline key-release: **nie są potrzebne** do tego flow.
- WebAuthn jako „magiczny decrypt”: może uwierzytelnić użytkownika, ale
  sam nie zweryfikuje atestacji ani nie zastąpi ochrony sekretu.

## Co już zaimplementowano w tym PR

`confidential/customer_release.py` to mała biblioteka referencyjna:
- AES-GCM z AAD wiążącym tenant/case/object/version i pin klucza klienta;
- RSA-OAEP do klucza kancelarii i potem ephemeralnego RSA guest;
- grant ważny <= 900 s, związany z jobem, SHA-256 koperty, odbiorcą;
- ścisła walidacja pól / odmowy przy podmianie, cross-tenant, replay do
  nowego guest, po czasie i bez klucza kancelarii;
- zero AWS calls; zero plaintext w podpisach/logach/serwerze.

`test_customer_release.py` testuje wyłącznie offline, na fikcyjnych danych.

## Czego NIE wdrożono — konieczne przed live

- **Weryfikator autentycznej atestacji AWS**: COSE/cert chain, świeży nonce,
  pomiary PCR/image i embedded guest ephemeral key. Nazwa argumentu
  `independently_verified_recipient_public_pem` to kontrakt zaufania, a nie
  gwarancja techniczna. NIE pobierać go bez weryfikacji z API NotarAI.
- Niezależna dystrybucja klienta kancelarii i zapis jego klucza prywatnego
  poza administrowanymi przez operatora serwerami. Istniejący offline client
  PR #68 jest punktem wyjścia; wymaga rozszerzenia o ten protokół.
- Guest v3 parse/authorization i prawdziwe podłączenie do S3/SQS/Nitro NSM;
  dotąd działa inny format `Envelope v2` z KMS. Nie przełączać go automatycznie.
- Weryfikacja podpisanego pochodzenia dokumentu dla **v3**. Istniejący v2
  receipt zawiera KMS ARN i nie jest semantycznie zgodny z v3; trzeba
  jawnej adaptacji z podpisem kancelarii, nie wolno pomijać origin.
- Klucz prywatny odbiorcy musi faktycznie powstać **w zweryfikowanym Nitro**;
  w testach użyto zwykłego RSA jako fixtury, nie dowodu sprzętowego.
- Czas ścienny wewnątrz guest nie jest niezależnym bezpiecznym zegarem.
  Realna 15-minutowa granica wymaga zaufanej świeżości, osobnego
  wygaśnięcia zadania i rotacji ephemeralnego klucza. Sam expires_at nie
  dowodzi fizycznej nieważności grantu.
- **Brak pracy offline bez końca**: po restarcie enclave upoważnienie do
  starego ephemeralnego klucza jest bezużyteczne. Ponowny start wymaga
  nowego zatwierdzenia kancelarii. Można wydać serię grantów w sesji.
- **Windows/RejNET** w zwykłej VM nie otrzymuje dowodu Zero Operator
  Access tylko dlatego, że dokument najpierw przetworzyło Nitro.
- **AI egress** poza attestowanym środowiskiem i ataki na frontend są
  niezależnymi ograniczeniami. Brak dowodu pełnego Zero Knowledge.

## Odbiór i bezpieczeństwo

`python -m pytest -q --noconftest test_customer_release.py`

Status: **kryptograficzny prototyp + testy offline**, nie zintegrowany,
nie uruchomiony na AWS i niezweryfikowany jako Zero Operator Access.
Nie scalać ze ścieżką produkcyjną, dopóki powyższe bramki są BLOCKED.