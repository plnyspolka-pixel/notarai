# Kokpit NotarAI — rzeczywisty ekran aplikacji

Ta zmiana włącza **prawdziwy ekran startowy**, nie makietę. Korzysta z
autoryzowanych danych spraw w dotychczasowej aplikacji.

## Gdzie działa
Po zalogowaniu lub w trybie lokalnym: `/` aplikacji FastAPI.
Pliki: `static/index.html`, `static/kokpit.css`, `static/kokpit.js`,
`static/notarai-symbol.svg`. Nie zmieniono endpointów serwera.

## Funkcje
- **Moje sprawy**: rzeczywiste dane z `/api/sprawy` przez istniejący `api()`,
  z poprawnym tokenem i nagłówkiem dostępu serwisowego. Przy przechowywaniu lokalnym
  używa `dysk.listaSpraw()` z już wybranego folderu.
- **Otwórz sprawę**: wywołuje oryginalne `wczytajSprawe(id)`, które pobiera stan
  sprawy i przełącza na odczyt lub gotowy projekt.
- **Nowa sprawa**: wykonuje oryginalny reset `btn-nowa`.
- **Dodaj pliki**: nowa sprawa + systemowy selektor `#pliki`. Bez automatycznego uploadu.
- **Odczyt AI**: przechodzi do istniejącego formularza i przycisku `Odczytaj skany`;
  użytkownik nadal musi wskazać dokumenty i zatwierdzić operację.
- **Sprawdź dane**: etap 2 bieżącej, odczytanej sprawy.
- **Projekt Word**: etap 3 z rzeczywistym linkiem pobierania przez stary przycisk
  lub etap 2 z istniejącym `Sporządź projekt`.
- **Asystent AI**: istniejący czat sprawy lub formularz dokumentów.
- **Szukaj, filtruj, odśwież**: działają na bieżącej liście, nie na rekordach demo.
- **Brak spraw, błąd API, brak uprawnień folderu, brak zaakceptowanej umowy**:
  mają jawne komunikaty.
- **Wylogowanie**: czyści listę spraw z widoku przed pokazaniem bramy logowania.

## Zakres zmian i bezpieczeństwo
- Nie ma nowych endpointów z pominięciem autoryzacji.
- Dane spraw są wprowadzane do DOM przez `textContent`, bez składania HTML
  z nazwisk i sygnatur.
- Nie wprowadzamy deklaracji, że projekt jest zaakceptowany czy podpisany;
  status „Projekt Word” oznacza jedynie, że zapisano plik.
- Lokalne sprawy rozpoznają etap 3 na podstawie istniejących plików projektu.
- Zachowano dotychczasowy proces dokumentów i umów powierzenia.

## Testy
- `python -m pytest test_kokpit.py` — statyczne kontrole połączeń.
- `node --check static/kokpit.js` — składnia JavaScript.
- Smoke test przed produkcją: osobno SaaS + lokalne foldery; sprawa z odczytem,
  sprawa z projektem, brak spraw, logowanie/wylogowanie, konto bez powierzenia,
  telefon 390px, ekran szeroki, klawiatura.
- Testy funkcjonalne UI na modelu DOM wykonano podczas przygotowania zmian;
  pełnego testu backendu z AWS i rzeczywistą autoryzacją nie wykonano.

## Wdrożenie
Ta gałąź jest oparta na `design/notarai-brand-landing`, która z kolei opiera się
na `design/financeyou-visual-refresh`.
Scalić poprzedzające zmiany w kolejności, a przed publikacją zrobić test na
wydzielonym środowisku. Nie należy nazywać tej gałęzi produkcyjnie wdrożoną.
