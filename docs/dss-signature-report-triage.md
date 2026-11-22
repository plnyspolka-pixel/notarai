# NotarAI: DSS SimpleReport offline triage — R&D

**Scope:** independent, read-only interpretation of a DSS SimpleReport XML that an authenticated DSS service has already generated. This project **does not validate a signature**, prove signature qualification, authenticate a validation report, fetch Trusted Lists, perform certificate path validation or establish that a document may legally be signed electronically.

## Key distinction

- `Indication=TOTAL_PASSED` means a DSS validator *reports* a passed cryptographic/policy outcome. It is not proof of a qualified electronic signature (QES).
- `SignatureLevel=QESig` is a *reported candidate* for QES (different from qualified electronic seal, `QESeal`). NotarAI never changes `qualified_signature_confirmed` to true.
- `TOTAL_FAILED` means *reported* failure, `INDETERMINATE` means unresolved validation and must not be treated as valid.
- Missing scope, partial coverage, countersignatures always require separate review.
- An adversary can forge XML. Never trust reports that are not authenticated and independently bound to the exact uploaded file by a trusted service. SHA256 here is a record of local bytes, not a cryptographic link to the report.

## Usage on fictional test material

```bash
python -m tools.signature_policy --report sample-simple-report.xml --document sample-signed.pdf
python -m pytest -q test_signature_policy_gate.py
```

No network or external binaries. Output is JSON counts, categories and hashes only; names, source XML and file contents are not echoed. The summary is *always* `manual_review_required=true`, `qualified_signature_confirmed=false`, `production_approved=false`.

## Source and licenses

- European Commission DSS [home](https://ec.europa.eu/digital-building-blocks/sites/spaces/DIGITAL/pages/467109107/Digital+Signature+Service+-+DSS), [source](https://github.com/esig/dss); official schema: `dss-simple-report-jaxb/src/main/resources/xsd/SimpleReport.xsd`. Current DSS version in Commission docs on 22.11.2026: **6.5.1** (October 2026). DSS license LGPL-2.1.
- [toresoft/sign-verify](https://github.com/toresoft/sign-verify) has contradictory license indicators (LICENSE = GPL-3.0, README = LGPL-3.0, OpenAPI = Apache-2.0). No third-party code imported from it. Its API illustrates that a top-level `TOTAL_PASSED` result can be returned without making a legal qualification determination.
- EU Trusted Lists version TLv6 is relevant from 29 April 2026; a production bridge must use up-to-date trusted lists and official validation policy. Missing or stale trust data must be treated as indeterminate, not as success.

## Required next phase before operational use

1. Stand up pinned DSS in an isolated EU environment (no external service for documents). Verify library and transitive dependencies, licenses and SBOM, with explicit TLv6 support.
2. Validate reference fixtures (valid/invalid/expired/revoked/QES/eSeal/multiple-signatures/partial coverage/countersigned) using an actual DSS service and preserve full internal diagnostic evidence without PII in logs.
3. Design an authenticated report transport bound to the SHA256 of each uploaded signed document, avoiding unsigned XML as an authority.
4. Show detailed validation outcomes to the notary for review. Never automatically mark an act properly signed based solely on this triage result.
5. Only separately approved and tested production integration may use these summaries; nothing in this PR changes the app or automates signature acceptance.
