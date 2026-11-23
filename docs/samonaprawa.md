# Samonaprawa notarai

System, który sam wykrywa błędy aplikacji na produkcji, naprawia je, wdraża
poprawkę i sprawdza, czy pomogła. Gdy nie pomogła, sam cofa poprawkę.
Właściciel nie musi czytać kodu: dostaje wiadomość po polsku, co się stało
i co kliknąć w aplikacji, żeby sprawdzić.

Decyzja właściciela z 23.11.2026, po błędzie „Sporządź projekt: Błąd modelu
(ParamValidationError)”.

## Jak to działa

```
błąd u notariusza
  └─ samonaprawa.py: odcisk błędu + znacznik w CloudWatch (bez danych klientów)
       ├─ od razu: repository_dispatch do GitHuba (gdy jest token)
       └─ co 30 min: workflow sam przegląda znaczniki (działa też bez tokenu)
  └─ .github/workflows/samonaprawa.yml
       1. zgłoszenie (issue) „[samonaprawa] <odcisk>”, limity, eskalacja
       2. agent naprawczy (Claude przez Bedrock, eu-central-1):
          przyczyna -> test, który odtwarza błąd -> poprawka -> wszystkie testy
       3. bramki (scripts/samonaprawa/bramki.py, deterministyczne)
       4. niezależny agent recenzent (widzi sam kod, nie rozumowanie)
       5. werdykt:
          auto   -> scalenie -> testy -> wdrożenie -> 20 min obserwacji
                    -> błąd wrócił albo przyszedł nowy? automatyczne cofnięcie
          pr     -> pull request z opisem dla właściciela + e-mail
          odrzuc -> komentarz w zgłoszeniu; po 2 próbach eskalacja + e-mail
```

## Bramki: co musi spełnić poprawka, żeby weszła sama

| Bramka | Po co |
|---|---|
| Test regresji **oblewa** kod sprzed poprawki (pytest = 1) i **przechodzi** po niej | dowód, że poprawka naprawia ten błąd, a nie coś obok |
| Pełny zestaw testów zielony | nic innego się nie zepsuło (w tym walidacja zapytań do Bedrock przez SDK, `test_zgodnosc_sdk.py`) |
| Żadnych usuniętych testów ani `skip`/`xfail`/`except: pass` | agent nie może „naprawić” przez wyciszenie |
| Niezależny recenzent: `przepusc` | drugi agent szuka, co poprawka może zepsuć |
| Poza strefami zakazanymi | patrz niżej - tam zawsze decyduje właściciel |
| Najwyżej 10 plików i 400 linii, ryzyko „niskie” | automat tylko do wąskich napraw |
| Najwyżej 3 automatyczne wdrożenia na dobę | seria błędnych poprawek nie rozleje się po produkcji |
| `master` nie zmienił się w trakcie | testy szły na tym samym kodzie, który zostanie scalony |

Bramki uruchamiane są z kopii `scripts/samonaprawa/` sprzed zmian agenta,
a te pliki (i `.github/`, `conftest.py`, `test_samonaprawa.py`) są w strefie
zakazanej, więc agent nie osłabi własnej kontroli.

## Strefy zakazane: zawsze pull request, nigdy automat

Treść prawna (`prompty.py`, `zasady.py`, `styl.py`, `personalizacja.py`,
`klauzule.py`, `taksa.py`, `dokumenty_prawne.py`, `formularze/`, GIIF, AML),
RODO i dane (`autoryzacja.py`, `logowanie.py`, `dziennik*.py`, `magazyn.py`,
`poswiadczenia.py`, `osoby.py`, `walidacja.py`), pieniądze (`platnosci.py`,
`tokenomia.py`, `kalkulator.py`), infrastruktura (`infra/`, `Dockerfile`,
`.dockerignore`, `confidential/`) i sama samonaprawa. Pełna lista:
`STREFY_ZAKAZANE` w `bramki.py`.

## Bezpieczeństwo i RODO

- Zgłoszenie zawiera tylko typ wyjątku, kod i komunikat AWS, miejsca w kodzie,
  wersję i endpoint, po `dziennik.maskuj()`. Treść wyjątków spoza AWS, treść
  spraw i identyfikatory kancelarii nie wychodzą z aplikacji.
- Agent dostaje sesję AWS zawężoną polityką sesji do wywołań modeli Bedrock
  (profile `eu.anthropic.*`, regiony UE). Nie ma tokenu GitHub, tokenu OIDC
  ani dostępu do logów, sekretów i bucketa spraw.
- Rola `notarai-github-samonaprawa` (stos `notarai-github`) działa tylko
  z gałęzi `master` i nie może budować obrazów ani zmieniać stosów; wdrożenie
  idzie zwykłym `wdrozenie.yml`.

## Sterowanie

- **Wyłącznik / tryb:** GitHub → Settings → Secrets and variables → Actions →
  Variables → `SAMONAPRAWA` = `auto` (domyślnie) | `pr` (tylko pull requesty) |
  `wylaczona` (tylko zgłoszenia).
- **Model agenta:** zmienna `SAMONAPRAWA_MODEL` (domyślnie
  `eu.anthropic.claude-opus-4-6-v1`, jak aplikacja).
- **Zgłoszenie ręczne** (np. ze zrzutu ekranu): Actions → „NotarAI -
  samonaprawa” → Run workflow → opis słowami, bez danych klientów.
- **Podgląd:** GitHub → Issues z etykietą `samonaprawa`; w aplikacji
  `GET /api/admin/samonaprawa` (liczniki błędów w kontenerze).
- **Powiadomienia:** e-mail z tematu SNS `notarai-alarmy` (ten sam adres co
  alarmy). Dodatkowo alarm `notarai-samonaprawa-bledy` przy 5+ błędach kodu
  w 5 minut, niezależny od GitHuba.

## Uruchomienie (jednorazowo)

1. Stos uprawnień `notarai-github` (rola samonaprawy) - wdrożony 23.11.2026.
2. Token GitHub dla zgłoszeń w czasie rzeczywistym i scaleń, które uruchamiają
   zwykłe testy i wdrożenie: `infra\zapisz-sekret-samonaprawy.ps1` (instrukcja
   w nagłówku skryptu). Bez tokenu działa przegląd co 30 minut, a scalenie
   wyzwala wdrożenie przez `workflow_dispatch`.
3. Bez tokenu tworzenie pull requestów przez `GITHUB_TOKEN` wymaga ustawienia
   Settings → Actions → General → „Allow GitHub Actions to create and approve
   pull requests”.

## Asystent kancelarii (prośby notariusza)

Przycisk „Asystent kancelarii” w aplikacji (`asystent_kancelarii.py`,
`POST /api/asystent-kancelarii`). Notariusz pisze po swojemu, co ma działać
inaczej, a asystent (Claude przez Bedrock, narzędzia Converse):
- od razu zmienia to, co da się ustawić: ustawienia ogólne
  (`ustawienia_kancelarii.OPISY_USTAWIEN`), zasady kancelarii, wbudowane kontrole;
  każda zmiana w dzienniku (plik kancelarii `asystent`), „cofnij” ją odwraca,
- czego nie da się ustawić - przekazuje do samonaprawy jako zgłoszenie ręczne
  (`samonaprawa.zglos_prosbe`, po anonimizacji; od razu z tokenem, bez tokenu
  przez przegląd co 30 minut). Agent robi z prośby ustawienie tej kancelarii
  (domyślnie po staremu) i dopisuje je do `OPISY_USTAWIEN`, więc asystent od razu
  umie je przełączać,
- zmiany tylko dla notariusza (właściciela kancelarii); pracownik może pytać
  i zgłaszać prośby (limit 5 na dobę na kancelarię).

## Ograniczenia

- Automat naprawia błędy kodu (wyjątki). Błędy chwilowe AWS (limity, przeciążenie)
  tylko zlicza i alarmuje - na nie pomaga czekanie albo zmiana limitów, nie kod.
- Błąd merytoryczny bez wyjątku (np. zła treść aktu) nie wywoła samonaprawy -
  to zgłoszenie ręczne i zawsze strefa zakazana.
- Jeśli gałąź `master` dostanie ochronę wymagającą recenzji, automatyczne
  scalenie i cofnięcie przestaną działać (poprawki zostaną jako pull requesty).
