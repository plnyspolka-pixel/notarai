# CIV-01 — czysta baza NotarAI Confidential bez kustosza

**Status:** zadanie zaplanowane; ten PR zawiera wyłącznie specyfikację. **Docelowa gałąź kodowa: master.** Priorytet P0.

## Cel biznesowy
Przenieść *minimalny, już napisany* mechanizm klucza kancelarii + atestacji Nitro do jednej łatwej do utrzymania gałęzi. Bez przepisywania NotarAI, nowego frameworka TEE, kont kustosza i dodatkowych usług. To jest osobny PR do wdrożenia przez jedną sesję kodowania.

## Stan wejściowy / źródła kodu
- #50 i #51 zostały scalone: istniejące Confidential Browser, Nitro, AWS.
- #68 (szyfrowanie w kliencie, origin admission, standalone signed HTML) leży na **starej** gałęzi z custody.
- #86 (klucz kancelarii RSA-3072, envelope AES-GCM, jednorazowy grant) zależy od #68.
- #87 (lokalna walidacja NSM/COSE, nonce/PCR, challenge, klient i guest) zależy od #86. CI syntetyczne: 54/54 na SHA 76b741c6.
**Nie wolno scalić całego starego stosu automatycznie:** #65/#61/#62/#70/#71 implementują uprzedni model kustosza.

## W implementacji
1. Otwórz nowy kodowy branch od *aktualnego* master, cherry-pick/przenieś wyłącznie zatwierdzone komponenty AES-GCM/RSA z #86, attestation/guest #87, origin i klienta #68, wraz z testami.
2. Zdefiniuj jedno wersjonowane API envelope v3 (`customer-envelope.v1` z #86) i jego jawny parser. Nie zmieniaj w locie v2, nie wykonuj cichej migracji i nie przepuszczaj mixed v2/v3.
3. Uporządkuj importy, dokładne licencje MIT-0 AWS, zależności i testy; opcjonalne cbor2 nie może psuć instalacji podstawowej aplikacji.
4. Wstaw dokument z granicami ochrony: szyfrowanie klienta + Nitro to **nie** poufne Bedrock, Windows VM ani portale zewnętrzne.
5. Dopiero po akceptacji tej bazy kolejna sesja może dokładać UX, S3/SQS v3 i dowody AWS.

## Kryteria odbioru — każde obowiązkowe
- [ ] Kod startuje z czystego master (bez wymuszonego merge starych gałęzi custody). `git diff master` zawiera tylko potrzebne biblioteki, testy, dokumentację i uzasadnione zmiany.
- [ ] `python -m pytest -q --noconftest test_customer_release.py test_customer_attestation.py test_customer_guest_v3.py`: **0 failure, 0 error**; testy negatywne fałszywego korzenia AWS, debug, PCR, nonce, certyfikatu, czasu i klucza odbiorcy.
- [ ] Cały istniejący CI master (Python, frontend, security) **zielony na dokładnym SHA**; brak regression w v2 i w zwykłym panelu NotarAI.
- [ ] Zero nowych obowiązkowych AWS zasobów, konto kustosza, KMS z dostępem operatora do DEK i mechanizmów Shamir/MPC/ZKP/FHE.
- [ ] Dla v3 nie istnieje ścieżka odtworzenia klucza kancelarii z konta operatora; statyczna lista plików/endpointów i testy odmowy.
- [ ] Test negatywny: stary `kms_key_arn` we v3 i `owner_spki_sha256` we v2 powodują odmowę bez odszyfrowania.
- [ ] Dokumenty `docs/security-...` jasno oznaczają: **synthetic only / AWS not tested / Zero Operator Access not yet proven**.
- [ ] Nie włączono nowej funkcji produkcyjnie; PR ma czytelną instrukcję lokalnych testów i listę wymaganych PR-ów następnych.

## Poza zakresem
Nie wprowadzaj GUI klienta, realnych S3/SQS/guest v3, deploymentu AWS, środowiska Windows, generowania dokumentów notarialnych ani kompletnego AI. To odrębne sesje.

## Praktyczna definicja bezpieczeństwa
Chronimy dane przed zwykłym administratorem/opiekunem NotarAI oraz przejęciem operatorowego konta aplikacji. Nie konstruujemy systemu na poziomie obronnym/wojskowym i nie obiecujemy odporności na złamanie sprzętu AWS, kompromitację urządzenia notariusza czy fizyczne ataki na chip.
