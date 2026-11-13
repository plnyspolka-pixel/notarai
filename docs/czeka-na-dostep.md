# Czeka na dostęp — zadania do zrobienia na żywo

Rejestr rzeczy, których nie da się dokończyć bez dostępu z zewnątrz (konto
notariusza, środowisko testowe urzędu, dokument, którego nie ma publicznie).
Gdy pojawia się dostęp, robimy test **na żywo z notariuszem** według kroków
z danej pozycji i odhaczamy ją tutaj.

Zasady:
- Nowe zadanie tego typu = nowa pozycja `NA-n` na końcu listy (numerów nie
  używamy ponownie).
- Każda pozycja mówi: czego brakuje, co zrobić na żywo, gdzie w kodzie to
  wpiąć i kiedy uznajemy ją za zamkniętą.
- Na żywo nie wpisujemy prawdziwych danych klientów do środowisk testowych,
  nie klikamy „podpisz”/„wyślij” za notariusza, nie zapisujemy haseł ani PIN-ów.
- Zamknięta pozycja: status `zrobione` + data + commit; nie kasujemy jej.

Statusy: `czeka` · `w toku` · `zrobione` · `porzucone (powód)`

---

## NA-1. Portal MS — formularz wniosku wieczystoksięgowego (pomocnik)

- **Status:** czeka
- **Brakuje:** konta notariusza w systemie teleinformatycznym MS (EKW) — adres
  formularza po zalogowaniu i selektory pól.
- **Na żywo:**
  1. Notariusz loguje się sam (certyfikat / podpis), my podłączamy pomocnika
     do jego przeglądarki w trybie podglądu.
  2. Przechodzimy jeden wniosek z danymi pokazowymi
     (`scripts/dane_pokazowe_ksiegi.py`), zapisujemy selektory każdego pola.
  3. Sprawdzamy, czy portal ma import wniosku z pliku (XML) albo „wczytaj szkic”
     — jeśli tak, to lepsza droga niż wypełnianie pól.
  4. Zapisujemy **dokładny format numeru REP.C** pokazany po złożeniu
     (separatory) i sposób powiadamiania o wpisie.
  5. STOP przed „podpisz i wyślij”.
- **W kodzie:** `formularze/wniosek_kw_portal_ms.yaml` (status `szkic` → `gotowe`),
  `wnioski_kw.dane_formularza`, `wnioski_kw.normalizuj_rep_c`.
- **Zamknięte, gdy:** pomocnik wypełnia formularz w trybie podglądu bez błędów
  i notariusz potwierdza zgodność z tym, co wpisałby ręcznie.

## NA-2. SI*GIIF — słowniki kodów

- **Status:** czeka
- **Brakuje:** słowników dostępnych po zalogowaniu w SI*GIIF
  (`giif.mofnet.gov.pl/api/web/slowniki/...`, z zewnątrz blokowane):
  TytulTr, rodzaje przedmiotów (z flagami K/U/Z/H/E i atrybutem „A” =
  nieruchomość), charakter podmiotu (Z/N/I), rodzaje dokumentów, formy
  organizacyjne, USK (urząd skarbowy kancelarii).
- **Na żywo:** notariusz loguje się do SI*GIIF, pobieramy/zapisujemy słowniki
  (eksport albo zrzuty), wpisujemy kody kancelarii w „Ustawieniach GIIF”.
- **W kodzie:** `giif.POLA_USTAWIEN`, edytor karty w `static/ksiegi.js` (listy
  wyboru zamiast wpisywania kodów), `giif_xml.bledy_regul` (wymagane pola
  nieruchomości wg flag K/U/Z/H/E).
- **Zamknięte, gdy:** karta wybiera kody z list, a reguły pól nieruchomości
  działają według flag słownika.

## NA-3. SI*GIIF — próbna wysyłka pliku i UPO (środowisko testowe)

- **Status:** czeka (najważniejszy test GIIF)
- **Brakuje:** konta na `https://test.giif.mofnet.gov.pl` i opisu REST API
  (`/api/rest2018`, dostępny po zalogowaniu).
- **Na żywo:**
  1. Karta z danymi pokazowymi → „Pobierz XML do podpisu”.
  2. Notariusz podpisuje (CAdES) i szyfruje („Bezpieczny plik”), wysyła na
     środowisko testowe.
  3. Sprawdzamy status (Z → O → P → R; X = odrzucony — zapisać kod i komunikat).
  4. Pobieramy UPO w XML i wgrywamy do notarai.
- **W kodzie:** `giif_xml.py` (reguły dla błędów zgłoszonych przez SI*GIIF),
  `giif.odczytaj_upo` (test na prawdziwym UPO w `test_ksiegi_notarialne.py`),
  decyzja o wysyłce przez REST API.
- **Zamknięte, gdy:** plik z notarai ma status R na środowisku testowym, a UPO
  wgrywa się bez ostrzeżeń.

## NA-4. Rejestr Zastrzeżeń PESEL (moduł KRN „Rejestry Notarialne”)

- **Status:** czeka
- **Brakuje:** adresu modułu i selektorów pola PESEL / przycisku „Sprawdź”
  (konto notariusza w Rejestrach Notarialnych KRN).
- **Na żywo:** jak NA-1 — podgląd, jedno sprawdzenie na danych testowych,
  selektory do YAML.
- **W kodzie:** `formularze/rejestry_notarialne_pesel.yaml` (status `szkic`),
  `docs/formularze.md`.
- **Zamknięte, gdy:** pomocnik wpisuje PESEL w trybie podglądu i zatrzymuje się
  przed „Sprawdź”.

## NA-5. Program kancelaryjny notariusza — przeniesienie bieżącego roku

- **Status:** czeka
- **Brakuje:** nazwy programu i informacji, czy ma eksport (CSV/XML) repertorium.
- **Na żywo:** eksport repertorium A z bieżącego roku (bez danych osobowych
  albo na kopii) i porównanie kolumn z `ksiegi_notarialne.KSIEGI`.
- **W kodzie:** nowy import do `ksiegi_notarialne` (numery zachowane z programu).
- **Zamknięte, gdy:** rok w notarai zgadza się z księgą kancelarii co do numerów.

## NA-6. Potwierdzenia prawne

- **Status:** czeka
- **Do potwierdzenia (prawnik / notariusz / komunikaty):**
  - termin przekazania informacji do GIIF/KAS — `giif.TERMIN_DNI = 7`
    i sposób liczenia (komunikat GIIF nr 15);
  - czy repertorium może być prowadzone elektronicznie zamiast ksiąg
    oprawionych (nowelizacja Dz.U. 2025 poz. 1793);
  - nowy XSD z polem `WartoscBezBonifikaty` (opis v4.1) — numer CRWDE, gdy GIIF
    go opublikuje.
- **W kodzie:** `giif.TERMIN_DNI`, `docs/ksiegi-i-giif.md`, `giif_xml.CRWDE`.

## NA-7. Odcinek 01 — czas projektu aktu z prawdziwym modelem (Bedrock)

- **Status:** czeka
- **Brakuje:** poświadczeń AWS z dostępem do Bedrock w eu-central-1 na
  stanowisku, z którego nagrywamy (w sesji, w której powstał kod, ich nie było).
  Lokalnie zmierzono tylko narzut aplikacji na atrapie modelu: 0,3–0,5 s.
- **Na żywo:**
  1. `python scripts/demo_odcinek01.py przygotuj --dane dane/demo-odcinek01`
  2. `python scripts/demo_odcinek01.py serwer --dane dane/demo-odcinek01 --haslo '<hasło demo>'`
     (bez `--atrapa-modelu`), zalogować się jako Marta, sprawa „Nowak - Nowak”,
     „Sporządź projekt”.
  3. Zapisać czas z dziennika serwera (`projekt sporzadzony w N s`) i sprawdzić,
     że projekt ma 2× `<<BRAK>>` (data aktu, dowód kupującego) i warianty
     `<<WYBOR>>` z § 2 i § 4, a raport zasad pokazuje „kwoty słownie”.
  4. Na czas nagrania: przejście do kalendarza w trakcie, powiadomienie, DOCX.
- **W kodzie:** nic — ewentualnie tekst statusu w `pokazPostepProjektu`
  (`static/index.html`), jeśli czas odbiega od „do kilkunastu minut”.
- **Zamknięte, gdy:** czas zapisany w `docs/odcinek-01-luki.md`, a projekt
  z modelu przejrzał notariusz.

## NA-8. Odcinek 01 — przebieg na app.notarai.pl (S3 + Cognito, dwa urządzenia)

- **Status:** czeka
- **Brakuje:** wdrożenia gałęzi `claude/odcinek-01-ekrany` (po scaleniu do
  `master`) i kancelarii demo na app.notarai.pl z czterema kontami na
  prawdziwych skrzynkach (zaproszenia Cognito).
- **Na żywo:**
  1. W panelu /admin założyć kancelarię demo (np. „Kancelaria pod Siódemką
     DEMO”), właściciel akceptuje umowę powierzenia sam (to oświadczenie,
     nie skrypt).
  2. Właściciel zaprasza 3 osoby w „Zespół kancelarii”, od razu ze
     stanowiskiem (notariusz / aplikant / sekretariat).
  3. Dane sprawy: `PIECZAPP_MAGAZYN=s3 PIECZAPP_S3_BUCKET=<bucket> python
     scripts/demo_odcinek01.py przygotuj --kancelaria <id kancelarii demo>`
     (profil `notarai-admin`, eu-central-1; same dane fikcyjne).
  4. Telefon (Kuba): link `https://app.notarai.pl/#sprawa=e01demo00001`,
     zdjęcie aparatem → „Wyślij”; komputer Marty: plik pojawia się w ≤ 15 s.
  5. Marta: „Sporządź projekt”, przejście do kalendarza, odświeżenie strony
     w trakcie (status ma przetrwać), powiadomienie, „Pobierz jako Word”.
  6. Basia: brak „Sporządź projekt”; Kuba: brak „Księgi”/„GIIF”.
- **W kodzie:** nic, chyba że wyjdą różnice S3 (np. opóźnienie `projekt-stan.json`
  między kopiami aplikacji).
- **Zamknięte, gdy:** cały scenariusz przechodzi na produkcji na danych demo.

## NA-9. Poczta do spraw — prawdziwa skrzynka IMAP kancelarii

- **Status:** czeka
- **Brakuje:** skrzynki testowej kancelarii (IMAP, TLS) z hasłem aplikacji
  i wdrożenia stosu aplikacji z polityką `sekrety-skrzynki-pocztowej`
  (`infra/notarai-aplikacja.yaml`, sekret `notarai-skrzynka-<kancelaria>`).
- **Na żywo:**
  1. Właściciel kancelarii wpisuje w „Poczta do przypisania” sam adres e-mail
     i hasło (sprawdzić po jednej skrzynce: Onet/WP/Interia, home.pl albo nazwa.pl,
     Gmail z hasłem aplikacji); kreator ma sam znaleźć serwer. Sprawdzamy, że
     sekret powstał w Secrets Manager (eu-central-1) i że hasła nie ma w S3 ani w logach.
  2. Na skrzynkę wysyłamy z kont testowych 3 maile jak w demo
     (`scripts/demo_odcinek01_skrzynka/`, bez prawdziwych danych klientów).
  3. „Sprawdź skrzynkę”: propozycje (sygnatura, adres, wątek) i to, że w programie
     pocztowym maile nadal są „nieprzeczytane” (BODY.PEEK).
  4. Przypisanie jednym kliknięciem, pliki w „Plikach sprawy”, „Wyciągnij
     ustalenia” na prawdziwym modelu (Bedrock): komunikat przy polu, pole puste,
     projekt z `<<BRAK>>`.
  5. Logi CloudWatch z tego czasu: brak tematów, treści, adresów i nazwisk.
- **W kodzie:** `korespondencja.DostawcaImap` (np. nietypowe odpowiedzi serwera,
  foldery z polskimi znakami — modified UTF-7), prompt `USTALENIA_Z_KORESPONDENCJI`.
- **Zamknięte, gdy:** przebieg działa na prawdziwej skrzynce, a notariusz
  potwierdza, że ustalenia i ich źródła są trafne.

## NA-10. Poczta do spraw — logowanie przez Microsoft 365 i Google (OAuth)

- **Status:** czeka
- **Brakuje:** rejestracji aplikacji w Microsoft Entra i Google Cloud (konto
  właściciela notarai) oraz sekretu `notarai/oauth-poczty`
  (`infra\zapisz-sekret-oauth-poczty.ps1`), potem `infra\3-wdroz-aplikacje.ps1`.
  Google: zakres `https://mail.google.com/` jest zastrzeżony — weryfikacja aplikacji
  (do tego czasu tylko użytkownicy testowi).
- **Na żywo:**
  1. Kancelaria z Microsoft 365 wpisuje adres → „Zaloguj przez Microsoft” → zgoda →
     powrót do aplikacji „Skrzynka podłączona”. Jeśli tenant blokuje zgodę
     użytkownika — sprawdzić komunikat i ścieżkę zgody administratora.
  2. Po godzinie (wygaśnięcie tokenu dostępu) „Sprawdź skrzynkę” nadal działa
     (odświeżenie tokenu, rotacja zapisana w sekrecie).
  3. „Odłącz skrzynkę” kasuje sekret; to samo dla konta Google testowego.
- **W kodzie:** `skrzynki.OAUTH`, `korespondencja.oauth_start/oauth_powrot`.
- **Zamknięte, gdy:** obie ścieżki działają na produkcji na skrzynkach testowych.

## NA-11. Pierwszy zakup pakietu kredytów na żywo (przez Finance You / TPay)

- **Status:** czeka
- **Brakuje:** wdrożenia gałęzi `claude/tokenomia-tpay-integration-52zu6a` w obu
  repozytoriach (notarai i finyou, z migracją `partner_credit_orders`) oraz decyzji
  o § 7 Regulaminu (`docs/projekt-regulamin-par7-kredyty.md`, 14 dni wcześniej
  e-mail do kancelarii).
- **Na żywo:**
  1. Przed wdrożeniem notarai: w panelu Stripe anulować trwające subskrypcje
     abonamentu notarai (aplikacja już ich nie obsługuje — bez tego Stripe dalej
     pobierałby opłaty) i usunąć webhook `notarai-aplikacja`; kancelariom, które
     zapłaciły za bieżący okres, dopisać w `/admin` kredyty za niewykorzystaną część.
  2. Finance You: migracja `20261113120000_partner_credit_orders.sql`; w env
     opcjonalnie `PARTNER_PLATNOSCI_TOKEN` (bez niego działa `KW_PARTNER_TOKEN`)
     i `PARTNER_PLATNOSCI_ORIGINS` (domyślnie `https://app.notarai.pl`).
     Sprawdzić, że podmiot Fundacji w module księgowym ma stawkę „zw”.
  3. notarai: sekret `notarai/finyou` i `FinyouAdres` już są (treść KW) — wystarczy
     wdrożenie `infra\3-wdroz-aplikacje.ps1`.
  4. Kancelaria demo, właściciel: „Kredyty” → pakiet 100 kr → BLIK → powrót; saldo
     rośnie o 100 w ≤ 1 min, w oknie widać numer faktury.
  5. W panelu TPay „Wyślij ponownie powiadomienie” — saldo bez zmian (raz).
  6. Faktura: jest w KSeF na NIP kancelarii demo, e-mail doszedł, pozycja
     „Bon jednego przeznaczenia - pakiet 100 kredytów…”, stawka „zw”.
  7. Zwrot w panelu TPay — w Finance You `refunded`, w notarai saldo −100 (raz);
     korekta faktury ręcznie w module księgowym.
- **W kodzie:** notarai `platnosci.py`, `tokenomia.py` (`kup_pakiet`,
  `uzgodnij_zamowienie`, `ping_platnosci`); finyou `src/lib/partner-payments/`,
  `src/routes/api/public/partner-platnosci.ts`, `webhook-core.server.ts` (prefiks `NOTARAI:`).
- **Zamknięte, gdy:** prawdziwy zakup na produkcji dopisuje kredyty raz i ma
  fakturę w KSeF.

---

Szczegóły działania: `docs/ksiegi-i-giif.md`. Scenariusz spotkania:
`docs/testy-z-notariuszem-ksiegi.md`.

## NA-11. Stanowisko GPU do ujęć bez mowy (RunPod 4090 + ComfyUI + Wan 2.2)

- **Status:** czeka
- **Brakuje:** konta RunPod (albo Modal) z saldem i dysku sieciowego 100 GB; skrypty
  w `docs/kampania-komputerku/narzedzia/gpu/` powstały bez dostępu do karty, więc nazwy
  plików modeli (Comfy-Org, lightx2v) i węzłów ComfyUI nie były uruchomione.
- **Na żywo:**
  1. Pod RTX 4090 (Community, 0,34 USD/h) z Network Volume w `/workspace`, port 8188;
     `bash runpod_4090.sh`, potem `bash runpod_4090.sh start`. Zapisać, które nazwy
     plików trzeba było poprawić.
  2. `klipy_batch.py ../../odcinki/EP01.json --comfy <url> --powtorzenia 1` na 2–3 ujęciach
     bez mowy; porównać `wan22_i2v_lightning.json` z szablonem „Wan 2.2 14B I2V” w ComfyUI.
  3. Zmierzyć sekundy GPU na klip (log w `narzedzia/koszty_log.csv`) i wpisać realny mnożnik
     do `koszty_odcinka.py` (tor `gpu_4090`).
  4. Osobno: 10 kwestii po polsku przez EchoMimicV3 i InfiniteTalk, odsłuch z dźwiękiem;
     decyzja, czy „mówiące w planie” schodzą z Kling Avatar v2 Pro.
  5. **Usunąć pod** po teście (dysk zostaje).
- **Gdzie w kodzie:** `docs/kampania-komputerku/narzedzia/gpu/`, `koszty_odcinka.py` (TORY["gpu_4090"]),
  `KOSZTY_I_COMPUTE_2026-11-13.md` §3 pkt 2 i 4.
- **Zamknięte, gdy:** paczka klipów z jednego odcinka przeszła end-to-end, a zmierzony koszt
  klipu jest w `koszty_log.csv` i w dokumencie kosztów.
