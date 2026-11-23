---
name: koder
description: Zlecanie zadań programistycznych agentowi na wynajętym GPU (SaladCloud + vLLM) i odbiór wyników. Używaj, gdy użytkownik prosi o zmiany w kodzie, które da się podzielić na małe zadania z testem, mówi o "koderze", "agentach", "GPU" albo o paczce zadań.
---

# koder

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
   gałąź `koder/<paczka>`. Przebieg prowadzi Worker Cloudflare `notarai-koder` (webhook push
   albo `POST /start` z tokenem - `docs/koder.md`, „Gdzie to działa”); płatne, limit
   `KODER_MAX_USD` w `tools/agent_factory/koder/cloudflare/wrangler.jsonc`. NIGDY nie dodawaj
   workflow GitHub Actions, który wynajmuje GPU albo uruchamia koder (twarda reguła 23.11.2026,
   pilnuje `tools/zakaz_renderu_gha.py`). Postęp: `GET /stan`; awaryjnie `POST /stop`.
5. Gdy przebieg jest w fazie `do_odbioru` (Worker bez GITHUB_TOKEN), załóż gałęzie:
   `KODER_TOKEN_PLIK=<plik> python3 tools/agent_factory/koder/odbierz.py <przebieg> --push`.
   Potem pobierz `agent/<przebieg>-wyniki`, przeczytaj `WYNIKI.md`, przejrzyj KAŻDY diff
   z gałęzi `agent/<przebieg>-<id>`. Przyjęte zmiany złóż w jeden pull request; niezaliczone
   i odrzucone zrób sam. Niczego nie scalaj bez zgody użytkownika.
6. Zapisz w odpowiedzi: ile zaliczył automat, ile przyjąłeś po przeglądzie, koszt karty.

Nigdy nie wysyłaj do kodera danych klientów, `dane/`, `.env` ani zadań z obszarów zastrzeżonych.
