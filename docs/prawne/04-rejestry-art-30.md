# REJESTRY PRZETWARZANIA FUNDACJI (art. 30 RODO)

Prowadzi: Fundacja Krzewienia Edukacji Finansowej im. Pieczaka,
ul. Wilhelma Orlika Ruckemana 4/18, 20-244 Lublin, KRS 0001140846. Kontakt: kontakt@notarai.pl. Inspektor ochrony danych: [nie wyznaczono
/ imię i nazwisko].

Rejestry prowadzi się w formie elektronicznej, aktualizuje przy każdej
zmianie i udostępnia Prezesowi UODO na żądanie. Zwolnienie z art. 30 ust. 5
RODO nie ma zastosowania, bo przetwarzanie nie ma charakteru sporadycznego
i obejmuje dane z art. 9 i 10 RODO.

Data ostatniej aktualizacji: [data].

---

## Część A. Rejestr kategorii czynności przetwarzania - Fundacja jako podmiot przetwarzający (art. 30 ust. 2)

| Pole | Treść |
|---|---|
| Podmiot przetwarzający | Fundacja (jw.) |
| Administratorzy, w imieniu których przetwarzamy | Kancelarie notarialne - wykaz w tabeli niżej |
| Kategoria przetwarzania | Świadczenie usługi notarai: przechowywanie materiałów spraw, odczyt dokumentów przez model AI, walidacja danych, przygotowanie projektów dokumentów, rozmowa z asystentem, wsparcie pracy z rejestrami publicznymi |
| Rodzaje danych | jak w Załączniku nr 1 do umowy powierzenia (w tym PESEL, dane z art. 9 i 10 RODO, jeżeli występują w dokumentach) |
| Przekazania do państw trzecich | brak; przetwarzanie wyłącznie w EOG (AWS Frankfurt; model w regionach UE) |
| Dalsi podmioty przetwarzający | Amazon Web Services EMEA SARL |
| Ogólny opis środków bezpieczeństwa (art. 32 ust. 1) | Załącznik nr 2 do umowy powierzenia |

### Wykaz administratorów

| Lp. | Notariusz / kancelaria | Kontakt (osoba, e-mail) | Data umowy powierzenia | Tryb plików | Data zakończenia i usunięcia danych |
|---|---|---|---|---|---|
| 1 | | | | chmura / u kancelarii | |

---

## Część B. Rejestr czynności przetwarzania - Fundacja jako administrator (art. 30 ust. 1)

| Lp. | Nazwa czynności | Cel | Kategorie osób | Kategorie danych | Odbiorcy | Państwa trzecie | Okres przechowywania | Środki bezpieczeństwa |
|---|---|---|---|---|---|---|---|---|
| 1 | Konta użytkowników notarai | prowadzenie kont, logowanie, zaproszenia | notariusze, pracownicy kancelarii | e-mail, imię i nazwisko, kancelaria, rola, daty, dane logowania | AWS EMEA SARL | brak | do usunięcia konta + 90 dni | Załącznik nr 2 do umowy powierzenia, część C |
| 2 | Dzienniki bezpieczeństwa | bezpieczeństwo usługi, wykrywanie awarii i nadużyć | użytkownicy | IP, identyfikatory techniczne, czas, kody błędów | AWS EMEA SARL | brak | 90 dni | jw., część E |
| 3 | Umowy z kancelariami i rozliczenia | zawarcie i wykonanie umowy, księgowość | notariusze, osoby reprezentujące | dane identyfikacyjne i kontaktowe, NIP, dane do faktur | biuro rachunkowe [●], organy podatkowe | brak | 5 lat podatkowych + przedawnienie roszczeń | dostęp imienny, poczta z MFA |
| 4 | Korespondencja, reklamacje, zgłoszenia DSA | obsługa zapytań | osoby kontaktujące się | e-mail, imię i nazwisko, treść | dostawca poczty [●] | brak | do zakończenia sprawy, max 3 lata | jw. |
| 5 | Osoby upoważnione Fundacji | upoważnienia, poufność | członkowie zarządu, współpracownicy | imię i nazwisko, zakres upoważnienia, podpis | brak | brak | czas współpracy + 5 lat | dokumentacja w zamkniętej szafie / repozytorium z ograniczonym dostępem |

---

## Część C. Rejestr naruszeń (art. 33 ust. 5 - prowadzony pomocniczo)

Administratorem dla danych w sprawach jest kancelaria i to ona prowadzi
właściwy rejestr naruszeń. Fundacja prowadzi własną ewidencję incydentów,
żeby wykazać terminowe zgłoszenia (procedura w pliku 05).

| Lp. | Data wykrycia | Opis | Dotknięte kancelarie | Kategorie i liczba osób | Ocena ryzyka | Data i sposób zgłoszenia kancelarii | Działania naprawcze |
|---|---|---|---|---|---|---|---|

## Część D. Rejestr dostępów serwisowych do treści spraw

| Lp. | Data | Osoba Fundacji | Kancelaria / sprawa | Powód | Zgoda (kto, kiedy, jak) | Zakres dostępu |
|---|---|---|---|---|---|---|
