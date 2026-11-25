"""Reczne zgloszenie do samonaprawy (zamiast Run workflow w GitHubie).

  python scripts/samonaprawa/zglos.py "opis bledu slowami, bez danych klientow"
      -> zdarzenie na szyne EventBridge (to samo, co wysyla aplikacja), potok w CodeBuild je podejmie
  python scripts/samonaprawa/zglos.py --przeglad
      -> od razu przeglad bledow (jak harmonogram co 30 min)
  python scripts/samonaprawa/zglos.py --test
      -> NIESZKODLIWY test sciezki wdrozenia: wpis w docs/samonaprawa-testy-wdrozenia.md,
         bez agentow, ale z wdrozeniem na produkcje, obserwacja i logika cofniecia

Wymaga poswiadczen wlasciciela konta (events:PutEvents albo codebuild:StartBuild).
"""
from __future__ import annotations

import argparse
import base64
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import zgloszenie as zgl  # noqa: E402

REGION = "eu-central-1"
KOLEJKA = "notarai-samonaprawa-kolejka"
PROJEKT = "notarai-samonaprawa"


def koduj(dane: dict) -> str:
    return base64.b64encode(json.dumps(dane, ensure_ascii=False, sort_keys=True).encode("utf-8")).decode("ascii")


def wpis_zdarzenia(typ: str, dane: dict) -> dict:
    """Ten sam ksztalt co samonaprawa.wpis_zdarzenia() w aplikacji."""
    return {"Source": "notarai.samonaprawa", "DetailType": typ, "EventBusName": "default",
            "Detail": json.dumps({**dane, "ladunek_b64": koduj(dane)}, ensure_ascii=False)}


def main(argv: list[str] | None = None, klienci: dict | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("opis", nargs="?", default="")
    parser.add_argument("--przeglad", action="store_true")
    parser.add_argument("--test", action="store_true")
    a = parser.parse_args(argv)
    klienci = klienci or {}
    if a.test:
        dane = zgl.oczysc({"uwagi": "Test sciezki wdrozenia samonaprawy w AWS - bez agenta, zmiana tylko w docs/.",
                           "rodzaj": "reczne", "typ": "zgloszenie reczne", "wersja": "produkcja"})
        sqs = klienci.get("sqs") or _klient("sqs")
        adres = sqs.get_queue_url(QueueName=KOLEJKA)["QueueUrl"]
        odp = sqs.send_message(QueueUrl=adres, MessageBody=json.dumps({"ladunek": koduj(dane), "test": True}))
        print(f"Test wdrozenia w kolejce: {odp['MessageId']} (potok podejmie go, gdy bedzie wolny)")
        return 0
    if a.przeglad:
        # Jak harmonogram: wprost do kolejki (zdarzenie "przeglad" nie pasuje do zadnej reguly EventBridge).
        sqs = klienci.get("sqs") or _klient("sqs")
        adres = sqs.get_queue_url(QueueName=KOLEJKA)["QueueUrl"]
        odp = sqs.send_message(QueueUrl=adres, MessageBody=json.dumps({"ladunek": koduj({"zdarzenie": "przeglad"})}))
        print(f"Przeglad w kolejce: {odp['MessageId']} (potok podejmie go, gdy bedzie wolny)")
        return 0
    elif a.opis.strip():
        dane = zgl.oczysc({"uwagi": a.opis, "rodzaj": "reczne", "typ": "zgloszenie reczne", "wersja": "produkcja"})
        wpis = wpis_zdarzenia("zgloszenie", dane)
    else:
        parser.error("podaj opis bledu albo --przeglad albo --test")
    ev = klienci.get("events") or _klient("events")
    odp = ev.put_events(Entries=[wpis])
    if odp.get("FailedEntryCount"):
        print("EventBridge odrzucil zdarzenie", file=sys.stderr)
        return 1
    print("Zgloszenie wyslane - potok podejmie je w ciagu minuty (CodeBuild notarai-samonaprawa).")
    return 0


def _klient(nazwa: str):
    import boto3
    return boto3.client(nazwa, region_name=REGION)


if __name__ == "__main__":
    sys.exit(main())
