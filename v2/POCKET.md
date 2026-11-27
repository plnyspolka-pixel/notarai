# Pocket prototype
Local test only, no real notarial files. Start the worker using README.md.
Run `python -m worker.pair_cli invite phone --scope write` and open http://127.0.0.1:8765/v2/pocket on the SAME computer. Enter the one-time code within five minutes. Create or import a synthetic file (up to 20 MiB). Edit UTF-8 TXT files and save revisions. The version selector opens earlier revisions for review or download. Other formats can be stored and downloaded byte-for-byte. To edit a DOCX or PDF externally, download the latest revision, edit it in your application, and upload it as the next revision. If another session saves first, the editor keeps the draft and lets you save it as a separate document. Devices paired with `--scope read` can browse and download revisions. Use `python -m worker.pair_cli list` and `python -m worker.pair_cli revoke DEVICE_ID` to revoke server access.

The current browser UI is responsive but does not yet provide secure remote access or encrypted offline storage. Do not bind the API to 0.0.0.0, expose a proxy, or forward ports. The future native mobile client will use device-bound keys and approved encrypted transport; tokens here are development credentials stored in memory of the open tab. Device registry names and revision IDs are local SQLite metadata, not encrypted yet. Read/write grants are vault-wide, not case-specific. Revocation blocks new requests; it cannot erase existing copies. A manifest comparison assumes one authoritative worker, and does not implement peer-to-peer convergence or a download/apply client. Independently edited copies must be reviewed, not automatically overwritten.

## Since the first prototype
Cases, per-case device grants, the case assistant with approval of drafts, the fee calculator and the
installable shell are described in [STAN.md](STAN.md). Remote access no longer needs a forwarded port:
enable "Dostęp spoza kancelarii" in the workstation panel, scan the QR code with the phone, and the
device keeps a non-extractable signing key in the browser. The relay forwards ciphertext only
(`relay/relay.mjs`). Paragraphs above about tokens in tab memory apply to local pairing on the same
computer; remote sessions use no bearer token at all. Offline replicas on the phone are still not
implemented: when the office computer is off, documents are unavailable.
