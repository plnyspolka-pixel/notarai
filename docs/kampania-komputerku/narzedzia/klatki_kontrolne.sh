#!/usr/bin/env bash
# Arkusz klatek co 1 s (lista kontrolna B1-B6): oglądam przed wysłaniem do akceptacji.
# Użycie: klatki_kontrolne.sh <plik.mp4> <wyjscie.jpg> [kolumn=10]
set -euo pipefail
ffmpeg -nostdin -v error -y -i "$1" -vf "fps=1,scale=160:-1,tile=${3:-10}x$(( ( $(ffprobe -v error -show_entries format=duration -of csv=p=0 "$1" | cut -d. -f1) / ${3:-10} ) + 1 ))" -frames:v 1 "$2"
echo "$2"
