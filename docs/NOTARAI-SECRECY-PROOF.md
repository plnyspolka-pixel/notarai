# NotarAI Secrecy Proof — model gwarancji i dowodów (draft v0.1)

## Cel
Udostępnić notariuszowi niezależnie weryfikowalne dowody zastosowanych zabezpieczeń służących zachowaniu tajemnicy notarialnej. Nie emitować kategorycznego certyfikatu „żaden człowiek nie widział treści”, bo takiej uniwersalnej negacji nie można wykazać z samego logu lub blockchaina.

## Aktorzy i zagrożenia
- uprawniony notariusz / aplikant / sekretariat (w granicach uprawnień),
- członek personelu z dostępem do klienta bez upoważnienia do danej sprawy,
- operator NotarAI, support, admin systemu/aplikacji, administrator chmury,
- podwykonawca/AI provider, usługi logów i backupu, narzędzia analityczne,
- przestępca ze skradzioną sesją lub urządzeniem; administrator z uprawnieniami root,
- incydentalne przetwarzanie po stronie modelu lub przez człowieka podczas wsparcia.

## Ścisłe twierdzenia dowodowe
| ID | Co można poddać audytowi | Warunek dowodu | Czego dowód nie gwarantuje |
|---|---|---|---|
| SP-01 | Operator nie ma klucza do konkretnego ciphertext | key custody po stronie kancelarii, atestowany podpisany klient, brak plaintext upload | ochrony przy skompromitowanym urządzeniu kancelarii |
| SP-02 | Dokument zaszyfrowano przed uploadem | kod klienta + deterministyczny test e2e + metadata AEAD | że nie wykonano równolegle innej transmisji |
| SP-03 | Konkretne zdarzenia dostępu znalazły się w nienaruszonej historii | append-only, sekwencja, podpis, test kompletności, Merkle root | że nie było dostępu poza monitorowanymi ścieżkami |
| SP-04 | Pakiet dowodowy istniał przed określonym blokiem Ethereum | weryfikator tx, recipient, chain id, calldata, confirmations | prawdziwości merytorycznej zdarzeń i chwili konkretnego odczytu |
| SP-05 | Przetwarzanie AI miało określoną konfigurację | model ID, region, polityka retencji, audit artefacts, request class | że fizycznie żaden pracownik dostawcy nigdy nie uzyskał dostępu |
| SP-06 | Odmowa próby nieuprawnionego API | test polityki i odmowy z datą/wersją builda | że nie istnieje nieobjęty testem bypass |

## Tryby
- **Sealed**: klucze u kancelarii, lokalna obróbka, szyfrowanie przed uploadem, serwer nie dostaje plaintextu. Zero-knowledge jest aspiracją wymagającą niezależnego audytu i hermetycznej dystrybucji klienta.
- **Private AI**: osobny status, bo dane trafiają do AWS Bedrock; nie wolno odziedziczyć odznaki operator-blind. Wyświetlaj rzeczywisty region modelu i jego policy, bez marketingowego uproszczenia.
- **Confidential Computing (future)**: atestacja Nitro Enclaves i warunkowe wydanie DEK do określonego pomiaru wykonywanego kodu; wywołanie Bedrock poza enclave jest inną granicą zaufania.

## Przykładowy schemat prywatnego receipt
```json
{
  "schema": "notarai.secrecy.v1",
  "tenant_ref": "pseudonymous-tenant-id",
  "event_id": "uuid",
  "event_kind": "client_side_encrypted",
  "document_ref": "opaque-random-id",
  "client_build_digest": "sha256",
  "encryption_profile": "AES-256-GCM/DEK-v1",
  "key_custodian": "notary-office",
  "processing_mode": "sealed",
  "occurred_at": "RFC3339 timestamp from attested time source",
  "evidence_ref": "private-object-id"
}
```
Nigdy nie publikuj tego JSON w Ethereum. Konieczny osobny podpis/atestacja źródła, sól per zdarzenie, canonical JSON, Merkle proof i kontrola eksportu.

## Minimalny przebieg weryfikacji
1. Weryfikator odbiera *autoryzowany* pakiet dowodowy.
2. Sprawdza podpisy/atestacje i źródło czasu.
3. Sprawdza wersję protokołu, integralność dokumentu lub ciphertext, konfigurację szyfrowania i key custody.
4. Weryfikuje witness Merkle i transakcję Ethereum, jeśli była potwierdzona; wyraźnie rozdziela status „prepared” od „confirmed”.
5. Przedstawia zakres gwarancji, znane nieobjęte ścieżki i identyfikator testowanego builda. Brak danych lub błąd = `NOT_VERIFIED`, nigdy zielona odznaka.

## Integracja z obecnym repo
- `magazyn.py`: dziś magazynuje plaintext po stronie serwera i szyfruje S3 na serwerze; to nie jest ślepe szyfrowanie end-to-end.
- `bedrock.py`: realnie wysyła treść skanów/aktów do modelu; tryb Sealed musi wyłączać te ścieżki lub wykonywać analizę lokalnie.
- `autoryzacja.py`, `stanowiska.py`: kontrola ról i serwisu; obecne zmiany chronią nowy `/api/dowody/*`, ale trzeba zbadać wszystkie historyczne ścieżki pobierania plaintextu.
- `proof_engine.py`, `dowody_ethereum.py`: obecne receipts potwierdzają integralność, nie samą poufność.
- `CLAUDE_ETHEREUM_MISSION.md`: zadania do implementacji.

## Zasada release
Nie wprowadzaj „Tajemnica notarialna kryptograficznie zagwarantowana”. Dopiero po testach i niezależnej weryfikacji konkretnych twierdzeń: „Ścieżka Sealed ogranicza dostęp operatora do kluczy i plaintextu w zdefiniowanym modelu zagrożeń”.
