# NotarAI Connect
Local Windows integration plane for V2, never deployed with V1. AWS Bedrock only; the adapter runtime itself does not call any model or network.

## Routing priority
1. Vendor-approved API, MCP, native CLI or import/export (prefer official interfaces).
2. Browser DOM / Playwright, for authorized browser sessions.
3. Windows UI Automation via WinApp CLI / FlaUI-MCP in the interactive, non-admin Windows session.
4. UIA combined with image analysis; then Computer Use, only with explicit task scope.
5. Demonstration-based workflow authoring, reviewed and signed before installation.
6. Human intervention. Never switch backend after an uncertain attempted mutation.

CLI-Anything (https://github.com/HKUDS/CLI-Anything) is a harness generator/catalog, not a universal runtime for proprietary apps. Generated harnesses must be inspected, dependency-pinned, tested in an isolated environment, and explicitly approved; no automatic execution of generated code.
Stemma (https://github.com/stemma-sh/stemma) is a candidate for local DOCX tracked changes, not the workflow recorder. Microsoft Record-and-Run (https://github.com/microsoft/Record-and-Run) is a separate candidate for learning by demonstration; any non-Bedrock inference and cloud persistence must be removed or disabled before adoption.

## Adapter profile contract (planned)
- Stable app identifier, vendor, executable signature/version or authorized API endpoint.
- Named business operations, strict typed arguments, data classification, read/write risk and approval policy.
- Explicit selector scope, preconditions, verified postconditions, timeout, idempotency constraints.
- No shell passthrough. No arbitrary paths or URLs supplied by a model.
- Adapter package signature and checksum, dependency lock, synthetic fixtures, compatibility version matrix.
- Execution receipts stored locally; no raw UI snapshots or credentials in telemetry.
- Separate per-app and per-user permissions. Approval binds exact action, parameters, target and expiry.
- Candidate adapter generated locally or from synthetic specs, never auto-enabled. Only signed and verified versions installed.
- App upgrades invalidate compatibility until regression checks pass.

## Current milestone: operator-only read inspection
Install and verify Microsoft WinApp CLI independently; use the absolute path to the trusted executable. Start an isolated Windows session with synthetic test apps and no real client records. From v2:
    python -m worker.winapp_adapter --winapp "C:\path\winapp.exe" --synthetic-only
    python -m worker.winapp_adapter --winapp "C:\path\winapp.exe" --hwnd 123456 --synthetic-only
The first command lists windows; the second inspects a selected window. Output can contain sensitive UI text; do not save or forward real snapshots. The synthetic flag is an operator attestation, not a technical classifier. The adapter is not exposed through Pocket/API, does not invoke clicks, and does not yet validate binary signatures or process ownership. Current tests use a fake subprocess, not actual Windows apps.

## Release gates
Real Windows interactive-session smoke tests, process/window identity verification, signed binary verification, bounded outputs and process isolation, session lock, role and per-app allowlists, safe local auditing, signed procedure registry, and synthetic RejNET integration trial. Add production writes only with independent verification and explicit approval for consequential actions. No real document data to Bedrock before retention, region and legal review gates.

## Connect SDK v1: inspect a vault DOCX revision

From `v2`, use `python -m worker.inspect_docx DOCUMENT_UUID REVISION --synthetic-only --approve` with a synthetic development vault. The operator's local session grants `inspect_docx` to the pinned WordprocessingML adapter. Consent binds the complete v1 request, including the parser identity, UUID and revision. The SDK uses it once and expires pending consent after 60 seconds. Probes can select another registered backend before dispatch. After dispatch the SDK verifies the reported revision and records the outcome, with no retry on an uncertain result.

The adapter reads the selected encrypted revision into memory, checks package size and part limits, then uses [python-docx 1.2.0](https://github.com/python-openxml/python-docx/tree/v1.2.0) (MIT) with lxml 6.1.3. Inspection returns counts of direct body paragraphs and tables. Headers, nested table content and paragraphs wrapped in tracked changes are outside that count. Document bytes and text do not enter the result. The operator can inspect synthetic `.docx` files from Microsoft Word or LibreOffice Writer. The automated Writer test generates a fresh DOCX in an isolated profile. Native Word and RejNET integration require separate tests.

Receipts are kept in `connect-receipts.sqlite3` in the local development vault directory. They contain operation, parser identity, time and outcome. A `started` receipt without a terminal state indicates an interrupted inspection. Receipt rows omit the document UUID, revision, token and document content. The CLI is a local operator entry point, outside the development HTTP API and Windows service.

## Connect SDK v1: approved DOCX write and desktop editing
`write_docx` stores reviewed text as a DOCX revision. The request carries the SHA-256 of the text, the
case, the file name, an optional base revision and an optional office template taken from the vault.
Approval is single-use and bound to those exact fields; content that differs from the approved hash is
refused before any adapter runs. After the write the SDK reads the stored revision back and compares
the text hash; a mismatch is `uncertain`, recorded in the receipt, and never retried.

`worker/workcopy.py` is the first integration with Word and LibreOffice that changes documents. It
uses the file interface (the top routing tier), not UI automation: check-out writes a working copy and
opens it with its registered application, check-in refuses while the editor's lock file exists, and a
newer vault revision keeps the working copy instead of overwriting either side. Verified with a real
LibreOffice round trip; Microsoft Word uses the same mechanism and still needs a run on Windows.
