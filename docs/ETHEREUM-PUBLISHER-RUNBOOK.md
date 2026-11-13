# Ethereum proof publisher — AWS KMS + Sepolia (feature branch)

## Architecture
- Sealing remains local to existing proof engine (SHA-256 salted commitments → Merkle root).
- `kms_anchor.py` / `scripts/kms_anchor.py` signs EIP-1559 through **AWS KMS asymmetric ECC_SECG_P256K1**. Key `SIGN_VERIFY`, signing algorithm `ECDSA_SHA_256`, `MessageType=DIGEST`. The 32-byte digest is computed via Ethereum Keccak-256. DER signature is converted to canonical low-S (r,s) and the parity bit is recovered against the KMS public key.
- Transaction: 0 ETH sent to the signer's own address, `data = 0x46595031 || 32-byte root`, gas ≤ 25,000, fee caps checked, chain allowlisted. Only a salted aggregate root enters Ethereum, never names, PESEL, KW, document text or direct hashes.
- By default, **Sepolia (11155111)** and dry-run. Broadcast requires an explicit CLI switch. Mainnet additionally requires a second explicit environment approval and human approval outside this tooling.
- Confirmation uses an independent RPC check of sender, recipient, calldata, chain, tx hash, receipt status and confirmation depth. The blockchain proves presence of root at block inclusion, not accuracy of business events or absence of off-platform disclosures.

## Deployment prerequisites (NOT DONE)
1. An EU-region AWS KMS key of type ECC_SECG_P256K1, KeyUsage=SIGN_VERIFY. Use an IAM role restricted to **kms:GetPublicKey** and **kms:Sign** on only that key; no admin, no decryption privileges, no wildcards.
2. AWS workload identity / short-lived role, no static AWS keys in source or runner; AWS CloudTrail auditing of `Sign`; alerts for abnormal volume.
3. Sepolia RPC endpoint over HTTPS, allowlisted outbound host; account derived from KMS public key needs **testnet ETH** to pay gas. No end-user wallet.
4. Restricted API `service_role` token for Finance You stored in AWS Secrets Manager and **not accessible to browser or CI public runner**. Never disclose it to Claude/GitHub logs.
5. Policy on batch sealing, hash checks, daily limit, loss/recovery and dual operator approval before any Mainnet broadcasting.
6. Manual signed release and verified host software build for the NotarAI local client.

## Finance You worker (branch only)
`scripts/anchor_worker.py` reads a prepared batch from private Supabase API. In dry-run it reads without changing state. In broadcast mode it calls `fy_proof_claim_next_batch` (Postgres row lock and `signing` state), signs via KMS, broadcasts and stores the returned hash with `fy_proof_mark_submitted`. Another worker cannot claim the same prepared batch concurrently.

Example dry-run, with credentials provided by authorized AWS execution environment (not pasted into Git):
```sh
python -m pip install boto3 requests cryptography rlp eth-utils eth-keys "eth-hash[pycryptodome]"
python scripts/anchor_worker.py \
  --supabase-url https://YOUR-SUPABASE.supabase.co \
  --rpc-url https://YOUR-TRUSTED-SEPOLIA-RPC \
  --kms-key-id alias/financeyou-ethereum-proof \
  --chain-id 11155111
```

With explicit operator approval **for Sepolia only**, set `FY_ETH_BROADCAST_ENABLED=YES` in the worker environment and add `--broadcast`. This has **not** been done; no Ethereum tx or charge has been generated in this task.

Recovery: if broadcast succeeds but writing tx hash to database fails, **do not automatically unlock or re-sign**. Inspect the signing key address, transaction nonce and mempool/chain and reconcile the signed tx against batch root. Duplicate publication is possible if retry is not managed. Only after reconciliation manually mark the tx hash and run the independent confirmation check.

## NotarAI branch
`kms_anchor.py` is the same KMS signer. The `/api/dowody/partie` endpoint produces Sepolia-root calldata. With an authorized, *separate* signing workflow the root can be published; `/api/dowody/partie/{id}/potwierdz` stores confirmation after checking the tx at `NOTARAI_ETH_RPC_URL` against `NOTARAI_ETH_SENDER`, `NOTARAI_ETH_RECIPIENT` and the batch chain ID.

NotarAI does NOT yet run an automatic batch queue publisher; due to the sensitivity of notarial records this requires detailed IAM, encryption-key custody and a privacy threat model first.

## Known limitations / red lines
- No Mainnet transactions, no funded KMS signer, no production Supabase migration, no AWS IAM permission changes and no active scheduler were performed.
- Gas and RPC fees can vary. Use independent budget caps and cost alerts.
- KMS ECDSA secp256k1 proves one signing key was used. It does **not** itself establish eIDAS/QTSP qualification or that no human viewed data.
- PostgreSQL append-only triggers do not protect against the database superuser or complete system compromise. Independent WORM archival and auditor signature are separate controls.
