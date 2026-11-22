# NotarAI Confidential — cywilny plan wykonawczy, 22.11.2026

## Zasada nadrzędna
Bezpieczny produkt cywilny: **proste kontrolowane szyfrowanie, klucz kancelarii, Nitro, udokumentowana atestacja**. Zero nowego kustosza, nie mnożymy kont i infrastruktury ani nie odtwarzamy kryptografii. Marketing opisuje **dokładny zakres** dowodów, nie absolutną nieprzenikalność. Dwa poziomy produktu: `Confidential Documents` (najpierw) oraz opcjonalny `Confidential AI` (później); Windows/RejNET poza tą gwarancją.

## Jeden PR = jedna sesja. Plan kolejności

| Faza | PR | Jedno zadanie | Zależności i bramka |
| --- | --- | --- | --- |
| 0 / threat | [#66](https://github.com/plnyspolka-pixel/notarai/pull/66) | Zwięzła granica zagrożeń i twierdzeń; bez starego modelu custody | Równolegle z #88; kod tylko ze zgodą właściciela |
| 1 / baza | [#88](https://github.com/plnyspolka-pixel/notarai/pull/88) CIV-01 | Czysta ekstrakcja AES/RSA/atestation z #68/#86/#87 na master | Punkt startowy dalszego kodowania; **nie scalać zagnieżdżonej gałęzi custody** |
| 2 / klient | [#89](https://github.com/plnyspolka-pixel/notarai/pull/89) CIV-02 | Samodzielny, podpisany klient webowy bez instalacji | Po #88; kontrakt API uzgodnić z #90; równolegle z #90 |
| 3 / worker | [#90](https://github.com/plnyspolka-pixel/notarai/pull/90) CIV-03 | v3 S3/SQS/Nitro/immutable VersionId/one-use, preview-only | Po #88; równolegle z #89; nie dotyka Windows |
| 4 / klucze | [#91](https://github.com/plnyspolka-pixel/notarai/pull/91) CIV-04 | Backup, odzyskanie i rotacja klucza kancelarii | Po #89; równolegle z hardware #72 |
| 5 / sprzęt | [#72](https://github.com/plnyspolka-pixel/notarai/pull/72) | Autentyczny NSM/COSE, attestation i negatywne próby | Po #89 + #90; AWS tylko z autoryzacją i limitem kosztu |
| 6a / sieć | [#73](https://github.com/plnyspolka-pixel/notarai/pull/73) | Antyeksfiltracja E2E podczas obsługi plaintext | Po #90; równolegle z #74 |
| 6b / izolacja | [#74](https://github.com/plnyspolka-pixel/notarai/pull/74) | Dwóch tenantów na wspólnym ekonomicznym środowisku | Po #90; równolegle z #73 |
| 7a / retencja | [#75](https://github.com/plnyspolka-pixel/notarai/pull/75) | Retencja, kopie, brak plaintext w logach | Po #90 + #73; bez trzech podpisów kustosza |
| 7b / dowody | [#76](https://github.com/plnyspolka-pixel/notarai/pull/76) | Zrozumiały dowód offline dla kancelarii | Po #72; bez WORM u zewnętrznego trustee |
| 8 / pilot | [#77](https://github.com/plnyspolka-pixel/notarai/pull/77) | E2E w AWS na 2 fikcyjnych kancelariach, retry i koszty | Po #72-#76; brak realnych aktów do GO |
| 9 / sprzedaż | [#78](https://github.com/plnyspolka-pixel/notarai/pull/78) | GO/NO-GO, RODO, umowa, claimy i onboarding | Po #77 + #91; bez dowodów OFF |
| 10 / AI | [#69](https://github.com/plnyspolka-pixel/notarai/pull/69) | Realny Confidential AI albo „Unavailable”; zwykły Bedrock osobnym wariantem | Po #89/#90/#72/#73; **nie blokuje Confidential Documents bez AI** |
| 11 / Windows (osobna linia) | [#63](https://github.com/plnyspolka-pixel/notarai/pull/63), [#64](https://github.com/plnyspolka-pixel/notarai/pull/64) | Virtual Employee i RejNET Office | Nie zaliczać do dowodu ZOA dla dokumentów/AI; osobne threat model i pilot |

### Istniejące repozytoria/kod traktowane jako źródła, nie produkcyjne gałęzie do automatycznego merge
- #50/#51 scalone do master — baza.
- #57/#58/#60 — lifecycle, Control Room, współdzielona infrastruktura: selektywnie adaptować do CIV-03.
- #68/#86/#87 — cryptographic components i syntetyczne testy: źródło dla #88.
- #65/#61/#62/#70/#71 — **stary external custody**. Nie integrować w customer-owned v3; archiwizować dopiero po upewnieniu się, że testy i runbooki zostały przeniesione.
- #85 — podpisany transparency log: opcjonalny wzorzec dla #76, nie warunek „blockchain/WORM/niezależny kustosz”.

## Wspólny protokół wykonawczy dla każdej sesji
1. Otwórz dokładnie podany PR i jego dokument planistyczny lub aneks w opisie. Sprawdź aktualny HEAD i base **przed** kodowaniem.
2. Implementacja na dedykowanej gałęzi aktualnego master **z zaakceptowaną bazą CIV-01**; dla istniejących zagnieżdżonych PR wykorzystaj selektywny cherry-pick, nie merge całej cudzej gałęzi.
3. Nie zmieniaj innych obszarów ani nie łącz cudzych PR; spisz powody każdego istotnego odstępstwa i wymagane migracje v2/v3.
4. Każda sesja kończy się: kodem w PR, testami pozytywnymi i negatywnymi, linkiem do CI z dokładnym SHA, mierzalnym statusem `PASS / BLOCKED / FAIL`, listą rzeczy wymagających realnego AWS, i bez produkcyjnego przełączenia.
5. Do zakończenia własnych testów wymagane są **0 failed i 0 errors**, brak plaintext w logach, brak sekretów w commitach; software test ≠ hardware proof.
6. Dane syntetyczne, domyślny read-only AWS, deployment tylko za wyraźną zgodą i budżetem. Nie obiecuj pracy asynchronicznej. Nie uruchamiaj rzeczywistych notarialnych formularzy bez oddzielnego planu autoryzacji.
7. Niespełniony warunek oznacza Draft/BLOCKED, nie „prawie gotowe”.

## Rzeczywiste minimum komercyjne
**Confidential Documents:** #88, #89, #90, #91, #72, #73, #74, #75, #76, #77, #78 i adekwatny threat model #66.  
**Confidential AI:** wyżej + #69, z osobnym dowodem granicy AI.  
**Virtual Employee:** #63/#64 i osobny audyt uprawnień Windows. Brak automatycznej gwarancji z Nitro.

Klucz kancelarii nie jest wymienny z logowaniem: WebAuthn/QES może potwierdzać tożsamość, ale nie zastępuje atestacji ani nie daje operatorowi klucza. Utrata kopii klucza i hasła może oznaczać nieodwracalną utratę dostępu; CIV-04 eliminuje przypadkową utratę przez praktyczny proces backup/restore, nie przez backdoor.

## Bramka produktowa
- Green CI i symulacja: **gotowy kod do dalszych testów**, nie pozwolenie na realne dane.
- Hardware + izolacja + egress + backup/restore i dokumentacja: **kandydat do kontrolowanego pilota z danymi rzeczywistymi**, po adekwatnym audycie i ocenie prawnej.
- Dopiero niezależnie potwierdzony zakres i #78: **go-to-market z precyzyjnymi claimami**. Nie nazywać „Zero Knowledge” formalnym ZKP ani całego NotarAI pełnym ZOA, jeśli Windows/AI wykracza poza granice.


## Instrukcje dla Opus i gotowe OSS (obowiązkowe)
[**CIV-OSS-OPUS-reuse-playbook.md**](./CIV-OSS-OPUS-reuse-playbook.md) zawiera zweryfikowane repozytoria, pliki źródłowe i licencje, istniejące komponenty NotarAI, mikrofragmenty integracji i gotowy kontrakt sesji. Wszystkie planowane PR #88–#91 i istniejące #66/#69/#72–#78/#63/#64 mają własny rozdział `OPUS — INSTRUKCJA WYKONAWCZA I REUSE OSS` w opisach PR. **Zadania implementacyjne są nadal Draft; dopisanie instrukcji nie oznacza ukończenia kodu.**
