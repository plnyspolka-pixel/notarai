# Cache promptu w Bedrock (prompt caching)

Od tej zmiany `bedrock.py` stawia w wywołaniach Converse punkty `cachePoint`. Wszystko przed
punktem Bedrock zapisuje w pamięci podręcznej i przy następnym wywołaniu z **identycznym**
prefiksem czyta za ok. 10 % ceny wejścia (zapis kosztuje 125 %). `tokenomia.py` od dawna umie
liczyć `cacheReadInputTokens` / `cacheWriteInputTokens`; brakowało tylko punktów.

## Gdzie są punkty i dlaczego tylko tam
Opus 4.6 i Haiku 4.5 cache'ują prefiks dopiero od **4096 tokenów**, Sonnet 4.6 od 1024. Krótszy
prefiks jest ignorowany po cichu (bez błędu i bez kosztu). Prompty systemowe aplikacji mają
300–2100 tokenów, więc ich nie cache'ujemy. Punkty stoją tam, gdzie ten sam duży tekst wraca:

| Miejsce | Punkt cache | Co wraca z cache |
|---|---|---|
| `rozmawiaj` (rozmowa o sprawie) | za kontekstem sprawy w pierwszej turze **i** za ostatnią odpowiedzią asystenta | od drugiej tury: cały kontekst (odczytane dane) i cała dotychczasowa rozmowa; każda tura płaci pełną cenę tylko za nową wiadomość |
| `sporzadz_projekt` | za blokiem „konwencja + legenda + WZÓR DOKUMENTU” (`prompty.polecenie_generowania_bloki`) | kolejne sprawy kancelarii na tym samym wzorze (i poprawki tego samego projektu) czytają wzór z cache |

Tekst, który widzi model, jest identyczny jak przed zmianą (test `test_projekt_ma_wzor_przed_punktem_cache_a_dane_po`
sprawdza równość z dawnym jednoblokowym poleceniem).

Nie cache'ujemy transkrypcji stron (każda paczka to inne obrazy; zapis 125 % opłaciłby się tylko
przy ponad ~28 % ponowień) ani pętli `nastepny_krok` (prompt za krótki).

## Sterowanie i awaria
- `PIECZAPP_CACHE_PROMPTU=0` wyłącza punkty (bez zmian w tekście promptów).
- Gdy Bedrock odrzuci `cachePoint` (ValidationException z „cache” w treści, np. model lub region bez
  tej funkcji), `bedrock.py` wyłącza punkty do końca procesu i powtarza wywołanie bez nich, więc
  użytkownik nie widzi błędu, a kolejne wywołania nie marnują zapytania. Inne błędy walidacji idą
  dalej jak dotąd.
- Log `wywolanie modelu:` pokazuje teraz także `cache_odczyt` i `cache_zapis`. Jeśli przy drugiej
  turze rozmowy `cache_odczyt` jest 0, kontekst sprawy ma mniej niż 4096 tokenów (małe sprawy) albo
  minęło >5 min od poprzedniej tury (TTL cache 5 minut, odnawiany każdym odczytem).

## Co to daje
Rozmowa o sprawie z kontekstem 20 tys. tokenów i 10 turami: dawniej ~220 tys. tokenów wejścia po
pełnej cenie, teraz ~25 tys. po pełnej + ~200 tys. po 10 %, czyli ok. **4× tańsza rozmowa**.
Cennik pozostaje bez zmian (`tokenomia.akcja("rozmowa_tura", ...)` nadal liczy kredyty od znaków),
więc różnica zostaje po naszej stronie jako marża.

## Następny krok (do zmierzenia, nie wdrażać w ciemno)
`PIECZAPP_WYSILEK` ma domyślnie `max` dla wszystkich wywołań, także transkrypcji stron. Na Opus 4.6
to największy mnożnik tokenów wyjścia (myślenie). Zmierzyć na 10 prawdziwych sprawach `high` vs `max`
dla transkrypcji (parametr `wysilek` już istnieje w API) - jeśli pola wymagające uwagi wychodzą tak
samo, przełączyć transkrypcję na `high`, zostawiając `max` dla zestawienia i projektu.
