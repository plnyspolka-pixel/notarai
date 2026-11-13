# EP06 — Kto ma tę sprawę?

> **Nota dramaturgiczna V5 — powracający gag „nakarmić komputerka”.** Ciocia Teresa Janicka w swojej dwuosobowej kancelarii pyta rzeczowo, ile «komputerek» kosztuje miesięcznie. Rozmowa dotyczy organizacji pracy, a nie obietnicy darmowej automatyzacji. Szczegóły, rytm i ograniczenia produktu: [biblia gagu](../08_MOTYW_KARMIENIE_KOMPUTERKA.md). Beat jest propozycją do następnego passu scenariuszowego; wszystkie dotychczasowe ujęcia pozostają do oceny przed ewentualnym nowym renderem.


**Data fabularna:** 23.11.2026 · **Czas:** 80 s · **Wersja:** robocza do autoryzacji · **Format:** 9:16, adaptacja 16:9


> **Kanon:** nie zmieniać nazwisk, wieku, relacji, dat ani dokumentów z `01_KANON/BIBLIA_INTRYGI_KANON_2026-11-12.md`. Odcinek nie jest konsultacją prawną; przed publikacją wymaga kontroli notariusza.


## Funkcja główna
Sprawdzenie KRZ przez lokalnego pomocnika w osobnej sprawie


**Uzupełniające:** Zespół i uprawnienia; kalendarz; lista spraw; archiwum wyniku.


**Logline:** Jednocześnie prowadzone sprawy naświetlają rolę kalendarza, zespołu i sprawdzenia KRZ, a Paweł ujawnia swój błąd.


**Hak:** Trzy osoby pytają naraz, kto zajmuje się którym dokumentem.


**Co widz odkrywa:** Paweł wpłacił z własnych środków opłatę rezerwacyjną za mieszkanie na parterze.


**Pytanie końcowe:** Czy Irena wybaczy mu przejęcie inicjatywy?


## Scenopis — wszystkie sceny


### E06S01 · 00–07 · Nakładają się pytania

- **Miejsce:** recepcja / korytarz; **obsada:** Basia, Marta, Kuba.

- **Działanie:** Basia rozmawia przez telefon, Marta pyta o termin, Kuba o plik w innej sprawie. Urywki rozmów splatają się w jeden rytm.

- **Dialog / napisy:** BASIA: „Jedno po drugim, proszę…”

**KUBA:** „Która teczka jest teraz pilna?”

**MARTA:** „Najpierw terminy”.

- **Kadr i montaż:** Montaż trzy plany; kontrolowany chaos dźwiękowy.

- **Prawdziwa funkcja / ograniczenie:** Brak. Początek organizacyjny.

- **Biblioteka wspólna:** `R01,R03,R04` · **nowy beat/ujęcie:** `N06A: potrójna interakcja w recepcji`.

- **Punkt kontrolny:** Sprawdzić continuity, dane demonstracyjne i realne UI.

- **Minimalny prompt delta** (dołączany do jednego promptu bazowego, nie samodzielny): `busy secretary and two notary colleagues coordinate overlapping tasks`.



### E06S02 · 07–15 · Wspólna lista spraw

- **Miejsce:** stanowisko Marty; **obsada:** Marta, Kuba.

- **Działanie:** Marta otwiera kokpit „Moje sprawy”, filtruje i znajduje sprawę Nowak oraz odrębną sprawę do sprawdzenia w KRZ.

- **Dialog / napisy:** MARTA: „Sprawa Nowak jest tu. Borowska jest osobno. A to jest sprawa do KRZ”.

- **Kadr i montaż:** Rzeczywisty kokpit, nie plansza nierealnych przypisań do pracowników.

- **Prawdziwa funkcja / ograniczenie:** Kokpit rzeczywisty `/api/sprawy`, wyszukiwanie/filtr.

- **Biblioteka wspólna:** `R08,R14` · **nowy beat/ujęcie:** `N06B: dwa różne wpisy listy spraw`.

- **Punkt kontrolny:** Nie sugerować automatycznego delegowania bez implementacji.

- **Minimalny prompt delta** (dołączany do jednego promptu bazowego, nie samodzielny): `authentic NotarAI cases dashboard showing several separate demo matters`.



### E06S03 · 15–23 · Termin i ludzie

- **Miejsce:** stanowisko Basi; **obsada:** Basia, Marta.

- **Działanie:** Basia przegląda kalendarz i listę osób zespołu. Zaznacza, jaki termin wymaga kontaktu z klientem.

- **Dialog / napisy:** BASIA: „Kontakt mam. Termin widzę. Teraz potrzebujemy potwierdzenia od stron”.

- **Kadr i montaż:** Przebitka kalendarz → twarz Basi.

- **Prawdziwa funkcja / ograniczenie:** Kalendarz, telefony do stron, konta zespołu.

- **Biblioteka wspólna:** `R10,R14` · **nowy beat/ujęcie:** `N06C: prawdziwe elementy menu`.

- **Punkt kontrolny:** Nie tworzyć fikcyjnej tablicy „przydzielono Basi”, jeśli brak w UI.

- **Minimalny prompt delta** (dołączany do jednego promptu bazowego, nie samodzielny): `secretary reviewing real calendar entries and contacts`.



### E06S04 · 23–33 · KRZ nie jest jednym magicznym wynikiem

- **Miejsce:** lokalny komputer Kuby; **obsada:** Kuba, Marta.

- **Działanie:** Kuba, po jawnym potwierdzeniu i z uruchomionym lokalnym pomocnikiem, otwiera sprawdzenie KRZ w ODREBNEJ fikcyjnej sprawie. Portal może działać wolno.

- **Dialog / napisy:** KUBA: „Sprawdzenie ruszyło przez pomocnika na tym komputerze”.

**MARTA:** „Zapisz wynik, a potem go ocenimy”.

- **Kadr i montaż:** Ujęcie pomagające zrozumieć, że przeglądarka jest lokalna; bez fałszywego wyniku.

- **Prawdziwa funkcja / ograniczenie:** `/api/sprawy/{id}/krz`, pomocnik KRZ; działanie zależne od portalu.

- **Biblioteka wspólna:** `R08,R11,R16` · **nowy beat/ujęcie:** `N06D: prawdziwy przebieg KRZ na środowisku testowym`.

- **Punkt kontrolny:** Nie używać prawdziwego PESEL ani nie twierdzić, że „brak wpisu” oznacza bezwzględne bezpieczeństwo.

- **Minimalny prompt delta** (dołączany do jednego promptu bazowego, nie samodzielny): `notary local browser assistant checking KRZ publicly with human review`.



### E06S05 · 33–41 · Zapis, nie wyrok

- **Miejsce:** stanowisko Marty; **obsada:** Kuba, Marta.

- **Działanie:** Marta ogląda ślad sprawdzenia w sprawie. Nie wyciąga automatycznego wniosku prawnego.

- **Dialog / napisy:** MARTA: „Dobrze. Mamy datę i wynik próby sprawdzenia. Teraz weryfikacja”.

- **Kadr i montaż:** CU rzeczywistej historii sprawdzeń, jeśli demo działa; w przeciwnym razie dokumentacyjne ujęcie bez nazwiska.

- **Prawdziwa funkcja / ograniczenie:** Ślad audytowy `rejestry.py`, `krz.py`; odpowiedzialność człowieka.

- **Biblioteka wspólna:** `R14` · **nowy beat/ujęcie:** `N06E: podgląd faktycznie uzyskanego wyniku`.

- **Punkt kontrolny:** Wynik portalu tylko z dozwolonych danych testowych.

- **Minimalny prompt delta** (dołączany do jednego promptu bazowego, nie samodzielny): `authentic case check audit log without personal identifiers`.



### E06S06 · 41–50 · Prawda wychodzi na jaw

- **Miejsce:** korytarz; **obsada:** Paweł, Marta.

- **Działanie:** Paweł zostaje na chwilę na osobności z Martą, pokazuje własną notatkę o rezerwacji mieszkania na parterze.

- **Dialog / napisy:** PAWEŁ: „Znalazłem mamie mieszkanie bez schodów. Zapłaciłem za rezerwację. I potem zacząłem wszystko przyspieszać”.

- **Kadr i montaż:** Zbliżenie na dłoń Pawła trzymającą potwierdzenie D21.

- **Prawdziwa funkcja / ograniczenie:** Brak. Rewelacja nie pochodzi z AI.

- **Biblioteka wspólna:** `R05,R09` · **nowy beat/ujęcie:** `N06F: wyznanie Pawła`.

- **Punkt kontrolny:** Paweł nie przerzuca własnych zobowiązań na matkę; dokument to fikcyjna rezerwacja.

- **Minimalny prompt delta** (dołączany do jednego promptu bazowego, nie samodzielny): `adult son confesses he reserved ground-floor flat with his own money`.



### E06S07 · 50–60 · Wstyd, nie przestępstwo

- **Miejsce:** korytarz; **obsada:** Paweł, Marta.

- **Działanie:** Marta nie ocenia go moralnie; wyjaśnia znaczenie potwierdzania informacji przez właściwe osoby.

- **Dialog / napisy:** MARTA: „Chciał pan jej pomóc. Ale to pani Irena decyduje, czy i kiedy”.

**PAWEŁ:** „Wiem. Teraz już wiem”.

- **Kadr i montaż:** Dłuższe ujęcie dwuosobowe, żadnego agresywnego cięcia.

- **Prawdziwa funkcja / ograniczenie:** Nie ma interwencji AI.

- **Biblioteka wspólna:** `R05` · **nowy beat/ujęcie:** `N06G: szczery wstyd Pawła`.

- **Punkt kontrolny:** Prawidłowa reprezentacja Ireny; nie sugerować winy karnej.

- **Minimalny prompt delta** (dołączany do jednego promptu bazowego, nie samodzielny): `gentle frank talk about autonomy and family pressure`.



### E06S08 · 60–71 · Wiedza o człowieku

- **Miejsce:** gabinet Heleny; **obsada:** Helena, Marta.

- **Działanie:** Marta przekazuje Helenie informację, że termin był efektem nadgorliwości syna. Helena rozumie sytuację, ale nie poświęca zasad.

- **Dialog / napisy:** HELENA: „Nie jest źle mieć dobry zamiar. Trzeba jeszcze zostawić drugiemu człowiekowi decyzję”.

- **Kadr i montaż:** Statyczny, bezpośredni portret Heleny.

- **Prawdziwa funkcja / ograniczenie:** Granice oceny prawnej.

- **Biblioteka wspólna:** `R06` · **nowy beat/ujęcie:** `N06H: lekcja Heleny`.

- **Punkt kontrolny:** Sprawdzić continuity, dane demonstracyjne i realne UI.

- **Minimalny prompt delta** (dołączany do jednego promptu bazowego, nie samodzielny): `experienced notary thoughtful reaction to family conflict`.



### E06S09 · 71–80 · Zawieszenie

- **Miejsce:** recepcja / plansza; **obsada:** Basia, Paweł.

- **Działanie:** Paweł wychodzi. Basia patrzy za nim, telefon dzwoni ponownie — tym razem nie rzuca się od razu, spokojnie kończy notatkę.

- **Dialog / napisy:** NAPIS: „Czy odważy się powiedzieć to matce?”

- **Kadr i montaż:** Wyjście z budynku + outro.

- **Prawdziwa funkcja / ograniczenie:** Brak.

- **Biblioteka wspólna:** `R01,R03,R20` · **nowy beat/ujęcie:** `N06I: cisza wśród hałasu`.

- **Punkt kontrolny:** Sprawdzić continuity, dane demonstracyjne i realne UI.

- **Minimalny prompt delta** (dołączany do jednego promptu bazowego, nie samodzielny): `somber adult man leaving legal office as secretary calmly finishes task`.




## Kluczowe warunki prawne i produktowe

- Nie ma globalnej, potwierdzonej tablicy przydziałów zadań. KRZ wynik to materiał do kontroli, nie automatyczna decyzja.

- Nie wprowadzać screenów lub komunikatów, których rzeczywisty NotarAI nie wygenerował podczas testu.

- W każdym ujęciu ze sprawą główną zachować cenę 640 000 zł, wydanie 15.01.2027 r. po ustaleniach T2 i tytuł „NOWAK — KACZMAREK”.

- Tytuł własności, sytuację majątkową stron, sposoby zapłaty oraz stan KW zweryfikować przed inscenizacją czynności.


## Mailing do odcinka: kierunek
Wspólne informacje o sprawach nie wymagają wspólnej pamięci jednej osoby.

**CTA:** Zobacz, jak sprawy i sprawdzenia trafiają do teczki. Nie zdradzać w mailu puenty odcinka.


## Reuse

Ujęcia R** odczytać w `04_PROMPTY_I_MONTAZ/BIBLIOTEKA_UREC.md`. Nowy beat N** jest unikalną grą aktorską lub realnym nagraniem UI, ale nie wymaga nowego wygenerowania całej scenografii ani nowego promptu tożsamości.


## Decyzja o publikacji

**HOLD** do czasu zatwierdzenia przez praktykującego notariusza, testów UX na syntetycznej teczce oraz kontroli napisów.

---
