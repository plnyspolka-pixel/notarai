# NotarAI — Microsoft Edge Add-ons

The existing extension in the directory rozszerzenie/ works on Chromium
(Chrome and Microsoft Edge). There is ONE source of truth: do not fork
the extension engine or remove its hard stops for submitting, signing,
paying, deleting, or filling passwords/PINs.

## Test locally (no developer account required)

1. Open edge://extensions in Edge.
2. Enable Developer mode.
3. Click Load unpacked / Załaduj rozpakowane.
4. Choose the existing rozszerzenie/ folder. Alternatively, unpack
   the ZIP from GitHub Actions and choose that folder.
5. Open the NotarAI side panel, pair with the logged-in demo tenant
   via app.notarai.pl, and test on authorized test pages.
6. Check domain-by-domain permission prompts, iframes, disconnect,
   the stop button, and refusal to submit/sign/pay or type a PIN.

Do not confuse this with the Microsoft Store desktop application.
Edge extension publishing is a separate Microsoft Edge program.

## Build two distribution packages

Run: python scripts/build_browser_extensions.py

Outputs:
- dist/extensions/NotarAI-chrome-<version>.zip
- dist/extensions/NotarAI-edge-<version>.zip

Both are built from the identical Manifest V3 code. Manifest is at
the ZIP root. Dev-only files/tests are excluded. GitHub Actions
workflow "NotarAI - Chrome i Edge ZIP" runs extension unit tests,
verifies packages and provides downloadable ZIP artifacts.

## Publish to Microsoft Edge Add-ons

1. Create/enroll a Partner Center developer account:
   https://partner.microsoft.com/dashboard
2. Microsoft says there is no registration fee for the Edge extension
   program. The Primary Owner needs a Microsoft account (MSA), not just
   an organization/work account. A GitHub account can be used to
   establish the required Microsoft account.
3. Choose Company for the actual legal owner of the NotarAI product.
   Prepare company verification; account type cannot be changed later.
4. After approval, start a new extension submission, upload the
   NotarAI-edge ZIP, and provide category, description, listing media,
   support contact and public privacy-policy URL as requested.
5. Supply a safe, isolated DEMO account and test instructions to
   Microsoft reviewers. Never expose actual notarial files.
6. Submit for certification; only publish the store URL on notarai.pl
   after Microsoft approves and assigns a permanent listing URL.

References:
https://learn.microsoft.com/en-us/microsoft-edge/extensions/publish/create-dev-account
https://learn.microsoft.com/en-us/microsoft-edge/extensions/publish/publish-extension
https://learn.microsoft.com/en-us/microsoft-edge/extensions/developer-guide/port-chrome-extension
https://learn.microsoft.com/en-us/microsoft-edge/extensions/developer-guide/sidebar

## Permissions and safety

The optional site permission remains granted per site. No
debugger/nativeMessaging and no automatic permanent all-sites access.
The user personally confirms final sending, filing, electronic signing
and payments. The extension must not capture passwords or PINs.

Status: package automation prepared; Edge browser smoke test,
Partner Center registration and store certification still required.
