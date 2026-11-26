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
