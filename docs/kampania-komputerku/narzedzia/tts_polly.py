#!/usr/bin/env python3
"""Polski lektor z Amazon Polly (ten sam rachunek AWS co aplikacja) + visemy do rigu 2D.

Glosy pl-PL: Ola (neural i generative), Ewa (generative; standard: Ewa, Maja, Jacek, Jan).
Darmowy limit: 12 mies. po 1 mln znakow neural / 100 tys. generative miesiecznie; potem
16 USD (neural) / 30 USD (generative) za 1 mln znakow. Speech Marks (viseme, word) ida
razem z audio - bez osobnego rozpoznawania mowy do synchronizacji ust.

Uzycie:
  tts_polly.py "Tekst kwestii po polsku." -o kwestia.mp3 [--glos Ola] [--silnik neural|generative] [--visemy]
Poswiadczenia AWS jak dla aplikacji (profil / zmienne / rola), region eu-central-1.
"""
import json
import os
import sys

import boto3

REGION = os.getenv("AWS_REGION", "eu-central-1")


def main(a: list[str]) -> None:
    if not a:
        sys.exit(__doc__)
    tekst, out, glos, silnik, visemy = a[0], "kwestia.mp3", "Ola", "neural", False
    i = 1
    while i < len(a):
        if a[i] == "-o":
            out = a[i + 1]; i += 2
        elif a[i] == "--glos":
            glos = a[i + 1]; i += 2
        elif a[i] == "--silnik":
            silnik = a[i + 1]; i += 2
        elif a[i] == "--visemy":
            visemy = True; i += 1
        else:
            i += 1
    polly = boto3.client("polly", region_name=REGION)
    wspolne = {"Text": tekst, "VoiceId": glos, "Engine": silnik, "LanguageCode": "pl-PL"}
    audio = polly.synthesize_speech(OutputFormat="mp3", **wspolne)
    with open(out, "wb") as f:
        f.write(audio["AudioStream"].read())
    print(f"audio: {out} ({len(tekst)} znakow, {glos}/{silnik})")
    if visemy:
        znaki = polly.synthesize_speech(OutputFormat="json", SpeechMarkTypes=["viseme", "word"], **wspolne)
        wiersze = [json.loads(w) for w in znaki["AudioStream"].read().decode("utf-8").splitlines() if w.strip()]
        cel = os.path.splitext(out)[0] + ".visemy.json"
        json.dump(wiersze, open(cel, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"visemy: {cel} ({sum(1 for w in wiersze if w['type'] == 'viseme')} visemow)")


if __name__ == "__main__":
    main(sys.argv[1:])
