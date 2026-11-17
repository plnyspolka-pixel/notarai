# Koder – zlecanie pracy agentom na wynajętym GPU

Dwa tory pisania kodu w NotarAI:

- **koder** – otwarty model (Qwen3.8-27B) na karcie wynajmowanej na SaladCloud. Tani, pracuje
  w chmurze bez komputera operatora, dobry w małych, zamkniętych zadaniach z testem.
- **claude** – sesja Claude Code. Projektuje, dzieli pracę na karty, robi to, czego koder nie
  powinien dotykać, i przegląda wszystko, co koder oddał.

## Jak zlecasz

Mówisz Claude zwykłym zdaniem, co ma być zrobione. Resztę robi Claude:

1. **Dzieli** pracę na zadania i dla każdego pisze kartę w `docs/agent-tasks/kolejka/`.
2. **Przydziela tor** według reguły poniżej i sprawdza karty poleceniem
   `python tools/agent_factory/koder/karta.py lint`.
3. **Wypycha** gałąź `koder/<nazwa-paczki>`. To uruchamia workflow `koder.yml`: wynajem karty,
   model, zadania po trzy naraz, usunięcie karty.
4. **Odbiera** wyniki z gałęzi `agent/<przebieg>-wyniki` (`WYNIKI.md`) i przegląda każdy diff
   z gałęzi `agent/<przebieg>-<id>`.
5. **Składa** przyjęte zmiany w jeden pull request do Twojej akceptacji. Zadania niezaliczone
   robi sam albo zwraca z pytaniem. Karty zadań tor `claude` wykonuje w zwykłej sesji.

Agent niczego nie scala, nie wdraża i nie ma żadnych kluczy.

## Karta zadania

```markdown
---
id: taksa-wypis-granice
tor: koder
zakres:
  - taksa.py
  - test_taksa.py
sprawdzenie: python -m pytest -q test_taksa.py
kroki: 40
---
# Koszt wypisu: odrzucaj ujemną liczbę stron

Co jest teraz, co ma być, na jakim przykładzie widać różnicę, czego nie ruszać.
```

Dobra karta dla kodera odpowiada na cztery pytania bez zgadywania: **gdzie** (plik, funkcja),
**co ma się zmienić** (zachowanie przed i po, najlepiej na przykładzie wejście → wynik),
**po czym poznać koniec** (test), **czego nie ruszać**. Wzór: `docs/agent-tasks/SZABLON.md`.

## Reguła przydziału: koder czy Claude

Zadanie idzie do **kodera**, gdy spełnia wszystkie warunki:

| Warunek | Dlaczego |
|---|---|
| Najwyżej 4 pliki, wskazane z nazwy | mały model gubi się w szukaniu po całym repo |
| Jest test `pytest`, który rozstrzyga wynik | bez testu nie ma jak odebrać pracy automatycznie |
| „Co” jest przesądzone, zostaje tylko „napisz” | decyzje projektowe to praca Claude i Twoja |
| Nie wymaga sieci, kluczy, przeglądarki ani żywych systemów | robotnik jest odcięty od świata |
| Nie dotyka obszarów zastrzeżonych | patrz niżej |
| Jest ich co najmniej kilka naraz | start karty to ok. 25 minut i 0,25 USD przed pierwszym zadaniem |

Zadanie zostaje u **Claude**, gdy zachodzi którykolwiek punkt:

- obszary zastrzeżone: logowanie i uprawnienia, płatności i tokenomia, dane osobowe i ich
  przetwarzanie, AML/GIIF i księgi notarialne, teksty prawne, infrastruktura AWS i workflowy,
  wywołania modeli i prompty (lista plików: `ZASTRZEZONE` w `karta.py`);
- zmiana przechodzi przez kilka modułów albo wymaga decyzji o architekturze;
- przyczyna błędu jest nieznana i trzeba jej szukać;
- wynik ocenia się okiem (wygląd strony, tekst dla klienta) albo na żywym systemie;
- wymaganie jest niejasne i trzeba dopytać;
- zadanie jest pojedyncze i pilne – Claude zrobi je szybciej, niż wstanie karta.

Pierwsze trzy warunki i obszary zastrzeżone pilnuje kod: karta z torem `koder`, która je łamie,
nie przejdzie `karta.py lint` i workflow ją pominie.

## Kiedy wynik kodera jest zaliczony

Automatycznie, wszystkie naraz: agent zakończył sam (`Submitted`), test z karty przechodzi
w świeżym kontenerze bez sieci, **ukryte testy przechodzą**, coś zostało zmienione i nic poza
zakresem karty.

### Ukryte testy (od 17.11.2026)

Agenci zgłaszają jako ukończone ok. 70% zadań, które faktycznie się nie udały, a gdy widzą
testy, potrafią się do nich dopasować (laboratorium OpenAlex, `docs/lab-openalex/STAN-WIEDZY.md`,
działy C2 i D2). Dlatego każdą kartę toru `koder` Claude pisze razem z katalogiem
`docs/agent-tasks/ukryte/<id>/`, którego agent nie widzi (kopia dla agenta powstaje bez niego
i bez `.git`):

| `rodzaj:` w karcie | Co Claude dokłada do `ukryte/<id>/` | Warunek przed startem agenta | Zaliczenie |
|---|---|---|---|
| `zmiana` (domyślny) | `test_*.py` – testy zachowania docelowego, inne przypadki niż w treści karty; opcjonalnie `*.patch` | ukryte testy **oblewają** kod bazowy | ukryte testy przechodzą |
| `refaktor` | `test_*.py` + co najmniej jedna łatka `*.patch` zmieniająca zachowanie | ukryte testy przechodzą na bazie, a **oblewają** każdą łatkę | ukryte testy przechodzą |
| `testy` | co najmniej jedna łatka `*.patch` z celowym błędem w module | łatki dają się nałożyć | test z karty **oblewa** każdą łatkę |

Łatki to „test sabotażu”: celowo złe rozwiązanie, które musi zostać odrzucone. Karta, która nie
przejdzie warunku przed startem, jest wadliwa – agent jej nie dostaje (oszczędza czas GPU),
a karta wraca do Claude. Logika: `tools/agent_factory/koder/ukryte.py`; lokalnie bez Dockera:
`KODER_OCENA=lokalnie python tools/agent_factory/koder/ukryte.py przed <karta> <katalog>`.

W `WYNIKI.md` jest kolumna „Ukryte” i licznik **fałszywych sukcesów** (agent zgłosił koniec,
widoczny test zielony, ukryte czerwone) – to miara W6 dla każdego modelu.
Niezaliczone zadanie nie jest ponawiane na GPU – przechodzi do Claude.
Zaliczone i tak czyta Claude przed złożeniem pull requesta: test mówi, że działa, nie że jest dobrze.

## Koszty i miara

- Karta RTX 5090: 0,60 USD/h, naliczane od pobierania modelu. Limity w `koder.yml`:
  `KODER_MINUTES`, `KODER_MAX_USD`; po terminie model wyłącza się sam nawet bez workflow.
- Pierwsza próba (16.11.2026): 5 zadań, 5 oddanych, 4 z 4 sprawdzanych zaliczone, 52 minuty
  karty, ok. 0,52 USD. To za mało na wniosek o jakości.
- Miarą jest **koszt przyjętej zmiany** (USD karty ÷ liczba zmian przyjętych po przeglądzie),
  nie cena tokenu. Wyniki każdego przebiegu zostają w `docs/agent-tasks/wyniki/<przebieg>/`.

## Ograniczenia

- Węzły Salad to cudze komputery poza UE: do kodera trafia wyłącznie kod z tego publicznego
  repozytorium i dane syntetyczne. Nigdy `dane/`, `.env`, dane klientów.
- Największa karta Salad ma 32 GB, stąd model 27B w 4 bitach. Większe modele wymagają innego
  dostawcy.
- Brama Salad ucina żądanie po 100 s, więc odpowiedź modelu jest ograniczona do 4096 tokenów,
  a tryb „myślenia” modelu jest wyłączony.
- Strażnika usuwającego kartę spoza workflow jeszcze nie ma; zabezpieczeniem jest krok
  „Usuń kartę (zawsze)” i samowyłączenie modelu po terminie.
