# NotarAI: jedna ścieżka klienta i notariusza (08.11.2026)

## Źródło projektu
Gałąź `feature/notarai-unified-client-notary-ux` oparta jest na
`claude/nice-goodall-1yvls3`: zawiera bazę kancelarii, `wizyty.py`,
`kalkulator.py`, `seo/*` oraz bezpiecznie przeniesiony z głównej gałęzi
moduł EKW. Odrębna mapa została przeniesiona z
`claude/serene-davinci-3535om`, a design i kokpit z
`fix/dashboard-session-and-sidebar-20261108`. Nie zastąpiono backendu
starszą wersją aplikacji.

## Publiczny klient kancelarii
1. `notarai.pl/` — odrębna sekcja „Dla klientów”, usługi i CTA.
2. `/kalkulator/` — istniejący kalkulator taksy + asystent AI;
   wynik ma charakter szacunkowy, nie oferty kancelarii.
3. `/notariusz/` i `/notariusz/<miejscowosc>/` — katalog
   kancelarii z `seo/kancelarie.json`, formularzem zgłoszenia i
   prywatnością. To strony generowane skryptem `seo/generuj.py`, muszą
   zostać zbudowane i opublikowane przez proces wdrożenia statycznego.
4. `/blog/` — treść generowana przez `seo/blog.py`; opublikowane
   są tylko zatwierdzone artykuły, nie automatyczne szkice.
5. `app.notarai.pl/notariusze` — interaktywna mapa *kancelarii
   świadomie publikujących swoje dane*. Lista nie publikuje PESEL,
   danych spraw czy kontaktów z zapytań.

## Panel notariusza
- `/api/sprawy` — sprawy, generowanie Word, weryfikacja i AI.
- `/api/zapytania` — statusy `nowa`, `kontakt`, `umowiona`,
  `odrzucona`; otwieranie przez kokpit; przypisanie przyjętego
  terminu do kalendarza. Zgłoszenie NIE jest automatycznie wizytą.
- Skróty „Zapytania klientów”, „Kalkulator taksy” i „Kalendarz”
  na głównym kokpicie; obsługa klientów korzysta z istniejącej
  autoryzacji oraz istniejących endpointów.
- Właściciel może w „Dokumentach” włączyć/wyłączyć publikację
  kancelarii na mapie. Domyślnie **brak publikacji**.
- Księga wieczysta EKW: pobranie wyłącznie po potwierdzeniu
  notariusza, tylko jeśli dostawca Finance You/Apify jest
  skonfigurowany; ślad audytowy i przypisanie do sprawy.
- Nadal dostępne: moduł „Klikamy”, pomocnik przeglądarkowy,
  sprawdzenia KRZ/PESEL, kalendarz, telefony, dokumenty,
  dostęp zespołu i uprawnienia, abonament.

## Bezpieczeństwo / ograniczenia
- `/api/notariusze`: publiczny read-only; `/api/mapa`
  właściciela wymaga JWT. Dostęp serwisowy NIE obejmuje
  ustawień mapy ani prywatnych zapytań klientów.
- Dane klienta przez `/api/wizyty` trafiają do kancelarii
  według istniejącego backendu, nie do publicznej wyszukiwarki.
- Publiczne API nie przyjmuje autoryzacji aplikacji w miejsce zgody.
- Nie wdrożono na produkcję, nie uruchomiono testów e2e z
  SES/AWS/BEDROCK/EKW ani kontroli dostawcy geokodowania.
- `seo/kancelarie.json` jest odziedziczone po gałęzi źródłowej,
  dlatego nie można scalać tylko samych plików `strona/`.

## Uruchomienie i testy
- `pytest test_taksa.py test_kalkulator.py test_wizyty.py test_notariusze.py test_ekw.py test_ekw_finyou.py test_kokpit.py test_unified_ux.py`.
- Testy z danymi sztucznymi: kancelaria opt-in na mapie,
  odmowa dostępu serwisowego, status zapytania i blokada
  kalendarza dla trybu lokalnego.
- Sprawdź desktop/mobile (min. 390px), działanie menu,
  przejście z publicznego kalkulatora do zapytania, EKW
  z i bez sekretu dostawcy, pełen login/reset oraz płatności.
- Stos CloudFormation `infra/notarai-aplikacja.yaml` łączy
  konfigurację SES do zapytań i opcjonalne sekrety EKW.
- Przed publikacją `notarai.pl` zbuduj strony miejscowości
  i blog zgodnie z `docs/seo.md` i zweryfikuj linki.

## Scalenie
Ponieważ baza gałęzi klientowskiej i `master` powstały
równolegle, sprawdź rebase i konfliktujące pliki.
Nie nadpisuj zmian z `master` i nie publikuj bez testów.
