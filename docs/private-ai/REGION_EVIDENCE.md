# Read-only evidence gate — source and destination EU residency

Never claim EU-only solely on the string prefix \`eu.\`. Per AWS:
https://docs.aws.amazon.com/bedrock/latest/userguide/inference-profiles-support.html
Bedrock cross-region inference profile routes to the list returned by
GetInferenceProfile. All destination model ARNs are inspected and compared
against an EU member state allowlist (not UK or Switzerland).

Execute BEFORE creating any infrastructure, with READ-ONLY AWS permissions:
\`\`\`sh
python -m private_ai.preflight \
  --expected-account 123456789012 \
  --vpc-id vpc-EXAMPLE \
  --subnet-id subnet-FIRST --subnet-id subnet-SECOND \
  --route-table-id rtb-FIRST --route-table-id rtb-SECOND \
  --model-id eu.anthropic.claude-opus-4-6-v1
\`\`\`
Replace every placeholder. Do NOT use production routes/subnets for this pilot.
The preflight refuses any nonlocal route in the candidate private subnet tables
before the S3 VPC endpoint exists. This is intentionally stricter than a typical
VPC: it will reject VPCs with transit/NAT/peering and existing S3 gateway routes.

This check is a necessary pre-deployment gate, not a complete EU residence
guarantee. It does not prove model availability or IAM permissions, key support
location, logs, prompts stored by sub-processors, network egress on deployed
ENIs, or the full supply chain. Next evidence gate is an independent live
packet/flow log verification on the actual deployed staging workload.
