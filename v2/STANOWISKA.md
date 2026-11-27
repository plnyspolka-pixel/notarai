# Stanowiska audio i wideo

W Pocket otwórz „Test mikrofonu i kamery”. Podłącz Yeti przez USB na każdym stanowisku, a w gabinecie także Creative Live! Cam Sync 1080p V2. Pierwsze uruchomienie testu odblokuje nazwy urządzeń w przeglądarce. Wybierz Yeti jako wejście audio i w gabinecie wybierz Creative jako kamerę. Uruchom test ponownie. Zakończenie testu zwalnia urządzenia. Podgląd nie zapisuje i nie przesyła dźwięku ani obrazu. Prototyp służy do prób z fikcyjnymi danymi.

## Docelowy przebieg

- **Sekretariat:** po rozmowie pracownik dyktuje krótką notatkę. Aplikacja proponuje opis sprawy, ustalenia i termin. Jeżeli data jest niejednoznaczna, dopytuje. Sprawdza dostępność przy propozycji i ponownie przy zapisie. Pracownik zatwierdza wpis. Kamera jest wyłączona.
- **Gabinet:** operator wybiera czynność i uzbraja sesję po poinformowaniu uczestników. Aplikacja wyświetla stan uzbrojenia i przycisk zatrzymania. Start można wywołać poleceniem z aplikacji do odczytu lub wykryciem mowy w uzbrojonej sesji. Wykrycie mowy jest sygnałem startu, a powiązanie z wykonaną czynnością wymaga potwierdzenia w sprawie. Operator może też uruchomić zapis ręcznie.
- **Zapis:** przed startem krótki bufor w RAM może zachować pierwsze słowa. Poza uzbrojoną sesją mikrofon i kamera są wyłączone. Jeden wpis czynności zawiera zsynchronizowane audio i wideo, znaczniki czasu oraz stenogram. Wielkość pliku ogranicza kompresja i pomijanie czasu przed czynnością i po niej. Pauzy w zatwierdzonym oryginale pozostają. Widok stenogramu może je pomijać bez zmiany oryginału.
- **Kompletność:** przy zamknięciu czynności aplikacja pokazuje, czy zapis i stenogram są gotowe, przerwane lub brakujące. Rejestr odłączenia lub przerwania pozwala odróżnić brak nagrania od braku czynności.

## Miejsce zapisu i kopia

Zapis główny trafia do szyfrowanego magazynu kancelarii. Docelowy wybór kopii to oddzielny szyfrowany nośnik lub komputer kancelarii albo S3 w regionie eu-central-1 z szyfrowaniem po stronie kancelarii przed wysyłką i kluczem poza S3. Kopia na tym samym dysku nie chroni przed jego awarią.

Obecny V2 przewiduje wyłącznie przechowywanie lokalne. Wariant S3 wymaga zatwierdzenia zmiany zasad V2, okresu przechowywania i testu odtworzenia. Żaden zasób chmurowy nie jest tworzony przez prototyp. Obecny limit magazynu dokumentów Pocket wynosi 20 MiB na plik, więc audio i wideo potrzebują osobnego, strumieniowego zapisu szyfrowanych fragmentów.
