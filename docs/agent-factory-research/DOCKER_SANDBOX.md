# Agent Forge — docker test sandbox scaffold

A new isolated-code test runner exists at tools/agent_factory/forge_sandbox.py. It stages a synthetic Python solution and fixed, read-only test file in a fresh workspace, builds a Docker command with pinned image digest, network=none, read-only root FS, non-root uid, dropped capabilities, resource limits, and disabled external image pulls. It never evaluates untrusted Python on the host.

Default is STAGE ONLY. Container execution requires explicit operator flag and environment variable AGENT_FORGE_ALLOW_DOCKER_TEST=I_APPROVE_ISOLATED_SYNTHETIC_TEST, plus a locally cached image pinned by sha256. Test suite uses mocked subprocess and does not execute any Docker containers or cloud workloads.

CRITICAL SECURITY LIMITATIONS: Docker shares the host kernel and its daemon is privileged. This is not an adequate security boundary for hostile arbitrary model-generated code on a machine with customer data or credentials. Execute only in a separate disposable VM, without host secrets, IAM role, Docker socket inside container, privileged browser profiles or corporate network access. Docker daemon should not be reachable by model-generated code. Confirm networking restrictions externally and test for escapes before enabling generated code.

No container was started in GitHub CI. No model-generated code is executed at this stage. The CLI stages only a hardcoded safe example, proving packaging and command policy.
