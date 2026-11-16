# Finance You — zaszyfrowana baza pośredników KNF
Publiczny URL służy **wyłącznie do pobrania szyfrogramu**. Dane kontaktowe i klucz AES nie są publikowane. Przetwarzanie bazy powinno się odbywać w autoryzowanym środowisku Finance You.

Zawartość archiwum po odszyfrowaniu: `contacts_master_76663.csv`, `quality_report.json`, `README.md`.
Rekordy: 76 663 unikalne adresy. Klasy: 2 260 public_source; 1 064 manual_review; 73 339 generated.
Wariant `generated` zawiera domysły adresów i nie powinien służyć do mailingu.

## Dla Claude Code
1. Pobierz `manifest.json` i `download_and_decrypt.py` z tego katalogu.
2. Utwórz lokalny katalog `data-import/financial-intermediaries/` w repo FINYOU.
3. Ustaw zmienną `FINYOU_KNF_KEY_HEX` na prywatny klucz przekazany osobno przez właściciela.
4. Uruchom `python3 download_and_decrypt.py --manifest manifest.json --out data-import/financial-intermediaries`. Wymaga `cryptography` (`python3 -m pip install cryptography`).
5. Przetwarzaj tylko lokalnie. `marketing_eligible=false` domyślnie; osobno zweryfikuj podstawy prawne dla komunikacji.
6. Nie publikuj odszyfrowanych danych ani klucza w repozytorium, logach czy promptach.

Szyfrogram AES-256-GCM; pliki rozdzielone na części ok. 375 KiB ze względu na limit dostarczania przez API. Każda część i całość są kontrolowane SHA256.
