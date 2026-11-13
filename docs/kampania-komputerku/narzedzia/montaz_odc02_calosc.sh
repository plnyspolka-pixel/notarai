#!/usr/bin/env bash
# Pełny odcinek 02 „Proszę nie przy nim”: części 1–3 (W poprzednim odcinku, trzęsienie ziemi, intro, sc. 01–06, zapowiedź odc. 03, outro).
# Wynik: podglady/ODC02_Prosze_nie_przy_nim.mp4 (1080x1920, 30 kl./s, poniżej 100 MB). Na końcu automatyczna kontrola dźwięku.
set -euo pipefail
K="$(cd "$(dirname "$0")/.." && pwd)"; cd "$K"
python3 narzedzia/montaz_odc02_cz1.py; python3 narzedzia/montaz_odc02_cz2.py; python3 narzedzia/montaz_odc02_cz3.py
ffmpeg -nostdin -v error -y -i podglady/odc02_czesc1.mp4 -i podglady/odc02_czesc2.mp4 -i podglady/odc02_czesc3.mp4 \
 -filter_complex "[0:v][0:a][1:v][1:a][2:v][2:a]concat=n=3:v=1:a=1[v][a0];[a0]loudnorm=I=-16:TP=-1.5:LRA=11[a]" \
 -map "[v]" -map "[a]" -c:v libx264 -preset slow -crf 23 -pix_fmt yuv420p -r 30 -c:a aac -ar 48000 -b:a 192k -movflags +faststart podglady/ODC02_Prosze_nie_przy_nim.mp4
ffprobe -v error -show_entries format=duration,size -of csv=p=0 podglady/ODC02_Prosze_nie_przy_nim.mp4
python3 narzedzia/kontrola_odcinka.py podglady/ODC02_Prosze_nie_przy_nim.mp4 --pauzy 16.0-16.8
