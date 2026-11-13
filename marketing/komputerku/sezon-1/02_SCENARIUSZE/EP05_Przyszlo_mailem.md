# EP05 — Przyszło mailem

> **Nota dramaturgiczna V5 — powracający gag „nakarmić komputerka”.** Zosia Lewicka słyszy powiedzenie po raz pierwszy, pyta Kubę, czy karmią komputer. Kuba tłumaczy mechanizm kredytów. Pierwsza naturalna iskra romantyczna; nie dopisywać innej relacji. Szczegóły, rytm i ograniczenia produktu: [biblia gagu](../08_MOTYW_KARMIENIE_KOMPUTERKA.md). Beat jest propozycją do następnego passu scenariuszowego; wszystkie dotychczasowe ujęcia pozostają do oceny przed ewentualnym nowym renderem.


**Data fabularna:** 20.11.2026 · **Czas:** 70 s · **Wersja:** robocza do autoryzacji · **Format:** 9:16, adaptacja 16:9


> **Kanon:** nie zmieniać nazwisk, wieku, relacji, dat ani dokumentów z `01_KANON/BIBLIA_INTRYGI_KANON_2026-11-12.md`. Odcinek nie jest konsultacją prawną; przed publikacją wymaga kontroli notariusza.


## Funkcja główna
Pliki sprawy: ręczne dołączenie korespondencji


**Uzupełniające:** Ewidencja terminów; rozmowa o sprawie i sprawdzanie źródeł.


**Logline:** W mailach kupujących odkrywamy, jak propozycja wydania lokalu zamieniła się w rzekomo uzgodniony termin.


**Hak:** Basia mówi: „Dwa maile, dwa różne znaczenia tego samego zdania”.


**Co widz odkrywa:** Termin 1 grudnia był propozycją, której Irena osobiście nie potwierdziła.


**Pytanie końcowe:** Dlaczego Paweł nie sprostował informacji, choć widział pośpiech kupujących?


## Scenopis — wszystkie sceny


### E05S01 · 00–06 · Dwa maile

- **Miejsce:** recepcja; **obsada:** Basia.

- **Działanie:** Na ekranie prawdziwej skrzynki przychodzą dwie wiadomości: jedna z roboczym terminem, druga o potrzebie przedłużenia najmu.

- **Dialog / napisy:** BASIA: „Dwa maile. Ten sam lokal. Zupełnie inne oczekiwania”.

- **Kadr i montaż:** Zbliżenie prawdziwego mail klienta demo, nie NotarAI.

- **Prawdziwa funkcja / ograniczenie:** Brak automatycznego importu: to ekran osobnego programu pocztowego.

- **Biblioteka wspólna:** `R03,R12` · **nowy beat/ujęcie:** `N05A: sztuczna korespondencja D09,D10 w realnym kliencie poczty`.

- **Punkt kontrolny:** Żadnych danych istniejących osób; źródło wiadomości czytelne.

- **Minimalny prompt delta** (dołączany do jednego promptu bazowego, nie samodzielny): `email client with two contradictory fictitious property transaction messages`.



### E05S02 · 06–14 · Uproszczenie, które szkodzi

- **Miejsce:** stanowisko Marty; **obsada:** Basia, Marta.

- **Działanie:** Basia przypomina, że Robert w jednej wiadomości napisał „zakładamy wydanie do 1 grudnia”; Paweł powtórzył tę datę.

- **Dialog / napisy:** MARTA: „Zakładają — to nie znaczy, że sprzedająca się zgodziła”.

**BASIA:** „A wszyscy czytali to jak ustalenie”.

- **Kadr i montaż:** Dwuplan; podbicie słów „zakładamy” i „potwierdzono” tylko jako typografia filmu, nie funkcja AI.

- **Prawdziwa funkcja / ograniczenie:** Brak automatycznej interpretacji czy zatwierdzania umowy.

- **Biblioteka wspólna:** `R07,R12` · **nowy beat/ujęcie:** `N05B: emocja rozpoznania błędu komunikacji`.

- **Punkt kontrolny:** Nie traktować e-maila syna jako oświadczenia sprzedającej.

- **Minimalny prompt delta** (dołączany do jednego promptu bazowego, nie samodzielny): `notary and secretary reviewing tentative handover proposal email`.



### E05S03 · 14–24 · Z jednej skrzynki do jednej sprawy

- **Miejsce:** stanowisko Marty; **obsada:** Basia.

- **Działanie:** Basia zapisuje wiadomość jako plik `.eml` lub PDF, wchodzi w NotarAI → istniejąca sprawa → Pliki sprawy → Z pliku i ręcznie dodaje załącznik.

- **Dialog / napisy:** BASIA: „Niech to będzie przy sprawie, nie w piątym wątku na poczcie”.

- **Kadr i montaż:** Ujęcie prawdziwych dwóch aplikacji; jawny wybór pliku.

- **Prawdziwa funkcja / ograniczenie:** `POST /api/sprawy/{id}/pliki`; ręczny import z poczty.

- **Biblioteka wspólna:** `R08,R12,R14` · **nowy beat/ujęcie:** `N05C: realne wgranie pliku i jego pojawienie się w liście`.

- **Punkt kontrolny:** Wykluczone: automatyczne rozpoznanie klienta w skrzynce.

- **Minimalny prompt delta** (dołączany do jednego promptu bazowego, nie samodzielny): `secretary manually uploading email attachment to an existing legal case folder`.



### E05S04 · 24–32 · Presja zrozumiała

- **Miejsce:** poczekalnia; **obsada:** Joanna, Robert.

- **Działanie:** Kupujący czekają, Robert patrzy na kalendarz własnego telefonu, Joanna składa dokumenty najmu.

- **Dialog / napisy:** ROBERT: „Wynajem kończy nam się z końcem listopada”.

**JOANNA:** „Ale pani Irena też musi się gdzieś przeprowadzić”.

- **Kadr i montaż:** Dwuplan w poczekalni, bez efektów villain.

- **Prawdziwa funkcja / ograniczenie:** Brak; motywacje klientów.

- **Biblioteka wspólna:** `R01` · **nowy beat/ujęcie:** `N05D: kupujący jako realni ludzie`.

- **Punkt kontrolny:** Bez deklarowania nieuzgodnionych praw.

- **Minimalny prompt delta** (dołączany do jednego promptu bazowego, nie samodzielny): `young married couple worried about apartment move and rental ending`.



### E05S05 · 32–42 · Warunki nie są ostateczne

- **Miejsce:** gabinet Heleny; **obsada:** Helena, Joanna, Robert.

- **Działanie:** Helena wyjaśnia, że strony muszą porozumieć się co do wydania, kosztów i zasad płatności, a projekt może powstać dopiero na potwierdzonych danych.

- **Dialog / napisy:** HELENA: „Mamy projekt warunków. Nie mamy jeszcze wspólnego ustalenia”.

**JOANNA:** „Czyli termin wydania jest nadal otwarty?”

**HELENA:** „Tak”.

- **Kadr i montaż:** Stabilna kamera, bez udawania rozmowy doradczej trwającej 5 sekund; montaż skrótowy.

- **Prawdziwa funkcja / ograniczenie:** Ocena i wyjaśnienia notariusza, żadna autonomiczna decyzja AI.

- **Biblioteka wspólna:** `R06` · **nowy beat/ujęcie:** `N05E: rzeczowa rozmowa z kupującymi`.

- **Punkt kontrolny:** Weryfikacja obowiązków z art. 80 PrNot; nie sugerować gotowości aktu.

- **Minimalny prompt delta** (dołączany do jednego promptu bazowego, nie samodzielny): `notary calmly explaining unresolved terms to buyers`.



### E05S06 · 42–50 · Teczka jest jedna

- **Miejsce:** stanowisko Marty; **obsada:** Marta, Kuba.

- **Działanie:** Marta otwiera Pliki sprawy; pokazujemy papierową kartę T1 i nowo dołączony e-mail. Kuba zaznacza źródła w swojej roboczej notatce.

- **Dialog / napisy:** KUBA: „Znalezione. To wersja z korespondencji, nie potwierdzona przez panią Irenę”.

- **Kadr i montaż:** Match cut z poczty na jedną teczkę.

- **Prawdziwa funkcja / ograniczenie:** Pliki sprawy i rozdzielenie źródeł; brak automatycznego klasyfikatora maili.

- **Biblioteka wspólna:** `R08,R09,R14` · **nowy beat/ujęcie:** `N05F: potwierdzenie pochodzenia źródła`.

- **Punkt kontrolny:** Sprawdzić continuity, dane demonstracyjne i realne UI.

- **Minimalny prompt delta** (dołączany do jednego promptu bazowego, nie samodzielny): `authentic case attachments list with manually added email file and provisional terms`.



### E05S07 · 50–61 · Zawahanie Pawła

- **Miejsce:** recepcja; **obsada:** Paweł, Basia.

- **Działanie:** Paweł przynosi kolejną wiadomość od kupujących. Basia pyta o aktualne ustalenia z matką.

- **Dialog / napisy:** BASIA: „Czy pani Irena mówiła panu, że potwierdziła pierwszy grudnia?”

**PAWEŁ:** „Myślałem, że to już… załatwione”.

- **Kadr i montaż:** Dłuższa pauza na twarz Pawła, bez złowrogiej muzyki.

- **Prawdziwa funkcja / ograniczenie:** Brak. Prawdziwa intryga jest w ludzkich relacjach.

- **Biblioteka wspólna:** `R01` · **nowy beat/ujęcie:** `N05G: Paweł pierwszy raz pokazuje wątpliwości`.

- **Punkt kontrolny:** Paweł nie jest pełnomocnikiem.

- **Minimalny prompt delta** (dołączany do jednego promptu bazowego, nie samodzielny): `son hesitates when asked whether his mother actually confirmed terms`.



### E05S08 · 61–70 · Pytanie

- **Miejsce:** plansza + drobna reakcja; **obsada:** Paweł.

- **Działanie:** Pawłowi wibruje telefon. Na ekranie nie ma nowego zwrotu fabularnego — tylko krótka etykieta „Rezerwacja mieszkania”. Paweł chowa aparat.

- **Dialog / napisy:** NAPIS: „Dlaczego tak mu zależy na czasie?”

- **Kadr i montaż:** Krótki telefoniczny insert + outro.

- **Prawdziwa funkcja / ograniczenie:** Brak.

- **Biblioteka wspólna:** `R10,R20` · **nowy beat/ujęcie:** `N05H: preview prywatnego przypomnienia rezerwacji`.

- **Punkt kontrolny:** Nie pokazywać prawdziwej płatności czy tytułów.

- **Minimalny prompt delta** (dołączany do jednego promptu bazowego, nie samodzielny): `phone showing fictional apartment reservation reminder held discreetly`.




## Kluczowe warunki prawne i produktowe

- BRAK potwierdzonego mail-inbox→automatyczne przypisanie: nie inscenizować AI, które samo czyta przychodzącą skrzynkę.

- Nie wprowadzać screenów lub komunikatów, których rzeczywisty NotarAI nie wygenerował podczas testu.

- W każdym ujęciu ze sprawą główną zachować cenę 640 000 zł, wydanie 15.01.2027 r. po ustaleniach T2 i tytuł „NOWAK — KACZMAREK”.

- Tytuł własności, sytuację majątkową stron, sposoby zapłaty oraz stan KW zweryfikować przed inscenizacją czynności.


## Mailing do odcinka: kierunek
Zawsze dobrze wiedzieć, skąd pochodzi załącznik i kto potwierdził warunki.

**CTA:** Zobacz elektroniczną teczkę sprawy. Nie zdradzać w mailu puenty odcinka.


## Reuse

Ujęcia R** odczytać w `04_PROMPTY_I_MONTAZ/BIBLIOTEKA_UREC.md`. Nowy beat N** jest unikalną grą aktorską lub realnym nagraniem UI, ale nie wymaga nowego wygenerowania całej scenografii ani nowego promptu tożsamości.


## Decyzja o publikacji

**HOLD** do czasu zatwierdzenia przez praktykującego notariusza, testów UX na syntetycznej teczce oraz kontroli napisów.

---
