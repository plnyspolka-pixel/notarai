# CIV-04 — klucz kancelarii: onboarding, kopia zapasowa i odzyskiwanie

**Status:** PLAN ONLY. P0 przed realną sprzedażą, może być realizowane po CIV-02 (#89), równolegle do #72. Zero kustosza treści, zero Shamir/MPC, bez kwalifikowanego podpisu jako wymogu.

## Cel cywilny
Notariusz nie traci całego archiwum po utracie laptopa ani po usunięciu przeglądarki. Operator nie może odtworzyć klucza kancelarii, ale klient może **samodzielnie** odtworzyć dostęp z zabezpieczonej kopii. System uczciwie ostrzega o skutkach braku kopii.

## Zakres techniczny
1. Generowanie, import i identyfikacja klucza RSA-3072 kancelarii w zweryfikowanym kliencie CIV-02. Brak kopiowania prywatnego klucza do NotarAI/S3/CI/logów.
2. Eksport do zabezpieczonej kopii: prywatny klucz szyfrowany passphrase przez publicznie audytowany KDF (np. Argon2id z parametrami kalibrowanymi na urządzeniu) i AEAD; nie implementować kryptografii samodzielnie. Wariant web musi jednoznacznie określić, kiedy klucz jest `extractable`, i unikać fałszywej obietnicy sprzętowego HSM.
3. Czytelny onboarding: po utworzeniu klucza wymuś **potwierdzenie możliwości odtworzenia** na fikcyjnym testowym dokumencie przed przyjmowaniem realnych aktów. Dwóch kopii trzymanych przez kancelarię zalecamy jako procedurę organizacyjną (bez infrastruktury operatora).
4. Import na nowym urządzeniu: odczyt kopii, sprawdzenie hasła, obliczenie SPKI SHA-256 i porównanie z manifestem danych kancelarii/istniejących kopert; nie resetować cicho klucza i nie generować pozornego sukcesu.
5. Rotacja: nowe dokumenty na nowy klucz; stare dalej czytelne wyłącznie ze starym kluczem albo migrowane *po zgodzie* klienta wewnątrz atestowanego środowiska. Nie obiecywać automatycznego ponownego zaszyfrowania całości.
6. Dokumenty: prosta instrukcja dla notariusza i sekretariatu, ostrzeżenie o nieodwracalnej utracie danych po utracie wszystkich kopii i hasła. Brak recovery przez helpdesk.

## Kryteria odbioru
- [ ] W zaufanym kliencie nie potrzeba konsoli ani instalowania dodatkowego oprogramowania, aby wykonać export/restore.
- [ ] Utworzenie klucza → zaszyfrowanie fikcyjnego dokumentu → kopia offline → usunięcie lokalnego profilu/stanowiska → odtworzenie na drugim urządzeniu → odszyfrowanie tego samego dokumentu: **PASS**.
- [ ] Złe hasło, podmieniony blob AEAD, nieodpowiedni klucz/tenant, niekompletna kopia i błędny SPKI pin: **DENY**, zero plaintext.
- [ ] Próby pobrania private key poprzez HTTP fetch, API NotarAI, aplikacyjny log i telemetrię są negatywne; test sieciowy z fikcyjnym canary.
- [ ] Przynajmniej **jeden niezależny od przeglądarki test interoperacyjności** kopii (jawnie opisany format i parametry KDF/AEAD, test vectors) bez używania środowiska operatora.
- [ ] Rotacja nie psuje starych dokumentów; test odmowy migracji bez wyraźnego upoważnienia.
- [ ] UX przed włączeniem realnych danych: komunikat o kopii i test restore są obowiązkowe; wpis w dokumentacji „operator nie odzyska danych”.
- [ ] Nie istnieje „admin reset” prywatnego klucza, przywracanie z KMS operatora ani cichy fallback na nowy klucz.
- [ ] Testy na fikcyjnych danych + CI zielone; bez sekretów w repo oraz nowych kosztownych usług.

## Poza zakresem
Nie budować PKI, bankowego HSM, współdzielonego recovery multi-party, FHE, blockchain, kont KRN, inspektora ani osoby-trustee. Jest to zwykła odpowiedzialna kryptografia cywilna.

## Interfejsy
CIV-02 dostarcza podpisany klient bez instalacji i UI zgód, CIV-03 egzekwuje job/scope. Recovery testowana z dokładnym formatem v3 z CIV-01. Stary #68 recovery custodial może służyć do porównania testów, ale nie przenosić mechanizmu kustosza.
