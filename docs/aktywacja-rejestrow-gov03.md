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

## Czego tu NIE ma (zależy od zewnętrznych elementów)
1. Prawdziwy weryfikator podpisu (EU trusted list, CRL/OCSP, status w chwili podpisu): potrzebny zatwierdzony QTSP/biblioteka
   (np. oparta o DSS); nie piszę własnej kryptografii ani własnego QTSP. Port jest gotowy, testy używają atrapy.
2. Adapter wykazu KRN - do czasu GOV-09 (czy istnieje oficjalne API) zostaje ręczne potwierdzenie przez operatora.
3. Sejf: implementacja na AWS Secrets Manager wymaga zgody i zmian AWS (poza zakresem PR #137).
4. Trwały magazyn statusów, endpointy i ekran w aplikacji - po decyzji o bazie (dane osobowe, pytanie do właściciela).
5. Podpięcie `rznp.py` i `edoreczenia_*` do bramki `moze_uzyc` - po pkt 1-4.
