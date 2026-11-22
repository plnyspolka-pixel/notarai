# NotarAI Confidential — rejestr zabezpieczenia i porządkowania PR, 2026-11-22

Status: **W TRAKCIE.** Ten plik jest manifestem źródeł, nie akceptacją wdrożenia. `master` pozostaje bez zmian.

## Wykonana ekstrakcja do #88 (CIV-01)

Źródła: [#86](https://github.com/plnyspolka-pixel/notarai/pull/86) (`e3d573c3d4b3b46d4fe1c741f5fbc03fde4e6874`), [#87](https://github.com/plnyspolka-pixel/notarai/pull/87) (`76b741c6a266b713b21ea4f5079db51fe9cdb1fd`).

| Przeniesiony artefakt | Źródło | Rola |
| --- | --- | --- |
| `confidential/customer_release.py` | #86 | AES-GCM/RSA, single-job grant; nie loguje prywatnych kluczy |
| `confidential/customer_origin.py` | #86 | Ed25519 signed origin of ciphertext |
| `confidential/customer_nitro_attestation.py` | #87 | client-side NSM COSE, pinned root, PCR + nonce |
| `confidential/customer_attested_release.py` | #87 | weryfikacja przed rewrap DEK |
| `confidential/customer_guest_v3.py` | #87 | per-job guest session; nadal bez produkcyjnego schedulera |
| `scripts/customer_attested_release.py` | #87 | lokalny CLI tylko do prototypu |
| `confidential/nsm_recipient.py` | #87 | adapter NSM z opcjonalnym nonce/user_data; zachowuje poprzednie API |
| `test_customer_release.py` | #86 | roundtrip + denial + signed origin |
| `test_customer_attestation.py` | #87 | syntetyczne COSE/X509/nonce/PCR/adversarial |
| `test_customer_guest_v3.py` | #87 | guest one-shot i signed manifest |
| `.github/workflows/confidential-customer-v3-baseline.yml` | CI #87 zaadaptowane | testy offline bez AWS |

Wyłączone celowo z ekstrakcji: `#68` jako cała gałąź, stare KMS custodian i signer, stary `nsm_recipient` bez nonce/user_data, produkcyjne przełączenie v2->v3, browser UX #89, S3/SQS worker #90. **Żaden test syntetyczny nie dowodzi sprzętowej atestacji na AWS.**

## LEGACY: zamknięte bez merge — nie scalać do v3

| PR | HEAD w dniu przeglądu | Dlaczego zamknąć | Zachować do ponownego użycia |
| --- | --- | --- | --- |
| [#61](https://github.com/plnyspolka-pixel/notarai/pull/61) | `4c68c3a1b9a29f5e94f23429a9b8aa37a9c48d51` | zewnętrzny KMS custodian | negatywne przypadki IAM/key policy, jeśli niezależne od kustosza |
| [#62](https://github.com/plnyspolka-pixel/notarai/pull/62) | `d68532df0b77e959d4dbb2724d35e319d418880d` | custodian-signed release | wzorzec pinning/replay/digest dla #76 |
| [#65](https://github.com/plnyspolka-pixel/notarai/pull/65) | `d46e4896fcd0e2cd49295afdc5fd34933db0c68e` | launch gate zależny od podpisu kustosza | fail-closed weryfikacja task/PCR/IAM dla #72 |
| [#70](https://github.com/plnyspolka-pixel/notarai/pull/70) | `11e4575a52476aaa4d4f17ddeb34126257478ac1` | SEC-05 w starym modelu custody | testy supply-chain, image digest, rollback dla #76 |
| [#71](https://github.com/plnyspolka-pixel/notarai/pull/71) | `832b4936e146a9f9cf6a6a9f5c449c360799a445` | custody lifecycle/onboarding | all-keys-history negative tests (zaadaptować do customer-owned bez KMS custodian) |

Zamknięcie PR nie usuwa commitów ze wskazanych refów ani ich historii w GitHub. Nie usuwać ich branchy, dopóki odpowiednie negatywne testy nie zostaną ocenione w #72/#76. Źródła są wyłącznie do selektywnego odczytu.

## Pozostałe źródła oraz historyczne PR (zachować do odczytu)

- [#68](https://github.com/plnyspolka-pixel/notarai/pull/68) `d8e4b52f71699fa3ffabca39afa5372954c739cd`: client JS/HTML, origin, document registry; **nie merge całej gałęzi custody**; browser UI do #89, S3/versioning do #90.
- [#60](https://github.com/plnyspolka-pixel/notarai/pull/60) `44aa2877d31a2023b5732a1b5c1a19f1a7205685`: shared VPC/ECS, selective reuse w #90/#74; `mergeable=false` w dniu przeglądu.
- [#83](https://github.com/plnyspolka-pixel/notarai/pull/83) `38865d41efe7df81593a3b10ebae3c981660990d`: **zamknięty jako historyczna dokumentacja**; aktualne decyzje zapisane w CIV-00 i CIV-01.
- [#85](https://github.com/plnyspolka-pixel/notarai/pull/85) `3bf0373f90f4847f39574125a06a0b69554117df`: transparency log powiązany z podpisem kustosza. Opcjonalna adaptacja do #76, bez mnożenia rejestrów.
- [#63](https://github.com/plnyspolka-pixel/notarai/pull/63) / [#64](https://github.com/plnyspolka-pixel/notarai/pull/64): Python control plane i Windows .NET agent; **jeden wspólny job contract**, osobny produkt od Nitro.
- [#69](https://github.com/plnyspolka-pixel/notarai/pull/69): osobny Confidential AI, nie blokować produktu bez AI.

## Gates dla następnych sesji

1. #88: świeży green CI (w tym testy negatywne v3 i brak brakujących importów); bez merge na `master` przed review.
2. #89/#90: kontrakt API versioned i end-to-end, fail-closed na zmianę klucza/PCR, nie budować drugiego ledger/SQS.
3. #72/#73/#74/#75/#76/#77: **realny dowód sprzętowy i odmowy** z bezpiecznym budżetem i danymi syntetycznymi.
4. #78: dopiero po dowodach, RODO i niezależnym przeglądzie. Windows i Bedrock nie dziedziczą claimów Confidential Documents.
5. **#86/#87 zamknięte**, kod/testy przeniesione do #88; 4/4 workflow na SHA `22cbcd8a3612bdc9d226901708bda9832238bb06` zielone. **#68 nadal otwarty** jako źródło klienta JS/HTML i registry dla #89/#90. Przed przełączeniem produktu przegląd niezgodności v2/v3.
6. **#83 zamknięty** jako zastąpiona dokumentacja, source SHA zachowany. **#82 CI zielone** na `d262702f03964f1940da7d23e3662599fa4a438c`, status Ready for review bez merge.
7. Pozostałe blokady: #63 — 10 realnych nieudanych testów po instalacji zależności; #72 — 2 błędy testów legacy custody-v1/v2. Żadna z tych blokad nie powinna być obchodzona przez zmianę testów na sztuczny PASS.

Główny rejestr porządkowy: [#92](https://github.com/plnyspolka-pixel/notarai/issues/92).
