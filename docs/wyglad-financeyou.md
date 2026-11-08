# NotarAI — nowa szata graficzna (inspiracja Finance You)

## Źródło
System projektowy został oparty na rzeczywistych tokenach z
`plnyspolka-pixel/finyou/src/styles.css`:
granat `#0d193c`, ciemny granat `#050a30`, indigo `#1c1cc0`,
błękit `#2197d3`, marketingowy dark-glow i typografia Montserrat.

Zachowana jest **osobna tożsamość NotarAI**: nazwa, znak i treści.
Nie kopiujemy logotypu ani assetów Finance You.

## Co zostało zmienione
- `strona/style.css`: nawigacja dark navy, rozświetlony hero z podglądem
  aplikacji, karty z lekką głębią, trzy kroki, cennik, stopka, podstrony prawne.
- `static/financeyou-theme.css`: wspólny motyw aplikacji, rejestracji i
  administracji. Ciemny sidebar, jasne powierzchnie, gradientowe CTA,
  nowe stany focus/hover, tryb ciemny i mobile.
- `static/index.html`, `static/admin.html`,
  `static/rejestracja.html`: dołączony nowy CSS po istniejących stylach.

## Zasady i tokeny
| Rola | Kolor |
|---|---|
| Primary navy | `#0d193c` |
| Deep navy | `#050a30` |
| Akcent | `#1c1cc0` |
| Cyan | `#2197d3` |
| Hero gold | `#e4c47a` |
| App background | `#f5f7fc` |
| App text | `#0d193c` |

Typografia: `Montserrat` z systemowym fallbackiem (bez zewnętrznego
CDN — brak dodatkowego transferu danych użytkownika do dostawcy fontu).
Podgląd aktu notarialnego zachowuje szeryfowy krój dokumentowy.

## Przegląd przed wdrożeniem
1. Otwórz `/`, `/rejestracja`, `/admin`, a także stronę publiczną
   i podstrony prawne.
2. Sprawdź na desktopie i w widoku 390px: nawigację, otwieranie szuflady,
   drag & drop plików, formularz, listę etapów i modalne okna.
3. Zweryfikuj jasny i ciemny motyw systemowy (szczególnie pola formularzy).
4. Zbadaj kontrast i focus klawiaturowy, także dla stanów disabled.
5. Uruchom testy repozytorium i wykonaj wizualny smoke test po wdrożeniu.

Nie zmieniano logiki JS, API, treści dokumentów ani umów.
Zmiany z tej gałęzi nie są wdrożeniem produkcyjnym.
