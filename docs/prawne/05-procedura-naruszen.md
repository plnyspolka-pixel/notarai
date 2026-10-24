# PROCEDURA POSTĘPOWANIA W RAZIE NARUSZENIA OCHRONY DANYCH

Fundacja Krzewienia Edukacji Finansowej im. Pieczaka - usługa notarai.
Obowiązuje od 24.10.2026, przyjęta przez Zarząd Fundacji. Osoba odpowiedzialna: Filip Robert Bielak, Prezes Zarządu.

## 1. Co jest naruszeniem

Każde zdarzenie, które prowadzi albo mogło prowadzić do przypadkowego lub
bezprawnego zniszczenia, utracenia, zmodyfikowania, nieuprawnionego
ujawnienia lub dostępu do danych. Przykłady w notarai:

- sprawa jednej kancelarii widoczna dla użytkownika innej kancelarii,
- przejęcie konta użytkownika albo klucza dostępu do AWS,
- dane osobowe znalezione w dziennikach CloudWatch,
- włączenie rejestrowania wywołań modelu w Bedrock,
- utrata lub nieodwracalne uszkodzenie plików spraw,
- e-mail z danymi klientów wysłany do niewłaściwej osoby,
- zgubiony lub skradziony laptop z dostępem administracyjnym,
- niedostępność usługi uniemożliwiająca dostęp do spraw (naruszenie
  dostępności).

**W razie wątpliwości traktuj zdarzenie jak naruszenie.**

## 2. Kroki i terminy

Zegar biegnie od chwili, gdy ktokolwiek w Fundacji poweźmie rozsądne
przekonanie, że doszło do naruszenia.

| Kiedy | Co | Kto |
|---|---|---|
| natychmiast | Zatrzymać wyciek: dezaktywować klucz IAM, zablokować konto w Cognito, wyłączyć kancelarię, zatrzymać usługę ECS, zmienić hasła. Zabezpieczyć dowody (nie kasować dzienników, zrobić zrzuty ustawień). | osoba, która wykryła, i osoba odpowiedzialna |
| do 4 h | Wpis do ewidencji incydentów (plik 04, część C). Wstępne ustalenie: które kancelarie, jakie dane, ile osób, czy dane były zaszyfrowane, czy naruszenie trwa. | osoba odpowiedzialna |
| **do 24 h** | **Zgłoszenie do każdej dotkniętej kancelarii** e-mailem na adres z umowy powierzenia (wzór niżej). Nie czekać na pełne ustalenia. | osoba odpowiedzialna |
| na bieżąco | Uzupełnianie informacji, pomoc kancelarii przy zgłoszeniu do UODO (kancelaria ma 72 h od chwili, gdy się dowiedziała) i przy zawiadomieniu osób. | osoba odpowiedzialna |
| do 14 dni | Analiza przyczyn, działania naprawcze, test, że naprawa działa; aktualizacja Załącznika nr 2, jeżeli zmieniły się środki. | zespół techniczny |

Fundacja **nie zgłasza** naruszenia do UODO ani klientom kancelarii za
kancelarię, chyba że kancelaria tak poleci.

Jeżeli naruszenie dotyczy danych, dla których Fundacja jest administratorem
(np. konta użytkowników), Fundacja sama ocenia ryzyko i w razie potrzeby
zgłasza naruszenie Prezesowi UODO w ciągu 72 godzin (formularz na
uodo.gov.pl).

## 3. Wzór zgłoszenia do kancelarii

> **Temat:** notarai - zgłoszenie naruszenia ochrony danych osobowych
>
> Szanowna Pani Notariusz / Szanowny Panie Notariuszu,
>
> zgodnie z § 10 umowy powierzenia zawartej <DATA AKCEPTACJI z panelu
> /admin> zgłaszamy naruszenie ochrony danych osobowych.
>
> 1. Data i godzina naruszenia (lub okres): <…>; data stwierdzenia: <…>.
> 2. Opis zdarzenia: <…>.
> 3. Kategorie danych: <…>. Kategorie osób: <…>.
> 4. Przybliżona liczba osób / spraw / plików: <…>.
> 5. Czy dane były zaszyfrowane lub w inny sposób niezrozumiałe dla osób
>    nieuprawnionych: <…>.
> 6. Możliwe konsekwencje: <…>.
> 7. Działania podjęte: <…>. Działania planowane: <…>.
> 8. Czy naruszenie trwa: <tak / nie>.
> 9. Osoba kontaktowa: Filip Robert Bielak, kontakt@notarai.pl.
>
> Informacje, których jeszcze nie znamy, przekażemy niezwłocznie.

W zgłoszeniu **nie umieszczać** danych osobowych klientów kancelarii
(PESEL, nazwisk). Wskazywać sprawy identyfikatorami.

## 4. Ćwiczenie

Raz w roku przećwiczyć scenariusz (np. przejęcie klucza IAM) i zapisać
wnioski.
