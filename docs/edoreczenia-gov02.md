# e-Doręczenia - GOV-02: stan, dowody, braki (25.11.2026)

Źródło: https://www.gov.pl/web/e-doreczenia/integracja-uslugi-e-doreczen-z-systemami-klasy-ezd
Pobrane załączniki (nie w repo), pierwsze 16 znaków SHA-256:
Regulamin INT 970f2fe862599ff5; Zał. 1a (instrukcja INT v1.9.7) 57e0de36cc747c9f; Zał. 1c (dodanie systemu v1.5) 75a802931b08d148;
Zał. 2a (zgłoszenie, docx) 5c66b5febb398c06; Projekt techniczny SE API v4 (v1.08, kontrakt 4.0.5) c4e68778428a380f;
Instrukcja PROD (07.2025) 16f7b7b89be2be23.

## Ustalone z dokumentów (publicznych)
- Uwierzytelnienie: certyfikat X.509 systemu -> JWT RS256 (RFC 7523: aud, iss=sub=`<ADE>.SYSTEM.<nazwa>`, iat, nbf, exp, jti UUIDv4)
  -> POST `.../auth/realms/EDOR/protocol/openid-connect/token?login_hint=<ADE>` (client_credentials + jwt-bearer) -> token 5 min.
  Nie pobierać nowego tokenu przed wygaśnięciem starego. Wymagany zsynchronizowany czas (NTP).
- URL: INT `int-ow.edoreczenia.gov.pl` (UA API: `uaapi-int-ow.poczta-polska.pl/api/v1|v2|v3`, SE API: `/api/se/v2|v3|v4/`);
  PROD `ow.edoreczenia.gov.pl`, `uaapi-ow.poczta-polska.pl`.
- Certyfikat: jeden certyfikat = jeden system. INT: darmowe certyfikaty. PROD: podmioty niepubliczne (notariusz) kupują
  certyfikat kwalifikowany; system dodaje administrator/właściciel skrzynki w Module uprawnień (Węzeł Krajowy).
- Dostęp INT: zgłoszenie (Zał. 2a) na test.edoreczenia@cyfra.gov.pl z publicznymi adresami IP (serwery i testerzy); COI daje 3 konta PZ
  i do 6 testowych adresów ADE; konta PZ dodatkowo test.pz.edoreczenia@cyfra.gov.pl; ponowne zgłoszenie dopiero po 90 dniach.
- SE API v4: wyszukiwanie ADE adresata, dane posiadacza ADE, wielu adresatów po ADE; dostęp do danych podmiotu wg R.SEAPI.03.

## Zrobione w kodzie
- `edoreczenia_auth.py` - klient tokenu (signedJWT, cache do wygaśnięcia, domyślnie wyłączony, PROD tylko z `produkcja=True`,
  klucz tylko jako funkcja z sejfu).
- `edoreczenia_wysylka.py` - cykl przesyłki: szkic oddzielony od wysyłki, zatwierdzenie osoby uprawnionej związane z hashem treści,
  atomowa jednorazowa wysyłka, timeout = NIEZNANY (bez auto-ponowienia, tylko ręczne uzgodnienie), ponowienie tylko po jednoznacznym
  odrzuceniu, izolacja kancelarii. Transport (UA API) to port - nie zgadywałem ścieżek ani pól.
- `test_edoreczenia.py` - 11 testów (w tym izolacja kancelarii i wysyłka równoległa).

## BRAKI (blokady zewnętrzne - nie obchodzone)
1. Kontrakty `ua_api.yaml` i `se_api.yaml` oraz instrukcje techniczne UA API są dostępne po przyznaniu dostępu do INT
   (`int.edoreczenia.gov.pl/dokumentacja`) lub z hosta Poczty Polskiej; z tej sesji oba są zablokowane. Bez nich nie ma klienta
   listy skrzynek, wyszukiwania adresata (BAE/SE), odbioru wiadomości i dowodów - zostają do wykonania po zdobyciu YAML.
2. `aud` w JWT wg instrukcji ma schemat `http://` - do potwierdzenia na INT; ADE z/bez prefiksu `ADE.` w `login_hint`
   (przykłady w instrukcji się różnią) - do potwierdzenia na INT.
3. Zgłoszenie INT (Zał. 2a), certyfikat testowy/CSR i dodanie systemu w Module uprawnień - czynności człowieka.
4. Trwały magazyn przesyłek (Skrzynka jest referencyjna, w pamięci) - po decyzji o bazie; wymaga zgody (dane osobowe, CLAUDE.md).
5. Oficjalne testy INT; brak realnych wysyłek do czasu ich przejścia.
