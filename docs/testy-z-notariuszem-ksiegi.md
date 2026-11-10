# Test z notariuszem: księgi, wnioski KW (repertorium C), GIIF

Cel spotkania: sprawdzić na prawdziwym stanowisku, czy obieg w notarai pasuje
do pracy kancelarii, i zebrać to, czego nie da się ustalić bez konta notariusza.
Czas: ok. 90 minut. Opis działania: `docs/ksiegi-i-giif.md`.

## 0. Przed spotkaniem (my)

- [ ] Wdrożona wersja z gałęzi `claude/notary-registry-gif-requests-gu1uzj`
      (lxml jest w `requirements.txt` — obraz trzeba zbudować od nowa).
- [ ] Konto testowe kancelarii w notarai, zaakceptowane dokumenty.
- [ ] Dane pokazowe na stanowisku lokalnym: `python scripts/dane_pokazowe_ksiegi.py`
      (osoby zmyślone; kody GIIF przykładowe).
- [ ] Na spotkaniu NIE wprowadzamy prawdziwych danych klientów do konta testowego.
      Do SI*GIIF i portalu MS wysyłamy wyłącznie na środowiskach testowych.

## 1. Repertorium A i pozostałe księgi (20 min)

| Krok | Oczekiwany wynik | OK? | Uwagi notariusza |
|---|---|---|---|
| Wpis czynności z formularza: data, strony `Jan Sobczak, sprzedający, PESEL; …`, treść, kwoty | Numer `Rep. A nr N/RRRR` nadany sam | | |
| Wpis z datą wcześniejszą niż ostatni | Odmowa: „Repertorium prowadzi się chronologicznie” | | Czy tak ma być? Jak kancelaria postępuje przy wpisie „z opóźnieniem”? |
| Błędny PESEL strony | Odmowa z nazwą strony | | |
| Poprawka rubryki z powodem | Stara treść w historii, numer bez zmian | | Czy forma adnotacji wystarcza? |
| Uwaga „wydano wypis …” | Widoczna przy wpisie | | |
| Wydruk do oprawienia (A4 poziomo) | Wszystkie rubryki, poprawki, sumy miesięczne | | **Porównać z obecną księgą papierową** — kolejność i nazwy rubryk |
| Eksport CSV | Otwiera się w Excelu z polskimi znakami | | |
| Księga depozytowa, dzienniki, repertorium P | Numeracja ciągła / roczna | | |

**Pytania do notariusza:**
1. Jak dziś prowadzi repertorium — program (jaki?), papier, oba? Czy program ma eksport (CSV/XML), żeby przenieść bieżący rok?
2. Jakie rubryki/kolumny ma obecnie w rep. A (zdjęcie strony bez danych osobowych)?
3. Czy prowadzi inne księgi/spisy niż te sześć (np. rejestr protestów, spis aktów do CREWAN, ewidencja AML)?

## 2. Wniosek KW → repertorium C (30 min)

| Krok | Oczekiwany wynik | OK? | Uwagi |
|---|---|---|---|
| Z wpisu rep. A: „Wniosek KW”, numer KW, sąd, nabywca, imiona rodziców, żądania | Lista braków, opłata sądowa (np. wpis własności 200 zł) | | Czy opłaty się zgadzają? |
| Pakiet do portalu | Kroki w kolejności formularza, przyciski Kopiuj, na końcu STOP | | **Czy kolejność pasuje do formularza w portalu?** |
| Notariusz przygotowuje wniosek w portalu (środowisko/konto notariusza), kopiując z pakietu | — | | Mierzymy czas vs obecny program |
| Po podpisie i wysłaniu: „Złożony — wpisz REP.C” | Wpis w zakładce Repertorium C | | **Zapisać dokładny format numeru REP.C z portalu** (separatory) |
| Zmiana stanu: w sądzie / wpis dokonany z sygnaturą Dz.Kw. | Historia w rep. C | | |

**Do zebrania (bez tego nie dokończymy pomocnika):**
- [ ] Adres formularza wniosku w portalu MS po zalogowaniu.
- [ ] Nagranie przejścia jednego wniosku w trybie podglądu pomocnika (selektory pól
      do `formularze/wniosek_kw_portal_ms.yaml`). Nie klikamy „podpisz”/„wyślij”.
- [ ] Czy portal ma import wniosku z pliku (XML) albo „wczytaj szkic” — to byłoby lepsze niż wypełnianie pól.
- [ ] Jak notariusz dostaje informację o wpisie (e-mail, portal, doręczenie elektroniczne).

## 3. GIIF / Szef KAS (30 min)

| Krok | Oczekiwany wynik | OK? | Uwagi |
|---|---|---|---|
| Z wpisu rep. A: „GIIF”, kurs EUR | Szkic, termin 7 dni, równowartość EUR | | |
| Ustawienia GIIF: NIP, urząd skarbowy, kody | Zapis | | Kody przepisujemy ze słowników SI*GIIF na koncie notariusza |
| Karta XML: uzupełnienie stron (dokumenty), adresu TERYT, CREWAN | Lista błędów maleje do zera | | Które pola są uciążliwe? Skąd notariusz bierze TERYT? |
| Zatwierdź → Pobierz XML do podpisu | Plik `giif-….xml` | | |
| **Środowisko testowe SI*GIIF** (`test.giif.mofnet.gov.pl`): podpis CAdES + szyfrowanie („Bezpieczny plik”), wysyłka | Status P/R, UPO | | **Najważniejszy test: czy SI*GIIF przyjmuje plik z notarai** |
| Wysłane w SI*GIIF (numer przesyłki) → wgranie UPO (XML) | Numer referencyjny i NIP zgodne, brak ostrzeżeń | | |

**Do zebrania:**
- [ ] Słowniki z SI*GIIF (eksport albo zrzuty): TytulTr, rodzaje przedmiotów
      (z flagami K/U/Z/H/E), charakter podmiotu (Z/N/I), rodzaje dokumentów,
      formy organizacyjne, numer urzędu skarbowego (USK) kancelarii.
- [ ] Przykładowe UPO w XML (z konta testowego) — do testu automatycznego.
- [ ] Jeśli SI*GIIF odrzuci plik: kod błędu i komunikat (status X).
- [ ] Jak notariusz dziś wysyła (program kancelaryjny przez API czy strona SI*GIIF) i czym podpisuje (karta, podpis w chmurze).
- [ ] Potwierdzenie terminu (7 dni od sporządzenia aktu) i sposobu liczenia.

## 4. Po spotkaniu (my)

1. Selektory → `formularze/wniosek_kw_portal_ms.yaml`, status `gotowe` dopiero po teście w trybie podglądu.
2. Słowniki GIIF → lista wyboru w karcie zamiast wpisywania kodów (walidacja flag K/U/Z/H/E dla nieruchomości).
3. UPO z testu → test automatyczny `test_ksiegi_notarialne.py`.
4. Błędy SI*GIIF → nowe reguły w `giif_xml.bledy_regul`.
5. Decyzja: wysyłka przez REST API SI*GIIF (wymaga opisu API z konta) czy zostajemy przy pobraniu pliku.
