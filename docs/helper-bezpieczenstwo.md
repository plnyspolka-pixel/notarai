# Helper notarai — głęboka ochrona komputera kancelarii

Status: projekt do akceptacji. Opisuje, jak **sam helper** (podpisana usługa
Windows działająca jako SYSTEM) może zapewnić notariuszowi realną ochronę przed
konkretnymi metodami ataku — wyłącznie przez wbudowane mechanizmy Windows i ich
CLI, bez własnej kryptografii i bez otwartego zdalnego wykonywania poleceń.

Każdy mechanizm opisany jest w dwóch trybach:
- **Sprawdza** (read‑only) — część darmowego/diagnostycznego skanu, nic nie zmienia.
- **Egzekwuje** — jawna akcja z uprawnieniami, odwracalna tam, gdzie to możliwe,
  zawsze zapisana w dzienniku audytu.

---

## 0. Zasada nadrzędna: bezpieczeństwo samego helpera

Dając helperowi moc „jeszcze więcej zabezpieczeń", dajemy mu moc nad całym
komputerem. Dlatego więcej ochrony = więcej rygoru wobec samego agenta:

- **Zamknięta, zaszyta lista operacji.** Helper umie tylko to, co jest w jego
  podpisanym kodzie. Serwer nie może wysłać dowolnej komendy do wykonania jako
  SYSTEM. To jedyny sposób, żeby notarai nie stało się furtką, przed którą chroni.
- **Podpis EV + weryfikacja aktualizacji.** Każda wersja agenta i każda
  „polityka" (zestaw ustawień) podpisana; agent odrzuca niepodpisane.
- **Dziennik audytu.** Każda zmiana (co, kiedy, poprzedni stan, nowy stan)
  zapisana lokalnie i raportowana do panelu — pełna przejrzystość i możliwość
  cofnięcia.
- **Least privilege i odwracalność.** Zmiany odwracalne (eksport poprzedniego
  stanu przed zmianą); operacje nieodwracalne (np. kasowanie) — niedozwolone.
- **UE/RODO.** Agent nie wysyła danych osobowych klientów; kopie i telemetria w
  eu-central-1; dziennik bez PESEL/nazwisk.

---

## 1. Ochrona według metody ataku

### A. Ransomware (zaszyfrowanie akt + okup)

Ransomware wchodzi (załącznik/link/niezałatana luka), uruchamia się, szyfruje
pliki i kasuje kopie. Helper atakuje każdy z tych etapów.

1. **Niemodyfikowalne kopie zapasowe (rdzeń).**
   - *Co:* automatyczne, wersjonowane kopie akt do certyfikowanego magazynu w UE
     z **blokadą obiektu (Object Lock / immutability)** — kopii nie da się
     nadpisać ani skasować przez zadany czas, nawet skradzionym hasłem.
   - *Egzekwuje:* helper uruchamia zaplanowany backup (np. restic/Windows Backup
     → S3 eu-central-1 z object-lock), szyfrowanie po stronie klienta, rotacja.
   - *Efekt:* nawet jeśli ransomware zaszyfruje komputer — jest z czego odtworzyć,
     więc okup traci sens. To jest najważniejszy pojedynczy mechanizm.
2. **Controlled Folder Access (ochrona folderów przed nieznanymi programami).**
   - *Sprawdza:* `Get-MpPreference | Select EnableControlledFolderAccess`.
   - *Egzekwuje:* `Set-MpPreference -EnableControlledFolderAccess Enabled` +
     dodanie folderu akt do chronionych. Tylko zaufane programy mogą je zmieniać.
3. **Attack Surface Reduction (reguły ASR Defendera).**
   - *Egzekwuje:* włączenie reguł blokujących typowe zachowania ransomware/malware:
     uruchamianie plików wykonywalnych z poczty, tworzenie procesów potomnych przez
     pakiet Office, uruchamianie zaciemnionych skryptów, kradzież z LSASS.
   - *CLI:* `Add-MpPreference -AttackSurfaceReductionRules_Ids <reguła> -AttackSurfaceReductionRules_Actions Enabled`.
4. **Twardnienie makr Office** — blokada makr z internetu (źródło zakażeń).
5. **Aktualność systemu i oprogramowania** — zamyka luki wejścia (patrz C).
6. **Wykrywanie w locie:** pliki‑wabiki (canary) w folderze akt; masowa zmiana/
   wzrost entropii → alarm i możliwość zatrzymania. (Monitoring, nie gwarancja.)

> Granica: szyfrowanie dysku (BitLocker) **nie** chroni przed ransomware — chroni
> przed kradzieżą. Przeciw ransomware liczą się kopie + ograniczenie uruchamiania
> + łatki. Mówimy to wprost.

### B. Phishing i przejęcie konta

Najwięcej dzieje się poza komputerem (poczta w chmurze), ale helper domyka endpoint.

1. **Filtrowanie DNS (ochronny resolver).**
   - *Egzekwuje:* ustawienie bezpiecznego resolvera (DNS‑over‑HTTPS do
     filtrującego, np. klasy Quad9/Protective DNS) — znane domeny phishingowe i
     malware nie rozwiązują się w ogóle.
2. **Credential Guard (ochrona poświadczeń, VBS/TPM).**
   - *Sprawdza:* stan Virtualization‑Based Security.
   - *Egzekwuje:* włączenie Credential Guard — skradzione hasła/hashe z pamięci
     stają się bezużyteczne (blokuje pass‑the‑hash po przejęciu komputera).
3. **SmartScreen + twardnienie przeglądarki** — ostrzeżenia o fałszywych stronach i
   pobraniach włączone i zablokowane przed wyłączeniem.
4. **Menedżer haseł + koniec powtarzania** — wdrożenie i wymuszenie.
5. **Wsparcie dla kluczy FIDO2/passkey** — logowanie odporne na phishing tam, gdzie
   usługa je obsługuje.

> Granica: **2FA na poczcie w chmurze (M365/Google) konfiguruje się po stronie
> dostawcy tożsamości**, nie z komputera. Helper to sprawdza i prowadzi krok po
> kroku, ale sam nie „włączy" MFA w cudzej chmurze. Czynnika ludzkiego (ktoś
> wpisze hasło na podróbce) nie da się wyzerować — zmniejszamy go DNS‑em,
> Credential Guard i passkey, nie eliminujemy.

### C. Włamanie zdalne i kradzież danych

1. **Zapora i zamknięcie ekspozycji.**
   - *Egzekwuje:* `Set-NetFirewallProfile` — blokada ruchu przychodzącego;
     wyłączenie/ograniczenie RDP, jeśli nieużywany (zamyka drogę typu BlueKeep).
2. **Wyłączenie przestarzałych protokołów** — SMBv1 (`Set-SmbServerConfiguration
   -EnableSMB1Protocol $false` — droga EternalBlue), LLMNR/NetBIOS.
3. **Windows Update wymuszony** — zaległe poprawki to główna droga wejścia.
   - *Sprawdza:* stan i data ostatniej aktualizacji. *Egzekwuje:* wymuszenie
     pobrania/instalacji i konfiguracja automatyki.
4. **Defender: pełna ochrona + ochrona w chmurze + Tamper Protection** — żeby
   atakujący nie wyłączył antywirusa.
5. **Twardnienie konta administratora** — praca na koncie standardowym,
   losowane hasło lokalnego admina (mechanizm typu LAPS), brak autologowania.

### D. Kradzież lub zguba sprzętu

1. **Szyfrowanie dysków BitLocker** (sprawdzony mechanizm, nie własny).
   - *Sprawdza:* `Get-BitLockerVolume` / `manage-bde -status`.
   - *Egzekwuje:* `Enable-BitLocker` z TPM (+ PIN przy starcie), bezpieczne
     zdeponowanie klucza odzyskiwania (wydruk do sejfu; opcjonalny escrow w
     Secrets Manager eu-central-1 — decyzja notariusza).
   - *Edycje Home:* wykrycie i alternatywa (Device Encryption, gdy dostępne, albo
     VeraCrypt) — bo BitLocker Pro/Enterprise nie zadziała na Home.
2. **Automatyczna blokada ekranu** po bezczynności, hasło po wznowieniu.

### E. Nieuprawniony dostęp lokalny / insider / USB

1. **Kontrola nośników USB** — blokada nieautoryzowanych pamięci masowych
   (wyniesienie akt na pendrive), przez Defender Device Control / polityki.
2. **Audyt logowań** — rejestr, kto i kiedy logował się na stanowisko.
3. **Auto‑lock + kontrola dostępu** (jak D2).

### F. Złośliwe / niechciane oprogramowanie (w tym supply chain)

1. **Allow‑listing aplikacji (WDAC lub AppLocker)** — uruchamia się tylko
   zatwierdzone oprogramowanie; ransomware i „lewe" instalatory nie startują.
   (Etap zaawansowany — wymaga ustalenia listy programów kancelarii.)
2. **Aktualizacja oprogramowania** — `winget upgrade` dla znanych aplikacji.

---

## 2. Mechanizmy przekrojowe (to one robią różnicę „na co dzień")

- **Ciągły monitoring postawy + naprawa dryfu.** Jeśli ktoś wyłączy BitLockera,
  Defendera albo zaporę, helper to wykrywa, zgłasza i (za zgodą polityki)
  przywraca. Bezpieczeństwo to nie jednorazowy klik, tylko utrzymanie stanu.
- **Kopie niemodyfikowalne w UE** — opisane w A1, fundament przeciw ransomware.
- **Dziennik audytu + raport do panelu SaaS** — notariusz i my widzimy, co helper
  zmienił i jaki jest wynik bezpieczeństwa w czasie (trend, nie migawka).
- **Polityki, nie ręczne komendy** — helper stosuje zestaw ustawień („polityka
  kancelarii"), podpisany; zmiana polityki jest widoczna i odwracalna.

---

## 3. Czego helper NIE zrobi sam (uczciwie)

- **Nie włączy MFA w cudzej chmurze** (M365/Google) — to strona dostawcy
  tożsamości; helper sprawdza i prowadzi.
- **Nie wyeliminuje czynnika ludzkiego** — ktoś może wpisać hasło na podróbce.
  Zmniejszamy ryzyko (DNS, Credential Guard, passkey, szkolenie), nie zerujemy.
- **To nie pełny EDR/SOC 24/7.** To twardnienie + kopie + monitoring. Głębsze
  wykrywanie można dołożyć integracją z Defender for Business/MDE — osobny etap.
- **Nie obejmuje procesów i prawa** (polityki RODO, umowy powierzenia) — to
  warstwa organizacyjna, nie agent.
- **Żadnych absolutów.** Nie mówimy „100% bezpieczne" ani „nie do zhakowania" —
  mówimy „drastycznie mniejsze ryzyko" i „masz z czego odtworzyć".

---

## 4. Etapy wdrożenia (kolejność od najtańszego i najbezpieczniejszego)

1. **Skan read‑only** — stan BitLockera, Defendera, zapory, aktualizacji, kopii,
   protokołów. Nic nie zmienia. (To jest też darmowy głęboki skan z landingu.)
2. **Hardening odwracalny** — Controlled Folder Access, ASR, Tamper Protection,
   zapora, wyłączenie SMBv1, DNS filtrujący, auto‑lock. Niskie ryzyko, duży zysk.
3. **Szyfrowanie + kopie** — BitLocker z depozytem klucza; niemodyfikowalne kopie
   w UE. Wymaga zgody i procedury klucza (utrata wydruku = utrata danych).
4. **Zaawansowane** — Credential Guard, kontrola USB, allow‑listing (WDAC/
   AppLocker), LAPS. Wymaga ustaleń (lista aplikacji, sprzęt z TPM).

Każdy etap: najpierw „sprawdza" (pokazuje stan w panelu), potem „egzekwuje" po
zatwierdzeniu polityki, zawsze z wpisem w dzienniku i możliwością cofnięcia.

---

## 5. Co z tego wynika dla produktu

- **Landing** może pokazać przy każdym zagrożeniu nie ogólnik, tylko konkretny
  mechanizm helpera (np. przy ransomware: „niemodyfikowalne kopie w UE +
  Controlled Folder Access + reguły ASR").
- **Helper** sprzedaje się jako „zainstaluj i masz utrzymywany stan
  bezpieczeństwa", a nie jednorazowy skan — to uzasadnia abonament.
- **Granice** trzymają całość wiarygodną wobec informatyka klienta.

Następny krok realizacyjny: zacząć od etapu 1 (skaner read‑only jako silnik
helpera) i przygotować podpisaną „politykę etapu 2" jako pierwszy zestaw akcji.
