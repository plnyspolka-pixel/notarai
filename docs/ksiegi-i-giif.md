# Księgi notarialne, wnioski KW i zgłoszenia do GIIF w notarai

Stan na 08.11.2026. Kod: `ksiegi_notarialne.py`, `giif.py`, testy
`test_ksiegi_notarialne.py`, API `/api/ksiegi-kancelarii/*` i `/api/giif/*`.

## 1. Jakie księgi notariusz musi prowadzić

Rozporządzenie MS z 12.04.1991 w sprawie prowadzenia ksiąg notarialnych
(t.j. Dz.U. 2018 poz. 2039), § 1 ust. 1:

| Księga | W notarai | Numeracja |
|---|---|---|
| Repertorium A (wszystkie czynności poza protestami) | `repertorium_a` | roczna, `Rep. A nr N/RRRR` |
| Repertorium P (protesty weksli i czeków) | `repertorium_p` | roczna |
| Księga depozytowa (§ 4) | `depozytowa` | ciągła |
| Dziennik przesyłanych dokumentów (wnioski i pisma z urzędu do sądów i organów) | `dziennik_przesylanych` | ciągła |
| Dziennik korespondencyjny | `dziennik_korespondencyjny` | ciągła |
| Skorowidz alfabetyczno-numerowy (tylko do rep. A) | wyliczany: `/repertorium_a/skorowidz` | — |

**Repertorium C nie występuje w rozporządzeniu.** Jeżeli kancelaria używa tej
nazwy (np. wewnętrznie albo w programie kancelaryjnym), trzeba ustalić, co do
niego wpisuje — dopiszemy je jako kolejną pozycję słownika `KSIEGI`.

Zasady wpisane w kod: numer nadaje serwer, repertorium jest chronologiczne,
poprawki nie wymazują treści (historia: było/jest, kto, kiedy, powód — odpowiednik
przekreślenia na czerwono), adnotacje o wypisach idą do „uwag” pod numerem
rep. A, należności sumowane dziennie i miesięcznie.

**Uwaga prawna:** rozporządzenie z 1991 r. wymaga ksiąg oprawionych, z
ponumerowanymi stronami. Wersja w notarai to rejestr roboczy z pełną historią
i podstawą do wydruku; czy może zastąpić księgę papierową, zależy od przepisów
o elektronicznym repertorium (sprawdzić nowelizację Dz.U. 2025 poz. 1793).
Do tego czasu w dokumentach prawnych zostaje zdanie, że notarai nie jest
archiwum notarialnym.

## 2. Wnioski do ksiąg wieczystych

- Notariusz składa wniosek o wpis **wyłącznie przez system teleinformatyczny**
  (art. 626⁴ KPC, art. 92 § 4 PrNot), portal MS EKW.
- Dostęp: konto w portalu i certyfikat dostępowy, wysłanie wniosku wymaga
  **kwalifikowanego podpisu elektronicznego**. Wniosek można przygotować
  wcześniej i wstępnie zweryfikować, a podpisać i wysłać później — tak to działa
  w obecnych programach kancelaryjnych: przygotowanie u siebie, podpis w portalu.
- Publicznego API do składania wniosków dla zewnętrznych programów nie
  potwierdziliśmy. Nie da się więc „zduplikować” wysyłki bez portalu MS:
  podpis kwalifikowany i wysłanie zawsze robi notariusz.
- Co robi notarai: wniosek przypięty do czynności z rep. A (`/wnioski-kw`),
  status `przygotowany → zlozony → wpis_dokonany / zwrot / oddalony`. Po
  oznaczeniu „złożony” sam powstaje wpis w dzienniku przesyłanych dokumentów
  (numer rep. A, numer KW, identyfikator z systemu). Treść KW pobiera już `ekw.py`.
- Następny krok (poziom 4 z `docs/formularze.md`): pomocnik w przeglądarce
  wypełnia formularz wniosku w portalu i zatrzymuje się przed podpisem.

## 3. GIIF / Szef KAS

- Od 1.03.2023 notariusz przekazuje informacje o czynnościach do GIIF i Szefa
  KAS **wyłącznie elektronicznie przez SI*GIIF**, w formie ustrukturyzowanej
  według XSD (komunikat KAS z 28.11.2022; ustawa z 7.10.2022, Dz.U. poz. 2180)
  — tzw. eNotariusz (podatki.gov.pl/enotariusz). Obejmuje czynności z PCC, SD,
  oświadczenia z art. 43 ust. 10 pkt 2 lit. b ustawy o VAT, APD i europejskie
  poświadczenia spadkowe. Każda czynność ma osobną kartę transakcji z tym
  samym numerem rep. A.
- Art. 72 ust. 4 ustawy AML: transakcje powyżej równowartości 15 000 EUR;
  art. 72 ust. 6 pkt 7a: przedmiot transakcji, a przy nieruchomości adres.
- Komunikat GIIF nr 110: nowy XSD od 30.06.2026 (CRWDE 2026/04/28/14250) z polami
  numer KW, identyfikator działki, liczba pokoi, kondygnacja, powierzchnia
  użytkowa lokalu, powierzchnia nieruchomości zabudowanej domem; dla osób
  fizycznych państwo wydania dokumentu. Osobny XSD „tylko do GIIF” (CRWDE
  2026/04/30/14252) od 15.06.2026.
- SI*GIIF ma REST API dla oprogramowania kancelarii; dokumentacja jest dostępna
  po zalogowaniu, środowisko testowe: test.giif.mofnet.gov.pl. Status przesyłek
  sprawdza się po zalogowaniu kwalifikowanym podpisem zgłoszonym do GIIF.
- Zawiadomienia o podejrzeniach (art. 74, 86, 89) też idą przez SI*GIIF.

### Co przeniesiono z Finance You

Obieg z `finyou/src/lib/aml/aml-reports.functions.ts`: szkic → kontrola
kompletności → zatwierdzenie (skrót SHA-256 treści) → wysyłka w SI*GIIF
podpisem kwalifikowanym → rejestracja identyfikatora → UPO (skrót). Do tego
kurs EUR z tabeli A NBP z cofaniem do dnia roboczego (`nbp-eur.server.ts`)
i termin. W notarai szkic tworzy się jednym kliknięciem z wpisu rep. A,
a `kwalifikuj()` podpowiada, czy czynność trzeba zgłosić (PCC/SD → KAS,
> 15 000 EUR → GIIF). Decyzję podejmuje notariusz.

### Czego NIE przeniesiono i dlaczego

Generatora XML z Finance You (`giif-xml.server.ts`). Buduje on własną
strukturę (`urn:giif:rest2018:zgloszenie`), która nie jest oficjalnym schematem
GIIF — SI*GIIF odrzuciłby taki plik. Ten sam problem dotyczy Finance You.

## 4. Kolejne kroki

1. Pobrać z CRWDE oba XSD notariusza (14250, 14252) i opis schematów v3.0
   (załączniki do komunikatu nr 110), dodać do repozytorium i napisać mapowanie
   karty transakcji na XML z walidacją `xmllint --schema`.
2. Konto testowe w test.giif.mofnet.gov.pl i dokumentacja REST API: wysyłka
   pliku podpisanego podpisem kwalifikowanym notariusza (podpis zawsze u
   notariusza — kartą lub podpisem w chmurze, nie na serwerze notarai).
3. Termin 7 dni (`giif.TERMIN_DNI`) potwierdzić z komunikatem GIIF o liczeniu
   terminów.
4. Ekran w aplikacji: zakładka „Księgi” (repertoria, depozyt, dzienniki,
   wydruk) i „GIIF” (lista z terminami, zaległe na górze).
5. Ustalić z kancelarią, co oznacza „repertorium C”.
