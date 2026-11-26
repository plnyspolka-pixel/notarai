# NotarAI V2 Preview for Windows x64

Run `NotarAI-V2-Setup-x64.exe` and launch **NotarAI V2 Preview** from the Start menu. Setup installs for the current user and includes a private Python runtime. Pocket opens in the default browser on `127.0.0.1`. Paste the one-time code from the NotarAI console to connect. Use synthetic documents only. Press Ctrl+C in the console to stop the local process.

The preview runs with Bedrock disabled. Its encrypted test vault uses the current Windows user's DPAPI and lives under `%LOCALAPPDATA%\NotarAI\V2-preview`. Uninstalling removes the program and shortcut and preserves the test vault. The preview installer is unsigned.

## Build and verify

On Windows x64 with Python 3.14, run `./v2/installer/build.ps1 -OutputDirectory ./dist` from the repository root. The build uses the official CPython 3.14.10 embeddable package, the pinned V2 dependency constraints and Inno Setup 6.4.3. Both tool downloads are verified against their SHA-256 digests. [CPython embedding guide](https://docs.python.org/3.14/using/windows.html#the-embeddable-package) · [Inno Setup license](https://github.com/jrsoftware/issrc/blob/is-6_4_3/license.txt)

GitHub Actions builds the installer, installs it in a disposable Windows profile, pairs Pocket in Edge, saves a synthetic document, reopens it after restart and tests removal of the program. The job uploads the tested EXE as an artifact.
