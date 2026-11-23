# Lekkie narzędzie (rozszerzenie) — maksimum bezpieczeństwa bez uprawnień systemowych

Status: w budowie. Cel: wycisnąć z rozszerzenia (lekka instalacja ze sklepu,
bez admina) tyle ochrony, ile pozwala piaskownica przeglądarki — i ani słowa
więcej niż to, co naprawdę robi.

Rozszerzenie **nie dotyka systemu** (BitLocker, Defender, dysk, zapora — to
agent uprzywilejowany, patrz `helper-bezpieczenstwo.md`). Ale żyje w
przeglądarce, czyli **dokładnie tam, gdzie dzieje się phishing** — i to jest
jego najmocniejsza karta.

## Menu możliwości (od najwyższej wartości)

### 1. Ochrona przed phishingiem — RDZEŃ ZBUDOWANY (`bezpieczna_strona.js`)
Lokalnie, na urządzeniu, bez wysyłania historii przeglądania:
- **Łudząco podobne domeny** (literówka typu `mbonk.pl`, podstawienie segmentu
  `mbank.pl.evil.com`) → ostrzeżenie „to może być podróbka, nie wpisuj haseł".
- **Punycode / IDN** (`xn--…`) — klasyczny trik udawania znanej strony.
- **Formularz logowania po http** — ostrzeżenie przed podaniem danych.
- Lista ważnych domen (banki, poczta, urzędy) rozszerzalna; notariusz dodaje
  własne. Testy: `testy/bezpieczna_strona.test.mjs`.

### 2. Ostrzeżenia o ryzykownych pobraniach — LOGIKA ZBUDOWANA
`.exe/.js/.scr/.msi…` → „pobierasz plik, który może uruchomić program; tak
wchodzi ransomware". (Wymaga uprawnienia `downloads` do włączenia na żywo.)

### 3. Minimalizacja i maskowanie danych — ZROBIONE
`silnik.js`: PESEL/dowód/nr aktu/konto/tel. maskowane przed wysłaniem do modelu.

### 4. Prowadzone twardnienie + przypomnienia — ZROBIONE na landingu
Checklist „jak włączyć X" + skróty do Ustawień Windows + sugerowany (nie
wymuszony) Windows Update. Do przeniesienia do panelu rozszerzenia, żeby
przypominał i odhaczał na bieżąco.

### 5. Higiena przeglądarki — OPCJA
- Wykrycie przestarzałej przeglądarki (mamy na landingu).
- Przegląd innych zainstalowanych rozszerzeń i oznaczenie nadmiernie
  uprawnionych/nieznanych (`chrome.management`).

### 6. Ostrzeżenie o ponownym użyciu hasła — DO ROZWAŻENIA
Lokalne skróty „chronionych" haseł; alarm, gdy notariusz wpisuje je na
nieoczekiwanej domenie. Skuteczne, ale bardziej inwazyjne — tylko za wyraźną
zgodą, wyłącznie lokalnie.

## Kompromis, który trzeba podjąć (uprawnienia vs „lekkość")

Phishing i pobrania można ostrzegać na żywo **tylko wtedy, gdy rozszerzenie
widzi adresy odwiedzanych stron** (i zdarzenia pobrań). To realny skok zgody
przy instalacji — mniej „niewidoczne". Zasada, której się trzymamy:
- **wszystko liczone lokalnie, zero wysyłki** historii przeglądania do nas,
- jasny komunikat przy instalacji: „sprawdzamy adresy u Ciebie, żeby ostrzec
  przed podróbką; nic nie wysyłamy",
- można zacząć wąsko: sprawdzanie tylko na stronach z formularzem logowania.

Bez tej zgody rozszerzenie dalej robi pkt 3–4 i skan świadomościowy, ale nie
ostrzega na żywo przed phishingiem.

## Granice (uczciwie)

- To **nie EDR ani antywirus** — uzupełnia wbudowane Safe Browsing przeglądarki,
  nie zastępuje. Nieznanego, sprytnego phishingu heurystyki nie złapią w 100%.
- Nie chroni poza przeglądarką (pliki, poczta w aplikacji klienckiej, system).
- Skuteczność rośnie z listą ważnych domen i opt‑in na głębsze funkcje.

## Zbudowane w tej rundzie

- `bezpieczna_strona.js` — wykrywanie podróbek (literówka, segment, punycode),
  http‑login, ryzyko pobrania. Czysta logika, 9 testów, w bramce
  `test_rozszerzenie.py`.

## Następny krok (wg decyzji o uprawnieniach)

Włączyć ochronę „na żywo": listener nawigacji + `downloads`, baner ostrzegawczy
w stronie/panelu, konfiguracja ważnych domen. To wymaga rozszerzenia uprawnień
w `manifest.json` — i o to pytam, zanim zmienię zgodę instalacyjną.
