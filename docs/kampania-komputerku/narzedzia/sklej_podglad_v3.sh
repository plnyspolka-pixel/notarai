#!/usr/bin/env bash
# Podgląd odc. 1 v3: kancelaria-v2, awatary v2 (Avatar 6 Turbo + motion_prompt), głosy v2. Reszta jak v2.
# Warstwy jak w sklej_podglad.sh (logo + znaczek AI na u1–u4, dymek „Komputerku…” na u4),
# odtworzone z pakietu: warstwy/warstwa_logo_ai.png (górny pas OVERLAY_TRANSPARENT 9x16),
# warstwy/warstwa_dymek.png (04_grafika_systemowa/dymek_komputerku_transparent.png, 640 px, x=40 y=1000).
# Ambience kancelarii pod u1–u4 (glosy_v2/zrodla/ambience_kancelaria_22s.mp3), całość loudnorm -16 LUFS.
set -euo pipefail
K="$(cd "$(dirname "$0")/.." && pwd)"; W="$K/narzedzia/warstwy"
T="${TMPDIR:-/tmp}/podglad_v3"; mkdir -p "$T"; cd "$T"
B=https://vkzndnaoxhdxrxlpntcb.supabase.co/storage/v1/object/public/studio-media/mcp/heygen/2026-11
declare -A U=([u1]=komputerku-odc1-u1-basia-v2-16697f37 [u2]=komputerku-odc1-u2-kuba-v2-8e7109e8 \
              [u3]=komputerku-odc1-u3-basia-v2-81d67c73 [u4]=komputerku-odc1-u4-marta-v2-10201726)
for u in u1 u2 u3 u4; do [ -s $u.mp4 ] || curl -sS -o $u.mp4 "$B/${U[$u]}.mp4"; done
ENC="-c:v libx264 -preset veryfast -crf 19 -c:a aac -ar 48000 -ac 2 -b:a 160k"
SC="scale=720:1280:force_original_aspect_ratio=decrease,pad=720:1280:(ow-iw)/2:(oh-ih)/2,fps=25"
for u in u1 u2 u3; do ffmpeg -y -v error -i $u.mp4 -vf "$SC,format=yuv420p" $ENC n_$u.mp4; done
ffmpeg -y -v error -i u4.mp4 -i "$W/warstwa_dymek.png" -filter_complex "[0:v]$SC[v];[v][1:v]overlay=0:0:enable='gte(t,0.2)',format=yuv420p" $ENC n_u4.mp4
# u5: ekran aplikacji (bez zmian), z ciszą jeśli plik nie ma ścieżki audio
ffmpeg -y -v error -i "$K/podglady/u5_ekran_komputerku_1080x1920.mp4" -f lavfi -i anullsrc=r=48000:cl=stereo \
  -map 0:v -map 1:a -shortest -vf "$SC,format=yuv420p" $ENC n_u5.mp4
ffmpeg -y -v error -loop 1 -t 3 -i "$K/pakiet/03_plansze_video/9x16/OUTRO_komputerku.png" -f lavfi -t 3 -i anullsrc=r=48000:cl=stereo \
  -vf "scale=720:1280,fps=25,format=yuv420p" $ENC -shortest n_outro.mp4
printf "file 'n_%s.mp4'\n" u1 u2 u3 u4 u5 outro > lista.txt
ffmpeg -y -v error -f concat -safe 0 -i lista.txt -c copy surowa.mp4
DO=$(python3 -c "import subprocess as sp;print(round(sum(float(sp.check_output(['ffprobe','-v','error','-show_entries','format=duration','-of','csv=p=0',f'n_u{i}.mp4']).decode()) for i in range(1,5)),3))")
ffmpeg -y -v error -i surowa.mp4 -i "$W/warstwa_logo_ai.png" -stream_loop -1 -i "$K/glosy_v2/zrodla/ambience_kancelaria_22s.mp3" -filter_complex \
  "[0:v][1:v]overlay=0:0:enable='lt(t,$DO)',format=yuv420p[v];[2:a]atrim=0:$DO,volume=0.55,afade=t=in:d=0.3,afade=t=out:st=$(python3 -c "print($DO-0.6)"):d=0.6,aformat=sample_rates=48000:channel_layouts=stereo[amb];[0:a][amb]amix=inputs=2:duration=first:normalize=0,loudnorm=I=-16:TP=-1.5:LRA=11[a]" \
  -map "[v]" -map "[a]" -c:v libx264 -preset medium -crf 20 -c:a aac -ar 48000 -b:a 160k -movflags +faststart "$K/podglady/odc1_podglad_v3.mp4"
ffprobe -v error -show_entries format=duration -of csv=p=0 "$K/podglady/odc1_podglad_v3.mp4"
