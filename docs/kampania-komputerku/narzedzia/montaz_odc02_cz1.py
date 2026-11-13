#!/usr/bin/env python3
"""Montaż odc. 02, część 1: W poprzednim odcinku → trzęsienie ziemi („Wszystko stoi”) → intro 5 → sc. 01 („Kawy, panie Pawle?”).
Wynik: podglady/odc02_czesc1.mp4 (1080x1920, 30 kl./s). Zasady: produkcja-odc02/LISTA_KONTROLNA.md."""
import os, subprocess, tempfile
K = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
P1 = f'{K}/produkcja-odc01'; P2 = f'{K}/produkcja-odc02'; V = f'{P2}/cz1_wideo'; WL = f'{P1}/czesc1_wideo/warstwy'
LOGO = f'{K}/narzedzia/warstwy/warstwa_logo_ai.png'; INTRO = f'{K}/intro/INTRO_5_komputerku_9x16_odc02.mp4'
T = tempfile.mkdtemp(dir=os.environ.get('TMPDIR')); ENC = '-c:v libx264 -preset medium -crf 18 -pix_fmt yuv420p -r 30'.split()
def sh(*a): subprocess.run(a, check=True)
def dl(f): return float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', f], capture_output=True, text=True).stdout)
def kadr(z=1.0, fx=0.5, fy=0.5):
    if z == 1.0: return 'scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps=30,setsar=1'
    return (f"crop=iw/{z}:ih/{z}:'max(0,min(iw-iw/{z},iw*{fx}-iw/{z}/2))':'max(0,min(ih-ih/{z},ih*{fy}-ih/{z}/2))',"
            'scale=1080:1920,fps=30,setsar=1')
IRENA = kadr(1.4, 0.68, 0.38)   # bez postaci z lewej krawędzi kadru
PAWEL = kadr(1.5, 0.45, 0.32)   # twarz, bez koszulki z dokumentem z odc. 01
# (źródło, ss, t, logo, warstwa, w_od, w_do, kadr)
UJ = [
 # W poprzednim odcinku
 (f'{P1}/czesc1_wideo/t2_pawel.mp4', 0.5, 1.6, True, 'pop_naglowek.png', 0.0, 8.0, None),
 (f'{P1}/czesc4_wideo/G3_wybor_brak.mp4', 1.0, 1.6, False, 'pop_naglowek.png', 0.0, 8.0, None),
 (f'{P1}/czesc4_wideo/s11_helena_2.mp4', 1.8, 3.2, True, None, 0, 0, None),
 (f'{P1}/czesc4_wideo/s12_basia_2.mp4', 3.7, 1.6, True, None, 0, 0, None),
 (f'{P1}/czesc4_wideo/b13_dlugopis.mp4', 1.2, 1.5, True, None, 0, 0, None),
 ('CZERN', 0, 0.4, False, None, 0, 0, None),
 # trzęsienie ziemi: wtorek 10:12
 (f'{V}/t_pawel_telefon.mp4', 0, None, True, 'czas_wt_1012.png', 0.2, 2.4, None),
 (f'{V}/b1_drzwi.mp4', 1.5, 3.0, True, None, 0, 0, None),
 # intro
 ('INTRO', 0, None, False, None, 0, 0, None),
 # sc. 01: recepcja, dwie minuty wcześniej
 (f'{V}/s01_basia_1.mp4', 0, None, True, 'czas_dwie_min.png', 0.1, 2.2, None),
 (f'{V}/s01_basia_2.mp4', 0, None, True, None, 0, 0, None),
 (f'{V}/s01_pawel.mp4', 0.2, 1.9, True, None, 0, 0, PAWEL),
 (f'{V}/s01_irena_lada.mp4', 0, None, True, 'karta_irena.png', 0.1, 2.8, IRENA),
 (f'{P1}/zapowiedz_odc02/pawel_czeka.mp4', 0.3, 2.4, True, None, 0, 0, None),
]
start = []; t = 0; lista = []
for i, (f, ss, d, logo, w, a, b, kd) in enumerate(UJ):
    if d is None:
        d = round(dl(INTRO if f == 'INTRO' else f) - ss - 0.05, 2); UJ[i] = (f, ss, d, logo, w, a, b, kd)
    start.append(t); t += d; out = f'{T}/v{i:02d}.mp4'
    if f == 'CZERN':
        inp = ['-f', 'lavfi', '-t', str(d), '-i', 'color=c=black:s=1080x1920:r=30']; fc = '[0:v]setsar=1[v0]'
    elif f == 'INTRO':
        inp = ['-i', INTRO]; fc = f'[0:v]{kadr()}[v0]'
    else:
        inp = ['-ss', str(ss), '-t', str(d), '-i', f]; fc = f'[0:v]{kd or kadr()}[v0]'
    last = 'v0'; k = 1
    if logo: inp += ['-i', LOGO]; fc += f';[{k}:v]scale=1080:1920[l];[{last}][l]overlay=0:0[v1]'; last = 'v1'; k += 1
    if w: inp += ['-loop', '1', '-t', str(d), '-i', f'{WL}/{w}']; fc += f";[{k}:v]format=rgba,fade=t=in:st={a}:d=0.3:alpha=1{f',fade=t=out:st={b}:d=0.3:alpha=1' if b < 7 else ''}[w];[{last}][w]overlay=0:0[v2]"; last = 'v2'
    sh('ffmpeg', '-nostdin', '-v', 'error', '-y', *inp, '-filter_complex', fc, '-map', f'[{last}]', '-an', '-t', str(d), *ENC, out); lista.append(out)
DL = t
open(f'{T}/l.txt', 'w').write(''.join(f"file '{x}'\n" for x in lista))
sh('ffmpeg', '-nostdin', '-v', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', f'{T}/l.txt', '-c', 'copy', f'{T}/obraz.mp4')
TZ, IN, S1 = start[6], start[8], start[9]
AMB = f'{P1}/czesc3_wideo/amb_recepcja_n.mp3'; MUZ = f'{P1}/czesc4_wideo/muz_intryga.mp3'
# (start, plik, ss, t, głośność)
DZ = [
 (0, MUZ, 0, TZ, 0.5),                                                     # pod „W poprzednim odcinku”
 (start[2], UJ[2][0], 1.8, 3.2, 1.5),                                      # Helena: „…Dokumentów nie uzupełnia się domysłami.”
 (start[3], UJ[3][0], 3.7, 1.6, 1.6),                                      # Basia: „…bez syna.”
 (start[4] + 1.0, f'{P1}/czesc4_wideo/sfx_dlugopis.mp3', 1.27, 0.25, 2.2),  # tylko klik pióra
 (TZ, f'{V}/t_pawel_telefon.mp4', 0, UJ[6][2], 1.5),
 (start[7] + 1.9, f'{P1}/czesc1_wideo/sfx_drzwi.mp3', 0, 1.2, 0.7),         # drzwi gabinetu się zamykają
 (TZ, AMB, 0, IN - TZ + 0.3, 0.8),
 (IN, INTRO, 0, dl(INTRO), 1.0),
 (S1, f'{V}/s01_basia_1.mp4', 0, UJ[9][2], 1.5),
 (start[10], f'{V}/s01_basia_2.mp4', 0, UJ[10][2], 1.5),
 (start[11], f'{V}/s01_pawel.mp4', 0.2, 1.9, 1.5),
 (start[12], f'{V}/s01_irena_lada.mp4', 0, UJ[12][2], 1.5),
 (S1, AMB, 12, DL - S1, 0.9),
]
inp = ['-i', f'{T}/obraz.mp4']; fc = []
for i, (st, f, ss, d, g) in enumerate(DZ, 1):
    tlo = 'amb_' in f or 'muz_' in f
    inp += (['-stream_loop', '-1'] if 'amb_' in f else []) + ['-i', f]; ms = int(st * 1000)
    fade = f',afade=t=in:d=0.3,afade=t=out:st={d - 0.5:.2f}:d=0.5' if tlo else ''
    fc.append(f'[{i}:a]atrim={ss}:{ss + d},asetpts=PTS-STARTPTS{fade},volume={g},aformat=sample_rates=48000:channel_layouts=stereo,adelay={ms}|{ms}[a{i}]')
fc.append(''.join(f'[a{i}]' for i in range(1, len(DZ) + 1)) + f'amix=inputs={len(DZ)}:duration=longest:normalize=0,apad,atrim=0:{DL},loudnorm=I=-16:TP=-1.5:LRA=11[a]')
wyj = f'{K}/podglady/odc02_czesc1.mp4'
sh('ffmpeg', '-nostdin', '-v', 'error', '-y', *inp, '-filter_complex', ';'.join(fc), '-map', '0:v', '-map', '[a]', '-c:v', 'copy', '-c:a', 'aac', '-ar', '48000', '-b:a', '192k', '-movflags', '+faststart', '-t', str(DL), wyj)
print(f'{wyj}  {DL:.2f} s, trzęsienie od {TZ:.2f} s, intro od {IN:.2f} s, sc. 01 od {S1:.2f} s')
