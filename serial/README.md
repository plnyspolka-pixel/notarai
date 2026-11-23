# Serial „Kancelaria pod Siódemką” — publikacja na notarai.pl

- `odcinki.json` — kolejka. Odcinek jest publiczny dopiero, gdy: `status` = `gotowy`,
  minęło `publish_at` (z jawną strefą, np. `+01:00`), a plik `pliki.wideo` istnieje.
  Bez wideo odcinek jest pomijany i zapisany w logu, nigdy nie trafia na stronę częściowo.
- `media/` — pliki odcinków: `sXXeYY.mp4` (9:16), opcjonalnie `sXXeYY.jpg` (plakat)
  i `sXXeYY.vtt` (napisy). Zamiast pliku w repo można podać adres `https://`.
  Pliki z `media/` są kopiowane na stronę tylko dla odcinków już opublikowanych,
  więc odcinek przed premierą nie jest dostępny nawet po zgadnięciu adresu.
- `zasoby/` — `serial.css` i `serial.js` (pomiar, tylko po zgodzie na cookie).

Generator: `python -I seo/serial.py zbuduj` (buduje `strona/serial/`, RSS, dopisuje
sitemap). Podgląd decyzji: `python -I seo/serial.py plan --teraz 2026-11-24T09:05:00+01:00`.

Publikacja: `.github/workflows/serial-publikacja.yml` codziennie o 9:00 i 16:00
czasu polskiego uruchamia wysyłkę strony (`strona.yml`). Dodanie odcinka = commit
z plikami w `media/` i wpisem w `odcinki.json` na `master` przed godziną premiery.
Pomiar i nazwy zdarzeń: `docs/serial-pomiar.md`.
