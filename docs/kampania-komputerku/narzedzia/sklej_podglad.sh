#!/usr/bin/env bash
# Sklejka podglądowa odc. 1 (u1–u4 + outro) z warstwami: logo + znaczek AI
# (bez belki „Treść wygenerowana przez AI”), dymek „Komputerku…” na ujęciu Marty (u4).
set -euo pipefail
cd "$(dirname "$0")"
norm() { # $1 wejście, $2 wyjście — 720x1280, 25 fps, AAC 48k stereo
  ffmpeg -y -v error -i "$1" -vf "scale=720:1280:force_original_aspect_ratio=decrease,pad=720:1280:(ow-iw)/2:(oh-ih)/2,fps=25,format=yuv420p" \
    -c:v libx264 -preset veryfast -crf 19 -c:a aac -ar 48000 -ac 2 -b:a 160k "$2"
}
for u in u1 u2 u3; do norm "$u.mp4" "n_$u.mp4"; done
# u4 z dymkiem „Komputerku…” przez całe ujęcie
ffmpeg -y -v error -i u4.mp4 -i warstwa_dymek.png -filter_complex \
  "[0:v]scale=720:1280:force_original_aspect_ratio=decrease,pad=720:1280:(ow-iw)/2:(oh-ih)/2,fps=25[v];[v][1:v]overlay=0:0:enable='gte(t,0.2)',format=yuv420p" \
  -c:v libx264 -preset veryfast -crf 19 -c:a aac -ar 48000 -ac 2 -b:a 160k n_u4.mp4
# u5 (ekran aplikacji z trybem Komputerku) robi narzedzia/nagraj_komputerku.js -> n_u5.mp4
# outro 3 s z ciszą
ffmpeg -y -v error -loop 1 -t 3 -i outro.png -f lavfi -t 3 -i anullsrc=r=48000:cl=stereo \
  -vf "fps=25,format=yuv420p" -c:v libx264 -preset veryfast -crf 19 -c:a aac -b:a 160k -shortest n_outro.mp4
printf "file 'n_u1.mp4'\nfile 'n_u2.mp4'\nfile 'n_u3.mp4'\nfile 'n_u4.mp4'\nfile 'n_u5.mp4'\nfile 'n_outro.mp4'\n" > lista.txt
ffmpeg -y -v error -f concat -safe 0 -i lista.txt -c copy surowa.mp4
# warstwy na całość: logo + znaczek AI tylko na ujęciach z postaciami (u1–u4);
# na ekranie aplikacji (u5) i planszy końcowej aplikacja/plansza ma własne logo.
DO=$(python3 -c "import subprocess as sp;print(sum(float(sp.check_output(['ffprobe','-v','error','-show_entries','format=duration','-of','csv=p=0',f]).decode()) for f in ['n_u1.mp4','n_u2.mp4','n_u3.mp4','n_u4.mp4']))")
ffmpeg -y -v error -i surowa.mp4 -i warstwa_logo_ai.png -filter_complex \
  "[0:v][1:v]overlay=0:0:enable='lt(t,$DO)',format=yuv420p" \
  -c:v libx264 -preset medium -crf 20 -c:a copy -movflags +faststart odc1_podglad.mp4
ffprobe -v error -show_entries format=duration -of csv=p=0 odc1_podglad.mp4
