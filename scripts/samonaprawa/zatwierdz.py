"""Zatwierdzenie poprawki, ktora czeka na decyzje wlasciciela (werdykt "pr").

  python scripts/samonaprawa/zatwierdz.py <odcisk>

Zatwierdzenie to FLAGA w DynamoDB (rekord BLAD#<odcisk>, pole zatwierdzone=true), ktora moze
ustawic tylko ktos z uprawnieniami do tabeli (aplikacja ich nie ma). Potem zdarzenie
"zatwierdzenie" uruchamia czesc wdrozeniowa potoku: patch z S3 na biezaca wersje z produkcji,
pelny zestaw testow, wdrozenie, 20 minut obserwacji, cofniecie przy nawrocie.

Reczny odpowiednik bez tego skryptu - patrz docs/samonaprawa.md (aws dynamodb update-item + aws events put-events).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import stan as stan_mod  # noqa: E402
import zglos  # noqa: E402

REGION = "eu-central-1"


def zatwierdz(odcisk: str, stan, ev, kto: str = "") -> str:
    """Ustawia flage i wysyla zdarzenie. Zwraca komunikat; ValueError, gdy nie ma czego zatwierdzac."""
    wpis = stan.pobierz(odcisk)
    if not wpis or wpis.get("status") != stan_mod.CZEKA or not wpis.get("patch_klucz"):
        raise ValueError(f"blad {odcisk} nie ma poprawki czekajacej na zatwierdzenie")
    stan.ustaw(odcisk, zatwierdzone=True, zatwierdzil=kto[:200] or "wlasciciel")
    odp = ev.put_events(Entries=[zglos.wpis_zdarzenia("zatwierdzenie", {"zdarzenie": "zatwierdzenie", "odcisk": odcisk})])
    if odp.get("FailedEntryCount"):
        raise RuntimeError("EventBridge odrzucil zdarzenie - flaga ustawiona, ponow wysylke")
    return f"Zatwierdzono poprawke {odcisk}. Potok (CodeBuild notarai-samonaprawa) wdrozy ja w ciagu minuty."


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("odcisk")
    a = parser.parse_args(argv)
    import boto3
    stan = stan_mod.Stan(stan_mod.TabelaDynamo(stan_mod.TABELA, REGION))
    kto = boto3.client("sts", region_name=REGION).get_caller_identity()["Arn"]
    try:
        print(zatwierdz(a.odcisk, stan, boto3.client("events", region_name=REGION), kto))
    except (ValueError, RuntimeError) as e:
        print(str(e), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
