# NotarAI Pocket na Androida

Cienka aplikacja (Trusted Web Activity), która otwiera `https://notarai.pl/pocket/` w Chrome telefonu
bez paska adresu. Nie ma własnego kodu ani danych: parowanie kodem QR, klucz urządzenia i szyfrowany
tunel do komputera kancelarii działają tak samo jak w przeglądarce, a zmiany strony widać od razu,
bez wydawania nowej wersji aplikacji.

- Pakiet: `pl.notarai.pocket`, Android 8.0 lub nowszy.
- Aplikacja nie prosi o żadne uprawnienia; mikrofon i aparat nadaje Chrome stronie notarai.pl.
- Kod QR z panelu stanowiska (`https://notarai.pl/pocket/#...`) otwiera od razu aplikację.

## Powiązanie ze stroną

Pasek adresu znika tylko wtedy, gdy `https://notarai.pl/.well-known/assetlinks.json`
(`strona/.well-known/assetlinks.json`) zawiera odcisk SHA-256 certyfikatu, którym podpisano zainstalowaną
paczkę. Jest tam odcisk naszego klucza. Po włączeniu podpisywania w Google Play trzeba dopisać drugi
odcisk, z Konsoli Play (Konfiguracja > Podpisywanie aplikacji); patrz `docs/czeka-na-dostep.md`, NA-20.

## Budowanie

Potrzebne: JDK 17 lub nowszy i Android SDK (`ANDROID_HOME`, platforma 36).

    cd android/pocket
    ./gradlew assembleRelease bundleRelease lintRelease

Bez klucza powstaje paczka niepodpisana. Klucz podpisu leży w AWS Secrets Manager (eu-central-1) jako
`notarai/pocket-android-podpis` (pola `keystore_b64`, `haslo`, `alias`), nigdy w repozytorium. Do
podpisania zapisz `keystore_b64` po zdekodowaniu do pliku poza repozytorium i ustaw:

    NOTARAI_POCKET_KEYSTORE=/sciezka/do/klucz.jks
    NOTARAI_POCKET_KEYSTORE_HASLO={{resolve:secretsmanager:notarai/pocket-android-podpis:SecretString:haslo}}   # przez asm-exec

Wynik: `app/build/outputs/apk/release/app-release.apk` (instalacja ręczna na telefonie) i
`app/build/outputs/bundle/release/app-release.aab` (Google Play). Przy każdym wydaniu podnieś
`versionCode` w `app/build.gradle`.
