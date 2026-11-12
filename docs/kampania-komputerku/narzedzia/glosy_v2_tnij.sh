#!/usr/bin/env bash
# Głosy v2: cięcie dialogu (Text to Dialogue) na kwestie u1–u4 + wersje A/B.
# Czasy cięć z transkrypcji Scribe (czasy słów) i pomiaru ciszy; patrz glosy.md.
set -euo pipefail
cd "$(dirname "$0")/../glosy_v2"
Z=zrodla
cut() { # $1 wejście $2 start $3 koniec $4 wyjście — 48 kHz mono, 15 ms wejście/wyjście
  local d; d=$(python3 -c "print(round($3-$2,3))")
  ffmpeg -y -v error -ss "$2" -t "$d" -i "$1" -af "afade=t=in:d=0.015,afade=t=out:st=$(python3 -c "print(round($d-0.04,3))"):d=0.04" -ar 48000 -ac 1 -c:a libmp3lame -b:a 192k "$4"
}
mkdir -p nowe_w1 nowe_w2 stare
# wariant 1 (eleven_v3, seed 23, [short pause]) — wybrany do renderu
cut $Z/dialog_w1_v3_seed23.mp3 0.00 5.00  nowe_w1/u1_basia.mp3
cut $Z/dialog_w1_v3_seed23.mp3 5.50 9.10  nowe_w1/u2_kuba.mp3
cut $Z/dialog_w1_v3_seed23.mp3 9.22 14.10 nowe_w1/u3_basia.mp3
cut $Z/dialog_w1_v3_seed23.mp3 14.35 17.79 nowe_w1/u4_marta.mp3
# wariant 2 (eleven_v4, seed 11) — wolniejszy, dłuższe pauzy
cut $Z/dialog_w2_v4_seed11.mp3 0.00 5.60  nowe_w2/u1_basia.mp3
cut $Z/dialog_w2_v4_seed11.mp3 5.70 10.12 nowe_w2/u2_kuba.mp3
cut $Z/dialog_w2_v4_seed11.mp3 10.15 15.65 nowe_w2/u3_basia.mp3
cut $Z/dialog_w2_v4_seed11.mp3 15.70 19.49 nowe_w2/u4_marta.mp3
# stare (v1): ścieżka dźwiękowa z ujęć HeyGen odc. 1
B=https://vkzndnaoxhdxrxlpntcb.supabase.co/storage/v1/object/public/studio-media/mcp/heygen/2026-11
i=0; for f in 16a47fa74b04d59cf4bccd1add59458a-b1a380f5 48dfcb8e3c3df21a592e64f42aff5f9c-100973d4 277604080409d31d3a536cb0802bfdd1-9085413c 46b0cea24ef6255fecc245d7662193fd-811ee76d; do
  i=$((i+1)); [ -f stare/u$i.mp3 ] || ffmpeg -y -v error -i "$B/$f.mp4" -vn -ar 48000 -ac 1 -c:a libmp3lame -b:a 192k stare/u$i.mp3
done
# sceny do odsłuchu: kwestie jedna po drugiej (jak w montażu), z ambience pod spodem dla v2
scena() { # $1 katalog/prefiks plików, $2 wyjście, $3 ambience 0/1
  for f in $1; do echo "file '$f'"; done > lista.txt
  ffmpeg -y -v error -f concat -safe 0 -i lista.txt -c:a libmp3lame -b:a 192k tmp_scena.mp3
  if [ "$3" = 1 ]; then
    ffmpeg -y -v error -i tmp_scena.mp3 -stream_loop -1 -i $Z/ambience_kancelaria_22s.mp3 -filter_complex \
      "[1:a]volume=0.55,afade=t=in:d=0.3[a];[0:a][a]amix=inputs=2:duration=first:normalize=0,loudnorm=I=-16:TP=-1.5:LRA=11" -ar 48000 -c:a libmp3lame -b:a 192k "$2"
  else
    ffmpeg -y -v error -i tmp_scena.mp3 -af loudnorm=I=-16:TP=-1.5:LRA=11 -ar 48000 -c:a libmp3lame -b:a 192k "$2"
  fi
  rm -f tmp_scena.mp3 lista.txt
}
scena "stare/u1.mp3 stare/u2.mp3 stare/u3.mp3 stare/u4.mp3" A_stare_v1_scena.mp3 0
scena "nowe_w1/u1_basia.mp3 nowe_w1/u2_kuba.mp3 nowe_w1/u3_basia.mp3 nowe_w1/u4_marta.mp3" B_nowe_v2_w1_scena.mp3 1
scena "nowe_w2/u1_basia.mp3 nowe_w2/u2_kuba.mp3 nowe_w2/u3_basia.mp3 nowe_w2/u4_marta.mp3" B_nowe_v2_w2_scena.mp3 1
for f in A_*.mp3 B_*.mp3 nowe_w1/*.mp3 nowe_w2/*.mp3 stare/*.mp3; do printf "%-32s %s s\n" "$f" "$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$f")"; done
