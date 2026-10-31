# notarai - co dzieje się z danymi kancelarii

Dokument do rozmowy z kancelarią. Każde zdanie odpowiada faktycznemu
ustawieniu, sprawdzonemu w AWS 18.09.2026. Gdy coś zmienimy w aplikacji,
ten plik trzeba poprawić razem z nią.

## Gdzie są dane

Kancelaria wybiera przy zakładaniu konta jedną z dwóch możliwości.

**Pliki w chmurze** (domyślnie): sprawy leżą w S3 we Frankfurcie, szyfrowane
i wersjonowane. Odzyskanie po przypadkowym nadpisaniu jest możliwe.

**Pliki u kancelarii**: sprawy zapisują się w folderze na komputerze
notariusza. Serwer nie przechowuje wtedy niczego. Skany i tak przechodzą przez
model, żeby dało się je odczytać, ale po przetworzeniu nie zostaje po nich
żaden plik. Za kopie zapasowe odpowiada wtedy kancelaria; wymaga to
przeglądarki Chrome albo Edge.

Poniższa tabela opisuje wariant chmurowy.

| Co | Gdzie | Zabezpieczenie |
|---|---|---|
| Skany, odczyty, przepisana treść stron (transkrypcje), rozmowy, projekty | S3, Frankfurt (eu-central-1) | szyfrowane, dostęp tylko po TLS, wersjonowane |
| Kalendarz terminów i numery telefonów stron (bez numerów PESEL; spis osób powstaje na bieżąco z odczytów) | S3, Frankfurt, osobno dla każdej kancelarii | szyfrowane, dostęp tylko po TLS, wersjonowane; usuwane razem z danymi kancelarii |
| Dane kancelarii i zapis akceptacji umowy powierzenia | S3, Frankfurt, obszar administracyjny | szyfrowane, tylko dla aplikacji i administratora |
| Konta i hasła użytkowników | Amazon Cognito, Frankfurt | hasła przechowuje AWS, aplikacja ich nie widzi |
| Dzienniki pracy aplikacji | CloudWatch, Frankfurt | 90 dni, bez danych osobowych |
| Odczyt skanów przez model | Amazon Bedrock, regiony UE | patrz niżej |

Dane nie opuszczają Unii Europejskiej.

## Model językowy

Skany i odczytane dane trafiają do modelu Claude uruchomionego w Amazon
Bedrock. Zapytania idą przez profil europejski, więc są przetwarzane w
regionach UE: Frankfurt, Irlandia, Paryż i Sztokholm.

Na koncie ustawione jest **zerowe przechowywanie danych** (tryb `none`) we
wszystkich czterech regionach. Znaczy to, że AWS nie zapisuje treści zapytań
ani odpowiedzi w trwałej pamięci. Dostawca modelu nie otrzymuje tych treści;
zgodnie z dokumentacją AWS dostawcy modeli nie mają dostępu do zapytań i
odpowiedzi klientów.

Model nie uczy się na danych kancelarii.

## Oddzielenie kancelarii od siebie

Każda kancelaria ma własny obszar w magazynie, a aplikacja pilnuje, żeby
zalogowany użytkownik widział wyłącznie sprawy swojej kancelarii.
Przypisanie użytkownika do kancelarii jest zapisane w jego koncie i nie da
się go zmienić od strony przeglądarki.

Uczciwie: rozdzielenie zapewnia aplikacja, a nie osobny magazyn czy osobny
klucz szyfrujący dla każdej kancelarii. Przy wymaganiu pełnego rozdzielenia
technicznego trzeba osobnej instalacji.

## Usuwanie danych

Kancelaria może usunąć każdą sprawę z poziomu aplikacji. Kasowane są skany,
odczytane dane, przepisana treść stron, rozmowa i projekt, razem
z wcześniejszymi wersjami plików.
Usunięcie jest natychmiastowe i nieodwracalne.

Wcześniejsze wersje plików istnieją po to, żeby dało się cofnąć przypadkowe
nadpisanie. Znikają automatycznie po 90 dniach, a przy usunięciu sprawy od
razu.

Po zakończeniu współpracy usuwamy jedną operacją wszystkie dane kancelarii:
sprawy ze wszystkimi wersjami, zlecenia pomocnika, połączone komputery,
konta zespołu i samą kancelarię.

## Kopia zapasowa

Co noc AWS Backup robi kopię całego magazynu spraw do osobnego sejfu we
Frankfurcie. Sejf jest zablokowany: nikt, także właściciel konta, nie usunie
kopii przed upływem 7 dni ani nie zatrzyma jej dłużej niż 35 dni. Każda kopia
wygasa po 21 dniach. Dlatego dane usunięte z aplikacji znikają z kopii
najpóźniej po 21 dniach; do tego czasu są zaszyfrowane i aplikacja nie ma do
nich dostępu.

## Logi

W dziennikach zapisujemy identyfikator sprawy, liczbę stron, czas i rodzaj
błędu. Nie zapisujemy numerów PESEL, nazwisk, adresów ani treści dokumentów.
Pilnują tego testy automatyczne, które sprawdzają, że dane osobowe nie
pojawiają się w logach nawet przy błędach.

## Dostęp

Aplikacja działa na uprawnieniach ograniczonych do jednego magazynu spraw i
do wywołania modelu. Nie ma dostępu do innych zasobów konta.

Dostęp administracyjny do konta AWS ma właściciel usługi. Do danych
kancelarii nikt inny nie ma wglądu.

## Czego aplikacja nie robi

Nie tworzy dokumentu gotowego do podpisu. Każdy projekt wymaga sprawdzenia i
akceptacji notariusza; aplikacja wprost oznacza braki i miejsca do
rozstrzygnięcia. Nie loguje się w systemach urzędowych i nie składa za
notariusza żadnych wniosków.

## Podstawa prawna współpracy

Przetwarzanie danych klientów kancelarii wymaga umowy powierzenia
przetwarzania danych osobowych między kancelarią a dostawcą usługi.
Kancelaria zawiera ją przy rejestracji, akceptując Regulamin, bez podpisu.
Bez zaakceptowanej umowy aplikacja nie przyjmuje spraw. AWS występuje jako
dalszy podmiot przetwarzający, na warunkach umowy powierzenia AWS.

---

## Do zrobienia po naszej stronie (część wewnętrzna, nie dla kancelarii)

- Dokumentacja prawna (umowa powierzenia, regulamin, rejestry, procedura
  naruszeń) jest w `docs/prawne/` i obowiązuje od 24.10.2026; lista tego,
  co zostało, jest w `docs/prawne/README.md`.
- Wdrożyć stos `notarai-kopia` (polecenie w `docs/prawne/README.md`). Do
  tego czasu sekcja „Kopia zapasowa” wyżej jest zapowiedzią, nie faktem.
- Kopia chroni przed skasowaniem bucketa i przejęciem konta (blokada sejfu),
  ale leży na tym samym koncie AWS. Kopia na drugim koncie wymaga AWS
  Organizations - do rozważenia przy kilkunastu kancelariach.
- MFA dla użytkowników w Cognito.
