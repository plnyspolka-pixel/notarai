# 3 × ZERO w wersji minimalnej (stan 23.11.2026)

Ten dokument zastępuje plan z PR #94 i z ~40 zarchiwizowanych PR-ów
(SEC-01…13, CIV-01…04, Confidential Browser, kustosz KMS). Tamte PR-y
były sugestią. Decyzja: **najpierw najprostsza wersja, którą da się wdrożyć
od razu na obecnym stosie AWS, bez nowych kosztów.** Atestacja Nitro
zostaje opcjonalnym etapem 2, budowanym dopiero wtedy, gdy zapłaci za nią
klient.

## 1. Co realnie dostajemy

| Hasło | Co znaczy w tej wersji | Czym jest egzekwowane |
|---|---|---|
| Zero Knowledge (w spoczynku) | Sprawy kancelarii leżą w S3 i w kopiach zapasowych wyłącznie jako szyfrogram AES-256-GCM. Klucza nie mamy: nie ma go w S3, w Secrets Manager, w logach ani w rejestrze kancelarii (jest tam tylko KCV) | kryptografia (`szyfrowanie_kancelarii.py`) |
| Zero Operator Access (w spoczynku) | Administrator notarai, dostęp serwisowy, ktoś z kopią bucketa albo backupu nie otworzy sprawy bez kodu kancelarii. Nie da się też podmienić ani przenieść pliku między sprawami (AAD = klucz S3) | kryptografia + odmowa w `magazyn.py` |
| Zero Trust | Każde żądanie: token Cognito, tenant z tokenu, stanowisko osoby, poprawny kod kancelarii (KCV). Zły kod daje 403 przed dotknięciem danych | `autoryzacja.middleware` |

**Czego NIE twierdzimy:** w trakcie żądania dokument i klucz są w pamięci
kontenera, bo Claude w Bedrock musi przeczytać skan. Operator, który
świadomie wdroży zmieniony kod, mógłby je przechwycić. Przed tym chronią
procedury, nie matematyka (sekcja 4). AWS i Bedrock są zaufanymi
podprocesorami (DPA AWS, region UE). Materiały sprzedażowe mają mówić
„zaszyfrowane kluczem kancelarii, którego notarai nie zna”, a nie
„matematycznie niemożliwy dostęp operatora”.

## 2. Jak to działa

1. Właściciel kancelarii: *Ustawienia kancelarii → Klucz kancelarii → Włącz*.
   Przeglądarka losuje 128-bitowy kod (`XXXX-XXXX-…`, 26 znaków base32),
   pokazuje go i daje do pobrania kartę `.txt`. Serwer dostaje kod jeden raz
   w nagłówku i zapisuje tylko `KCV = HMAC(HKDF(kod), "kcv")`.
2. Każdy komputer kancelarii pamięta kod w `localStorage`. Funkcja `api()`
   dokleja go do żądań jako `X-Klucz-Kancelarii`. Na nowym komputerze
   serwer odpowiada 423, a przeglądarka pyta o kod i ponawia żądanie.
3. Serwer: middleware sprawdza KCV i trzyma klucz w `ContextVar` tylko na czas
   żądania (także w wątkach tła uruchomionych z tego żądania). `magazyn.py`
   szyfruje każdy plik sprawy przed `put_object` i odszyfrowuje po
   `get_object`. Bez kodu nie ma ani zapisu, ani odczytu, nawet częściowego.
4. Jawna kopia na dysku kontenera (cache) znika po
   `PIECZAPP_CACHE_SZYFROWANYCH_MINUT` (domyślnie 60) bezczynności.
5. Zgubiony kod = utracone sprawy. Tak działa ta polityka i właściciel widzi
   to przed włączeniem. Odzyskiwanie to karta z kodem (wydruk, sejf), bez
   kustosza i bez naszego „wytrycha”.

## 3. Zakres wersji minimalnej i co celowo odłożone

Szyfrowane: **pliki spraw** (`kancelarie/{id}/sprawy/**`: skany, `sprawa.json`,
projekty aktów), czyli większość danych osobowych.

Bez zmian (SSE-S3, jak dotąd), z powodu: te dane są zapisywane bez
zalogowanego notariusza:
- pliki całej kancelarii (`kalendarz`, `rezerwacje`, `skrzynka`, …): piszą
  je rezerwacje publiczne i powrót OAuth poczty,
- teczki klientów z notarai.pl: otwiera je kancelaria, która nie zna tokenu
  klienta.

Odłożone (każde to osobny, mały krok, gdy klient o to poprosi):
- przeszyfrowanie istniejących spraw (wymaga usunięcia ich starszych wersji
  w S3); dziś klucz włącza się tylko w kancelarii bez spraw,
- rotacja kodu, czyli przeszyfrowanie wszystkich plików nowym kodem,
- szyfrowanie plików kancelarii po przeniesieniu zapisów publicznych do
  osobnej skrzynki „do odebrania”,
- **etap 2, atestacja Nitro**: kod przechodzi do enklawy, a przeglądarka wydaje
  klucz dopiero po sprawdzeniu PCR. Kod pilota leży na `master`
  (`confidential/`, wyłączony) i w PR #94. To dopiero zamyka lukę z sekcji 1,
  ale oznacza stałe instancje EC2 i dużo pracy, więc budujemy go tylko na
  zamówienie.

Alternatywa „tryb u klienta” (`przechowywanie: u-klienta`) już istnieje.
Serwer w ogóle nie zapisuje plików i trzyma je dysk notariusza. To
najsilniejsze ZK w spoczynku, ale bez pracy z kilku komputerów.

## 4. Procedury, które domykają lukę „w trakcie żądania”

Sprawdzone 23.11.2026 na koncie 127621462971 (tylko odczyt):
- [x] ECS Exec na usłudze `notarai` wyłączony (`enableExecuteCommand=false`),
  więc nikt nie wejdzie do pamięci kontenera.
- [x] Logowanie wywołań Bedrock nie jest skonfigurowane: prompty i skany nie
  trafiają do CloudWatch ani S3.
- [x] CloudTrail `notarai-slad` działa, więc każda zmiana usługi, roli czy
  obrazu zostawia ślad.
- [x] Wdrożenie wyłącznie z GitHub Actions (OIDC, gałąź `master`).
- [ ] **Do zrobienia ręcznie:** ochrona gałęzi `master` w GitHubie (wymagany
  przegląd i zielone testy). Bez niej każdy z prawem push wdraża dowolny kod.
- [ ] Alarm na `ecs:UpdateService` / `RegisterTaskDefinition` spoza roli
  `notarai-github-wdrozenie` (EventBridge → SNS `notarai-alarmy`), opcjonalnie.

Koszt wersji minimalnej: **0 zł więcej.** Bez KMS, bez nowych usług, bez
instancji. Szyfrowanie robi ta sama aplikacja na tym samym Fargate.

## 5. Co zrobić z pozostałościami pilota Nitro

Na koncie stoi ~20 stosów `notarai-confidential-*` (pilot01–03, shared
fabric/capacity/ECR, demo KMS). Nic w nich nie działa (0 zadań, 0 instancji,
brak NAT), a koszt to głównie 4 klucze KMS, około 4 USD miesięcznie. Można je
usunąć, gdy właściciel potwierdzi, że etap 2 nie startuje w najbliższych
miesiącach. Kod zostaje w repozytorium.

## 6. Testy

`test_szyfrowanie_kancelarii.py`: format kodu, KCV nie zdradza klucza, AAD
blokuje przeniesienie pliku do innej sprawy lub kancelarii, zmieniony bajt
albo jawny plik podłożony w S3 zostaje odrzucony, bez kodu nic nie idzie do S3
ani z S3, cache znika, zgodność wstecz dla kancelarii bez klucza, tylko
właściciel włącza klucz, kod nie trafia do logów.
