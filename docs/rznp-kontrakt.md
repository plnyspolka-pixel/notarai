# RZNP – dowody i kontrakt (GOV-01, 25.11.2026)

Źródło: https://www.gov.pl/web/cyfryzacja/udostepnianie-danych-z-rejestru-zastrzezen-numerow-pesel
(strona pobrana 25.11.2026; załączniki z datą 17.04.2024 - to aktualna wersja na stronie).

## Pobrany pakiet (nie jest w repozytorium)
`rejestr-zastrzezen-dokumentacja-integracyjna-17042024.zip` (73 754 B)
- zip: `a695241170ca84b0d54ea7cb88c2e58ad7b575dd149cab64bc1670417057c915`
- `rejestr-zastrzezen-proxy-contract.yml` (OpenAPI 2.0.8): `439275212dd57ab6a31d5550b17244c685da3a5e073977a787eb2a07dcf9a483`
- `dokumentacja-dla-integratorow-2.0.8.html`: `fee7294153e6f266638cdfdaa285329a7cb0569ecf00bfb8e64d25e16ff938e1`
- `rejestr-zastrzezen-proxy-2.0.8-stubs.jar`: `f25dbe72c46759ee64bcea1262f6a0d55be08e8dbaa80b2c3d9ad57dfe8ecc5a` (NIE uruchomiony, NIE w repo)
- `test-data-usluga-weryfikacji.csv`: `9c603e6775bb070b72f9f79dfd15aac593274402c03d7073a78c6f997fffabce` (numery testowe środowiska INT; nie kopiowane do testów)

Licencji pakietu nie sprawdzono (brak w ZIP) - nie commitować binariów ani CSV.

## Ustalenia z kontraktu
- Usługi: `POST /status-zastrzezenia/aktualny` (do weryfikacji przed umową), `POST /status-zastrzezenia/na-dzien` (historia, NIE do weryfikacji bieżącej).
- Nagłówki: `X-REQUEST-ID` (UUID, wymagany), `X-API-KEY` (klucz z wniosku; stub go nie wymaga).
- `powodWeryfikacji`: 3-512 znaków, regex `^[-.,_ a-zA-ZżźćńółęąśŻŹĆŃÓŁĘĄŚ0-9\\/]+$`.
- Statusy: `ZASTRZEZONY` | `NIEZASTRZEZONY`; daty ISO-8601 z offsetem; lista `na-dzien` posortowana od ostatnio wprowadzonego.
- Błędy: 400 (kontrakt), 401/403 (klucz, konto, IP), 429 (blokada IP), 500, 503 (w tym planowana: `planowanaNiedostepnoscDo`), 504.
- SLA: timeout 5 s; p95 < 1 s (aktualny), < 3 s (na-dzien); dostęp tylko z IP zgłoszonych we wniosku i geolokalizowanych w UE/UK/CH/USA.
- Środowiska: INT `https://int-rejestr-zastrzezen.obywatel.gov.pl:20443/api/v1`, PROD `https://rejestr-zastrzezen.obywatel.gov.pl:20443/api/v1`.
- Niespójność kontraktu: schemat `StatusZastrzezeniaPesel` wymaga `statusZastrzezenia`, a definiuje `status`. Klient wymaga pola `status`; do potwierdzenia na INT.

## Implementacja
`rznp.py` (klient) + `test_rznp.py` (emulator na `httpx.MockTransport`, syntetyczne PESEL).
Adapter wyłączony domyślnie; PROD tylko z `produkcja=True`; klucz per notariusz przekazywany do konstruktora;
awaria, timeout, 5xx lub nieczytelna odpowiedź = wyjątek, nigdy „niezastrzeżony"; PESEL i klucz nie trafiają do komunikatów.
Podpięcie do aplikacji (sejf kluczy, status per-user z GOV-03) - dopiero po GOV-03.

## Czeka na człowieka
- Formularz testowy do cc.wnioski@coi.gov.pl (wysyła notariusz/integrator, nie ja) - treść wniosku: `Wniosek_dostepowy...pdf` ze strony.
- Uruchomienie oficjalnego stuba (JAR) w izolowanym środowisku po weryfikacji pochodzenia/licencji.
- Potwierdzenie na INT niespójności `status`/`statusZastrzezenia`.
