---
name: strona-premium
description: Budowa i zmiana stron publicznych notarai.pl (katalog strona/, landing, podstrony marketingowe) tak, żeby były efektowne, szybkie, dostępne i zgodne z RODO. Użyj przy każdej pracy nad wyglądem, animacją, typografią, nową sekcją lub podstroną, wyborem biblioteki frontendowej oraz przed oddaniem zmian w strona/.
---

# Strona premium NotarAI

Agent proponuje kod, narzędzie sprawdza, człowiek zatwierdza wygląd. Nic z tej listy
nie trafia na produkcję bez przejścia audytu z punktu 5.

## 1. Źródła prawdy

- Tokeny marki: `tools/web-factory/design-system/tokens.json` (granat, błękit, cyjan,
  Montserrat, promienie, czasy ruchu). Nie wymyślaj nowych kolorów ani krojów.
- Biblioteki i licencje: `tools/web-factory/design-system/oss-registry.json`.
  `doNotUse` to zakaz. `requiresSeparateLegalReview` wymaga zgody użytkownika.
  Biblioteki spoza rejestru najpierw dopisz do niego z licencją odczytaną z repozytorium.
- Wzory efektów: `tools/web-factory/galeria/index.html`. Zanim napiszesz efekt od zera,
  sprawdź, czy jest tam gotowy, i skopiuj jego CSS razem z zapasem dla starszych przeglądarek.
- Istniejące style: `strona/brand-site.css` (strona główna), `strona/style.css` (podstrony).
- Część podstron powstaje z generatorów: `seo/strona.py`, `seo/lead_strona.py`,
  `seo/teczka_strona.py`, `dokumenty_prawne.py`. Poprawkę w wygenerowanym HTML wprowadź
  także w generatorze. Nie uruchamiaj `infra/strona_dokumenty.py` przy okazji: generator
  nagłówka jest starszy niż pliki w repozytorium i cofa logo.

## 2. Zasady wyglądu

- Jeden mocny pomysł na pierwszy ekran, reszta spokojna. Najwyżej dwa rodzaje animacji na stronę.
- Żadnych domyślnych ustawień generatora: fioletowo-niebieski gradient na bieli, kremowe tło
  z szeryfem, wszystko wyśrodkowane, jednakowe zaokrąglone karty w rzędzie.
- Tekst pomocniczy nie jaśniejszy niż `#5F6F8E` na białym. Cyjan `#00CFFF` tylko jako
  dekoracja i obrys fokusu, nigdy jako kolor tekstu na jasnym tle.
- Margines boczny treści co najmniej 16 px na telefonie. Nie zeruj go skrótem `padding`.
- Teksty konkretne, z prawdziwymi faktami o usłudze. Każda wzmianka o projekcie aktu
  idzie w parze z informacją, że projekt weryfikuje notariusz.
- Bez własnego kursora, bez przejmowania przewijania, bez płynnego przewijania z biblioteki.

## 3. Ruch

- Najpierw natywny CSS: `animation-timeline: view()`, `@view-transition`, `@starting-style`,
  `sibling-index()`, `@property`. Zawsze w `@supports`, z treścią widoczną bez animacji.
- Biblioteka JS dopiero wtedy, gdy CSS nie wystarcza, i tylko z rejestru.
- `prefers-reduced-motion: reduce` wyłącza animacje i przejścia. Pętle grają tylko
  na ekranie (IntersectionObserver), nigdy w tle.
- Animuj `transform` i `opacity`. Czasy z tokenów: 160, 320, 700 ms.
- Pierwszy ekran renderuje się z HTML i CSS. Cięższe efekty dołączaj po wyświetleniu treści.

## 4. RODO i bezpieczeństwo

- Zero żądań do obcych serwerów: kroje, skrypty, obrazy i ikony z własnej domeny.
  Montserrat (OFL 1.1) leży w `tools/web-factory/galeria/fonts/`.
- Żadnych danych osobowych, akt ani zrzutów z produkcji w przykładach i testach.
- Audyt uruchamiaj na serwerze lokalnym. Wywołania API zastępuj atrapami
  (`--stub-hosts`, `--stub-paths`), nie kieruj ich na produkcję.

## 5. Bramka przed oddaniem

    cd tools/web-factory
    npm install            # raz
    npm run serve:strona   # w tle
    npm run audit:strona

Przebieg musi zakończyć się `"pass":true`. Sprawdza 4 szerokości (1440, 834, 390, 320)
w trzech wariantach: bazowym, z ruchem i ciemnym. Nie przechodzi, gdy jest:
błąd dostępności poważny lub krytyczny, błąd JavaScript, nieudane żądanie,
poziome przewijanie, przekroczony budżet (CLS 0,1; waga 1500 kB) albo żądanie do
niezatwierdzonego hosta.

- Nową podstronę dopisz do `--paths` w skrypcie `audit:strona` w `package.json`.
- Wyłączenie z audytu (`--a11y-exclude`) tylko dla treści zwolnionej z WCAG, dziś jest
  nią wyłącznie logotyp. Nie dopisuj selektorów, żeby uciszyć błąd.
- Obejrzyj zrzuty z `artifacts/web-factory/notarai/images/` dla 1440 i 320 px.
  Audyt nie ocenia urody ani kolejności fokusu z klawiatury; to sprawdź sam.
- Wzorce wizualne (`--write-baseline`) zapisuje się dopiero po akceptacji wyglądu
  przez użytkownika.

## 6. Czego nie robić bez pytania

- Nie wdrażaj na produkcję i nie zmieniaj przepływów logowania, rejestracji ani API.
- Nie usuwaj wpisów z `.dockerignore`.
- Nie podmieniaj tokenów marki ani logo.
