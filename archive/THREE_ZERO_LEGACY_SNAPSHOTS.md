# NotarAI 3 × ZERO — archiwum wszystkich prac i eksperymentów (2026-11-22)

**ARCHIVE ONLY. Nie scalać tej gałęzi do master ani produkcji.** To backup techniczny i mapa pomysłów, w tym rozwiązań odrzuconych (kustosz, WORM, wiele podpisów, złożone KMS i inne). Główny produkt pozostaje na AWS ECS Nitro **CONFIDENTIAL_SANDBOX**, a to archiwum nie jest propozycją jego rozbudowy.

## Jak archiwum zabezpiecza kod
1. Drzewo początkowe pochodzi z **#87** (`76b741c6a266b713b21ea4f5079db51fe9cdb1fd`), zawiera zależności #86/#68 i historyczne zaplecze.
2. Wszystkie inne wskazane poniżej SHA zapisujemy jako **dodatkowych rodziców archiwalnego merge-commita bez łączenia drzew (archive-only octopus ancestry)**. Dzięki temu historia i pełne pliki każdego PR są osiągalne z gałęzi archiwalnej nawet po usunięciu oryginalnych branchy; brak ryzyka konfliktów, niemożliwego „supermerge” i przypadkowego aktywowania funkcji.
3. **To nie jest jeden działający checkout z każdym równoległym patchem.** W celu odzyskania dowolnego modułu użyj `git show <SHA>:<ścieżka>` lub `git switch --detach <SHA>`. Nie uruchamiaj/nie wdrażaj archiwalnego drzewa.
4. W tym archiwum **nie uruchamiano AWS**, nie scalono PR, nie zmieniono produkcji. Mapa zawiera aktualne SHA z GitHub w chwili snapshotu.

## Inwentarz PR i zapisane rewizje

### 01 base/dispatch/Nitro

| PR | Stan | Snapshot SHA | Kod w historycznej gałęzi | Temat |
|---|---|---|---|---|
| [#40](https://github.com/plnyspolka-pixel/notarai/pull/40) | open | `7153f112ceab09e6b8cd19bcbdb3d3ae459fbdab` | `feature/private-ai-eu-gateway-20261116` | WIP: European Private AI — high-assurance EU inference gateway and negative security tests |
| [#50](https://github.com/plnyspolka-pixel/notarai/pull/50) | merged | `885c45c2144c013c31f8b44328f2b67b5e77fb82` | `feature/confidential-browser-nitro` | Confidential NotarAI: szyfrowanie klienta, Nitro KMS attestation i bezpieczny Playwright |
| [#51](https://github.com/plnyspolka-pixel/notarai/pull/51) | merged | `076ca00e5f1b0f60e462caf9c468bd2eca998836` | `feature/confidential-nitro-bootstrap` | Nitro Bootstrap: oddzielny klaster ECS, capacity provider API i obserwowalność bez danych |
| [#52](https://github.com/plnyspolka-pixel/notarai/pull/52) | open | `2a29de514ff21fe30ffa31934d3de5a530d1349a` | `feature/confidential-pilot-preflight-20261121` | Confidential Browser: blokada startu Nitro przy rozbieżności ECS, PCR17 i KMS |
| [#53](https://github.com/plnyspolka-pixel/notarai/pull/53) | open | `ff6774a1f756639eb39dc3d18b517a8f4bc5ebe6` | `feature/confidential-scheduled-orchestrator-20261121` | Confidential Browser: harmonogram Nitro z blokadą duplikatów i izolacją zadań |
| [#54](https://github.com/plnyspolka-pixel/notarai/pull/54) | open | `20eff926fae03be61d568164b80ee0b4044b4b52` | `feature/confidential-signed-approval-20261121` | Confidential Browser: jednorazowa podpisana zgoda notariusza i anty-replay |
| [#55](https://github.com/plnyspolka-pixel/notarai/pull/55) | open | `1069de52d9ea35e2490c14b8335311915385ce72` | `feature/confidential-auto-preview-default-20261121` | Confidential Browser: AUTO domyślnie, przygotowanie bez zgody i twarda blokada wysyłki |
| [#56](https://github.com/plnyspolka-pixel/notarai/pull/56) | open | `a9a9716c7508c0e360ab6832a0644d37bdcf1f9c` | `feature/confidential-private-egress-20261121` | Confidential Browser: prywatna sieć AWS bez publicznego egress dla pilota Nitro |
| [#57](https://github.com/plnyspolka-pixel/notarai/pull/57) | open | `d2129a8a39ad2855aee9d1c1b5f0ba9d70881cdc` | `feature/confidential-job-ledger-aws-handoff-20261121` | Confidential Browser: trwały lifecycle zleceń + pełne polecenie AWS dla Claude |
| [#58](https://github.com/plnyspolka-pixel/notarai/pull/58) | open | `e677a6bd75f4c88ab9a03ab7154db9c24b6dcc81` | `feature/confidential-ops-control-room-20261122` | NotarAI AUTO: Control Room dla notariusza — podgląd zadań bez możliwości wysyłki |
| [#59](https://github.com/plnyspolka-pixel/notarai/pull/59) | open | `2fe022975f0b2e16cb81e95c1ca038b070007d9d` | `feature/confidential-audit-trail-20261122` | NotarAI AUTO: historia zmian stanu z DynamoDB Streams (audyt metadanych) |
| [#60](https://github.com/plnyspolka-pixel/notarai/pull/60) | open | `44aa2877d31a2023b5732a1b5c1a19f1a7205685` | `feature/confidential-shared-fabric-20261122` | NotarAI Confidential: jeden shared VPC + endpointy + ECS Nitro + ECR dla wszystkich kancelarii |

### 02 IAM/custody/AI/Windows

| PR | Stan | Snapshot SHA | Kod w historycznej gałęzi | Temat |
|---|---|---|---|---|
| [#61](https://github.com/plnyspolka-pixel/notarai/pull/61) | closed | `4c68c3a1b9a29f5e94f23429a9b8aa37a9c48d51` | `feature/confidential-independent-custody-proof-20261122` | [ARCHIVE/SUPERSEDED] Security: external KMS custody + independent Zero Operator Access verification gate |
| [#62](https://github.com/plnyspolka-pixel/notarai/pull/62) | closed | `d68532df0b77e959d4dbb2724d35e319d418880d` | `feature/confidential-independent-release-signoff-20261122` | [ARCHIVE/SUPERSEDED] Security: independent signed Nitro release approval pinned to PCR17, KMS policy and image digest |
| [#63](https://github.com/plnyspolka-pixel/notarai/pull/63) | open | `b860537349aedc04dc4b90b1e3fea1a94a5793bb` | `feature/virtual-employee-architecture-20261122` | NotarAI Universal Computer Agent — Computer Use + Vision + Control Plane + izolacja IAM |
| [#64](https://github.com/plnyspolka-pixel/notarai/pull/64) | open | `df6d78ab6535bda1de2564ba99835a9c19f14c07` | `feat/notarai-virtual-employee-aws-pilot` | feat: Virtual Employee - prywatna VM AWS + podpisany lokalny protokół zadań |
| [#65](https://github.com/plnyspolka-pixel/notarai/pull/65) | closed | `d46e4896fcd0e2cd49295afdc5fd34933db0c68e` | `feature/confidential-custody-verified-launch-20261122` | [ARCHIVE/SUPERSEDED] Security: blokada uruchomienia Nitro bez aktualnej podpisanej zgody niezależnego kustosza |
| [#66](https://github.com/plnyspolka-pixel/notarai/pull/66) | open | `0fc3d99838fba7d8d4bcb8d74540af91c536e1c3` | `plan/confidential-sec-01-threat-claims-20261122` | [SEC-01] Threat model oraz kryteria twierdzeń Zero Trust / Zero Operator / Zero Knowledge |
| [#67](https://github.com/plnyspolka-pixel/notarai/pull/67) | open | `7a67c9293de0906b95c830225933abf043b2ade0` | `plan/confidential-sec-02-operator-iam-org-20261122` | [SEC-02] Kontrola uprawnień operatora AWS, SCP i trybu awaryjnego |
| [#68](https://github.com/plnyspolka-pixel/notarai/pull/68) | open | `d8e4b52f71699fa3ffabca39afa5372954c739cd` | `plan/confidential-sec-03-zk-client-encryption-20261122` | [SEC-03] Zero Knowledge: szyfrowanie klienta, niezależne klucze i bezpieczne odzyskiwanie |
| [#69](https://github.com/plnyspolka-pixel/notarai/pull/69) | open | `4d4fedc1ff709f72978c5e095624aeca2adf8333` | `plan/confidential-sec-04-zk-llm-dataflow-20261122` | [SEC-04] Zero Knowledge: izolacja AI/LLM, inference i wyników |
| [#70](https://github.com/plnyspolka-pixel/notarai/pull/70) | closed | `11e4575a52476aaa4d4f17ddeb34126257478ac1` | `plan/confidential-sec-05-release-enforcement-20261122` | [ARCHIVE/SUPERSEDED] [SEC-05] Bezpieczne wydania: podpis kustosza obowiązkowy dla każdej uruchamianej wersji Nitro |
| [#71](https://github.com/plnyspolka-pixel/notarai/pull/71) | closed | `832b4936e146a9f9cf6a6a9f5c449c360799a445` | `plan/confidential-sec-06-independent-custody-20261122` | [ARCHIVE/SUPERSEDED] [SEC-06] Niezależny kustosz kluczy KMS: konto, onboarding, rotacja, odebranie uprawnień |

### 03 audit/assurance

| PR | Stan | Snapshot SHA | Kod w historycznej gałęzi | Temat |
|---|---|---|---|---|
| [#72](https://github.com/plnyspolka-pixel/notarai/pull/72) | open | `94ca0374866b4f30e7f22676e9cb66e85a194461` | `plan/confidential-sec-07-nitro-hardware-proof-20261122` | [SEC-07] Dowód sprzętowy Nitro/KMS: pozytywne i negatywne testy atestacji |
| [#73](https://github.com/plnyspolka-pixel/notarai/pull/73) | open | `2b7875579e939d11526e010c7709e424f803c001` | `plan/confidential-sec-08-egress-leak-prevention-20261122` | [SEC-08] Ochrona plaintext: izolowany egress, antyeksfiltracja i bezpieczna przeglądarka |
| [#74](https://github.com/plnyspolka-pixel/notarai/pull/74) | open | `45357eabeb6270ad3b9a572904125c8dfab2a423` | `plan/confidential-sec-09-tenant-isolation-20261122` | [SEC-09] Cross-tenant isolation: dwóch fikcyjnych klientów, odmowy IAM/KMS/S3/SQS/ECS |
| [#75](https://github.com/plnyspolka-pixel/notarai/pull/75) | open | `b7f3a76322d4c1f36e78b76e6909d950095344ae` | `plan/confidential-sec-10-zk-data-lifecycle-20261122` | [SEC-10] Zero Knowledge: cykl życia plaintext, retencja, logi, kopie i usuwanie |
| [#76](https://github.com/plnyspolka-pixel/notarai/pull/76) | open | `128848a702358db5b1aacf223b2e1b395206c80a` | `plan/confidential-sec-11-independent-evidence-20261122` | [SEC-11] Niezależny rejestr dowodów: atestacje, release, KMS, IAM i audyt zmian |
| [#77](https://github.com/plnyspolka-pixel/notarai/pull/77) | open | `a7a26f016be08e624ef02fda56f817fec155391b` | `plan/confidential-sec-12-adversarial-e2e-20261122` | [SEC-12] Zintegrowany test atakującego operatora i dwóch kancelarii (release gate) |
| [#78](https://github.com/plnyspolka-pixel/notarai/pull/78) | open | `92b865733d20675b7755b193e3408dc9e7501a15` | `plan/confidential-sec-13-audit-commercial-gate-20261122` | [SEC-13] Niezależny audyt i bramka sprzedaży Zero Trust / Zero Operator / Zero Knowledge |

### 04 utilities/transparency

| PR | Stan | Snapshot SHA | Kod w historycznej gałęzi | Temat |
|---|---|---|---|---|
| [#79](https://github.com/plnyspolka-pixel/notarai/pull/79) | open | `277d957db2794c314854d3d0e0e5c74e3a05fb18` | `research/legaltech-oss-anonymizer-benchmark-20261122` | R&D: LegalTech OSS — syntetyczny benchmark anonimizacji i rejestr zależności |
| [#81](https://github.com/plnyspolka-pixel/notarai/pull/81) | open | `b816563d5db44e050c1e3308d2e32d7e5972660a` | `research/dss-signature-report-triage-20261122` | R&D: DSS — bezpieczna interpretacja raportów podpisów (bez fałszywego QES) |
| [#82](https://github.com/plnyspolka-pixel/notarai/pull/82) | open | `d262702f03964f1940da7d23e3662599fa4a438c` | `fix/kwota-decimal-strict-20261122` | Fix: bezpieczna walidacja kwot aktów notarialnych — Decimal zamiast float |
| [#83](https://github.com/plnyspolka-pixel/notarai/pull/83) | closed | `38865d41efe7df81593a3b10ebae3c981660990d` | `docs/confidential-custody-samorzady-20261122` | [ARCHIVE/REPLACED BY #88] Docs: kierunek Confidential - bez kustosza treści |
| [#85](https://github.com/plnyspolka-pixel/notarai/pull/85) | open | `3bf0373f90f4847f39574125a06a0b69554117df` | `feature/confidential-transparency-log` | Confidential: publiczny rejestr wydań z weryfikacją offline (etap 0) |

### 05 customer-v3/roadmap

| PR | Stan | Snapshot SHA | Kod w historycznej gałęzi | Temat |
|---|---|---|---|---|
| [#86](https://github.com/plnyspolka-pixel/notarai/pull/86) | closed | `e3d573c3d4b3b46d4fe1c741f5fbc03fde4e6874` | `feature/confidential-customer-keys-minimal-20261122` | [EXTRACTED → #88] [SEC-06 simplification] Customer-owned keys: minimal single-job Nitro release prototype |
| [#87](https://github.com/plnyspolka-pixel/notarai/pull/87) | closed | `76b741c6a266b713b21ea4f5079db51fe9cdb1fd` | `feature/sec86-customer-attested-release-20261122` | [EXTRACTED → #88] [SEC-86] Klientowska atestacja AWS Nitro i jednorazowe wydanie DEK bez kustosza |
| [#88](https://github.com/plnyspolka-pixel/notarai/pull/88) | open | `f6516abfd2f1c48165f1ad6f09e3517379d745c8` | `plan/civil-confidential-civ01-clean-base-20261122` | [CIV-01/P0] Czysta baza Confidential v3 bez kustosza — ekstrakcja #68/#86/#87 |
| [#89](https://github.com/plnyspolka-pixel/notarai/pull/89) | open | `69c326181d1e8ac7309c4ba0f6042b550df79cf6` | `plan/civil-confidential-civ02-client-20261122` | [CIV-02/P0] Klient kancelarii v3: bez instalacji, podpisane wydanie i atestacja Nitro |
| [#90](https://github.com/plnyspolka-pixel/notarai/pull/90) | open | `f34ed6e24ae15c08c8fcc8a703c2dbf5a3859879` | `plan/civil-confidential-civ03-guest-20261122` | [CIV-03/P0] Nitro worker v3: S3/SQS, jednorazowy grant, atomowy anty-replay i podgląd |
| [#91](https://github.com/plnyspolka-pixel/notarai/pull/91) | open | `49eae4f7bedcfef8d79642ac9b475fb9637b76ce` | `plan/civil-confidential-civ04-key-recovery-20261122` | [CIV-04/P0] Klucze kancelarii: bezpieczna kopia, odtworzenie i rotacja bez kustosza |

## Decyzje dla nowej głównej gałęzi AWS
- **REUSE:** istniejące `infra/notarai-confidential-task.yaml` (`TrustedExecutionConfiguration.IsolationMode: CONFIDENTIAL_SANDBOX`), KMS attestation, `confidential/worker.py`, `nsm_recipient.py`, generowanie PCR, sieć, ledger, poświadczenia klienta z #86/#87.
- **SIMPLIFY:** jeden ECS Nitro Sandbox na job, jeden klient kancelarii, jeden model AI przez AWS Bedrock zgodnie z zatwierdzonym regionem/retencją, minimum IAM i S3/SQS.
- **ARCHIVE/DO NOT MERGE:** niezależny kustosz, cross-account escrow, dodatkowy blockchain, 3 podpisy retencji, rozbudowane własne frameworki OPA/OpenFGA i osobne VPC na kancelarię.
- **VERIFY:** IAM/KMS admin mutation, przypięte image digest/PCR/attestation policy, operator-controlled JS, plaintext egress/Bedrock logs, przekroczenie zakresu kancelarii; dowody AWS i testy rzeczywiste przed roszczeniem 3×ZERO.

## Odtwarzanie — przykłady
```bash
git fetch origin 'archive/three-zero-legacy-complete-20261122'
git show 76b741c6a266b713b21ea4f5079db51fe9cdb1fd:confidential/customer_nitro_attestation.py
# Alternatywny zestaw testów: checkout konkretnego SHA z tabeli.
git switch --detach <SHA_Z_TABELI>
```

Oryginalne PR-y są niezmienione, ale same nazwy branchy nie są dowodem archiwizacji — dlatego przechowujemy ich commity jako rzeczywistą historię gałęzi archiwalnej.
