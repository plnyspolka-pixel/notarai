#!/usr/bin/env python3
"""Montaż odc. 02, część 2: sc. 02 „Ja chcę sprzedać” (gabinet Heleny). Największa pauza odcinka: po „…że to na nic”
zbliżenie odkładanych okularów, dopiero potem odpowiedź Heleny (już bez okularów). Wynik: podglady/odc02_czesc2.mp4 (1080x1920, 30 kl./s). Zasady: produkcja-odc02/LISTA_KONTROLNA.md."""
import os, subprocess, tempfile
K = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
P1 = f'{K}/produkcja-odc01'; P2 = f'{K}/produkcja-odc02'; V = f'{P2}/cz2_wideo'; WL = f'{P1}/czesc1_wideo/warstwy'
LOGO = f'{K}/narzedzia/warstwy/warstwa_logo_ai.png'; INTRO = f'{K}/intro/INTRO_5_komputerku_9x16_odc02.mp4'
T = tempfile.mkdtemp(dir=os.environ.get('TMPDIR')); ENC = '-c:v libx264 -preset medium -crf 18 -pix_fmt yuv420p -r 30'.split()
def sh(*a): subprocess.run(a, check=True)
def dl(f): return float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', f], capture_output=True, text=True).stdout)
def kadr(z=1.0, fx=0.5, fy=0.5):
    if z == 1.0: return 'scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps=30,setsar=1'
    return (f"crop=iw/{z}:ih/{z}:'max(0,min(iw-iw/{z},iw*{fx}-iw/{z}/2))':'max(0,min(ih-ih/{z},ih*{fy}-ih/{z}/2))',"
            'scale=1080:1920,fps=30,setsar=1')
UJ = [
 (f'{V}/s02_helena_1.mp4', 0, None, True, None, 0, 0, None),
 (f'{V}/s02_irena_1.mp4', 0, None, True, None, 0, 0, None),
 (f'{V}/s02_helena_2.mp4', 0, None, True, None, 0, 0, None),
 (f'{V}/s02_irena_2.mp4', 0, None, True, None, 0, 0, None),
 (f'{V}/s02_helena_3.mp4', 0, None, True, None, 0, 0, None),
 (f'{V}/s02_irena_3.mp4', 0, None, True, None, 0, 0, None),
 (f'{V}/b2_okulary.mp4', 0.3, 3.2, True, None, 0, 0, None),
 (f'{V}/s02_helena_4.mp4', 0, None, True, None, 0, 0, None),
 (f'{V}/s02_irena_4.mp4', 0, None, True, None, 0, 0, None),
]
start = []; t = 0; lista = []
for i, (f, ss, d, logo, w, a, b, kd) in enumerate(UJ):
    if d is None:
        d = round(dl(f) - ss - 0.05, 2); UJ[i] = (f, ss, d, logo, w, a, b, kd)
    d = round(d * 30) / 30; start.append(t); t += d; out = f'{T}/v{i:02d}.mp4'
    inp = ['-ss', str(ss), '-t', str(d), '-i', f]; fc = f'[0:v]{kd or kadr()}[v0]'
    last = 'v0'; k = 1
    if logo: inp += ['-i', LOGO]; fc += f';[{k}:v]scale=1080:1920[l];[{last}][l]overlay=0:0[v1]'; last = 'v1'; k += 1
    sh('ffmpeg', '-nostdin', '-v', 'error', '-y', *inp, '-filter_complex', fc, '-map', f'[{last}]', '-an', '-t', str(d), *ENC, out); lista.append(out)
DL = t
open(f'{T}/l.txt', 'w').write(''.join(f"file '{x}'\n" for x in lista))
sh('ffmpeg', '-nostdin', '-v', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', f'{T}/l.txt', '-c', 'copy', f'{T}/obraz.mp4')
AMB = f'{P1}/czesc4_wideo/amb_gabinet.mp3'; MUZ = f'{P1}/czesc4_wideo/muz_intryga.mp3'
OK = start[6]
DZ = [(start[i], UJ[i][0], 0, UJ[i][2], 1.5) for i in (0, 1, 2, 3, 4, 5, 7, 8)]
DZ += [
 (0, AMB, 0, DL, 0.7),
 (OK - 3.0, MUZ, 0, start[8] - OK + 3.0, 0.35),                              # muzyka od wyznania Ireny przez pauzę
 (OK + 1.6, f'{P1}/czesc4_wideo/sfx_dlugopis.mp3', 1.27, 0.25, 1.4),          # ciche stuknięcie okularów o papier
]
inp = ['-i', f'{T}/obraz.mp4']; fc = []
for i, (st, f, ss, d, g) in enumerate(DZ, 1):
    tlo = 'amb_' in f or 'muz_' in f
    inp += (['-stream_loop', '-1'] if 'amb_' in f else []) + ['-i', f]; ms = int(st * 1000)
    fade = f',afade=t=in:d=0.6,afade=t=out:st={d - 0.8:.2f}:d=0.8' if tlo else ''
    fc.append(f'[{i}:a]atrim={ss}:{ss + d},asetpts=PTS-STARTPTS{fade},volume={g},aformat=sample_rates=48000:channel_layouts=stereo,adelay={ms}|{ms}[a{i}]')
fc.append(''.join(f'[a{i}]' for i in range(1, len(DZ) + 1)) + f'amix=inputs={len(DZ)}:duration=longest:normalize=0,apad,atrim=0:{DL},loudnorm=I=-16:TP=-1.5:LRA=11[a]')
wyj = f'{K}/podglady/odc02_czesc2.mp4'
sh('ffmpeg', '-nostdin', '-v', 'error', '-y', *inp, '-filter_complex', ';'.join(fc), '-map', '0:v', '-map', '[a]', '-c:v', 'copy', '-c:a', 'aac', '-ar', '48000', '-b:a', '192k', '-movflags', '+faststart', '-t', str(DL), wyj)
print(f'{wyj}  {DL:.2f} s, okulary od {OK:.2f} s')
