# NotarAI — Amazon Polly, pomocniczy odsłuch projektu

Moduł: \`polly_tts.py\`, \`static/polly-player.js\`; dostępny w etapie **Projekt dokumentu**.

## Zakres

- Głos Ola (domyślnie **generative**, opcjonalnie neural), Ewa (generative/standard), Jacek/Jan/Maja (standard).
- Syntetyczny odsłuch **projektu**, także wybranego fragmentu, z przyciskami Start / Pauza / Wznów / Stop.
- Odczyt długich projektów w paczkach do 2100 znaków; serwer akceptuje maksymalnie 2400 znaków.
- Endpoint \`POST /api/polly/synteza\` zwraca MP3 bez zapisu w S3, a przeglądarka usuwa URL obiektu po odtworzeniu.
- Jest to pomoc w weryfikacji i przygotowaniu aktu. **Nie stanowi automatycznie formalnego odczytania aktu w rozumieniu art. 94 Prawa o notariacie.**
- Nie zmienia dokumentów, nie zatwierdza poprawek i nie łączy głosu z uprawnieniem do wysyłania/podpisywania.
- Nie zastępuje istniejącego agenta telefonicznego ElevenLabs ani modułu stenogramów (STT).

## Prywatność

Cała synteza trafia do **Amazon Polly w eu-central-1 (Frankfurt)**, nie do ElevenLabs.
Tekst jest przesyłany do zarządzanej usługi AWS; użycie regionu UE samo w sobie
nie jest dowodem „zero operator access”. Własna aplikacja nie zapisuje tekstu
ani MP3 w cache, bazie, obiektach S3 czy logach aplikacji.

W SaaS middleware wymaga imiennego tokenu kancelarii i zaakceptowanej umowy,
a dodatkowo endpoint odrzuca dostęp serwisowy. \`stanowiska.py\` wymaga
uprawnienia \`projekt\` dla syntezy. Tokenów AWS **nigdy** nie ma w JS.

## Uruchomienie

1. Wdróż zaktualizowany \`infra/notarai-s3.yaml\`, aby polityka
   \`notarai-aplikacja\` dała \`polly:SynthesizeSpeech\` wyłącznie w regionie \`eu-central-1\`.
2. Zbuduj i opublikuj nowy kontener z kodem, a następnie wdróż
   \`infra/notarai-aplikacja.yaml\` (ustawia \`PIECZAPP_POLLY=true\` na ECS).
3. Zweryfikuj na fikcyjnym projekcie w zalogowanej kancelarii: Ola generative,
   Ewa generative oraz Start/Pauza/Wznów/Stop. Sprawdź, że bez JWT serwer zwraca
   401, dostęp serwisowy 403, brak IAM skutkuje bezpiecznym błędem 503.
4. Obserwuj koszty Polly w AWS Billing i ustaw AWS Budgets.
   Wbudowany limit żądań jest tylko per proces ECS i nie zastępuje limitu kosztów.

W lokalnym trybie bez poświadczeń funkcja jest domyślnie wyłączona.
Aby ją przetestować, ustaw \`PIECZAPP_POLLY=true\`, \`AWS_REGION=eu-central-1\`
i standardowe poświadczenia AWS z \`polly:SynthesizeSpeech\`.

Źródła:
- https://docs.aws.amazon.com/polly/latest/dg/available-voices.html
- https://docs.aws.amazon.com/polly/latest/APIReference/API_SynthesizeSpeech.html
- https://docs.aws.amazon.com/polly/latest/dg/generative-voices.html

## Testy

\`pytest -q test_polly_tts.py\` — testy offline, bez AWS.
