# Publikacja rozszerzenia notarai w sklepie (normalny install dla notariusza)

Cel: notariusz instaluje **jednym kliknięciem ze sklepu** („Dodaj do Chrome" /
„Pobierz" w Edge) — bez trybu dewelopera, bez rozpakowywania, bez `.exe`.

Tryb dewelopera („Załaduj rozpakowane") służy **wyłącznie nam do testów**.
Klient go nie widzi.

---

## Podział pracy

**Zespół notarai (konto i wysyłka):**
1. Chrome Web Store: konto developerskie, opłata ~5 USD jednorazowo
   (https://chrome.google.com/webstore/devconsole).
2. Edge Add-ons: konto developerskie, za darmo
   (https://partner.microsoft.com/dashboard/microsoftedge).
3. Wgrać paczkę + materiały (niżej), kliknąć „Wyślij", odebrać recenzję
   (Chrome zwykle 1–5 dni; Edge podobnie).

**Przygotowane (ten dokument + repo):**
- Paczka ZIP folderu `rozszerzenie/` (to samo, co ładowaliśmy lokalnie).
- Opis sklepowy, polityka prywatności, uzasadnienia uprawnień, plan zrzutów.

---

## Dane wpisu w sklepie

- **Nazwa:** notarai — asystent i ochrona w przeglądarce
- **Krótki opis (do 132 zn.):** Wypełnia formularze urzędów za Ciebie i ostrzega
  przed podróbkami stron. Nic nie wysyła, nie składa, nie podpisuje.
- **Kategoria:** Narzędzia / Produktywność.
- **Język:** polski.
- **Pełny opis (propozycja):**

  > notarai to lekki asystent kancelarii w przeglądarce. Dwie rzeczy:
  >
  > 1. Wypełnia i klika za Ciebie na stronach urzędów i rejestrów — ale nigdy
  >    nie wysyła, nie składa, nie podpisuje i nie wpisuje haseł ani PIN-u.
  >    Podpis elektroniczny składasz samodzielnie, jak zawsze. Dane wrażliwe
  >    (PESEL, numer aktu, konto) są maskowane, zanim cokolwiek opuści
  >    przeglądarkę.
  > 2. (Opcjonalnie) Ochrona przed phishingiem: ostrzega przed podrobionymi
  >    stronami i ryzykownymi pobraniami. Adresy sprawdzane są lokalnie, na
  >    Twoim komputerze — historia przeglądania nigdzie nie jest wysyłana.
  >
  > Instalacja jest wąska: stały dostęp tylko do app.notarai.pl. Ochronę przed
  > phishingiem włączasz sam jednym przełącznikiem — dopiero wtedy rozszerzenie
  > prosi o dostęp do adresów stron, i tylko po to, by ostrzegać.

## Polityka prywatności (wymagana przez Google)

Do opublikowania pod stałym adresem (np. `https://notarai.pl/prywatnosc-rozszerzenie/`
albo sekcja w istniejącej polityce). Treść do uzgodnienia z prawnikiem; szkielet:

- Jakie dane: adres i widoczny tekst otwartej strony (do wyboru kroku przez
  model), bez wartości wpisywanych i bez selektorów; przy ochronie phishingu —
  adres strony oceniany **lokalnie**, nie wysyłany.
- Po co: wykonanie polecenia na stronie urzędu / ostrzeżenie przed podróbką.
- Gdzie: serwer notarai w UE (eu-central-1); treść strony nie jest logowana ani
  przechowywana. Dane wrażliwe maskowane przed wysłaniem.
- Czego NIE robimy: nie sprzedajemy danych, nie śledzimy między stronami, nie
  wysyłamy historii przeglądania.

## Uzasadnienia uprawnień (Google o nie pyta w formularzu)

- **storage** — zapamiętanie połączenia z kancelarią i ustawień (np. czy
  ochrona phishingu włączona).
- **tabs** — rozpoznanie, na jakiej stronie stoi panel, żeby na niej pracować.
- **scripting** — odczyt elementów i wykonanie czynności na stronie wskazanej
  przez notariusza; wstrzyknięcie baneru ostrzegawczego.
- **sidePanel** — panel polecenia obok strony.
- **host_permissions: app.notarai.pl** — jedyny stały dostęp: rozmowa z
  serwerem notarai.
- **optional_host_permissions / webNavigation / downloads / notifications**
  (opcjonalne, proszone dopiero przy włączeniu ochrony phishingu) — sprawdzanie
  adresu odwiedzanej strony i pobrań **lokalnie** oraz ostrzeganie. Nie są
  wymagane do działania podstawowego; notariusz nadaje je świadomie.
- **Brak zdalnego kodu:** całość logiki jest w paczce; nic nie jest dociągane i
  uruchamiane z sieci (ważne dla recenzji Chrome).

## Zrzuty ekranu (wymagane: 1280×800 lub 640×400, min. 1)

Do zrobienia na realnym rozszerzeniu (po załadowaniu lokalnym):
1. Panel boczny obok strony rejestru z polem „co mam zrobić".
2. Lista kroków po wykonaniu polecenia (z „nie wysyłam/nie podpisuję").
3. Przełącznik „Ochrona przed phishingiem".
4. Czerwony baner ostrzegawczy na podrobionej/niezaszyfrowanej stronie.

## Wersjonowanie

`manifest.json` → `version`. Przy każdej aktualizacji w sklepie podnieść numer
(np. 0.1.0 → 0.1.1). Sklep sam rozprowadzi aktualizację do zainstalowanych.

## Po publikacji

- Zmienić w aplikacji notarai link „pobierz pomocnika": zamiast starego `.exe`
  pokazać przycisk „Dodaj do Chrome / Edge" (link do sklepu). To osobna, drobna
  zmiana w produkcie — do zrobienia, gdy wpis będzie zatwierdzony.
