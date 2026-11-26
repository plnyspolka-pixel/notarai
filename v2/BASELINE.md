# V2 test baseline

The original suite at `9a5fd0f0b373b670664f5f3d9980bdf71ca69563` ran with `python -m pytest -q` from `v2`.

| Environment | Output |
| --- | --- |
| Local Linux x86-64, CPython 3.11.18 | `20 passed, 1 warning in 0.54s` |
| [GitHub-hosted Ubuntu](https://github.com/plnyspolka-pixel/notarai/actions/runs/45818012945/job/139902648312) | `20 passed, 1 warning in 0.59s` |
| [GitHub-hosted Windows, CPython 3.11.9](https://github.com/plnyspolka-pixel/notarai/actions/runs/45818012945/job/139902648930) | `20 passed, 1 warning in 1.89s` |

Starlette reported a deprecation warning for its HTTPX-backed TestClient on both operating systems. The baseline pins that tested client. TestClient exercises HTTP handlers in-process. Bedrock and the original WinApp unit tests use fakes.

Reproduce with a fresh Python 3.11 virtual environment. From `v2`, run `python -m pip install -r requirements.txt`, `python -m pip check` and `python -m pytest -q`. The CI jobs run on pushes to V2 and on PRs targeting V2.

The V2 suite is collected under `v2/pytest.ini` so the repository-root V1 test job can use its own dependency set. Invocation from the repository root can select V2 explicitly with `python -m pytest -c v2/pytest.ini v2/tests`.

The Windows job checks the SHA-256 of the upstream x64 WinApp CLI release archive and invokes the installed binary with `--version`. The opt-in test creates a disposable Tk window, discovers its HWND using `winapp ui list-windows --json`, and checks the same window with `winapp ui inspect -w <hwnd> --depth 3 --json`. The `v0.8.0` tag documents the inspection envelope and its source emits a bare array for window listing. The test requires an interactive Windows desktop and a trusted binary specified by `NOTARAI_V2_TEST_WINAPP`. [Release](https://github.com/microsoft/winappCli/releases/tag/v0.8.0) · [Inspect output](https://github.com/microsoft/winappCli/blob/v0.8.0/plugins/winapp/skills/winapp-ui-automation/references/ui-json-envelope.md) · [List implementation](https://github.com/microsoft/winappCli/blob/v0.8.0/src/winapp-CLI/WinApp.Cli/Commands/UiListWindowsCommand.cs)
