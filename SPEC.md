# SPEC — pieczapp, etap 2

Ten plik jest specyfikacją zadania. Przeczytaj go w całości przed napisaniem
pierwszej linii kodu. Reguły z sekcji „Ograniczenia bezwzględne" mają
pierwszeństwo przed każdą inną częścią tego dokumentu.

---

## 1. Kontekst

Kancelaria notarialna w Polsce. Istnieje działająca aplikacja lokalna
(`app.py`, `bedrock.py`, `dokumenty.py`, `walidacja.py`, `prompty.py`,
`static/index.html`), która:

- przyjmuje wzór aktu (.docx/.txt) i skany sprawy (PDF/obrazy),
- wykrywa we wzorze pola `{{nazwa}}` i `[NAZWA]`,
- odczytuje dane ze skanów modelem Claude przez Amazon Bedrock,
- waliduje PESEL, NIP, numer KW i kwoty sumami kontrolnymi,
- pokazuje pola do zatwierdzenia przez człowieka,
- generuje projekt dokumentu i eksportuje do .docx.

Przeczytaj ten kod, zanim cokolwiek dopiszesz. Trzymaj się jego konwencji:
nazwy po polsku bez znaków diakrytycznych, dwuprzebiegowy podział
ekstrakcja/generowanie, walidacja twarda w kodzie a nie w promptcie.

## 2. Ograniczenia bezwzględne

Naruszenie któregokolwiek z tych punktów oznacza, że zadanie jest wykonane źle,
niezależnie od tego, jak dobrze działa reszta.

1. **Region UE.** Każde wywołanie modelu przez profil `eu.`. Żadnych profili
   `global.`. Nie zmieniaj `config.py` w sposób, który to obchodzi.
2. **Zero danych osobowych w logach.** Nie loguj treści promptów, odpowiedzi
   modelu, odczytanych pól ani zawartości skanów — ani do pliku, ani na konsolę,
   ani na poziomie DEBUG. Loguj wyłącznie: identyfikator sprawy, nazwę operacji,
   liczbę tokenów, czas, typ błędu.
3. **Człowiek zatwierdza.** Żadna operacja o skutku zewnętrznym (wysłanie
   formularza, złożenie wniosku, zapytanie do rejestru rozliczane per sztuka)
   nie może wykonać się bez jawnego potwierdzenia w interfejsie. Nie projektuj
   trybu „wyślij wszystko automatycznie".
4. **Żadnych poświadczeń w kodzie ani w plikach konfiguracyjnych.** Login,
   hasło, certyfikat, token — nic z tego nie trafia do repozytorium, do `.env`
   ani do bazy. Używaj Windows Credential Manager przez bibliotekę `keyring`.
5. **Nie omijaj CAPTCHA ani innych zabezpieczeń przed automatyzacją.** Jeśli
   system stawia CAPTCHA, przekaż sterowanie człowiekowi i poczekaj.
6. **Nie wymyślaj danych.** W żadnym miejscu model nie może uzupełnić
   brakującej wartości domysłem. Brak zostaje brakiem i jest widoczny.

## 3. Zadanie A — sprawdzanie w rejestrach

Cel: przy zakładaniu sprawy kancelaria chce automatycznie sprawdzić strony
czynności w rejestrach publicznych.

### A1. Zanim napiszesz kod — ustal fakty

Nie zakładaj niczego na podstawie swojej wiedzy o tym, jak te rejestry
działały wcześniej. **Sprawdź aktualny stan** i zapisz ustalenia w
`docs/rejestry.md` wraz z datą sprawdzenia i linkami do źródeł:

- **KRZ (Krajowy Rejestr Zadłużonych, krz.ms.gov.pl)** — czy istnieje
  oficjalne API lub udostępniane pliki danych? Jakie są zasady korzystania
  z wyszukiwarki? Czy regulamin dopuszcza zapytania automatyczne i w jakim
  wolumenie?
- **Rejestr Zastrzeżeń Numerów PESEL** — jaka jest **ścieżka dostępu dla
  notariuszy jako podmiotu ustawowo zobowiązanego do weryfikacji**. To jest
  kluczowe rozróżnienie: dostęp instytucjonalny to inny kanał niż aplikacja
  mObywatel dla obywatela.

Jeśli któregoś z tych ustaleń nie da się potwierdzić z oficjalnego źródła,
**nie implementuj tej integracji**. Napisz w `docs/rejestry.md`, czego
brakuje i kogo trzeba zapytać (Ministerstwo Cyfryzacji, izba notarialna,
dostawca oprogramowania kancelaryjnego). Zaślepka z jasnym komunikatem jest
lepsza niż integracja zbudowana na domysłach.

### A2. Czego nie robić

- **Nie automatyzuj interfejsu przeznaczonego dla obywatela**, żeby obejść brak
  dostępu instytucjonalnego. Jeśli oficjalna ścieżka wymaga umowy, certyfikatu
  albo wniosku — to jest wymóg, a nie przeszkoda techniczna.
- **Nie odpytuj rejestru masowo „na zapas".** Zapytanie wykonuje się dla
  konkretnej strony w konkretnej sprawie, w momencie, gdy notariusz tego żąda.
- **Nie buduj lokalnej kopii rejestru.** Wynik zapytania to fakt z chwili
  sprawdzenia, nie dane do gromadzenia.

### A3. Jeśli dostęp jest potwierdzony — jak to zbudować

Nowy moduł `rejestry.py`:

```
class WynikSprawdzenia:
    rejestr: str            # "KRZ" | "ZASTRZEZENIA_PESEL"
    zapytanie: str          # co sprawdzano (PESEL zamaskowany do 4 ostatnich cyfr)
    status: str             # "brak_wpisu" | "wpis" | "niedostepny" | "blad"
    szczegoly: str          # opis dla notariusza
    sprawdzono: datetime
    zrodlo: str             # URL lub nazwa endpointu
```

Wymagania:

- **Interfejs jednolity** — każdy rejestr implementuje ten sam protokół, żeby
  dołożenie kolejnego (np. CEIDG, KRS) nie wymagało zmian w warstwie wyżej.
- **Awaria rejestru nie blokuje sprawy.** Status `niedostepny` pokazuje się
  jako ostrzeżenie, notariusz decyduje, czy czekać czy sprawdzić ręcznie.
- **Ślad audytowy w `dane/sprawy/<id>/sprawdzenia.json`**: co sprawdzano,
  kiedy, z jakim skutkiem. PESEL zapisuj zamaskowany. To dowód dochowania
  staranności — ma przetrwać kontrolę.
- **Rate limiting i backoff** po stronie klienta, nawet jeśli rejestr nie
  wymusza. Nagłówek `User-Agent` identyfikujący kancelarię.
- **Testy na atrapach**, nie na produkcyjnym rejestrze.

W interfejsie: sekcja „Sprawdzenia" na etapie 2, przycisk uruchamiający
sprawdzenie dla wykrytych numerów PESEL, wynik jako wiersz z datą i statusem.
Wpis w rejestrze zastrzeżeń oznacz kolorem alarmowym — to informacja, która
wstrzymuje czynność.

## 4. Zadanie B — wypełnianie formularzy w aplikacjach urzędowych

Cel: kancelaria wypełnia te same rubryki w kilku systemach rządowych.
Dane są już w sprawie — chodzi o to, żeby nie przepisywać ich ręcznie.

### B1. Kolejność podejść — od najlepszego do ostatecznego

1. **Oficjalne API lub integracja.** Sprawdź, czy dany system je udostępnia.
   Wiele polskich systemów urzędowych ma udokumentowane interfejsy. To jedyna
   ścieżka, która nie psuje się przy przebudowie interfejsu.
2. **Eksport do formatu, który system przyjmuje** — XML, CSV, plik wsadowy.
   Aplikacja generuje plik, człowiek wgrywa go w systemie. Prosto i odporne.
3. **Schowek i asysta.** Aplikacja pokazuje wartości pole po polu z przyciskiem
   „kopiuj", człowiek wkleja. Prymitywne, ale działa wszędzie i nie łamie
   żadnego regulaminu.
4. **Automatyzacja przeglądarki** — dopiero gdy pierwsze trzy odpadną.

Zanim wybierzesz opcję 4, udokumentuj w `docs/formularze.md`, dlaczego 1–3 nie
wchodzą w grę dla danego systemu. Domyślnie zaczynaj od opcji 3 — daje
natychmiastową wartość przy zerowym ryzyku.

### B2. Jeśli automatyzacja przeglądarki — twarde reguły

- **Regulamin systemu ma pierwszeństwo.** Sprawdź, czy dopuszcza dostęp
  automatyczny. Jeśli zabrania — zejdź do opcji 3 i napisz o tym w dokumentacji.
- **Człowiek loguje się sam.** Skrypt nie wpisuje hasła, nie klika w podpis
  kwalifikowany, nie przechodzi przez uwierzytelnianie dwuskładnikowe.
  Automatyzacja startuje na już zalogowanej sesji.
- **Skrypt wypełnia, człowiek wysyła.** Wypełnij rubryki, zatrzymaj się przed
  przyciskiem wysyłki i pokaż podsumowanie. Nigdy nie klikaj „wyślij",
  „złóż wniosek", „podpisz" ani nic o nieodwracalnym skutku.
- **Mapowanie pól w pliku konfiguracyjnym**, nie w kodzie — `formularze/<system>.yaml`
  z selektorami i regułami transformacji. Gdy urząd przebuduje stronę, poprawia
  się jeden plik.
- **Tryb podglądu.** Domyślnie skrypt pokazuje, co by wpisał, bez wpisywania.
  Wejście w tryb faktyczny wymaga jawnego przełącznika.

Biblioteka: Playwright (Python). Lepiej radzi sobie z oczekiwaniem na elementy
niż Selenium i nie wymaga osobnego sterownika.

## 5. Zadanie C — porządki w istniejącym kodzie

- **Testy.** `pytest` na walidatorach (przypadki brzegowe PESEL: daty XIX i XXI
  wieku, nieprawidłowe miesiące), na wykrywaniu pól ze wzoru, na całym
  przepływie z atrapą Bedrock. Bez testów wywołujących prawdziwy model.
- **Konta użytkowników.** Logowanie do aplikacji, role (notariusz / pracownik),
  hasła hashowane `argon2`. Uprawnienia: kto może generować, kto tylko czytać.
- **Dziennik czynności** — kto, kiedy, w której sprawie, jaka operacja.
  Bez treści dokumentów.
- **Kopie zapasowe.** Skrypt tworzący zaszyfrowaną kopię katalogu `dane/`.
  Szyfrowanie po stronie kancelarii, przed wysłaniem gdziekolwiek.

## 6. Zasady pracy

- **Małe kroki.** Jedno zadanie, testy, działający stan, dopiero potem kolejne.
  Nie przepisuj działającego kodu przy okazji.
- **Pytaj, gdy specyfikacja milczy.** Zwłaszcza przy rejestrach — lepiej zapytać
  niż zgadnąć, jak wygląda odpowiedź API, której nie widziałeś.
- **Nie dokładaj zależności bez potrzeby.** Każda nowa biblioteka to coś, co
  kancelaria musi utrzymywać przez lata.
- Po każdym większym kroku uruchom `pytest` i pokaż wynik.

## 7. Kryteria ukończenia

Zadanie jest gotowe, gdy:

- [ ] `pytest` przechodzi w całości
- [ ] `docs/rejestry.md` zawiera ustalenia z datami i źródłami
- [ ] `docs/formularze.md` uzasadnia wybór podejścia dla każdego systemu
- [ ] żaden log nie zawiera danych osobowych — sprawdzone przez uruchomienie
      pełnego przepływu i przejrzenie wyjścia
- [ ] `grep -ri "global.anthropic" .` nie zwraca nic
- [ ] żadna operacja o skutku zewnętrznym nie wykonuje się bez potwierdzenia
- [ ] README opisuje, co zrobić, gdy rejestr jest niedostępny
