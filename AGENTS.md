# AGENTS.md (notarai)

Plik dla agentów kodujących innych niż Claude Code. Zasady projektu są w `CLAUDE.md`; tu tylko wskazówki, gdzie szukać reszty. Przed pracą przeczytaj `CLAUDE.md` w całości (RODO, region, sekret, zakaz renderu na GitHub Actions, konwencje nazw).

## Gdzie jest stan prac
- **Zadania czekające na dostęp i stan wdrożeń:** `docs/czeka-na-dostep.md` (pozycje `NA-n`). Aktualna: **NA-18** (stały adres wyjściowy, blokada modeli, umowa powierzenia, decyzje właściciela).
- **Umowa powierzenia i regulamin:** źródło `docs/prawne/`; strony generuje `infra/strona_dokumenty.py`. Nie edytuj HTML ręcznie.
- **Zatwierdzone modele AI:** `config.ZATWIERDZONE_MODELE`, hak w `bedrock.py`, uprawnienia w `infra/notarai-s3.yaml`. Nowy model dopisuj tylko po gwarancji zerowej retencji dla tego modelu, we wszystkich trzech miejscach naraz (pilnuje tego `test_model_zero_retencji.py`).
- **Stały adres wyjściowy:** `infra/notarai-egress.yaml` (stos `notarai-egress`). Brama NAT jest domyślnie wyłączona (koszt); adres działa tylko przy `NatWlaczony=true`.

## Czego nie wolno wpisywać do repozytorium
Adresów IP infrastruktury, identyfikatorów kont i zasobów AWS (vpc, subnet, eipalloc itp.), kluczy, pełnych polityk IAM, dowodów z audytu. Pełny pakiet dowodów A-F jest prywatny (poza repozytorium). Adres egress odczytasz z AWS: `aws cloudformation describe-stacks --stack-name notarai-egress` (wyjście `AdresEgress`).

## Zanim zmienisz produkcję
Wdrożenia IAM, sieci i umów wymagają zgody właściciela. Zmiana umowy powierzenia (zał. 2 i 3) wymaga powiadomienia kancelarii (§ 6 ust. 2 i § 8 ust. 2 umowy, 30 dni). Nie scalaj do `master` zmian umowy bez tej decyzji, bo scalenie publikuje je na stronie.
