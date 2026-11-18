# Synthetic coding-worker evaluation — task 001

Scope: tools/agent_factory and test_agent_factory.py ONLY. Do not touch application behavior, deployments, AWS resources or any file holding case/customer data.

Find one edge case missing from the endpoint and task-path validation utilities and add a focused regression test. If a bug is found, fix it with the smallest possible patch. Do not install dependencies or contact any network service. Run: python -m pytest -q test_agent_factory.py.

Expected result: one reviewable diff, a test that fails before the fix and passes afterward, and a short report of changed paths, test status, and limitations. If no trustworthy bug exists, explain why and make no code changes.

All data must be synthetic. Never read or access dane/, any .env file, credentials or browser profiles.
