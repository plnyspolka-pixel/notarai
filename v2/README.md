# NotarAI 2.0 — local-first / Bedrock-only

Development track separate from V1. No production deployment or migration.
Run only with synthetic data until security review, AWS policy validation and Windows/mobile integration tests are complete.

## Non-negotiable constraints
- Documents, CRM, indexes, conversation history, audit and keys remain on authorized endpoints.
- AWS Bedrock is the only AI inference provider. Transient inference is not the same as local-only processing. EU-only approved model IDs, retention and invocation logging must be verified before real data can be sent.
- No S3, cloud document persistence, hosted conversation state or cloud fallback.
- Existing V1 and its production configuration remain unchanged. No implicit import.
- Mobile: private authenticated transport, optional encrypted offline replicas, explicit per-device access; reject stale versions, never silently overwrite.
- Offline AI is not available. If all authorized replicas are offline, uncached files are unavailable.
- No extra hardware required. Wake-on-LAN is best-effort.

## What is built

Owner-facing status in Polish: [STAN.md](STAN.md).

| Module | Role |
| --- | --- |
| `worker/vault.py` | Encrypted SQLite revisions. Master key wraps one data key per document; names encrypted apart from bodies; cases; MAC-chained access log; migration from the first single-key format. |
| `worker/recovery.py` | Printable recovery code, backup file (ciphertext only), restore into an empty directory with full verification, interruption-safe master key rotation. |
| `worker/replica.py` | Optional off-site copy of the same backup file to the office's own S3 prefix in the EU. Off by default. |
| `worker/policy.py`, `inference.py`, `pseudonym.py`, `usage.py` | The single path to a model: EU-only model ids and `eu.` profiles verified against the account, no content logging, reversible pseudonymisation, local token ledger. |
| `worker/aws_credentials.py` | Workstation sign-in through Cognito; hour-long credentials that can only invoke Bedrock in the EU. No long-lived AWS key on the computer. |
| `worker/drafting.py`, `docx_writer.py`, `connect_sdk.py` | Case documents to a model draft; the notary approves exact text (SHA-256 bound into the Connect request); DOCX written once and read back before it counts. |
| `worker/workcopy.py` | Edit a vault document in Word or LibreOffice on the workstation; check-in creates the next revision and removes the plaintext working copy. |
| `worker/tunnel.py`, `tunnel.js`, `relay/` | Remote access for paired devices: end-to-end encrypted channel, device-bound non-extractable key, relay that forwards opaque frames and stores none. The worker opens no inbound port. |
| `worker/chat.py`, `pocket.*`, `admin.html` | Chat-first UI: one conversation window for Pocket and for the workstation panel. State-changing commands are matched deterministically, never by a model; irreversible ones need a tapped confirmation. |
| `worker/layout.py` | The notary's own tiles: a label plus the sentence it sends. None by default; per device. |
| `worker/mail.py` | Read-only access to the mail program on the workstation: Thunderbird mbox files, classic Outlook automation, or a folder of .eml files. A message enters the vault only when added to a case. |
| `worker/autofill.py`, `web_fill.py`, `win_fill.py` | Fills a form by itself: matches procedure steps to fields by their visible labels (web pages in a dedicated Edge profile through Playwright; Windows programs through UI Automation), reads every value back, presses navigation buttons, and stops before the sending button. Sending happens on the notary's explicit command („wypełnij … i wyślij”) or after a chat approval, bound to a fingerprint of the previewed form; one press, never retried. |
| `worker/procedures.py`, `transcribe.py` | Teaching by showing: frames and narration from a screen recording become a procedure the notary approves; for a case it yields values per field to copy. Speech-to-text for narrations and voice notes runs in the cloud by default (`cloud_speech.py`: Amazon Transcribe in eu-central-1, recording and result deleted right after reading; voice notes finish in the background and the window polls `/v2/voice/{job}`); local faster-whisper stays available via `speech.where`. Screenshots reach the EU model unmasked, so recordings must use synthetic cases. |
| `worker/rules.py` | The office's hard rules as data with fixed meaning (required/forbidden wording, required form fields, sending hours on Polish working days, pseudonymisation lock). Checked in code before a draft is stored, a Word edit is checked in, a form is sent, or settings change. Sentences the code cannot check are refused. |
| `worker/style.py` | Learns the office's wording from deeds already on its disks, read in place: only sentences repeated across many deeds of a kind (numbers blanked) and their usual order are kept, so client data never enters the profile. Drafts receive them as wording to use verbatim. |
| `worker/listening.py` | Always-on microphones: devices paired with the `listen` scope can only send audio segments. Segments are transcribed locally, joined per microphone into conversations, and filed: a conversation that follows a deed (word-trigram containment, in code) becomes that case's stenogram; others become notes in the case "sekretariat" with a model summary. Audio is never stored. |
| `worker/domain.py` | Deterministic notarial rules shared with V1 as code only (fee engine, amounts in words). |
| `infra/notarai-v2-*.yaml` | CloudFormation for Bedrock access, the relay and off-site copies. Validated, not deployed. |

The constraint "No S3, cloud document persistence" above still holds by default. `worker/replica.py`
is an opt-in exception that stores ciphertext only the office can open; enabling it is an owner decision.

## Release gates before real data
- Owner approval of the AWS stacks and of off-site ciphertext copies.
- Signed installer and update channel; Windows CI green on the service, installer and DPAPI tests.
- Privacy review of pseudonymisation: it is the office's setting (on by default); names not listed for a case reach the model in clear.
- Live relay deployed and exercised; revocation and lost-device drill on real phones.
- Independent security review. `ai.real_data_approved` in `settings.json` stays `false` until then and
  cannot be changed from the application.

## Tests
From `v2`: `python -m pytest -q` (unit and API), `node --test relay/relay.test.mjs` (relay),
`node tests/e2e/pocket.e2e.js python` (Pocket and panel in Chromium, fake model, local relay).
`python tests/live_bedrock.py` is an opt-in live check with synthetic text and ambient AWS credentials.

## Prototype usage
From v2: create a Python 3.11+ virtual environment, install requirements, set NOTARAI_V2_HOME to a local non-synced directory, run python -m worker.init_vault, then python -m worker.api. `python -m worker.pair_cli admin-link` prints a one-time link to the workstation panel; create the recovery code there first (or `python -m worker.recovery enroll`). The initializer prints a bearer token once. Do not store it in a shared or synced directory. New Windows development vaults protect the key and token with Windows DPAPI for the current user. Run pytest -q for tests.

Do not expose the development API to the LAN or internet. No production credentials or data in this public repository.

The [Windows session prototype](WINDOWS.md) covers the local boundary between a background service and an interactive agent.

The [Windows installer](installer/README.md) installs NotarAI 2 (production) for Windows x64; later versions arrive as small code updates.
