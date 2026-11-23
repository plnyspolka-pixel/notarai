# Pomiar serialu „Kancelaria pod Siódemką”

Dotyczy strony `notarai.pl/serial/` (generator `seo/serial.py`, skrypt
`serial/zasoby/serial.js`) i linków do niej z innych kanałów.

**RODO:** zdarzenia wysyła wyłącznie PostHog wczytany przez `strona/analityka.js`,
czyli dopiero po zgodzie na cookie analityczne. Bez zgody `serial.js` niczego nie
wysyła i niczego nie zapisuje. Dane bez zgody (liczba odtworzeń w ogóle) dają tylko
statystyki serwera az.pl, bez danych osobowych.

## Zdarzenia (PostHog, projekt wspólny z financeyou.pl, filtr `$host = notarai.pl`)

| Zdarzenie | Kiedy | Cechy |
|---|---|---|
| `serial_odcinek_otwarty` | 1,5 s po wczytaniu strony odcinka | `odcinek`, `zrodlo` (utm_source) |
| `serial_odtworzenie` | pierwsze uruchomienie wideo | `odcinek`, `zrodlo` |
| `serial_obejrzane_3s` | widz dotrwał do 3. sekundy | jw. |
| `serial_obejrzane_10s` | do 10. sekundy | jw. |
| `serial_obejrzane_procent` | 25, 50, 75, 100% długości (100% = 98% albo koniec) | `procent` |
| `serial_nastepny` / `serial_poprzedni` | klik w przycisk odcinka | `do_odcinka` |
| `serial_lista` | klik w odcinek na liście | `do_odcinka` |
| `serial_cta` | klik „Wypróbuj” / „Załóż konto kancelarii” | `odcinek` |

Każde zdarzenie wideo wysyła się najwyżej raz na wyświetlenie strony.

## Linki UTM

Schemat: `?utm_source=<kanał>&utm_medium=serial&utm_campaign=komputerku&utm_content=<odcinek>`.

| Kanał | `utm_source` |
|---|---|
| strona notarai.pl (CTA na stronie serialu) | `notarai_pl` |
| mailing | `email` |
| YouTube | `youtube` |
| Facebook | `facebook` |
| Instagram | `instagram` |
| LinkedIn | `linkedin` |

`utm_content` = identyfikator odcinka małymi literami, np. `s01e01`. Wariant testu A/B
dopisujemy po podkreślniku: `s01e01_a`, `s01e01_b`.

## Miary główne i jak je czytać

1. **Utrzymanie po 3 s** = `serial_obejrzane_3s` / `serial_odtworzenie`. To miara
   otwarcia (recepta `10_OTWARCIA_PIERWSZE_SEKUNDY.md`). Spadek przy jednym
   odcinku = do poprawy pierwsze ujęcie.
2. **Utrzymanie po 10 s** = `serial_obejrzane_10s` / `serial_odtworzenie`. Mówi,
   czy po haczyku jest powód zostać (świat i stawka do 20. s).
3. **Obejrzenie do końca** = `serial_obejrzane_procent` z `procent = 100` /
   `serial_odtworzenie`. Krzywa 25/50/75/100 pokazuje, w której części odcinka widz
   wychodzi; porównywać z szablonem 75 s z recepty `09_RECEPTA_Z_BADAN.md`.
4. **Powrót na następny odcinek** = odsetek osób z `serial_obejrzane_procent ≥ 75`
   dla odcinka N, które w ciągu 7 dni mają `serial_odcinek_otwarty` dla N+1 (lejek
   PostHog z oknem 7 dni). To główna miara serialu.
5. **Zapisy na demo** = `serial_cta` → rejestracja w aplikacji z `utm_campaign=komputerku`
   (atrybucja po `utm_content`).

Polubienia i liczba wyświetleń na platformach są pomocnicze. Przy małej widowni
zawodowej różnice między odcinkami czytamy jako kierunek; wniosek dopiero przy
powtórzeniu na kolejnym odcinku.

## Testy A/B (z recept 09–13)

Jedna zmiana naraz, ten sam kanał i godzina, warianty oznaczone w `utm_content`.

| Pytanie | A | B | Miara |
|---|---|---|---|
| Zawieszenie akcji na końcu | koniec w zawieszeniu | koniec domknięty | powrót na następny odcinek |
| Czyje oczy | scena kluczowa oczami Heleny | oczami Marty | obejrzenie do końca, komentarze |
| Marka | plansza tylko na końcu | logo w pierwszych 3 s | utrzymanie po 3 s, obejrzenie do końca |
| Plansza tytułowa | po zimnym otwarciu, 1,5 s | bez planszy | utrzymanie po 3 s i 10 s |
| Muzyka w otwarciu | brak | ciepły motyw | obejrzenie do końca |
| Głos | syntetyczny | ludzki lektor jednej postaci | obejrzenie do końca |
| Żart w odcinku | jest | brak | obejrzenie do końca, udostępnienia |
| Ujęcie reakcji po puencie | 1 s twarzy | od razu następna kwestia | obejrzenie do końca |
| Romans: beat w odcinku | jest | brak | powrót na następny odcinek |
| Miniatura | twarz | rekwizyt | kliknięcia, obejrzenie do końca |
| Temat maila | konkret | zagadka | otwarcia i kliknięcia |

## Panel PostHog (do założenia)

- Trendy: `serial_odtworzenie` dziennie, z podziałem na `odcinek` i `zrodlo`.
- Lejek: `serial_odtworzenie` → `serial_obejrzane_3s` → `serial_obejrzane_10s` →
  `serial_obejrzane_procent (procent=100)`, z podziałem na `odcinek`.
- Lejek powrotu: `serial_obejrzane_procent ≥ 75` → `serial_odcinek_otwarty` (kolejny
  odcinek), okno 7 dni.
- Konwersja: `serial_cta` → rejestracja (`utm_campaign = komputerku`).
