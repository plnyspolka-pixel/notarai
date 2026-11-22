# NotarAI Confidential: publiczny rejestr wydań (etap 0)

**Status: biblioteka, narzędzie wiersza poleceń i testy na danych syntetycznych.
Rejestr nie jest nigdzie opublikowany. Żadnych wywołań AWS, żadnych sekretów.**

Realizuje etap 0 z `docs/confidential-custody-samorzady.md` (pkt 5.1 i 5.7):
każdy może pobrać rejestr i sprawdzić go u siebie, bez konta AWS i bez zgody
NotarAI.

## Co jest w rejestrze

Każdy wpis to jedno wydanie podpisane przez kustosza (format z
`confidential/release_approval.py`): digest obrazu, PCR17, skrót polityki klucza
KMS, wersja definicji zadania, ARN klucza, okres ważności i podpis ECDSA P-256.
Wpis dodaje: numer, pełny identyfikator commita źródeł, czas zapisu, odcisk
klucza kustosza i skrót poprzedniego wpisu.

Wpisy mają wyłącznie pola o stałym formacie. Nie ma pola tekstowego, więc dane
klientów i dane osobowe nie mogą trafić do rejestru; próba dodania nieznanego
pola odrzuca cały rejestr.

## Co dowodzi poprawna weryfikacja

- Każde wydanie podpisał klucz kustosza, którego odcisk weryfikujący zna z
  niezależnego kanału.
- Historii nie zmieniono: wpisów nie da się przepisać, usunąć ani przestawić
  bez zmiany skrótu głowy rejestru.
- Z wcześniejszym punktem kontrolnym: rejestr jest przedłużeniem tego, który
  weryfikujący widział poprzednio. Operator nie pokazał mu innej historii.

## Czego nie dowodzi

Raport zawsze zostawia `live_kms_policy_verified`,
`hardware_nitro_attestation_verified` i `zero_operator_access_proven` jako
`false`. Rejestr mówi, co zatwierdzono, a nie jaki jest stan konta w tej chwili,
czy sprzęt Nitro naprawdę uruchomił ten obraz, ani czy kod nie wypuszcza treści.

## Użycie

Sprawdzenie (może to zrobić każdy):

```sh
python scripts/confidential_transparency_log.py verify \
  --log transparency-log.json \
  --trusted-custodian-public-key custody-public.pem \
  --trusted-custodian-public-key-sha256 <ODCISK_Z_NIEZALEZNEGO_KANALU> \
  --previous-checkpoint moj-poprzedni-punkt.json \
  --write-checkpoint moj-nowy-punkt.json
```

Klucz publiczny kustosza i jego odcisk muszą dotrzeć do sprawdzającego drogą,
której NotarAI nie kontroluje. Odcisk skopiowany z NotarAI nie jest niezależnym
dowodem. Punkt kontrolny to mały plik (rozmiar i skrót głowy); warto go
zachować i podać przy następnym sprawdzeniu.

Dopisanie wydania (po stronie publikującego; narzędzie niczego nie podpisuje):

```sh
python scripts/confidential_transparency_log.py append \
  --log transparency-log.json \
  --release-file /secure/approved-pilot01.json \
  --source-commit <40_ZNAKOW_COMMITA> \
  --output transparency-log-nowy.json \
  --trusted-custodian-public-key custody-public.pem \
  --trusted-custodian-public-key-sha256 <ODCISK>
```

Plik wynikowy musi być nowy; narzędzie nie nadpisuje istniejących plików.

Testy: `python -m pytest -q test_confidential_transparency_log.py`

## Czego jeszcze brakuje

1. **Miejsca publikacji** rejestru i kopii u niezależnych świadków.
2. **Dokumentów atestacji Nitro** jako osobnego rodzaju wpisu, z weryfikacją
   podpisu i łańcucha certyfikatów AWS. Wymaga prawdziwego dokumentu z pilota.
3. **Wiarygodnego czasu.** `recorded_at` podaje publikujący; nie ma jeszcze
   zewnętrznego znacznika czasu.
4. **Odtwarzalnej kompilacji**, która wiąże `source_commit` z digestem obrazu.
   Dziś commit jest deklaracją publikującego.
5. **Weryfikatora w przeglądarce** dla osób nietechnicznych (etap 1).

## Do decyzji właściciela

Wpis zawiera identyfikator kancelarii (np. `pilot01`) oraz numery kont AWS
operatora i kustosza. W publicznym rejestrze widać więc, ile kancelarii
korzysta z usługi i kiedy dostają wydania. Alternatywa: jedno wydanie dla
wspólnego obrazu zamiast wydania na kancelarię; wymaga zmiany formatu podpisu
kustosza.
