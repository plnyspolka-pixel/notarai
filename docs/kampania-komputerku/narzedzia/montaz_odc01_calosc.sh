#!/usr/bin/env bash
# Pełny odcinek 01 „Poniedziałek, 8:57”: części 1–4 (sc. 01 → intro 5 → sc. 02–12 → outro „Siódemka” z napisem końcowym).
# Wynik: podglady/ODC01_Poniedzialek_857.mp4 (1080x1920, 30 kl./s, poniżej 100 MB).
set -euo pipefail
K="$(cd "$(dirname "$0")/.." && pwd)"; cd "$K"
bash narzedzia/montaz_odc01_cz1.sh; python3 narzedzia/montaz_odc01_cz2.py; python3 narzedzia/montaz_odc01_cz3.py; python3 narzedzia/montaz_odc01_cz4.py
ffmpeg -v error -y -i podglady/odc01_czesc1.mp4 -i podglady/odc01_czesc2.mp4 -i podglady/odc01_czesc3.mp4 -i podglady/odc01_czesc4.mp4 \
 -filter_complex "[0:v][0:a][1:v][1:a][2:v][2:a][3:v][3:a]concat=n=4:v=1:a=1[v][a0];[a0]loudnorm=I=-16:TP=-1.5:LRA=11[a]" \
 -map "[v]" -map "[a]" -c:v libx264 -preset slow -crf 23 -pix_fmt yuv420p -r 30 -c:a aac -ar 48000 -b:a 192k -movflags +faststart podglady/ODC01_Poniedzialek_857.mp4
ffprobe -v error -show_entries format=duration,size -of csv=p=0 podglady/ODC01_Poniedzialek_857.mp4
