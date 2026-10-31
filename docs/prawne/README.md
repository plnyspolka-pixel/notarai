# notarai - dokumentacja prawna

Komplet dla Fundacji Krzewienia Edukacji Finansowej im. Pieczaka jako
dostawcy usługi notarai. Stan na 31.10.2026 (Regulamin, umowa powierzenia i DPIA: dopisany
kalendarz i spis telefonów), pierwsze wersje obowiązują od
24.10.2026.

**Nic tu nie wymaga podpisu.** Kancelaria zakłada konto sama pod
app.notarai.pl/rejestracja i jednym zaznaczeniem akceptuje Regulamin razem
z umową powierzenia (art. 28 ust. 9 RODO dopuszcza formę elektroniczną).
Aplikacja zapisuje dowód: wersje, czas, e-mail, adres IP, dane kancelarii.

To nie jest porada prawna. Dokumenty obowiązują, ale przegląd przez radcę
prawnego od RODO i notariatu nadal jest dobrym pomysłem. Zmiany po
przeglądzie wprowadza się w trybie § 14 Regulaminu (14 dni, e-mail
i komunikat w aplikacji).

## Pliki

| Plik | Dla kogo | Jak się go przyjmuje |
|---|---|---|
| [01-umowa-powierzenia.md](01-umowa-powierzenia.md) | każda kancelaria, z 3 załącznikami | akceptacja w formularzu rejestracji (albo przy pierwszym logowaniu właściciela, gdy konto założył administrator); bez akceptacji serwer nie wpuszcza do spraw (428) |
| [02-regulamin.md](02-regulamin.md) | publiczny | jw., razem z umową |
| [03-polityka-prywatnosci.md](03-polityka-prywatnosci.md) | publiczna | - |
| [04-rejestry-art-30.md](04-rejestry-art-30.md) | wewnętrzny, Fundacja | wykaz kancelarii prowadzi aplikacja: `/admin` → Rejestr umów (CSV) |
| [05-procedura-naruszen.md](05-procedura-naruszen.md) | wewnętrzna, Fundacja | przyjęta przez zarząd 24.10.2026 |
| [06-upowaznienie-i-poufnosc.md](06-upowaznienie-i-poufnosc.md) | osoby Fundacji z dostępem | forma dokumentowa: e-mail albo wpis w pliku; prezes działa jako organ |
| [07-dpia-dla-kancelarii.md](07-dpia-dla-kancelarii.md) | kancelaria | aplikacja wypełnia ją danymi kancelarii, notariusz klika „Przyjmuję ocenę” |
| [08-dla-kancelarii-checklista.md](08-dla-kancelarii-checklista.md) | kancelaria | - |
| [09-instrukcja-ai.md](09-instrukcja-ai.md) | każda osoba w kancelarii (§ 4 ust. 5 Regulaminu, art. 4 AI Act) | każdy potwierdza ją sam przy pierwszym logowaniu |
| [10-rejestr-dostepow-serwisowych.md](10-rejestr-dostepow-serwisowych.md) | wewnętrzny, Fundacja (§ 5 ust. 4 umowy powierzenia) | wpisy prowadzi aplikacja; kancelaria widzi je w oknie „Zespół kancelarii” |

Wersja dokumentu to data w linii „Wersja z dnia DD.MM.RRRR.”. Aplikacja
porównuje ją z zaakceptowaną. Zmiana daty w 01 lub 02 oznacza, że
właściciele dostaną prośbę o akceptację nowej wersji, w 09 - że każdy
ponownie potwierdzi instrukcję, w 07 - że notariusz ponownie przyjmie ocenę.

Strony notarai.pl/regulamin, /umowa-powierzenia, /instrukcja-ai
i /prywatnosc generuje `py -3 infra/strona_dokumenty.py`. Aplikacja
pokazuje te same pliki pod app.notarai.pl/dokumenty/... (z obrazu, więc
zawsze w wersji, która jest wdrożona). Po każdej zmianie uruchom generator
i wyślij stronę.

Opis techniczny „co się dzieje z danymi” jest w [../ochrona-danych.md](../ochrona-danych.md);
Załącznik nr 2 do umowy powierzenia musi się z nim zgadzać.

## Blokery - zanim podłączysz pierwszą obcą kancelarię

Prawne:

1. **Statut i KRS** - według Ciebie załatwione. Uwaga: aktualny odpis z API
   KRS (pobrany 23.10.2026, stan na 13.11.2025) pokazuje Fundację
   w rejestrze przedsiębiorców, bez statusu OPP, ale **bez PKD z działu 62/63**
   (oprogramowanie, hosting) - przeważające 85.59.B, reszta to finanse
   i nieruchomości. Jeżeli wniosek o zmianę PKD jest w sądzie, wszystko
   w porządku; jeżeli nie - dopisać np. 62.10 i 63.10 (PKD 2025) przy
   najbliższej zmianie wpisu.
2. Dane uzupełnione 24.10.2026: cena 600 zł bez VAT (Fundacja zwolniona,
   art. 113 - sprawdzone na białej liście; limit 200 000 zł rocznie to
   około 27 kancelarii przez cały rok, potem VAT i zmiana ceny w trybie
   § 14), przerwy zapowiadane 48 h przed, wypowiedzenie przez Fundację
   3 miesiące, IOD niewyznaczony, księgowość bez biura, poczta AZ.pl.
3. Upoważnienia (plik 06): dostęp ma tylko prezes, który działa jako organ.
   Każda kolejna osoba dostaje upoważnienie e-mailem i odpowiada
   zobowiązaniem - dopiero potem dostęp.
4. **Opublikować** stronę z dokumentami: `py -3 infra/strona_dokumenty.py`,
   potem `infra\strona.ps1 wyslij`.

Techniczne - kod gotowy, zostało wdrożyć (Ty uruchamiasz polecenia AWS):

5. MFA na koncie głównym AWS - zrobione.
6. **Nowa wersja aplikacji** (rejestracja z akceptacją umowy, dokumenty
   w aplikacji, usuwanie całej kancelarii, metadane AI w .docx, adres
   alarmów `plnyspolka@gmail.com` wpisany w skrypt jako domyślny):
   etap 2 i 3 jak zwykle. Rejestracja jest włączona parametrem stosu
   `Rejestracja` (domyślnie `true`). Po etapie 3 **potwierdź subskrypcję**
   linkiem z maila od AWS - bez tego alarmy nie dojdą.
7. **Kopia zapasowa** - nowy stos `infra/notarai-kopia.yaml`. Najpierw
   sprawdź, czy AWS Backup ma włączone S3 w regionie:

   ```powershell
   aws backup describe-region-settings --profile notarai-admin --region eu-central-1
   ```

   W wyniku `S3` musi mieć `true`; jeśli nie:
   `aws backup update-region-settings --resource-type-opt-in-preference S3=true --profile notarai-admin --region eu-central-1`.
   Potem (ARN tematu z wyniku `TematAlarmow` stosu `notarai-aplikacja`):

   ```powershell
   aws cloudformation deploy --stack-name notarai-kopia --template-file infra/notarai-kopia.yaml --capabilities CAPABILITY_NAMED_IAM --parameter-overrides TematAlarmow=<ARN tematu> --tags projekt=notarai --profile notarai-admin --region eu-central-1
   ```

   **Blokada sejfu po 3 dniach staje się nieodwracalna** (o to chodzi:
   przejęte konto nie skasuje kopii). Przez te 3 dni sprawdź, że nocna kopia
   się udała (konsola AWS Backup -> Jobs), i zrób raz próbne odtworzenie
   jednej sprawy do nowego bucketa.
8. Zalecane na później: MFA dla użytkowników w Cognito; kopia na drugim koncie
   AWS (wymaga AWS Organizations).

### Procedura końca współpracy z kancelarią

1. Panel `/admin` -> **Wyłącz kancelarię**.
2. Daj kancelarii czas na pobranie spraw (umowa: do 14 dni po końcu usługi
   na wniosek o kopię).
3. **Usuń wszystkie dane…** -> przepisz identyfikator. Zapisz datę z
   komunikatu i potwierdź ją notariuszowi e-mailem (umowa § 12 ust. 4).
4. Uruchom ponownie etap 3 (albo wymuś nowe wdrożenie usługi ECS), żeby
   wymienić kontenery - ich ulotna pamięć podręczna mogła trzymać pliki
   kancelarii, jeśli obsługiwał ją inny kontener niż ten, który usuwał.
5. Kopie zapasowe wygasną same po 21 dniach - mieści się to w 30 dniach
   z umowy.
6. Rejestr umów zapisuje datę usunięcia sam (historia przez 5 lat).

## Najważniejsze kwestie prawne i jak je rozwiązuje komplet

### RODO - rola Fundacji

Notariusz jest administratorem danych klientów. Fundacja jest podmiotem
przetwarzającym (art. 28 RODO) - także w trybie „Pliki u kancelarii”, bo
skany i tak przechodzą przez serwer i model. AWS jest dalszym podmiotem
przetwarzającym na podstawie AWS GDPR DPA, akceptowanego automatycznie
w AWS Service Terms. Anthropic nie jest podmiotem przetwarzającym - model
działa w infrastrukturze AWS (Bedrock) i dostawca modelu nie ma dostępu do
treści.

Dla danych użytkowników (konta, logowanie, kontakt) Fundacja jest
administratorem - stąd polityka prywatności i część B rejestru.

### Tajemnica notarialna (art. 18 Prawa o notariacie)

Przepis wiąże notariusza, nie dostawcę IT. Ustawa nie zakazuje wprost
korzystania przez notariusza z zewnętrznych usług informatycznych, ale nie
znalazłam (i nie mogę zweryfikować bez dostępu do aktualnych uchwał) stanowiska
Krajowej Rady Notarialnej dotyczącego chmury i AI. Komplet rozwiązuje to
umownie: § 5 umowy powierzenia rozciąga obowiązek tajemnicy na Fundację i jej
osoby bezterminowo, stwierdza, że Fundacja nie ma dostępu do treści spraw,
dopuszcza wyłącznie dostęp serwisowy włączany przez samą kancelarię na
wskazany czas i rejestrowany w aplikacji oraz nakłada procedurę na żądania
organów. Kod pilnuje tego samego: panel administracyjny nie otwiera spraw,
a polityka magazynu zakazuje odczytu wszystkim poza aplikacją i kopią
zapasową. Dla kancelarii, która
nie chce, by cokolwiek leżało poza nią, jest tryb „Pliki u kancelarii”.
Warto, by pierwszy notariusz-klient zapytał swoją izbę notarialną, czy są
wytyczne samorządu - to rozwiewa wątpliwości kolejnych.

### Dane szczególnych kategorii i PESEL

W aktach pojawiają się dane o zdrowiu (np. osoba niewidoma, niepiśmienna,
orzeczenia) i o ubezwłasnowolnieniu czy upadłości. Umowa wprost je obejmuje
i wymaga najwyższego poziomu ochrony dla wszystkich danych. Z tego powodu
i z powodu użycia AI kancelaria powinna przeprowadzić DPIA (wzór 07).

### AI Act (rozporządzenie 2024/1689)

- notarai **nie jest systemem wysokiego ryzyka**: notariusz nie jest
  organem wymiaru sprawiedliwości w rozumieniu załącznika III pkt 8,
  a system nie podejmuje decyzji - przygotowuje projekty do weryfikacji.
  To jest moja ocena; warto, by prawnik ją potwierdził.
- **art. 4 (kompetencje w zakresie AI)** obowiązuje od 2.02.2025 Fundację
  i kancelarie - pokrywa to instrukcja z ograniczeniami modelu
  (Regulamin § 4 ust. 5) i punkt 6 checklisty kancelarii. Instrukcję trzeba
  napisać, jeśli jej jeszcze nie ma w aplikacji.
- **art. 50 (przejrzystość)**: użytkownicy muszą wiedzieć, że pracują z AI
  (Regulamin § 4 ust. 1, plus oznaczenie w interfejsie). Obowiązek
  znakowania treści generowanych w formacie maszynowym (art. 50 ust. 2)
  przewidywano od 2.08.2026, a pakiet Digital Omnibus miał go przesunąć dla
  istniejących systemów - **nie mam pewności co do ostatecznego stanu**.
  Niezależnie od wyniku pobierany projekt .docx ma już w metadanych
  (autor, kategoria, słowa kluczowe, komentarz) informację, że powstał
  z udziałem AI i wymaga weryfikacji notariusza.

### Akt o usługach cyfrowych (DSA)

notarai przechowuje treści na żądanie użytkowników, więc jest usługą
hostingu. Dla mikroprzedsiębiorcy obowiązują: punkt kontaktowy (art. 11-12),
informacje w regulaminie (art. 14) i mechanizm zgłaszania nielegalnych treści
(art. 16-17) - są w Regulaminie § 1 i § 8. Obowiązki raportowe i platformowe
nie dotyczą mikro i małych przedsiębiorstw.

### Świadczenie usług drogą elektroniczną

Ustawa o ŚUDE (art. 8) wymaga regulaminu z zakresem usług, wymaganiami
technicznymi, zakazem treści bezprawnych, zasadami zawierania i rozwiązywania
umów i trybem reklamacji - wszystko jest w pliku 02.

### Rejestry publiczne i pomocnik

Pomocnik działa w przeglądarce notariusza, na jego koncie i po jego
zalogowaniu - Fundacja nie dostaje haseł, a program nie wysyła ani nie
podpisuje wniosków. To dobra konstrukcja. Ryzyko do sprawdzenia przez
prawnika: regulaminy poszczególnych portali (EKW, KRZ, rejestr PESEL dla
notariuszy) mogą ograniczać automatyzację - sprawdzić przed szerokim
udostępnieniem funkcji „Klikamy”.

### Inne

- **NIS2 / krajowy system cyberbezpieczeństwa**: dostawca usług chmurowych
  wpada w zakres dopiero od rozmiaru średniego przedsiębiorstwa; Fundacja
  jako mikropodmiot najpewniej poza zakresem. Sprawdzić przy wzroście.
- **Inspektor ochrony danych**: dla Fundacji przy obecnej skali raczej nie
  jest obowiązkowy (przetwarzanie danych art. 9 nie jest „na dużą skalę”).
  Gdy klientów będą dziesiątki, warto to ocenić ponownie.
- **Wersja lokalna pieczapp**: jeśli notariusz uruchamia ją na swoim
  komputerze z **własnym** kontem AWS, Fundacja nie jest podmiotem
  przetwarzającym - wystarczy licencja/regulamin oprogramowania. Jeżeli
  korzysta z konta AWS Fundacji, obowiązuje ta sama umowa powierzenia.

## Kolejność działań

1. Wdrożenie aplikacji (punkt 6) i kopii zapasowej (punkt 7).
2. Publikacja strony z dokumentami (punkt 4).
3. Kampania: kancelarie rejestrują się same, bez udziału Fundacji.
4. W tle: PKD w KRS (punkt 1) i przegląd prawnika; zmiany po przeglądzie
   w trybie § 14 Regulaminu.
