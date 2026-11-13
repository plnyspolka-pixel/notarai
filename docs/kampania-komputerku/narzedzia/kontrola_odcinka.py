#!/usr/bin/env python3
"""Automatyczna kontrola dźwięku odcinka (lista kontrolna C2, C3, C5).
Użycie: python3 kontrola_odcinka.py <plik.mp4> [--pauzy 61.5-63.0,170-172] [--sfx plik1.mp3 plik2.mp3 ...]
- Zgłasza każdy odcinek < -38 LUFS (głośność chwilowa) dłuższy niż 1,5 s, poza podanymi zamierzonymi pauzami
  i ostatnimi 1,5 s (wyciszenie końca).
- Dla podanych efektów zgłasza stały szum tła (najcichsze okno 50 ms > -60 dB), który po podbiciu będzie słychać.
Kod wyjścia 1, gdy coś znalazł."""
import re, subprocess, sys
args = sys.argv[1:]
if not args: sys.exit(__doc__)
plik = args[0]; pauzy = []; sfx = []
if '--pauzy' in args:
    for z in args[args.index('--pauzy') + 1].split(','):
        a, b = z.split('-'); pauzy.append((float(a), float(b)))
if '--sfx' in args:
    sfx = [a for a in args[args.index('--sfx') + 1:] if not a.startswith('--')]
log = subprocess.run(['ffmpeg', '-nostdin', '-nostats', '-i', plik, '-af', 'ebur128', '-f', 'null', '-'], capture_output=True, text=True).stderr
pomiary = [(float(t), float(m)) for t, m in re.findall(r't:\s*([\d.]+)\s+TARGET.*?M:\s*(-?[\d.]+|-inf)', log.replace('-inf', '-120'))]
dl = pomiary[-1][0] if pomiary else 0
bledy = []; start = None
for t, m in pomiary:
    cicho = m < -38 and not any(a <= t <= b for a, b in pauzy) and t < dl - 1.5
    if cicho and start is None: start = t
    if not cicho and start is not None:
        if t - start > 1.5: bledy.append(f'cisza {start:.1f}-{t:.1f} s ({t - start:.1f} s)')
        start = None
if start is not None and dl - start > 1.5: bledy.append(f'cisza {start:.1f}-{dl:.1f} s')
for f in sfx:
    # stały szum tła = najcichsze okno 50 ms wciąż głośne (długopis z odc. 01: -55 dB; czyste efekty: ok. -68 dB)
    s = subprocess.run(['ffmpeg', '-nostdin', '-i', f, '-af', 'astats=length=0.05', '-f', 'null', '-'], capture_output=True, text=True).stderr
    m = re.findall(r'RMS trough dB:\s*(-?[\d.]+)', s)
    if m and float(m[-1]) > -60: bledy.append(f'szum tła w efekcie {f}: najcichsze okno {m[-1]} dB (> -60)')
print(f'{plik}: {dl:.1f} s, ' + ('OK' if not bledy else f'{len(bledy)} uwag'))
for b in bledy: print('  -', b)
sys.exit(1 if bledy else 0)
