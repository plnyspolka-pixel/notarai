# SEC-08 | Anti-exfiltration evidence register (synthetic only)

Status: **IN PROGRESS / DRAFT**, 2026-11-22. Live AWS Nitro test **NOT PERFORMED**.
No client documents, secrets, real URLs or screenshots were accessed.

## Implemented on PR #73

- `confidential/egress_guard.py`: exact pinned GET (no query/userinfo/fragment,
  custom headers, IP destination or nonstandard TLS port); rejects POST and
  all routes after the initial navigation. No browser egress while confidential
  field values are present. Strictly preview-only.
- `confidential/form_engine.py`: attaches interception before `goto`; always
  locks in a finally block before form fill; rejects same-origin redirects to
  non-pinned paths. WebSockets remain disabled by the original context control.
- `scripts/probe_confidential_adversarial_browser.py`: hostile HTML/JS runs in real local Chromium with synthetic GET-query, POST, image, beacon and requestSubmit exfil attempts. Zero collector hits required; this is not a Nitro proof.
- `test_confidential_egress_adversarial.py`: synthetic positive/negative
  requests for GET query, POST, redirect, custom headers, DNS-based names,
  IPv6 literals, S3 URL, model-output URL, metadata, URL path, GET body and
  any request after secret-filled DOM.
- `scripts/verify_confidential_egress_live.py --check`: exits 2 / BLOCKED
  unless a real independent attested guest test is built and performed.
- `.github/workflows/confidential-browser.yml`: includes the new test file.

## Threat surfaces and enforcement boundary

| Exit channel | Current independent boundary | Remaining validation |
| --- | --- | --- |
| GET query/URL path/redirect | VPC guest SG denies ordinary public outbound; browser pins initial GET | Real guest negative probe, DNS proof |
| HTTP POST/body/headers/cookies | VPC guest SG; browser locks before values and strips request headers | Guest/parent raw-socket and cookie/browser bypass test |
| DNS tunneling | **NOT PROVEN**: VPC resolver may bypass Security Group filtering | DNS Firewall plus enclave/parent captures and active probes |
| IPv4/IPv6/raw sockets | Dedicated SG and private route fixture; no wildcard | Actual guest ENI, IPv6 routes/assignments and network tests |
| S3 presigned URLs | Endpoint route + assumed IAM scoping; **not independent proof** | Bucket policy, endpoint policy, IAM explicit deny, active exfil tests |
| AWS APIs/KMS/DynamoDB/SQS | Interface/gateway endpoints and identity checks | Verify request policies and deny wrong-account/wrong-tenant |
| Logs/stdout/stderr/traces | Worker prints only exception *class*; no payload in intended journal | Grep actual CloudWatch/CloudTrail/guest/proxy evidence |
| Screenshots/downloads | AUTO downloads disabled; no result screenshot stored | Confirm Chrome process/network and crashdump suppression |
| Model inference / model output | No model invocation in fictional worker | Separate SEC-04 inference egress and retention audit |
| Parent host / proxy / WebRTC | **NOT PROVEN** by Playwright | Independent host, proxy, DNS, WebRTC and off-enclave traffic test |
| External forms / send / sign | AUTO preview-only, HTTP requests locked before form fill | Real hostile HTML/JS + guest network probe |

Browser routing is **not** a security boundary against a malicious host or
Nitro parent, nor a reliable defense against the VPC resolver. The existing
private network validator proves only the inventory provided to it and
does not independently verify live effective permissions. AWS endpoint access
must be scoped to approved resources: a gateway prefix list is **not** an
S3-bucket allowlist.

## K1-K6 review (not a release authorization)

| Criterion | Status | Evidence still needed |
| --- | --- | --- |
| K1 full independent exit inventory | BLOCKED | DNS, host, S3 policy and model controls |
| K2 nine negative exfil proofs | BLOCKED | Offline tests alone cannot prove collector received zero live packets |
| K3 real guest egress boundary | BLOCKED | Active AWS ENI + task + routing audit |
| K4 fictional preview / final no-submit | UNVERIFIED | Green CI at current SHA and hostile-page execution |
| K5 actual logs contain no canary | BLOCKED | Actual AWS CloudWatch/proxy/flow/guest logs |
| K6 real independently verified Nitro egress | BLOCKED | Actual authorized hardware test, custodian/auditor evidence |

### Required independent audit checklist

1. Confirm signed release approval and PCR/task image under SEC-05/SEC-07.
2. Confirm operator and parent host cannot alter permitted egress under SEC-02.
3. Check exact ENI, VPC route tables, subnet public IP and IPv6 state,
   security groups, NACLs, VPC endpoints, policies and DNS resolver controls.
4. Capture actual guest/host negative probes using synthetic markers only:
   GET query, path, header, POST, redirect, DNS, IPv6, S3 URL, AWS API,
   model output, WebRTC and native sockets.
5. Capture absence of markers in external collectors and CloudWatch/traces,
   with independent verifier signatures and tamper-evident artifact hashes.
6. Preserve metadata-only evidence and provide time, tester, role,
   current HEAD SHA, executable commands and CI conclusion.
7. Until every K1-K6 is PASS, keep this PR **DRAFT**, production **OFF**,
   and prohibit unqualified Zero Knowledge / Zero Operator Access claims.

Commands:
- Offline: `python -m pytest -q test_confidential_egress_adversarial.py`
- Live gate: `python scripts/verify_confidential_egress_live.py --check`
  (exit 2 means BLOCKED; it MUST NOT be recorded as PASS).
