#!/usr/bin/env python3
"""Montaż odc. 01, część 2: sceny 03–05. Wynik: podglady/odc01_czesc2.mp4 (1080x1920, 30 kl./s).
Oś czasu: lista ujęć (obraz) + zdarzenia dźwiękowe w czasie bezwzględnym. Pauza strategiczna na końcu:
po kwestii Basi gwar cichnie do ciszy pokoju, ~0,9 s nic, potem dzwoni telefon (zasada pauz z KANON_ODC01.md)."""
import os, subprocess, sys, tempfile
K = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
V2 = f'{K}/produkcja-odc01/czesc2_wideo'; V1 = f'{K}/produkcja-odc01/czesc1_wideo'; WL = f'{V1}/warstwy'
LOGO = f'{K}/narzedzia/warstwy/warstwa_logo_ai.png'
T = tempfile.mkdtemp(dir=os.environ.get('TMPDIR')); ENC = '-c:v libx264 -preset medium -crf 18 -pix_fmt yuv420p -r 30'.split()
SC = 'scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps=30,setsar=1'
def sh(*a): subprocess.run(a, check=True)
# (plik, ss, t, logo, warstwa, w_od, w_do)
UJ = [
 ('t5_marta_podchodzi.mp4', 0.5, 1.8, True, None, 0, 0),
 ('s03_basia.mp4', 0, 1.4, True, None, 0, 0),
 ('E1_kalendarz.mp4', 0, 2.8, False, None, 0, 0),
 ('s03_basia.mp4', 4.2, 1.92, True, None, 0, 0),
 ('E2_sprawa.mp4', 0, 2.6, False, None, 0, 0),
 ('s04_pawel.mp4', 0, 1.9, True, None, 0, 0),
 ('s04_basia.mp4', 0, 3.4, True, None, 0, 0),
 ('b7_kuba_czeka.mp4', 0.5, 1.6, True, 'karta_kuba.png', 0.1, 1.3),
 ('E3_tel_sprawa.mp4', 0, 1.6, False, None, 0, 0),
 ('b6_zdjecie.mp4', 1.0, 2.0, True, None, 0, 0),
 ('E4_tel_aparatem.mp4', 0, 1.4, False, None, 0, 0),
 ('E5_tel_migawka.mp4', 0, 1.5, False, None, 0, 0),
 ('E6_tel_wyslij.mp4', 0, 1.4, False, None, 0, 0),
 ('E7_tel_zdjecie.mp4', 0, 1.6, False, None, 0, 0),
 ('E8_marta_puste.mp4', 0, 1.0, False, None, 0, 0),
 ('E9_marta_zdjecie.mp4', 0, 2.0, False, None, 0, 0),
 ('s05_marta.mp4', 0, 2.04, True, None, 0, 0),
 ('s05_basia.mp4', 0, 4.6, True, None, 0, 0),
 (f'{V1}/b2_telefon.mp4', 0.5, 1.9, True, None, 0, 0),
]
start = []; t = 0; lista = []
for i, (f, ss, d, logo, w, a, b) in enumerate(UJ):
    start.append(t); t += d; src = f if f.startswith('/') else f'{V2}/{f}'; out = f'{T}/v{i:02d}.mp4'
    inp = ['-ss', str(ss), '-t', str(d), '-i', src]; fc = f'[0:v]{SC}[v0]'; last = 'v0'; n = 1
    if logo: inp += ['-i', LOGO]; fc += f';[{n}:v]scale=1080:1920[l];[{last}][l]overlay=0:0[v1]'; last = 'v1'; n += 1
    if w: inp += ['-loop', '1', '-t', str(d), '-i', f'{WL}/{w}']; fc += f';[{n}:v]format=rgba,fade=t=in:st={a}:d=0.2:alpha=1,fade=t=out:st={b}:d=0.2:alpha=1[w];[{last}][w]overlay=0:0[v2]'; last = 'v2'
    sh('ffmpeg', '-v', 'error', '-y', *inp, '-filter_complex', fc, '-map', f'[{last}]', '-an', *ENC, out); lista.append(out)
DL = t
open(f'{T}/l.txt', 'w').write(''.join(f"file '{x}'\n" for x in lista))
sh('ffmpeg', '-v', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', f'{T}/l.txt', '-c', 'copy', f'{T}/obraz.mp4')
P = start[18]  # początek pauzy
# (start, plik, ss, t, głośność)
DZ = [
 (start[1], f'{V2}/s03_basia.mp4', 0, 6.12, 1.5),
 (start[4] + 0.4, f'{V2}/s03_marta_vo.mp3', 0, 2.2, 1.5),
 (start[5], f'{V2}/s04_pawel.mp4', 0, 1.9, 1.5),
 (start[6], f'{V2}/s04_basia.mp4', 0, 4.68, 1.5),
 (start[10] + 0.8, f'{V2}/sfx_tap.mp3', 0, 0.5, 0.8),
 (start[11] + 0.9, f'{V2}/sfx_migawka.mp3', 0, 0.6, 0.9),
 (start[12] + 0.8, f'{V2}/sfx_tap.mp3', 0, 0.5, 0.8),
 (start[16], f'{V2}/s05_marta.mp4', 0, 2.04, 1.5),
 (start[17], f'{V2}/s05_basia.mp4', 0, 4.6, 1.5),
 (P + 0.9, f'{V1}/sfx_telefon.mp3', 0, 1.0, 1.0),
 (0, f'{K}/produkcja-odc01/czesc3_wideo/amb_recepcja_n.mp3', 0, P, 0.85),
]
inp = ['-i', f'{T}/obraz.mp4']; fc = []
for i, (st, f, ss, d, g) in enumerate(DZ, 1):
    inp += (['-stream_loop', '-1'] if f.endswith('amb_recepcja_n.mp3') else []) + ['-i', f]; ms = int(st * 1000)
    fade = f',afade=t=out:st={d - 0.35}:d=0.35' if f.endswith('amb_recepcja_n.mp3') else ''
    fc.append(f'[{i}:a]atrim={ss}:{ss + d},asetpts=PTS-STARTPTS{fade},volume={g},aformat=sample_rates=48000:channel_layouts=stereo,adelay={ms}|{ms}[a{i}]')
fc.append(''.join(f'[a{i}]' for i in range(1, len(DZ) + 1)) + f'amix=inputs={len(DZ)}:duration=longest:normalize=0,atrim=0:{DL},loudnorm=I=-16:TP=-1.5:LRA=11[a]')
wyj = f'{K}/podglady/odc01_czesc2.mp4'
sh('ffmpeg', '-v', 'error', '-y', *inp, '-filter_complex', ';'.join(fc), '-map', '0:v', '-map', '[a]', '-c:v', 'copy', '-c:a', 'aac', '-ar', '48000', '-b:a', '192k', '-movflags', '+faststart', '-t', str(DL), wyj)
print(f'{wyj}  {DL:.2f} s, pauza od {P:.2f} s')
