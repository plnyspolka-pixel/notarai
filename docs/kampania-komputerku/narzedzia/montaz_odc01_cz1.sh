#!/usr/bin/env bash
# Montaż odc. 01, część 1: trzęsienie ziemi (sc. 01) → intro 5 → sc. 02. Wynik: podglady/odc01_czesc1.mp4 (1080x1920, 30 kl./s).
set -euo pipefail
K="$(cd "$(dirname "$0")/.." && pwd)"; V="$K/produkcja-odc01/czesc1_wideo"; WL="$V/warstwy"
T="${TMPDIR:-/tmp}/odc01_cz1"; rm -rf "$T"; mkdir -p "$T"; cd "$T"
LOGO="$K/narzedzia/warstwy/warstwa_logo_ai.png"
ENC="-c:v libx264 -preset medium -crf 18 -pix_fmt yuv420p -r 30"
SC="scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps=30,setsar=1"
# ujecie <wej> <ss> <t> <wyj> [warstwa start koniec]  — obraz bez dźwięku + logo/AI (+ opcjonalna warstwa)
ujecie() { local inp=$1 ss=$2 t=$3 out=$4 w=${5:-} a=${6:-0} b=${7:-0}
  if [ -n "$w" ]; then
    ffmpeg -v error -y -ss $ss -t $t -i "$inp" -i "$LOGO" -loop 1 -t $t -i "$w" -filter_complex \
      "[0:v]$SC[v];[1:v]scale=1080:1920[l];[v][l]overlay=0:0[v1];[2:v]format=rgba,fade=t=in:st=$a:d=0.2:alpha=1,fade=t=out:st=$b:d=0.2:alpha=1[w];[v1][w]overlay=0:0:enable='between(t,$a,$b+0.2)'" -an $ENC "$out"
  else
    ffmpeg -v error -y -ss $ss -t $t -i "$inp" -i "$LOGO" -filter_complex "[0:v]$SC[v];[1:v]scale=1080:1920[l];[v][l]overlay=0:0" -an $ENC "$out"
  fi; }
# --- sc. 01: trzęsienie ziemi ---
ujecie "$V/b1_zegar.mp4" 0.3 1.3 c1.mp4 "$WL/czas_0857.png" 0.1 1.1
ujecie "$V/b2_telefon.mp4" 0.5 0.9 c2.mp4
ujecie "$V/b3_pawel_drzwi.mp4" 0.2 1.6 c3.mp4
ujecie "$V/b4_drukarka.mp4" 1.0 0.9 c4.mp4
ujecie "$V/b5_basia_chwileczke.mp4" 0.3 2.8 c5.mp4
printf "file '%s'\n" c1.mp4 c2.mp4 c3.mp4 c4.mp4 c5.mp4 > l1.txt; ffmpeg -v error -y -f concat -safe 0 -i l1.txt -c copy cold_v.mp4
ffmpeg -v error -y -i cold_v.mp4 -i "$K/produkcja-odc01/czesc3_wideo/amb_recepcja_n.mp3" -i "$V/sfx_telefon.mp3" -i "$V/sfx_drzwi.mp3" -i "$V/sfx_drukarka.mp3" -i "$V/kuba_zza_kadru.mp3" -filter_complex \
 "[1:a]atrim=0:7.5,volume=1.0[a1];[2:a]adelay=300|300,volume=0.9[a2];[3:a]adelay=2100|2100,volume=0.8[a3];[4:a]adelay=4000|4000,volume=0.7[a4];[5:a]adelay=4200|4200,volume=1.6,aecho=0.6:0.5:35:0.15[a5];\
[a1][a2][a3][a4][a5]amix=inputs=5:duration=first:normalize=0,aformat=sample_rates=48000:channel_layouts=stereo[a]" \
 -map 0:v -map "[a]" -c:v copy -c:a aac -b:a 192k -t 7.5 cold.mp4
# --- intro 5 ---
ffmpeg -v error -y -i "$K/intro/INTRO_5_komputerku_9x16.mp4" -vf "$SC" $ENC -c:a aac -ar 48000 -ac 2 -b:a 192k intro.mp4
# --- sc. 02 ---
ujecie "$V/t1_basia_telefon.mp4" 0 3.88 d1.mp4 "$WL/karta_basia.png" 0.3 3.2
ujecie "$V/b2_telefon.mp4" 2.5 0.8 d2.mp4
ujecie "$V/t2_pawel.mp4" 0 5.95 d3.mp4 "$WL/karta_pawel.png" 0.5 3.4
ujecie "$V/t1_basia_zajmuje.mp4" 0 2.28 d4.mp4
ujecie "$V/t3_marta.mp4" 0 1.64 d5.mp4 "$WL/karta_marta.png" 0.05 1.4
ujecie "$V/t1_basia_sprawdzam.mp4" 0 1.24 d6.mp4
printf "file '%s'\n" d1.mp4 d2.mp4 d3.mp4 d4.mp4 d5.mp4 d6.mp4 > l2.txt; ffmpeg -v error -y -f concat -safe 0 -i l2.txt -c copy sc2_v.mp4
# dźwięk sc. 02: kwestie z ujęć HeyGen ułożone w czasie + ambience + drugi dzwonek
for f in t1_basia_telefon:0:3.88 t2_pawel:0:5.95 t1_basia_zajmuje:0:2.28 t3_marta:0:1.64 t1_basia_sprawdzam:0:1.24; do n=${f%%:*}; r=${f#*:}; d=${r#*:};
  ffmpeg -v error -y -i "$V/$n.mp4" -vn -t $d -af "aformat=sample_rates=48000:channel_layouts=stereo,apad=whole_dur=$d" "$n.wav"; done
ffmpeg -v error -y -f lavfi -t 0.8 -i anullsrc=r=48000:cl=stereo cisza08.wav
printf "file '%s'\n" t1_basia_telefon.wav cisza08.wav t2_pawel.wav t1_basia_zajmuje.wav t3_marta.wav t1_basia_sprawdzam.wav > la.txt
ffmpeg -v error -y -f concat -safe 0 -i la.txt -c pcm_s16le dialog.wav
D2=$(ffprobe -v error -show_entries format=duration -of csv=p=0 sc2_v.mp4)
ffmpeg -v error -y -i sc2_v.mp4 -i dialog.wav -i "$K/produkcja-odc01/czesc3_wideo/amb_recepcja_n.mp3" -i "$V/sfx_telefon.mp3" -filter_complex \
 "[1:a]volume=1.5[d];[2:a]atrim=3:20,asetpts=PTS-STARTPTS,volume=0.85[am];[3:a]adelay=3880|3880,volume=0.8[t];[d][am][t]amix=inputs=3:duration=first:normalize=0,afade=t=out:st=$(python3 -c "print($D2-0.4)"):d=0.4,aformat=sample_rates=48000:channel_layouts=stereo[a]" \
 -map 0:v -map "[a]" -c:v copy -c:a aac -b:a 192k -t $D2 sc2.mp4
# --- całość ---
printf "file '%s'\n" cold.mp4 intro.mp4 sc2.mp4 > lc.txt
ffmpeg -v error -y -f concat -safe 0 -i lc.txt -c copy sur.mp4
ffmpeg -v error -y -i sur.mp4 -c:v copy -af loudnorm=I=-16:TP=-1.5:LRA=11 -c:a aac -ar 48000 -b:a 192k -movflags +faststart "$K/podglady/odc01_czesc1.mp4"
ffprobe -v error -show_entries format=duration -of csv=p=0 "$K/podglady/odc01_czesc1.mp4"
