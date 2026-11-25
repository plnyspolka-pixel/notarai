# Korespondencja Fundacji – kontrola wysyłki (25.11.2026)

**Zakres:** wyłącznie dokumentacja i korespondencja, bez zmian aplikacji/AWS, bez nadawania uprawnień i bez wysyłania. Oddzielne od PR #137. Publiczne repozytorium zawiera zredagowane źródła wszystkich 22 pism. Pełne PDF/TXT oraz rejestr są w prywatnej Bibliotece użytkownika w `NotarAI_pakiet_dwa_tory_2026-11-25.zip` (SHA-256: 54c6e6d307c2f5beae94fabcdceae5accb58804a847c8fe23c823015fa3935ca). Nie publikować danych nadawcy, adresów infrastruktury, podpisów, dowodów doręczeń ani danych klientów. Nie wysyłać zredagowanych wzorów z repo.

## Rejestr i kolejność

Status P: przygotowane, do ostatecznej akceptacji nadawcy, weryfikacji prawnej szczegółowej i adresu; nie oznacza wysyłki. W: pismo wstępne (nie formularz). K: pismo warunkowe. Brak potwierdzonego nadania dla każdej pozycji.

| Znak | Adresat | Kanał | Status | Warunek szczególny |
|---|---|---|---|---|
| DIP-01 | MC | e-Doręczenia | P | Niezależne od AWS |
| DIP-02 | COI | e-Doręczenia | P | jw. |
| DIP-03 | GGK/GUGiK | e-Doręczenia | P | jw. |
| DIP-04 | MS | e-Doręczenia | P | jw. |
| DIP-05 | KRN | e-mail | P | priorytet; oddzielnie od TECH-01 |
| DIP-06 | MSWiA | e-Doręczenia | P | niezależne od AWS |
| DIP-07 | MF/GIIF | e-Doręczenia | P | MF jako adresat; ustalić kopię GIIF |
| DIP-08 | KRN | e-mail | P | priorytet; tajemnica notarialna |
| DIP-09 | MS | e-Doręczenia | P | priorytet; tajemnica notarialna |
| TECH-01 | KRN | e-mail | P | kopia MS |
| TECH-02 | Rejestry Notarialne | e-mail | P | kopia KRN |
| TECH-03 | RejNET | e-mail | P | opcjonalny kontakt serwisowy; kopia KRN/RN |
| TECH-04 | MC | e-Doręczenia | P | kopia MS w zakresie obowiązków notariuszy |
| TECH-05 | GGK | e-Doręczenia | P | nie jest formalnym wnioskiem ZSIN |
| TECH-06 | MS | e-Doręczenia | P | nie jest wnioskiem o indywidualną zgodę KW |
| TECH-07 | MSWiA | e-Doręczenia | P | kopia MC; nie zamawia przyłącza |
| TECH-08 | MF/GIIF | e-Doręczenia | P | nie jest formalnym zgłoszeniem produkcyjnym |
| TECH-09 | COI RZNP | e-mail | W | pytanie wstępne teraz; formularz testowy osobno |
| TECH-10 | zespół INT | e-mail | W | pytanie wstępne teraz; formularz 2a osobno |
| TECH-11 | mObywatel | Panel Współpracy | W | treść TXT; bez fałszywych deklaracji lub akceptacji regulaminu |
| TECH-12 | KRN | e-mail | K | ocena warunkowa modelu A–E, nie certyfikat; kopia MS |
| TECH-13 | MS | e-Doręczenia | K | po TECH-12, załączyć rzeczywiście wysłaną wersję; nie antydatować |

Fala 1: 9 DIP osobno; fala 2: 8 TECH zwykłych, 3 wstępne i 2 warunkowe. Fala 3: oficjalne formularze i dowody. Nie blokować fal 1–2 przez brak stałego IP; TECH-12/13 wyłącznie jako wnioski o ocenę warunkową, nie dowód działania produkcyjnego. Kopię do MS przewidzianą w TECH-12 wykonać przez TECH-13 z załącznikiem, bez niepotrzebnego dublowania. Rozstrzygnąć przed wysyłką pozostałe kopie wymienione w pismach. Jeżeli TECH-12 nie zostało nadane, nie wysyłać TECH-13 z twierdzeniem, że zostało skierowane.

## Kontrola wykonana

- ZIP: 22 PDF, 22 odpowiadające TXT, 22 unikalne znaki w rejestrze. 23 strony pism (TECH-12 ma 2 strony). Wszystkie PDF otworzyły się i zostały wyrenderowane; przegląd stykówek bez widocznych ucięć/nakładania. Porównanie tekstu PDF do TXT po normalizacji białych znaków, myślników i stopki: 22/22 zgodne (wynik zaokrąglony do 3 miejsc).
- Weryfikacja rozdzielenia DIP (istniejące dokumenty, nie tworzenie opinii) i TECH (uzgodnienia, nie wnioski o uprawnienia Fundacji). Nie podano fikcyjnych IP ani certyfikacji.
- Oficjalne źródła potwierdzają procedury test RZNP i INT oraz istnienie formularza ZSIN; adresy MS, MSWiA i e-mail KRN potwierdzono na stronach instytucji. Resztę adresów należy sprawdzić w BAE/na oficjalnej stronie bezpośrednio przed nadaniem.
- Kontrola jednostek redakcyjnych wszystkich ustaw, powołania na etykę adwokacką i rekomendacje KIRP oraz aktualnego KRS/reprezentacji nie jest zakończona. Nie oznaczać jako prawnie zatwierdzone. TECH-12: szczególnie sprawdzić warunki Bedrock per model; sformułowania opisują wymagany profil, nie dowiedzioną konfigurację. Jeśli nie można potwierdzić źródeł porównawczych, usunąć fragment III o NRA/KIRP przed drukiem.
- Data dokumentów 25.11.2026: przed wysyłką innego dnia zaktualizować datę PDF/TXT i odnotować zmianę wersji.

## Odbiór od Claude'a: prywatny pakiet, bez publikacji sekretów

**Obowiązujący szczegółowy kontrakt odbioru:** [CLAUDE-AWS-KRYTERIA-ODBIORU.md](CLAUDE-AWS-KRYTERIA-ODBIORU.md). Najpierw A+B (IP i mapa pól formularzy), niezależnie od C–F (dowody 3×Zero).

1. RZNP TEST / INT: rzeczywiste publiczne IPv4 egress z komponentu wykonującego żądania (test i prod według potrzeb), pomiar z każdego AZ, po wymianie instancji/zadania, NAT/EIP/routing. Nie IP ALB. Dla INT sprawdzić aktualne pola załącznika 2a i podać IP tylko jeśli wymagane. Kontakty techniczne potwierdzone przez osoby zainteresowane; komplet specyfikacji, aktualne oficjalne formularze i podpis reprezentanta. Produkcja RZNP dopiero po zgodzie właściwego organu dla uprawnionego użytkownika.
2. ZSIN / ULDK: formalny wniosek odpowiedniego podmiotu po potwierdzeniu podstawy, zakresu i warunków; IP do whitelist ULDK po potwierdzeniu rzeczywistego egress. SRP/PESEL/RDO/RDP: właściwy tryb i formularz dopiero po kwalifikacji; PESEL-NET osobno, nie zamawiać przyłącza.
3. TECH-12/13 – etap dowodowy po uzgodnieniu: specyfikacja release/commit, podpisany manifest, atestacja, polityka kluczy, dowody izolacji, przepływ/regiony i podwykonawcy, retencja per model i konfiguracja Bedrock, logi, fallbacki, testy syntetyczne i dokumentacja RODO. Nie przesyłać sekretów. Brak IP sam w sobie nie blokuje wniosku o stanowisko warunkowe.
4. Każdy brak oznaczyć jako BLOKER tylko dla procedury, której dotyczy. Pakiet dowodowy D01–D06 pozostaje po stronie technicznej PR #137; do tego PR trafi wyłącznie status i bezpieczne wskazanie dowodu.

## Procedura wysyłki (Work)

Zweryfikuj aktualny KRS i reprezentację, własne ADE, BAE/adresy, właściwy kanał i pełną treść PDF; potwierdź finalną wersję oraz wymagane kopie/załączniki. Podpis kwalifikowany jeżeli wymagany; wnioski DIP co do zasady bez takiego obowiązku. Przygotuj odrębną przesyłkę na każdy znak, przedstaw adresata, temat, treść, listę plików oraz kopie do zatwierdzenia. Bez nadania przed akceptacją użytkownika. Po faktycznym wysłaniu zapisz dowód nadania i doręczenia, datę, identyfikator i hash wersji w prywatnym rejestrze; nie ustawiaj daty z góry. DIP: termin co do zasady 14 dni od złożenia, z ustawowymi wyjątkami; TECH: kontakt roboczy po 7–14 dniach, nie traktować milczenia jako zgody. Nie wysyłać pakietu zbiorczego, instrukcji wewnętrznych ani dokumentów pilotażu.

## Źródła oficjalne – sprawdzone 25.11.2026 / do kontroli przed nadaniem

- UDIP: https://eli.gov.pl/eli/DU/2022/902 ; Prawo o notariacie: https://eli.gov.pl/eli/DU/2026/614 (aktualność i zmiany oraz jednostki weryfikować osobno).
- RZNP: https://www.gov.pl/web/cyfryzacja/udostepnianie-danych-z-rejestru-zastrzezen-numerow-pesel
- INT: https://www.gov.pl/web/e-doreczenia/integracja-uslugi-e-doreczen-z-systemami-klasy-ezd
- PESEL: https://www.gov.pl/web/cyfryzacja/udostepnianie-danych-z-rejestru-pesel1
- ZSIN: https://www.gov.pl/web/gugik/formularze ; ULDK: https://uldk.gugik.gov.pl/opis.html
- mObywatel: https://wspolpraca.mobywatel.gov.pl/
- Adresaci: https://www.gov.pl/web/sprawiedliwosc/dane-kontaktowe ; https://www.gov.pl/web/mswia/dane-kontaktowe ; https://bip.krn.org.pl/kontakt ; https://www.gov.pl/web/cyfryzacja/dane-kontaktowe ; https://coi.gov.pl/kontakt ; https://www.gov.pl/web/gugik/dostep-do-informacji-publicznej ; https://www.gov.pl/web/finanse/dane-teleadresowe .
