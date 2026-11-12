#!/usr/bin/env python3
"""Montaż odc. 01, część 3: sceny 06–09. Wynik: podglady/odc01_czesc3.mp4 (1080x1920, 30 kl./s).
Tempo: sc. 06–07 rozmowa (gwar recepcji), sc. 08 montaż zwalnia i gwar cichnie (zasada pauz z KANON_ODC01.md),
sc. 09 spokojny montaż równoległy w trakcie sporządzania projektu, na końcu przeskok 8:57 → 9:24.
Ujęcia sc. 09 bez ruchu to kadry z powolnym najazdem (do wymiany na klipy Kling, gdy będą środki na fal)."""
import os, subprocess, tempfile
K = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
P = f'{K}/produkcja-odc01'; V3 = f'{P}/czesc3_wideo'; V1 = f'{P}/czesc1_wideo'; KA = f'{P}/czesc3_kadry'; WL = f'{V1}/warstwy'
LOGO = f'{K}/narzedzia/warstwy/warstwa_logo_ai.png'
T = tempfile.mkdtemp(dir=os.environ.get('TMPDIR')); ENC = '-c:v libx264 -preset medium -crf 18 -pix_fmt yuv420p -r 30'.split()
def sh(*a): subprocess.run(a, check=True)
def kadr(z=1.0, fx=0.5, fy=0.5):
    # zbliżenie z, środek kadru (fx, fy) jako ułamek szerokości/wysokości, przycięte do krawędzi
    if z == 1.0: return 'scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps=30,setsar=1'
    return (f"crop=iw/{z}:ih/{z}:'max(0,min(iw-iw/{z},iw*{fx}-iw/{z}/2))':'max(0,min(ih-ih/{z},ih*{fy}-ih/{z}/2))',"
            'scale=1080:1920,fps=30,setsar=1')
# (źródło, ss, t, logo, warstwa, w_od, w_do, kadr)  źródło .png = kadr z powolnym najazdem
KUBA, MARTA, HELENA = kadr(1.45, 0.6, 0.36), kadr(1.45, 0.6, 0.40), kadr(1.5, 0.46, 0.33)
UJ = [
 # sc. 06 „Co jeszcze zostało?”
 ('s06_kuba_1.mp4', 0, 1.56, True, None, 0, 0, KUBA),
 ('s06_marta_1.mp4', 0, 4.76, True, None, 0, 0, MARTA),
 ('F1_weryfikacja.mp4', 0, 2.4, False, None, 0, 0, None),
 ('F2_wymagaja_uwagi.mp4', 0, 3.0, False, None, 0, 0, None),
 ('s06_marta_2.mp4', 2.7, 1.82, True, None, 0, 0, MARTA),
 ('s06_kuba_2.mp4', 0, 1.16, True, None, 0, 0, KUBA),
 # sc. 07 „Pani rejent chce to dzisiaj”
 ('s07_helena_1.mp4', 0, 5.72, True, 'karta_helena.png', 0.3, 2.6, HELENA),
 ('s07_marta.mp4', 0, 3.8, True, None, 0, 0, MARTA),
 ('s07_helena_2.mp4', 0, None, True, None, 0, 0, HELENA),
 ('b8_usmiechy.mp4', 1.0, 2.0, True, None, 0, 0, None),
 # sc. 08 „Komputerku…”: zwolnienie, krótka cisza przed kwestią
 ('s08_marta.mp4', 0, None, True, None, 0, 0, MARTA),
 ('F3_sporzadz.mp4', 0, 1.8, False, None, 0, 0, None),
 ('F4_sporzadzam.mp4', 0, 2.4, False, None, 0, 0, None),
 # sc. 09 „Kancelaria nie przestaje pracować”: każda rozmowa słyszalna, bez zmyślonych szczegółów
 ('s09_basia.mp4', 0, 3.1, True, None, 0, 0, None),
 ('F5_kalendarz.mp4', 0, 2.3, False, None, 0, 0, None),
 ('s09_basia.mp4', 6.45, 3.05, True, None, 0, 0, None),
 ('s09_kuba.mp4', 0, None, True, None, 0, 0, None),
 ('b10_marta_dok.mp4', 1.0, 1.6, True, None, 0, 0, None),
 ('s09_helena.mp4', 0, None, True, None, 0, 0, None),
 (f'{KA}/b8_marta_kuba_1.jpg', 0, 2.6, True, 'czas_0924.png', 0.7, 2.4, None),
]
def dl(f):
    return float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', f], capture_output=True, text=True).stdout)
start = []; t = 0; lista = []
for i, (f, ss, d, logo, w, a, b, kd) in enumerate(UJ):
    src = f if f.startswith('/') else f'{V3}/{f}'
    if d is None: d = round(dl(src) - ss - 0.05, 2)
    UJ[i] = (f, ss, d, logo, w, a, b, kd); start.append(t); t += d; out = f'{T}/v{i:02d}.mp4'
    if src.endswith(('.png', '.jpg')):
        n = int(d * 30)
        inp = ['-loop', '1', '-t', str(d), '-i', src]
        fc = (f"[0:v]scale=1620:2880,zoompan=z='1.0+0.07*on/{n}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s=1080x1920:fps=30,setsar=1[v0]")
    else:
        inp = ['-ss', str(ss), '-t', str(d), '-i', src]; fc = f'[0:v]{kd or kadr()}[v0]'
    last = 'v0'; k = 1
    if logo: inp += ['-i', LOGO]; fc += f';[{k}:v]scale=1080:1920[l];[{last}][l]overlay=0:0[v1]'; last = 'v1'; k += 1
    if w: inp += ['-loop', '1', '-t', str(d), '-i', f'{WL}/{w}']; fc += f';[{k}:v]format=rgba,fade=t=in:st={a}:d=0.25:alpha=1,fade=t=out:st={b}:d=0.2:alpha=1[w];[{last}][w]overlay=0:0[v2]'; last = 'v2'
    sh('ffmpeg', '-v', 'error', '-y', *inp, '-filter_complex', fc, '-map', f'[{last}]', '-an', '-t', str(d), *ENC, out); lista.append(out)
DL = t
open(f'{T}/l.txt', 'w').write(''.join(f"file '{x}'\n" for x in lista))
sh('ffmpeg', '-v', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', f'{T}/l.txt', '-c', 'copy', f'{T}/obraz.mp4')
S8, S9 = start[9], start[13]
A = f'{V3}/audio'
# (start, plik, ss, t, głośność, [zanik_na_końcu])
DZ = [
 (start[0], f'{V3}/s06_kuba_1.mp4', 0, 1.56, 1.5),
 (start[1], f'{V3}/s06_marta_1.mp4', 0, 4.76, 1.5),
 (start[2] + 1.7, f'{P}/czesc2_wideo/sfx_tap.mp3', 0, 0.5, 0.8),
 (start[3] + 0.3, f'{A}/odc01_s06_marta_2.mp3', 0, 4.68, 1.5),
 (start[5], f'{V3}/s06_kuba_2.mp4', 0, 1.16, 1.5),
 (start[6], f'{V3}/s07_helena_1.mp4', 0, 5.72, 1.5),
 (start[7], f'{V3}/s07_marta.mp4', 0, 3.8, 1.5),
 (start[8], f'{V3}/s07_helena_2.mp4', 0, UJ[8][2], 1.5),
 (start[10], f'{V3}/s08_marta.mp4', 0, UJ[10][2], 1.5),
 (start[11] + 1.1, f'{V3}/sfx_klik.mp3', 0, 0.5, 1.0),
 (S9 - 0.8, f'{V1}/sfx_telefon.mp3', 0, 1.0, 0.5),
 (start[13], f'{A}/odc01_s09_basia.mp3', 0, 5.4, 1.5),
 (start[15], f'{A}/odc01_s09_basia.mp3', 6.45, 3.05, 1.5),
 (start[16], f'{V3}/s09_kuba.mp4', 0, UJ[16][2], 1.5),
 (start[18], f'{V3}/s09_helena.mp4', 0, UJ[18][2], 1.3),
 (start[19] + 0.3, f'{V3}/sfx_zegar.mp3', 0, 2.3, 0.9),
 (0, f'{V3}/amb_recepcja_n.mp3', 0, S8 + 0.4, 0.9),
 (S8, f'{V3}/amb_recepcja_n.mp3', 5, S9 - S8 + 0.4, 0.75),
 (S9 - 0.2, f'{V3}/amb_recepcja_n.mp3', 15, DL - S9 + 0.2, 0.55),
 (S9 - 0.2, f'{V3}/amb_biuro_petla.mp3', 0, DL - S9 + 0.2, 0.8),
]
inp = ['-i', f'{T}/obraz.mp4']; fc = []
for i, (st, f, ss, d, g) in enumerate(DZ, 1):
    amb = 'amb_' in f
    inp += (['-stream_loop', '-1'] if amb else []) + ['-i', f]; ms = int(st * 1000)
    fade = f',afade=t=in:d=0.3,afade=t=out:st={d - 0.4:.2f}:d=0.4' if amb else ''
    fc.append(f'[{i}:a]atrim={ss}:{ss + d},asetpts=PTS-STARTPTS{fade},volume={g},aformat=sample_rates=48000:channel_layouts=stereo,adelay={ms}|{ms}[a{i}]')
fc.append(''.join(f'[a{i}]' for i in range(1, len(DZ) + 1)) + f'amix=inputs={len(DZ)}:duration=longest:normalize=0,atrim=0:{DL},loudnorm=I=-16:TP=-1.5:LRA=11[a]')
wyj = f'{K}/podglady/odc01_czesc3.mp4'
sh('ffmpeg', '-v', 'error', '-y', *inp, '-filter_complex', ';'.join(fc), '-map', '0:v', '-map', '[a]', '-c:v', 'copy', '-c:a', 'aac', '-ar', '48000', '-b:a', '192k', '-movflags', '+faststart', '-t', str(DL), wyj)
print(f'{wyj}  {DL:.2f} s, sc. 08 od {S8:.2f} s, sc. 09 od {S9:.2f} s')
