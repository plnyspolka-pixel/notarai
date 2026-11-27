# P0 — uruchomienie automatycznego audytu Bedrock
Narzędzie scripts/audyt_bedrock_dowody.py zostało przygotowane dla Claude'a. Nie wykonuje inferencji, nie zmienia konfiguracji, używa wyłącznie odczytów Bedrock. Testy mock nie wymagają AWS.

1. Z rzeczywistego wdrożenia ustal wszystkie modele i profile, w tym fallbacki, źródłowe regiony i ewentualne projekty. Utwórz prywatny JSON poza repo, np.:
```json
{"inventory_declared_complete":false,"invocations":[{"label":"main","region":"eu-central-1","kind":"profile","model":"REPLACE_WITH_VERIFIED_PROFILE","no_project_confirmed":false}]}
```
Dla bezpośredniego modelu użyj kind foundation. Jeżeli rzeczywiście nie ma projektu, ustaw no_project_confirmed=true, a jeżeli jest, przekaż project z identyfikatorem. Nie ustawiaj inventory_declared_complete=true przed porównaniem z wdrożeniem.

2. W prywatnym terminalu, z istniejącymi poświadczeniami tylko do odczytu:
```sh
python scripts/audyt_bedrock_dowody.py --plan /private/plan.json --out /private/04_BEDROCK_READS.json
```
Opcjonalnie --aws-profile. Katalog wyjściowy musi istnieć, plik nie może istnieć i musi znajdować się poza repo. Kod 2 oznacza niepełny inwentarz lub co najmniej jeden nierozstrzygnięty test; kod 0 potwierdza wyłącznie pozytywne odczyty z zadeklarowanego inwentarza, nie certyfikat bezpieczeństwa.

3. Skrypt sprawdza GetAccountDataRetention, GetModelInvocationLoggingConfiguration, GetInferenceProfile/GetFoundationModel i GetProject w zakresie wskazanych wywołań oraz regionów docelowych. Brak dostępu lub nieznany format nie może być potraktowany jako sukces. Nie rozszerzaj IAM samodzielnie; zgłoś brak uprawnienia. Sprawdź aktualny SDK. Wynik jest konserwatywny: kontroluje też ustawienia konta regionów docelowych.
4. Uzupełnij raport o modelowe warunki kontraktowe, rzeczywiste ścieżki cache/logów aplikacji, testy syntetyczne oraz całość D01–D06. Raport nie zastępuje niezależnego audytu 3×Zero. Nie publikuj inwentarza ani raportu w publicznym repo. Nie uruchamiaj publicznego CI z poświadczeniami AWS do tego zadania.

Źródła:
- https://docs.aws.amazon.com/bedrock/latest/userguide/data-retention.html
- https://docs.aws.amazon.com/bedrock/latest/APIReference/API_GetAccountDataRetention.html
- https://docs.aws.amazon.com/bedrock/latest/userguide/model-invocation-logging.html
- https://docs.aws.amazon.com/bedrock/latest/APIReference/API_GetInferenceProfile.html
