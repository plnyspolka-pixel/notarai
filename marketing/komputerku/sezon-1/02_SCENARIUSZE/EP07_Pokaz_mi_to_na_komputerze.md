# EP07 — Pokaż mi to na komputerze

> **Nota dramaturgiczna V5 — powracający gag „nakarmić komputerka”.** Po trudnym dniu Zosia zauważa, że sami nie jedli od rana. Kuba proponuje wspólny posiłek, zamiast kolejnego wykładu o narzędziu. Żart obsługuje romans poza kancelarią. Szczegóły, rytm i ograniczenia produktu: [biblia gagu](../08_MOTYW_KARMIENIE_KOMPUTERKA.md). Beat jest propozycją do następnego passu scenariuszowego; wszystkie dotychczasowe ujęcia pozostają do oceny przed ewentualnym nowym renderem.


**Data fabularna:** 25.11.2026 · **Czas:** 76 s · **Wersja:** robocza do autoryzacji · **Format:** 9:16, adaptacja 16:9


> **Kanon:** nie zmieniać nazwisk, wieku, relacji, dat ani dokumentów z `01_KANON/BIBLIA_INTRYGI_KANON_2026-11-12.md`. Odcinek nie jest konsultacją prawną; przed publikacją wymaga kontroli notariusza.


## Funkcja główna
Mobilny kokpit sprawy w trybie chmurowym; przygotowanie projektu


**Uzupełniające:** Lokalny pomocnik „Klikamy” na komputerze kancelarii, lecz bez bezdotykowego zdalnego wywołania z telefonu.


**Logline:** Helena poza kancelarią sprawdza status sprawy na telefonie, a w biurze Marta przygotowuje kolejną wersję projektu.


**Hak:** Helena poza biurem widzi status „Projekt Word”, ale wciąż potrzebuje potwierdzenia warunków.


**Co widz odkrywa:** Irena, kupujący i Paweł wreszcie rozmawiają o jednej wersji warunków z wydaniem 15 stycznia.


**Pytanie końcowe:** Czy zdążą przygotować bezpieczny projekt do piątku?


## Scenopis — wszystkie sceny


### E07S01 · 00–06 · Zdalny podgląd

- **Miejsce:** korytarz poza kancelarią; **obsada:** Helena.

- **Działanie:** Helena wychodzi z budynku, zatrzymuje się przed wejściem na spotkanie. Na ekranie telefonu widać NotarAI, nie tę samą makietę co na laptopie.

- **Dialog / napisy:** HELENA (pod nosem): „Sprawdźmy, co mamy”.

- **Kadr i montaż:** Półplan Helena, screen-record realnego mobilnego frontendu.

- **Prawdziwa funkcja / ograniczenie:** `/api/sprawy` i kokpit w trybie SaaS po autoryzacji.

- **Biblioteka wspólna:** `R10,R17` · **nowy beat/ujęcie:** `N07A: Helena poza biurem z telefonem`.

- **Punkt kontrolny:** Przed emisją test mobile konta, uprawnień i danych w chmurze.

- **Minimalny prompt delta** (dołączany do jednego promptu bazowego, nie samodzielny): `senior notary checking authentic NotarAI mobile case dashboard outside office`.



### E07S02 · 06–15 · Projekt nie oznacza końca

- **Miejsce:** telefon Heleny; **obsada:** Helena.

- **Działanie:** Helena otwiera „Moje sprawy” → NOWAK–KACZMAREK. Ekran wskazuje zapisany projekt, ale nie „sprawa zakończona”.

- **Dialog / napisy:** HELENA: „Projekt jest. Czekam jeszcze na potwierdzenie terminu wydania”.

- **Kadr i montaż:** Ujęcie mobilnego ekranu z prawdziwym statusem; zero fikcyjnych kart z automatycznym assignment.

- **Prawdziwa funkcja / ograniczenie:** Kokpit statusu projektu, nie pełny global task manager.

- **Biblioteka wspólna:** `R10,R14` · **nowy beat/ujęcie:** `N07B: rzeczywisty status sprawy na telefonie`.

- **Punkt kontrolny:** W aplikacji tryb SaaS.

- **Minimalny prompt delta** (dołączany do jednego promptu bazowego, nie samodzielny): `mobile dashboard genuine review-needed status not falsely marked approved`.



### E07S03 · 15–23 · Dobra rozmowa zamiast komendy

- **Miejsce:** stanowisko Marty; **obsada:** Marta, Kuba.

- **Działanie:** Helena dzwoni do Marty. Marta sprawdza, czy strony przekazały zgodne ustalenia i dokumenty D11.

- **Dialog / napisy:** HELENA (przez telefon): „Marto, pokaż mi, co jest już potwierdzone. Bez założeń”.

**MARTA:** „Sprawdzam źródła”.

- **Kadr i montaż:** Split edit dwóch realnych ujęć, bez animacji zdalnego kliknięcia.

- **Prawdziwa funkcja / ograniczenie:** Dane w sprawie + zwykły telefon; żadnego wywołania AI na zdalnym PC.

- **Biblioteka wspólna:** `R07,R10` · **nowy beat/ujęcie:** `N07C: autentyczna współpraca na odległość`.

- **Punkt kontrolny:** Nie podawać „Komputerku pokaż na moim komputerze” jako funkcji, dopóki nie przetestowano.

- **Minimalny prompt delta** (dołączany do jednego promptu bazowego, nie samodzielny): `colleague on office laptop reporting case status by phone`.



### E07S04 · 23–34 · Wspólny język

- **Miejsce:** recepcja / stół; **obsada:** Irena, Paweł, Joanna, Robert.

- **Działanie:** Przedstawiciele stron rozmawiają przy stole; Paweł nie mówi już za matkę. Kupujący potwierdzają, że mogą przedłużyć najem.

- **Dialog / napisy:** IRENA: „Potrzebuję czasu do piętnastego stycznia”.

**JOANNA:** „Udało nam się przedłużyć najem”.

**PAWEŁ:** „Mamo, przepraszam, że wszystko przyspieszyłem”.

- **Kadr i montaż:** Szeroki czteroosobowy plan, potem CU Ireny.

- **Prawdziwa funkcja / ograniczenie:** Brak. To człowiek ustala fakty.

- **Biblioteka wspólna:** `R02` · **nowy beat/ujęcie:** `N07D: unikalne emocjonalne pojednanie`.

- **Punkt kontrolny:** Nie przedstawiać jeszcze, że umowa została zawarta.

- **Minimalny prompt delta** (dołączany do jednego promptu bazowego, nie samodzielny): `mother son and married couple reach agreement around notary table`.



### E07S05 · 34–43 · Nowa wersja warunków

- **Miejsce:** stanowisko Marty; **obsada:** Marta, Kuba.

- **Działanie:** Marta wpisuje potwierdzone ustalenia do rzeczywistej rozmowy o sprawie lub aktualizuje pola i opis; źródłem jest oddzielnie przygotowana notatka D11, nie sam mail Pawła.

- **Dialog / napisy:** KUBA: „Piętnasty stycznia. Ustalony już ze wszystkimi”.

**MARTA:** „Zapisz źródło, nie tylko datę”.

- **Kadr i montaż:** CU notatki D11, klawiatura i prawdziwe UI.

- **Prawdziwa funkcja / ograniczenie:** Rozmowa o sprawie, dane do projektu; brak automatycznej formalnej akceptacji warunków.

- **Biblioteka wspólna:** `R08,R09` · **nowy beat/ujęcie:** `N07E: aktualizacja warunków z kontrolą źródła`.

- **Punkt kontrolny:** Komplet dokumentów i finansowania nadal do weryfikacji.

- **Minimalny prompt delta** (dołączany do jednego promptu bazowego, nie samodzielny): `notary enters verified January 15 handover terms in case notes`.



### E07S06 · 43–53 · Komputerku, robimy projekt

- **Miejsce:** stanowisko Marty; **obsada:** Marta.

- **Działanie:** Marta zwraca się do komputera zwyczajowo, klika „Sporządź projekt”; w filmie następuje wyraźny przeskok czasu.

- **Dialog / napisy:** MARTA: „Komputerku, przygotujmy kolejną wersję. Na tych ustaleniach”.

- **Kadr i montaż:** Prawdziwe UI i kliknięcie, nie sztuczny głos sterujący.

- **Prawdziwa funkcja / ograniczenie:** Generowanie projektu i raport zgodności.

- **Biblioteka wspólna:** `R08,R14,R15` · **nowy beat/ujęcie:** `N07F: unikalne rozpoczęcie generowania po nowym potwierdzeniu`.

- **Punkt kontrolny:** Projekt nadal jest do kontroli; nie obiecywać natychmiastowego wyniku.

- **Minimalny prompt delta** (dołączany do jednego promptu bazowego, nie samodzielny): `authentic word drafting UI after verified data update`.



### E07S07 · 53–61 · Granica pomocnika

- **Miejsce:** lokalny komputer kancelarii; **obsada:** Kuba, Marta.

- **Działanie:** Kuba pokazuje uruchomionego na komputerze pomocnika. Marta zaznacza, że może on pomóc w pracy z dozwolonymi portalami, ale zatrzymuje się przed wysłaniem, podpisaniem i płatnością.

- **Dialog / napisy:** KUBA: „Pomocnik działa tutaj, na naszym komputerze”.

**MARTA:** „A decyzje i podpisy zostają przy nas”.

- **Kadr i montaż:** Tylko prawdziwy ekran lokalnego pomocnika.

- **Prawdziwa funkcja / ograniczenie:** `pomocnik/klikamy.py`; kontrola działań o skutku zewnętrznym.

- **Biblioteka wspólna:** `R16,R14` · **nowy beat/ujęcie:** `N07G: autentyczna praca lokalnego pomocnika`.

- **Punkt kontrolny:** Połączenie urządzeń należy potwierdzić; nie udawać zdalnego polecenia z telefonu.

- **Minimalny prompt delta** (dołączany do jednego promptu bazowego, nie samodzielny): `local notary computer browser helper with cautious human control`.



### E07S08 · 61–69 · Spokój, ale nie koniec

- **Miejsce:** poza kancelarią; **obsada:** Helena.

- **Działanie:** Helena kończy połączenie, na telefonie widzi otwartą sprawę. Chowa urządzenie i idzie na spotkanie.

- **Dialog / napisy:** HELENA: „Dobrze. Jutro sprawdzę to na spokojnie”.

- **Kadr i montaż:** Kadr średni, dzień pochmurny, naturalna uliczna cisza.

- **Prawdziwa funkcja / ograniczenie:** Mobilny dostęp do stanu sprawy, bez fikcyjnego raportu zadań.

- **Biblioteka wspólna:** `R17,R10` · **nowy beat/ujęcie:** `N07H: komfort bez bycia stale online`.

- **Punkt kontrolny:** Sprawdzić continuity, dane demonstracyjne i realne UI.

- **Minimalny prompt delta** (dołączany do jednego promptu bazowego, nie samodzielny): `senior professional pockets phone after checking office case progress`.



### E07S09 · 69–76 · Cliffhanger

- **Miejsce:** plansza; **obsada:** -.

- **Działanie:** Plansza z datą „Piątek, 27 listopada” nad konturem dokumentu.

- **Dialog / napisy:** NAPIS: „Czy wszystko jest gotowe do podpisania?”

- **Kadr i montaż:** Stały outro.

- **Prawdziwa funkcja / ograniczenie:** Brak.

- **Biblioteka wspólna:** `R20` · **nowy beat/ujęcie:** `-`.

- **Punkt kontrolny:** Sprawdzić continuity, dane demonstracyjne i realne UI.

- **Minimalny prompt delta** (dołączany do jednego promptu bazowego, nie samodzielny): `clean legal technology suspense endcard with upcoming Friday date`.




## Kluczowe warunki prawne i produktowe

- Tryb lokalnego przechowywania nie uprawnia do obietnicy dostępu z całego świata; głos nie wykonuje zadań automatycznie.

- Nie wprowadzać screenów lub komunikatów, których rzeczywisty NotarAI nie wygenerował podczas testu.

- W każdym ujęciu ze sprawą główną zachować cenę 640 000 zł, wydanie 15.01.2027 r. po ustaleniach T2 i tytuł „NOWAK — KACZMAREK”.

- Tytuł własności, sytuację majątkową stron, sposoby zapłaty oraz stan KW zweryfikować przed inscenizacją czynności.


## Mailing do odcinka: kierunek
Notariusz może zobaczyć status sprawy poza biurem, ale nie musi wszystkiego robić sam.

**CTA:** Zobacz mobilny kokpit i projekt Word. Nie zdradzać w mailu puenty odcinka.


## Reuse

Ujęcia R** odczytać w `04_PROMPTY_I_MONTAZ/BIBLIOTEKA_UREC.md`. Nowy beat N** jest unikalną grą aktorską lub realnym nagraniem UI, ale nie wymaga nowego wygenerowania całej scenografii ani nowego promptu tożsamości.


## Decyzja o publikacji

**HOLD** do czasu zatwierdzenia przez praktykującego notariusza, testów UX na syntetycznej teczce oraz kontroli napisów.

---
