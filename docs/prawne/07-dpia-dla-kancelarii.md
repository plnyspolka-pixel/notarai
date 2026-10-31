# OCENA SKUTKÓW DLA OCHRONY DANYCH (DPIA) - KORZYSTANIE Z NOTARAI

Wersja z dnia 01.11.2026.

Ocena przygotowana przez Fundację dla kancelarii (art. 28 ust. 3 lit. f
RODO) i wypełniona przez aplikację danymi kancelarii. Ocenę przyjmuje
notariusz jako administrator: w aplikacji, w oknie Dokumenty, przyciskiem
**Przyjmuję ocenę**. Podpis nie jest wymagany. Data przyjęcia zostaje
zapisana. Jeżeli coś nie odpowiada praktyce kancelarii, pobierz ocenę,
popraw ją u siebie i przechowuj w dokumentacji ochrony danych kancelarii.

Kancelaria: {{kancelaria}}. Notariusz: {{notariusze}}. Data oceny:
{{data}}. Inspektor ochrony danych kancelarii: {{iod}}.

## 1. Czy ocena jest wymagana

Przetwarzanie spełnia co najmniej dwa kryteria z wytycznych EROD (WP248)
i wykazu Prezesa UODO (M.P. 2019 poz. 666): dane szczególnie chronione
lub o charakterze osobistym (PESEL, dane majątkowe, potencjalnie dane
o zdrowiu) oraz innowacyjne wykorzystanie rozwiązań technologicznych
(model sztucznej inteligencji). Ocenę przeprowadza się przed rozpoczęciem
korzystania z usługi.

## 2. Opis przetwarzania

- **Cel:** przyspieszenie przygotowania czynności notarialnych - odczyt
  dokumentów, zestawienie danych, projekt aktu do weryfikacji; kalendarz
  terminów i spis stron czynności z numerami telefonów do kontaktu przed
  czynnością (tylko przy przechowywaniu w chmurze, bez numerów PESEL).
- **Podstawa prawna przetwarzania przez kancelarię:** art. 6 ust. 1 lit. c
  i e RODO w związku z ustawą - Prawo o notariacie; dla danych z art. 9 -
  art. 9 ust. 2 lit. f i g; dla danych z art. 10 - przepisy ustawy - Prawo
  o notariacie.
- **Przepływ:** pracownik wgrywa skany i wzór → serwer notarai we Frankfurcie
  → model Claude w Amazon Bedrock (regiony UE, bez zapisu treści) → wynik
  zapisany w S3 we Frankfurcie albo w folderze kancelarii → notariusz
  sprawdza i poprawia → projekt pobierany do Worda.
- **Podmioty:** Fundacja (podmiot przetwarzający), AWS EMEA SARL (dalszy
  podmiot przetwarzający).
- **Tryb plików wybrany przez kancelarię:** {{przechowywanie}}.
- **Skala:** {{uzytkownicy}} użytkowników w chwili oceny; liczba spraw
  zależy od obłożenia kancelarii.

## 3. Niezbędność i proporcjonalność

| Zasada | Jak spełniona |
|---|---|
| Ograniczenie celu | dane używane wyłącznie do przygotowania czynności; zakaz trenowania modeli i innych celów w umowie powierzenia (§ 4) |
| Minimalizacja | do usługi wgrywa się tylko dokumenty potrzebne do danej czynności (instrukcja AI, pkt 6) |
| Prawidłowość | wyniki AI oznaczone jako projekt, walidacja sum kontrolnych, oznaczanie niepewnych odczytów, obowiązkowa weryfikacja przez notariusza |
| Ograniczenie przechowywania | kancelaria usuwa sprawę z notarai po zakończeniu czynności; dokumentacja notarialna jest przechowywana zgodnie z przepisami poza notarai |
| Integralność i poufność | Załącznik nr 2 do umowy powierzenia |
| Przejrzystość | klauzula informacyjna kancelarii wymienia dostawców usług IT jako odbiorców (wzór w aplikacji, Dokumenty → Co robi kancelaria) |

## 4. Ryzyka i środki

Skala: prawdopodobieństwo (P) i skutek (S) - niskie / średnie / wysokie.

| Ryzyko | P przed | S | Środki | P po |
|---|---|---|---|---|
| Błędny odczyt danych (cyfra PESEL, KW, kwota) przeniesiony do aktu | średnie | wysokie | sumy kontrolne, oznaczanie niepewnych pól, znaczniki BRAK, obowiązkowe porównanie ze źródłem przez notariusza | niskie |
| Halucynacja modelu (informacja nieobecna w dokumentach) | średnie | wysokie | projekt zawsze weryfikowany; asystent cytuje źródło przy dopasowaniu formularzy | niskie |
| Dostęp innej kancelarii do spraw | niskie | wysokie | izolacja w aplikacji, przypisanie kancelarii w tożsamości, testy automatyczne | niskie |
| Przejęcie konta pracownika | średnie | wysokie | indywidualne konta, hasła co najmniej 12 znaków, usuwanie członków zespołu przez właściciela, instrukcja potwierdzana przez każdego użytkownika | niskie |
| Ujawnienie danych przez dostawcę lub na żądanie organu państwa trzeciego | niskie | wysokie | dane wyłącznie w UE, szyfrowanie, zobowiązania AWS, § 5 ust. 7 umowy powierzenia; tryb „Pliki na komputerze kancelarii” ogranicza przechowywanie | niskie |
| Ujawnienie tajemnicy notarialnej przez personel Fundacji | niskie | wysokie | Fundacja nie ma dostępu do treści spraw: panel administracyjny ich nie otwiera, a polityka magazynu zakazuje odczytu wszystkim poza aplikacją i kopią zapasową; dostęp serwisowy tylko włączany przez kancelarię na wskazany czas, z zapisem widocznym dla kancelarii; zobowiązania do poufności | niskie |
| Utrata danych (awaria, usunięcie) | niskie | średnie | wersjonowanie, kopie zapasowe, oryginały dokumentów pozostają w kancelarii | niskie |
| Dane osobowe w logach | niskie | średnie | zakaz w umowie, testy automatyczne | niskie |
| Pomocnik wykona niepożądaną czynność w rejestrze | niskie | wysokie | blokada przycisków wysyłania, podpisu i płatności, pól haseł, dozwolone adresy, logowanie przez notariusza | niskie |

## 5. Wniosek

Po zastosowaniu środków ryzyko szczątkowe jest niskie. Uprzednia
konsultacja z Prezesem UODO (art. 36 RODO) nie jest wymagana.

Przegląd oceny: co najmniej raz w roku i przy istotnej zmianie usługi
(nowy dostawca, nowa funkcja AI, zmiana lokalizacji danych). O takiej
zmianie Fundacja informuje kancelarię e-mailem, a aplikacja prosi wtedy
o ponowne przyjęcie oceny.

Przyjęcie przez notariusza: {{przyjeto}}.
