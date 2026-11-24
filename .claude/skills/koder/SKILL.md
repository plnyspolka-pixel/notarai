---
name: koder
description: Zlecanie zadań programistycznych agentowi na wynajętym GPU (SaladCloud + vLLM) i odbiór wyników. Używaj, gdy użytkownik prosi o zmiany w kodzie, które da się podzielić na małe zadania z testem, mówi o "koderze", "agentach", "GPU" albo o paczce zadań.
---

# koder

> **23.11.2026: workflow `koder.yml` usunięty.** Runner GitHuba czekał na GPU do 2 h i palił minuty;
> wynajem GPU z GitHub Actions jest zakazany (CLAUDE.md, `tools/zakaz_renderu_gha.py`).
> Koder przechodzi na Cloudflare; do tego czasu push na `koder/*` niczego nie uruchamia.


Pełny opis: `docs/koder.md`. Skrót postępowania:

1. Podziel pracę na zadania. Dla każdego zdecyduj tor według reguły z `docs/koder.md`
   (koder: najwyżej 4 wskazane pliki, rozstrzygający test pytest, brak decyzji projektowych,
   poza obszarami zastrzeżonymi; wszystko inne: claude). Pojedynczego zadania nie wysyłaj na GPU.
2. Napisz karty w `docs/agent-tasks/kolejka/<id>.md` według `docs/agent-tasks/SZABLON.md`.
   Przed napisaniem karty przeczytaj kod, którego dotyczy: podaj funkcję, przykład wejście -> wynik
   i sprawdź, że polecenie z pola `sprawdzenie` dziś działa.
   Do każdej karty napisz ukryte testy w `docs/agent-tasks/ukryte/<id>/` (rodzaj karty
   i co tam włożyć: `docs/koder.md`, „Ukryte testy”): inne przypadki niż w treści karty
   i co najmniej jedną łatkę sabotażu `*.patch`, gdy rodzaj tego wymaga. Sprawdź lokalnie:
   `KODER_OCENA=lokalnie python tools/agent_factory/koder/ukryte.py przed <karta> .`
3. `python tools/agent_factory/koder/karta.py lint` musi przejść.
4. Powiedz użytkownikowi, ile kart idzie na który tor i jaki jest limit kosztu, potem wypchnij
   gałąź `koder/<paczka>` (to wynajmuje kartę - płatne, limit w `.github/workflows/koder.yml`).
5. Po przebiegu pobierz `agent/<przebieg>-wyniki`, przeczytaj `WYNIKI.md`, przejrzyj KAŻDY diff
   z gałęzi `agent/<przebieg>-<id>`. Przyjęte zmiany złóż w jeden pull request; niezaliczone
   i odrzucone zrób sam. Niczego nie scalaj bez zgody użytkownika.
6. Zapisz w odpowiedzi: ile zaliczył automat, ile przyjąłeś po przeglądzie, koszt karty.

Nigdy nie wysyłaj do kodera danych klientów, `dane/`, `.env` ani zadań z obszarów zastrzeżonych.
