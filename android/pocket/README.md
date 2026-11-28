# NotarAI Pocket na Androida

Cienka aplikacja (Trusted Web Activity), która otwiera `https://notarai.pl/pocket/` w Chrome telefonu
bez paska adresu. Nie ma własnego kodu ani danych: parowanie kodem QR, klucz urządzenia i szyfrowany
tunel do komputera kancelarii działają tak samo jak w przeglądarce, a zmiany strony widać od razu,
bez wydawania nowej wersji aplikacji.

- Pakiet: `pl.notarai.pocket`, Android 8.0 lub nowszy.
- Aplikacja nie prosi o żadne uprawnienia; mikrofon i aparat nadaje Chrome stronie notarai.pl.
- Kod QR z panelu stanowiska (`https://notarai.pl/pocket/#...`) otwiera od razu aplikację.

## Dwie drogi w aplikacji

- Konto kancelarii: ekran startowy prowadzi do `https://app.notarai.pl/`. Aplikacja ufa tej domenie
  (`dodatkowe_domeny` w `zasoby.xml`), a domena oddaje ten sam `assetlinks.json` (`app.py`).
- Komputer kancelarii: parowanie kodem QR, jak opisano wyżej.
- Skróty po przytrzymaniu ikony (`res/xml/skroty.xml`): „Konto kancelarii” i „Połącz z komputerem”
  (`/pocket/?wybor=1` wraca do ekranu wyboru).

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

Wynik: `app/build/outputs/apk/release/app-release.apk` (do pobrania ze strony; skopiuj jako
`strona/pocket/NotarAI-Pocket.apk` i popraw numer wersji na `strona/do-pobrania/index.html`) i
`app/build/outputs/bundle/release/app-release.aab` (Google Play).

## Próba przed wydaniem (obowiązkowa)

Każdą paczkę przed publikacją uruchom na Androidzie, choćby w emulatorze. Wersje 2.1.0-2.4.0 wyszły
bez tego i padały przy starcie (brak `ManageDataLauncherActivity` w manifeście).

    sdkmanager "emulator" "system-images;android-34;aosp_atd;x86_64"
    avdmanager create avd -n proba -k "system-images;android-34;aosp_atd;x86_64" -d pixel_5
    emulator -avd proba -no-window -no-audio -no-snapshot      # bez KVM: ANDROID_I_WANT_MY_TCG=yes i -accel off
    adb install -r app/build/outputs/apk/release/app-release.apk
    adb shell am start -W -n pl.notarai.pocket/com.google.androidbrowserhelper.trusted.LauncherActivity
    adb logcat -d | grep -E 'AndroidRuntime: FATAL|TWALauncherActivity'     # ma nie być FATAL
    adb shell pidof pl.notarai.pocket                                       # proces ma żyć

Sprawdź też skróty (`-a android.intent.action.VIEW -d https://notarai.pl/pocket/?wybor=1`) i udostępnianie
(`-a android.intent.action.SEND -t image/jpeg`).

## Aktualizacje

- Nowe funkcje Pocket trafiają do wszystkich same: aplikacja wyświetla stronę, a service worker pobiera
  ją przy każdym otwarciu z pominięciem pamięci podręcznej. Wystarczy opublikować stronę.
- Nową paczkę wydaje się tylko przy zmianie samej powłoki (ikona, nazwa, ustawienia systemowe). Podnieś
  `kodWersji` w `app/build.gradle` i `versionCode` w `strona/pocket/wersja.json`, zbuduj, podmień APK na
  stronie. Aplikacja pokaże wtedy wiersz „Jest nowa wersja” z przyciskiem pobrania
  (`strona/pocket/aktualizacja.js`). Android nie pozwala instalować po cichu aplikacji spoza sklepu,
  więc użytkownik potwierdza instalację jednym dotknięciem.
- Po eksporcie strony z gałęzi V2 uruchom `python3 tools/pocket_strona.py`, bo eksport nadpisuje te dodatki.
