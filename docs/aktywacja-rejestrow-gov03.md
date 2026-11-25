# GOV-03: indywidualna aktywacja rejestrów chronionych (25.11.2026)

Moduł: `aktywacja_rejestrow.py`, testy: `test_aktywacja_rejestrow.py` (20 testów). Cognito i logowanie bez zmian.

## Model
Status per osoba (kancelaria + e-mail) i per usługa: brak -> wniosek_przygotowany -> zlozony -> przyznany -> skonfigurowany;
oraz wygasly i odwolany. Usługi chronione = pozycje katalogu `wymaga_dostepu` / `wymaga_potwierdzenia`.

## Zasady egzekwowane w kodzie
- Challenge: losowy, jednorazowy (atomowe zużycie, także przy odrzuceniu podpisu), TTL 5 min, powiązany z sesją, osobą,
  kancelarią i usługą (cel).
- Podpis: akceptowany wyłącznie, gdy weryfikator zewnętrzny potwierdzi integralność, ścieżkę zaufania UE, status
  kwalifikowany, brak odwołania i dokładnie ten challenge. Plik certyfikatu ani certyfikat samopodpisany nie wystarczają.
- Status zawodowy: osobno, w wykazie KRN (port `WykazKrn`).
- Tożsamość podpisującego jest wiązana (hash) z kontem; inna osoba na tym koncie lub ta sama tożsamość na dwóch kontach = odrzucenie.
- Zgoda notariusza na zakres jest warunkiem złożenia wniosku.
- `przyznaj` wymaga udokumentowanej decyzji instytucji (numer, hash dokumentu, ważność) - to czynność operatora dowodów,
  NIE endpoint użytkownika. Użytkownik nie ma ścieżki do statusu „przyznany".
- Skonfigurowanie wymaga klucza w sejfie (port `Sejf`); klucze nigdy w zwykłym JSON.
- Bramka `moze_uzyc`: tylko indywidualna sesja (nie demo, serwis ani komputer), status „skonfigurowany", ważna decyzja,
  zgoda, klucz w sejfie. Wygaśnięcie decyzji i odwołanie blokują natychmiast.

## Wersja produkcyjna (AWS, eu-central-1)
- Zasady PR #137 o wyłączeniu AWS uchylone decyzją właściciela (25.11.2026): budujemy docelowo produkcyjnie.
- `infra/notarai-rejestry.yaml` (+ `infra/7-wdroz-rejestry.ps1`): klucz KMS z rotacją, tabela `notarai-rejestry`
  (SSE-KMS, PITR, TTL `wygasa`, Retain, tylko Frankfurt), polityka roli `notarai-ecs-zadanie` (bez Scan/Query;
  sejf tylko pod `notarai/rejestry/*`). cfn-lint czysty. NIE wdrożone - czeka na potwierdzenie (reguła RODO w CLAUDE.md).
- `aktywacja_aws.py`: `DynamoMagazyn` (challenge jako skrót nonce, atomowe zużycie przez warunkowe usunięcie, statusy z wersją
  i zapisem warunkowym, wiązanie tożsamości transakcją "wszystko albo nic") i `SejfSecretsManager` (klucz per kancelaria,
  osoba i usługa; `ma_klucz` nie czyta wartości). W bazie i nazwach sekretów tylko skróty SHA-256, bez e-maili.
- `aktywacja_router.py` (`/api/aktywacja/...`, wpięty w `app.py`): status, wniosek, challenge, złożenie z podpisem, wgranie klucza,
  odwołanie; administrator: `admin/przyznaj` (decyzja instytucji) i `admin/krn`. Tylko indywidualna sesja.
- Testy: moto (DynamoDB, Secrets Manager) + router; CI instaluje `moto==5.2.6`.

## Czego jeszcze NIE ma
1. Weryfikator podpisu kwalifikowanego (lista zaufania UE, CRL/OCSP): bez niego `zloz` zwraca 503 - świadomie nie przepuszcza
   niezweryfikowanego podpisu. Wymaga wyboru biblioteki/QTSP (np. DSS) i podpięcia do `aktywacja_router.WERYFIKATOR`.
2. Oficjalne API KRN (GOV-09): do tego czasu administrator potwierdza status zawodowy ręcznie (`admin/krn`).
3. Ekran w aplikacji dla tych endpointów i podpięcie adapterów `rznp.py` / `edoreczenia_*` do bramki `moze_uzyc`.
