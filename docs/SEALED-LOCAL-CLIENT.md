# NotarAI Sealed — lokalna aplikacja i łańcuch zaufania

## Fakt wdrożenia
`notarai_sealed_v2.py`: CLI przeznaczone do pracy całkowicie offline. Każdy dokument ma losowy 256-bitowy DEK, a DEK jest indywidualnie opakowany X25519 + HKDF-SHA256 + AES-256-GCM dla 1–16 wskazanych publicznych kluczy kancelarii. Prywatny klucz X25519 jest generowany na urządzeniu kancelarii i zapisywany jako zaszyfrowany PKCS8, nie trafia do NotarAI. Kopia publiczna może być udostępniana innym osobom w kancelarii. `grant` dodaje kolejnego odbiorcę BEZ udostępniania jawnej treści do operatora.

`sealed_release.py`: niezależne podpisywanie i weryfikacja manifestu Ed25519, chroniącego SHA-256 artefaktów. Klucz prywatny podpisującego musi pozostać **offline**, poza GitHub i poza systemem NotarAI. Publiczny klucz należy przekazać użytkownikom niezależnym zaufanym kanałem, aby nie polegać wyłącznie na serwerze dystrybuującym program.

`.github/workflows/sealed-local-client.yml`: ręcznie uruchamiany build Windows/Linux przy użyciu PyInstaller, z poświadczeniem GitHub OIDC oraz weryfikowalnym digestem. **Nie posiada podpisu Windows Authenticode i nie został z tego powodu uznany za zaufaną aplikację Windows.** Wdrożenie produkcyjne wymaga podpisu kodu właściwym certyfikatem, bezpiecznego aktualizatora i odpowiedniego klucza producenta.

## Użycie referencyjne (na fikcyjnych danych)
```sh
python notarai_sealed_v2.py keygen --office Kancelaria-Testowa --private-out office-private.json --public-out office-public.json
python notarai_sealed_v2.py encrypt --office Kancelaria-Testowa --input test.pdf --recipient office-public.json --output test.pdf.sealed
python notarai_sealed_v2.py decrypt --office Kancelaria-Testowa --private-key office-private.json --input test.pdf.sealed --output recovered.pdf
```
Hasła wczytywane przez `getpass`, nie trafiają do parametrów procesu. Wszystkie operacje odbywają się offline.

## Gwarancje i ograniczenia
- **Nie** jest to hardware-backed KeyStore ani formalne „zero knowledge” dla całego NotarAI. Obecna ścieżka Bedrock nadal istnieje niezależnie i przetwarza jawne dane. Tryby muszą być rozdzielone w UI i przy integracji.
- Prywatny klucz PKCS8 jest chroniony hasłem. Dla kancelarii wymagana jest polityka wydawania kluczy, kopii bezpieczeństwa, ochrony urządzenia, kontroli personelu oraz docelowo smartcard/TPM/HSM.
- Dodanie osoby do envelope nie usuwa dostępu osoby mającej starszy ciphertext i DEK. **Odwołanie dostępu wymaga rotacji DEK i ponownego zaszyfrowania danych**, a stare kopie nadal mogą istnieć poza systemem.
- Dokumenty mają limit 4 MiB w POC; aplikacja nie ma jeszcze GUI, wygodnego importu aktów, podpisanego auto-update ani repozytorium transakcyjnych dowodów dostępu. Wcześniejsze `/api/sealed` obsługuje v1, a v2 jest na razie niezależnym formatem offline — nie przesyłaj do v1.
- Wypuszczenie artefaktu z podpisanym manifestem wymaga **posiadania zaufanego klucza podpisu**, niezależnej dystrybucji jego części publicznej i weryfikacji przed instalacją. GitHub OIDC attestations potwierdzają pochodzenie builda na określonej gałęzi, ale nie zastępują Authenticode ani audytu bezpieczeństwa.

## Testy
`pytest -q test_sealed_v2.py test_sealed_release.py` w środowisku z `cryptography`.
