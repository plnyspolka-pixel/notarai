# NotarAI Virtual Employee - AWS Windows VM pilot

**Status: CloudFormation and code prepared, NOT deployed to AWS.** Synthetic data only. The existing production ECS/Fargate NotarAI application and Confidential Browser/Nitro project are unchanged.

## Architecture

- One dedicated Windows Server 2022 EC2 per tenant (first fictional tenant: `pilot01`), Windows GUI running on AWS, **no NotarAI installation on the notary's computer**.
- Region `eu-central-1` (Frankfurt). Dedicated VPC and a private subnet without Internet Gateway, NAT, public IP, public RDP or other inbound security-group ports.
- Three private AWS Systems Manager endpoints: `ssm`, `ssmmessages` and `ec2messages`. The VM's only network egress is HTTPS to these endpoints. No direct access yet to the production NotarAI API or RejNET servers.
- Official AWS Windows Server AMI, encrypted 100 GiB gp3 system disk, IMDSv2 required, EC2 IAM role with `AmazonSSMManagedInstanceCore`.
- Bootstrap creates protected `C:\ProgramData\NotarAI\VirtualEmployee` folders. **It does not install RejNET, create passwords, run RDP auto-logon or deploy an AI worker.**
- No real notarial files, customer database, PESEL, certificates, passwords or secrets in this pilot. EBS encryption and network isolation alone do not establish Zero Knowledge or Zero Operator Access.

## Files

- `infra/virtual-employee/notarai-virtual-employee-pilot.yaml`: isolated VPC, SSM endpoints, IAM, Windows EC2 and encrypted system disk.
- `infra/virtual-employee/deploy-pilot.ps1`: validates by default; deploys billable resources **only** with `-Apply`, after account and region checks.
- `infra/virtual-employee/check-windows-session.ps1`: Windows/SSM/RDP and interactive session smoke check, no user names in output.
- `agent/NotarAI.VirtualEmployee.Probe/`: read-only UIA3/FlaUI test for *Notepad only*.
- `tests/test_virtual_employee_iac.py`: offline infrastructure security assertions.
- `.github/workflows/virtual-employee-pilot-iac.yml`: AWS-free lint, offline tests, Windows PowerShell parser and .NET compilation.

## Deployment by an authorized AWS administrator

Requirements: an AWS profile with EC2/VPC/CloudFormation/IAM authority for this separate pilot, an EC2 key pair in Frankfurt, AWS CLI v2, Windows PowerShell, Session Manager plugin and cost approval. The existing GitHub OIDC deployment role only allows production `notarai-aplikacja` and must not be broadened silently.

```powershell
# Read-only checks by default, no stack created:
.\infra\virtual-employee\deploy-pilot.ps1 -Profile notarai-admin -KeyPairName <EC2-KEYPAIR>

# Paid creation only after review:
.\infra\virtual-employee\deploy-pilot.ps1 -Profile notarai-admin -KeyPairName <EC2-KEYPAIR> -Apply

aws cloudformation describe-stacks --stack-name notarai-ve-pilot01 --region eu-central-1 --profile notarai-admin --query 'Stacks[0].Outputs'
aws ssm describe-instance-information --region eu-central-1 --profile notarai-admin
```

Wait until the EC2 instance shows `PingStatus: Online` in SSM. If not, inspect endpoint Private DNS and endpoint security-group ingress, EC2 role and SSM Agent service. **Do not expose RDP to the internet.**

### Administrative GUI over SSM

```powershell
aws ssm start-session --target <INSTANCE-ID> `
  --document-name AWS-StartPortForwardingSession `
  --parameters 'portNumber=3389,localPortNumber=13389' `
  --region eu-central-1 --profile notarai-admin
```

Use your local Remote Desktop client to connect to `127.0.0.1:13389`. Decrypt the initial Windows Administrator password locally with the private EC2 key. Never paste credentials into chat, logs, git, documentation, or cloud command output. Provision a dedicated non-admin operator identity separately, using an approved secret-management and access process. Do not enable Windows auto-logon.

**Important:** SSM/RDP tunnel is administrative access, not end-user remote desktop. SSM tunnel contents are not recorded as a full application-action audit. Real notarial operations require a separate, minimal audit design.

### RejNET Office qualification and GUI test

1. Obtain the official installer and vendor confirmation for **RejNET Office (rejnet.pl)** support and licensing for Windows Server on AWS. This is different from KRN's `Rejestry Notarialne` and `appRejnetSign`.
2. Deliver the signed installer through an explicitly approved controlled channel (e.g. RDP drive redirection where allowed); this VPC intentionally has no general Internet egress. Verify publisher signature and package checksum.
3. Install RejNET with a *fictional* test database and a dedicated non-admin operator; test login and local storage, without real client data.
4. Run `check-windows-session.ps1`. Test first with the read-only FlaUI probe: `dotnet run --project agent/NotarAI.VirtualEmployee.Probe -- --inspect-notepad` (requires .NET 8 SDK and NuGet access at build time; run the compiled binary on the isolated VM).
5. Implement a limited RejNET adapter only after confirming its actual UI Automation control tree. Test opening a fictitious case, reading non-sensitive fields, entering a draft, saving and recovering after disconnect/reboot.
6. Stop before any `sign`, `send`, `submit`, `delete`, or irreversible step. Require an explicit notary approval gate for production.

**GUI warning:** UI Automation must run in an *authenticated interactive Windows desktop session*. A standard Windows Service executes in Session 0 and cannot reliably click GUI controls. An SSM command by itself does not create a suitable desktop. A disconnected RDP session may also change UI behaviour. This pilot does not solve unattended session lifecycle; test and design that next.

## Production connection not implemented yet

Planned: authenticated `app.notarai.pl` tenant-scoped API -> private job queue -> VM-bound Windows agent in an interactive session -> FlaUI/UIA3 -> RejNET -> tenant-scoped result. Require job signatures, expiry/idempotency, per-tenant authorization, operation allowlist, consent/approval for irreversible acts, network egress allowlist and audit logs without document contents. No new public API or permissive NAT should be opened just to make the VM connect.

Production hardening: key ownership and operator access boundaries, credential provisioning through Secrets Manager, OS/session lifecycle, vendor license proof, vendor update delivery, patching without general Internet, backup/retention/tenant deletion, emergency access logs, Windows Defender active, Windows/Office/RDS license verification, and independent security review. **Do not market this as zero-operator-access or zero-knowledge while those controls are unimplemented.**

## Billing and cleanup

The stack creates a billed Windows EC2, encrypted gp3 volume, 3 billed PrivateLink interfaces and monitoring. EC2 can be stopped when idle but EBS and VPC endpoint charges persist. This synthetic single-AZ pilot has no HA or automatic shutdown.

```powershell
aws ec2 stop-instances --instance-ids <INSTANCE-ID> --region eu-central-1 --profile notarai-admin
# Once done, remove the pilot stack (only after confirming no customer data exists):
aws cloudformation delete-stack --stack-name notarai-ve-pilot01 --region eu-central-1 --profile notarai-admin
```

## Acceptance criteria

- [ ] Stack validated locally with `cfn-lint` and through real AWS `validate-template`
- [ ] No public IP, no Internet Gateway/NAT, no inbound SG rules, IMDSv2 and encrypted disk
- [ ] SSM online through private endpoints; local RDP tunnel works
- [ ] Defender remains enabled, no antivirus exclusions
- [ ] Signed RejNET installer/licensing verified; GUI/Session 0 and disconnect behavior tested
- [ ] No real case data; staff approvals and audit plan in place before production
- [ ] VM stopped or stack removed after testing; costs reviewed

Sources: [AWS SSM PrivateLink](https://docs.aws.amazon.com/systems-manager/latest/userguide/setup-create-vpc.html), [Windows EC2 user data](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/user-data.html), [official Windows AMI SSM parameter](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/finding-an-ami-parameter-store.html).
