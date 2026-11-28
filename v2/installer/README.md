# NotarAI V2 Preview for Windows x64

Run `NotarAI-V2-Setup-x64.exe` and launch **NotarAI V2 Preview** from the Start menu. Setup installs for the current user and includes a private Python runtime. Pocket opens in the default browser on `127.0.0.1`. Paste the one-time code from the NotarAI console to connect. The **Nowy kod parowania** shortcut in the Start menu replaces the pending code and gives you five more minutes. Clicking the main Start menu entry again opens Pocket from the existing worker. Press Ctrl+C in the main NotarAI console to stop the worker. Use synthetic documents only.

The assistant is off until the notary writes „włącz asystenta” in the workstation panel and signs in with a NotarAI account in the `notarai-v2` group; service addresses come from `preset.json`. Its encrypted test vault uses the current Windows user's DPAPI and lives under `%LOCALAPPDATA%\NotarAI\V2-preview`. Uninstalling removes the program and shortcut and preserves the test vault. The preview installer is unsigned.

## Build and verify

On Windows x64 with Python 3.14, run `./v2/installer/build.ps1 -OutputDirectory ./dist` from the repository root. The build uses the official CPython 3.14.10 embeddable package, the pinned V2 dependency constraints and Inno Setup 6.4.3. Both tool downloads are verified against their SHA-256 digests. [CPython embedding guide](https://docs.python.org/3.14/using/windows.html#the-embeddable-package) · [Inno Setup license](https://github.com/jrsoftware/issrc/blob/is-6_4_3/license.txt)

GitHub Actions builds the installer and installs it in a disposable Windows profile. It checks the two Start menu shortcuts, verifies that opening the app twice uses the same worker and exercises the code replacement command. It pairs Pocket in Edge, reopens a synthetic document after a forced process exit and verifies uninstall. The job uploads the tested EXE as an artifact.
