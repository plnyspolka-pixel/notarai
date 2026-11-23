# Bezpieczeństwo danych kancelarii — moduł i ścieżka wdrożenia

Status: projekt do akceptacji (część realizacyjna poza landingiem jeszcze nie
zbudowana). Dotyczy modułu „Bezpieczeństwo danych" w notarai.

## 1. Co już działa (zbudowane, przetestowane)

- **Landing `strona/bezpieczenstwo-danych/`** — darmowy skan w przeglądarce
  (bez instalacji, bez logowania), uczciwy: czyta tylko to, co przeglądarka
  sama udostępnia każdej stronie, i wprost pisze, czego NIE robi (brak dostępu
  do plików, kamery, mikrofonu, dysku).
  - Wykrycia: wersja systemu i jej koniec wsparcia (Win 7/8.1, **Windows 10 —
    wsparcie zakończone 14.10.2025**), przestarzała przeglądarka, stan
    połączenia, „ślad" przeglądarki (strefa, ekran, rdzenie), publiczny IP.
  - **Test hasła na żywo**: wygwiazdkowane echo (`ha•••1 — 6 znaków`), dosadna
    ocena siły (lokalnie) i sprawdzenie w wyciekach (HIBP, model
    k-anonimowości — do serwera idzie tylko 5-znakowy prefiks skrótu, nigdy
    hasło). Przy mocnym i niewyciekniętym haśle: pochwała „dobra robota".
  - Samoaudyt (szyfrowanie, kopie, antywirus, blokada, 2FA, menedżer haseł) —
    rzeczy, których przeglądarka nie zobaczy; wpływają na wynik na żywo.
- **Backend `skan_bezpieczenstwa.py`** — `GET /api/skan/ip`,
  `GET /api/skan/hibp-haslo` (proxy k-anonimowości). Zero danych osobowych,
  zero zapisu, nie logujemy haseł ani prefiksów.

## 2. Produkt: od uświadomienia do rozwiązania

Landing kończy się sekcją produktu (bez formularza „skontaktuj się"): notarai
jako narzędzie, które nie tylko pozwala pracować, ale realnie zabezpiecza dane
kancelarii. Rdzeń wartości: **szyfrowanie dysków** (w większości kancelarii
dyski nie są zaszyfrowane — kto weźmie komputer, czyta wszystkie akta).

Ścieżka wdrożenia pokazana klientowi:
1. **Skan** — widzi luki (jest).
2. **Szyfrowanie dysków** — włączamy i konfigurujemy BitLocker.
3. **Klucz bezpieczeństwa** — ustawia hasło, dostaje klucz odzyskiwania;
   drukuje od razu i chowa do sejfu.
4. **Kopie i 2FA**.

## 3. Helper (głęboki skan) i szyfrowanie — do zbudowania

Przeglądarka nie wejdzie na dysk ani nie włączy szyfrowania. Robi to program
na komputerze notariusza, z prawami administratora. W repo jest już baza:
`pomocnik/` i `rozszerzenie/` (pomocnik sterujący przeglądarką przez CDP) —
helper bezpieczeństwa opieramy na tym, nie budujemy od zera.

Helper = **tylko odczyt** przy skanie + **jawne, potwierdzone** akcje przy
włączaniu ochrony. Podpisany cyfrowo, pokazuje dokładnie co robi, nic po cichu.

Głęboki skan (read-only): BitLocker wł./wył., Windows Update (zaległe
poprawki), Defender/antywirus, firewall, blokada ekranu, autologowanie, konto
admin bez hasła, obecność kopii zapasowych.

## 4. Decyzje bezpieczeństwa do akceptacji (zanim zbuduję szyfrowanie)

Szyfrowanie dysku dotyka **wszystkich akt klientów** — błąd = utrata danych
albo furtka. Dlatego wymaga Twojej świadomej zgody na poniższe:

1. **Mechanizm: BitLocker (rekomendacja), nie własna kryptografia.**
   „Zrobić po swojemu" = dobra obsługa i UX, nie własny szyfr. Alternatywa
   dla komputerów bez TPM/Pro: VeraCrypt (sprawdzony). **Nigdy** autorski
   algorytm.
2. **„Klucz" = 48-znakowy klucz odzyskiwania BitLockera**, a nie codzienne
   hasło. Rozdzielamy: codzienne hasło/PIN do odblokowania + klucz odzyskiwania
   drukowany i chowany do sejfu. Inaczej zgubiony wydruk = utrata wszystkich
   akt.
3. **Escrow (kopia klucza odzyskiwania u nas): tak/nie?**
   - Jeśli **nie** — pełna kontrola notariusza, ale zgubi wydruk → dane nie do
     odzyskania (musimy go o tym twardo uprzedzić).
   - Jeśli **tak** — bezpieczniej dla notariusza, ale my przechowujemy klucz:
     musi iść do AWS Secrets Manager w eu-central-1, zaszyfrowany, z dostępem
     wyłącznie właściciela; to decyzja RODO i zaufania. Rekomendacja: escrow
     **opcjonalny**, domyślnie wyłączony, włączany świadomie przez notariusza.
4. **Dystrybucja i podpis.** Helper musi być podpisany (certyfikat
   Authenticode/EV po Waszej stronie — ja go nie podpiszę). Bez tego SmartScreen
   i antywirusy będą go blokować.
5. **RODO.** Helper nie wysyła danych osobowych klientów; raport zostaje
   lokalnie. Logi bez PESEL/nazwisk/adresów (zasada z CLAUDE.md).

## 5. „Sprawdzanie w jak największej liczbie miejsc" — uczciwie

Dla **haseł** HIBP Pwned Passwords to nie jeden serwis, lecz skonsolidowany
zbiór ~900 mln haseł z tysięcy wycieków — to realnie „tak wiele miejsc, jak
się da" w bezpiecznym modelu k-anonimowości. Dokładanie losowych innych API
oznaczałoby wysyłanie skrótów haseł do mniej zaufanych stron — gorzej dla
prywatności. Osobna, szersza oś to sprawdzanie **e-maila/kont** w wyciekach
(HIBP breaches itp.) — wymaga płatnego klucza (→ Secrets Manager) i wysyła
adres e-mail do zewnętrznego dostawcy, więc to osobna decyzja RODO. Nie
włączone domyślnie.
