# High-Assurance Security Foundation — imported research prototype

Original source: high_assurance_security_starter.zip, 2026-11-15, from the user's previous security research conversation. This code is a lab reference, not a production-grade, audited, certified or deployed trust service.

Contents:
- policies/openfga.fga: object access relations for case/document examples
- policies/gateway.rego: OPA policy, deny by default; delegated agent actions and approval
- policies/gateway_test.rego: illustrative OPA checks
- auditlab/audit.py: SHA-384 log with Ed25519-signed checkpoints
- tests/test_audit.py: tampering and truncation regression tests

Run from this folder:
    pip install -r requirements.txt
    python3 -m unittest discover -s tests -v
    opa test policies -v          # optional, requires OPA v1 CLI installed

Never commit generated .pem keys or customer records. Local demo key-generation stores an unencrypted private key and is strictly prohibited for production use. The single-writer log is neither transactional nor externally witnessed. A signer with stolen key can forge new signed receipts; a proper witness is an independently controlled trust boundary.

For production research, see ../docs/security-architecture.md (KMS/HSM, TEE, mandatory approval and independent witness requirements).