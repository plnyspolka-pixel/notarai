# Propozycja W7: zwięzła karta (do wniesienia po scaleniu W6)

Tego pliku nie czyta agent. Zawiera tekst do przeniesienia do `SZABLON.md` i `docs/koder.md`
w tej sesji, która scali W6 (tamte pliki zmienia teraz gałąź `feature/koder-ukryte-testy`).
Mechanizm jest już w kodzie: `tools/agent_factory/koder/lint_karty.py`.

## 1. Do `docs/agent-tasks/SZABLON.md` - jedna nowa sekcja po „Stan docelowy”

```markdown
## Kryteria akceptacji
- 1-3 punkty, każdy sprawdzalny z zewnątrz: wejście -> wynik albo nazwa testu, który przechodzi.
```

I jedno zdanie na końcu sekcji „Nie ruszaj”:

```markdown
Jeżeli stan docelowy już jest spełniony, dozwolony wynik to „ZMIANA NIEPOTRZEBNA: <uzasadnienie>”.
```

Nic więcej - bez dodatkowych sekcji (uzasadnienie w punkcie 3).

## 2. Do zasad polecenia dla agenta (`karta.ZASADY`)

Gotowe zdanie: `lint_karty.ZASADA_NIEPOTRZEBNA`.

## 3. Do `docs/koder.md`

W sekcji „Karta zadania”, po zdaniu o czterech pytaniach:

> **Dlaczego karta jest krótka:** w naszym pomiarze na 100 parach zwykłe polecenie dało 27/100,
> a „ustrukturyzowany kontrakt” 13/100 (gałąź learning-loop, 16.11.2026) - sekcji nie dokładamy
> bez pomiaru A/B.

W sekcji „Kiedy wynik kodera jest zaliczony” - dopisać:

> Karta z tytułem albo punktem zaczynającym się od „popraw”, „zrefaktoruj”, „ulepsz”,
> „uporządkuj” (i podobnych) musi mieć `## Kryteria akceptacji` z 1-3 punktami - inaczej nie
> przejdzie `karta.py lint`. Wynik „zmiana niepotrzebna” jest dozwolony i liczony osobno
> (`niepotrzebna`), jeżeli agent niczego nie zmienił, a testy - także ukryte - przechodzą na
> niezmienionym kodzie; w przeciwnym razie odrzucenie z powodem `niepotrzebna_niepotwierdzona`.
> Diff dopisujący import spoza stdlib, repozytorium i `requirements.txt` jest odrzucany
> (`nowa_zaleznosc`, miara K5). Każde zadanie zostawia wiersz w `dziennik.jsonl` z manifestem
> silnika (model, vLLM, dtype, kwantyzacja, kontekst, prefix caching, GPU, sha uprzęży, sha karty,
> skrót ukrytych testów); koszt nieznany to `null`, nigdy 0.
