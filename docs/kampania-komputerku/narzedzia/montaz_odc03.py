#!/usr/bin/env python3
"""Montaż odc. 03 „U nas się tak nie pisze”: W poprzednim odcinku → trzęsienie ziemi (kartka z § 5, „U nas się tak nie pisze”) → intro
→ sc. 01 (biurko Marty, 11:02) → sc. 02 (gabinet: „w/w”, własność przy akcie) → sc. 03 (zasady kancelarii, poprawka § 5, projekt v2)
→ sc. 04 („Nie synowi”) → zapowiedź odc. 04 → outro. Wynik: podglady/ODC03_U_nas_sie_tak_nie_pisze.mp4 (CRF 23, < 100 MB).
Zasady: produkcja-odc02/LISTA_KONTROLNA.md — długości ujęć z plików (C7), tła znormalizowane (C2), muzyka pod planszami (C5)."""
import os, subprocess, tempfile
K = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
P1, P2, P3 = f'{K}/produkcja-odc01', f'{K}/produkcja-odc02', f'{K}/produkcja-odc03'
V, E, KD, A = f'{P3}/wideo', f'{P3}/wideo_ekrany', f'{P3}/kadry', f'{P3}/audio'
WL = f'{P1}/czesc1_wideo/warstwy'; LOGO = f'{K}/narzedzia/warstwy/warstwa_logo_ai.png'
INTRO = f'{K}/intro/INTRO_5_komputerku_9x16_odc03.mp4'; OUTRO = f'{K}/intro/OUTRO_siodemka_9x16.mp4'
T = tempfile.mkdtemp(dir=os.environ.get('TMPDIR')); ENC = '-c:v libx264 -preset medium -crf 18 -pix_fmt yuv420p -r 30'.split()
def sh(*a): subprocess.run(a, check=True)
def dl(f): return float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', f], capture_output=True, text=True).stdout)
def kadr(z=1.0, fx=0.5, fy=0.5):
    if z == 1.0: return 'scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps=30,setsar=1'
    return (f"crop=iw/{z}:ih/{z}:'max(0,min(iw-iw/{z},iw*{fx}-iw/{z}/2))':'max(0,min(ih-ih/{z},ih*{fy}-ih/{z}/2))',"
            'scale=1080:1920,fps=30,setsar=1')
KUBA, MARTA = kadr(1.45, 0.6, 0.36), kadr(1.45, 0.6, 0.40)
# najazd na obraz (kartka, kadr Kuby): (z0, z1, fx, fy)
KARTKA = (1.18, 1.26, 0.5, 0.27); KARTKA_W = (1.26, 1.34, 0.5, 0.27); KUBA_STOP = (1.0, 1.1, 0.5, 0.3)
def U(src, ss=0, t=None, logo=True, w=None, wa=0, wb=99, kd=None, glos=None, zoom=None):
    """glos: True = dźwięk z pliku ujęcia, albo (plik, ss, t) — mowa podłożona pod ujęcie (np. głos zza kadru)."""
    return dict(src=src, ss=ss, t=t, logo=logo, w=w, wa=wa, wb=wb, kd=kd, glos=glos, zoom=zoom)
H2 = f'{V}/sc02_helena2.mp4'; H2C = 2.2; H2K = 5.3          # Helena o własności: odcinek 2,2–5,3 s pod kartką z podkreśleniem
UJ = [
 # W poprzednim odcinku (odc. 02)
 U(f'{P2}/cz2_wideo/s02_irena_1.mp4', 0, 4.4, w='pop_naglowek.png', wb=3.2, glos=True),
 U(f'{P2}/cz2_wideo/s02_helena_4.mp4', 9.5, 2.75, glos=True),
 U(f'{P2}/cz3_wideo/basia_telefon_kadr.jpg', 0, None, glos=(f'{P2}/cz3_wideo/audio/odc02_s06_joanna_2_tel.mp3', 0, None)),
 U('CZERN', 0, 0.4, logo=False),
 # trzęsienie ziemi: kartka Kuby, długopis Heleny na „w/w”
 U(f'{KD}/kartka_a.png', 0, 1.4, zoom=KARTKA),
 U(f'{KD}/kartka_b.png', 0, 1.3, zoom=KARTKA_W),
 U(f'{V}/sc02_helena1.mp4', 0, 5.45, glos=True),
 U('CZERN', 0, 0.5, logo=False),
 U('INTRO', logo=False),
 # sc. 01: biurko Marty, wtorek 11:02
 U(f'{V}/sc01_marta.mp4', kd=MARTA, w='czas_wt_1102.png', wa=0.1, wb=2.4, glos=True),
 U(f'{V}/sc01_kuba.mp4', 0.2, kd=KUBA, glos=True),
 # sc. 02: gabinet
 U(f'{KD}/kartka_a.png', 0, 1.8, zoom=KARTKA),
 U(f'{V}/sc02_helena1.mp4', glos=True),
 U(H2, 0, H2C, glos=(H2, 0, None)),
 U(f'{KD}/kartka_c.png', 0, H2K - H2C, zoom=KARTKA_W),
 U(H2, H2K),
 U(f'{KD}/kartka_c.png', 0, None, zoom=(1.34, 1.4, 0.5, 0.27), glos=(f'{A}/odc03_sc02_kuba.mp3', 0, None)),
 U(f'{KD}/kuba_gabinet_crop.png', 0, 2.4, zoom=KUBA_STOP),          # największa pauza odcinka
 U(f'{V}/sc02_helena3.mp4', glos=True),
 # sc. 03: biurko Marty, NotarAI
 U(f'{E}/E1_zasady.mp4', logo=False),
 U(f'{V}/sc03_marta1.mp4', kd=MARTA, glos=True),
 U(f'{V}/sc03_marta2.mp4', kd=MARTA, glos=True),
 U(f'{V}/sc03_kuba.mp4', kd=KUBA, glos=True),
 U(f'{E}/E2_poprawka.mp4', logo=False),
 U(f'{E}/E3_sporzadz.mp4', logo=False),
 U(f'{E}/E4_par5_v2.mp4', logo=False),
 U(f'{V}/sc03_marta3.mp4', kd=MARTA, glos=True),
 # sc. 04: Basia w drzwiach gabinetu
 U(f'{V}/sc04_basia1.mp4', glos=True),
 U(f'{V}/sc04_helena.mp4', glos=True),
 U(f'{V}/sc04_basia2.mp4', 0.3, glos=True),
 U('CZERN', 0, 0.9, logo=False),
 # zapowiedź odc. 04
 U(f'{V}/zap_kuba.mp4', 0, kd=KUBA, w='zap_naglowek.png', wb=1.6, glos=True),
 U(f'{V}/zap_helena.mp4', 0, glos=True),
 U('CZERN', 0, 2.2, logo=False, w='zap_tytul_odc04.png', wa=0.0),
 U('OUTRO', 0, 7.4, logo=False, w='outro_napis.png', wa=4.3),
]
start = []; t = 0; lista = []
for i, u in enumerate(UJ):
    f = u['src']
    if u['t'] is None:
        if f.endswith(('.png', '.jpg')): u['t'] = round(dl(u['glos'][0]) + 0.35, 2)
        else: u['t'] = round(dl(INTRO if f == 'INTRO' else f) - u['ss'] - 0.05, 2)
    d = u['t']; start.append(t); t += d; out = f'{T}/v{i:02d}.mp4'
    if f == 'CZERN':
        inp = ['-f', 'lavfi', '-t', str(d), '-i', 'color=c=black:s=1080x1920:r=30']; fc = '[0:v]setsar=1[v0]'
    elif f == 'INTRO':
        inp = ['-i', INTRO]; fc = f'[0:v]{kadr()}[v0]'
    elif f == 'OUTRO':
        inp = ['-i', OUTRO]; fc = f'[0:v]tpad=stop_mode=clone:stop_duration={d - dl(OUTRO) + 0.1:.2f},fps=30,setsar=1[v0]'
    elif f.endswith(('.png', '.jpg')):
        z0, z1, fx, fy = u['zoom'] or (1.0, 1.06, 0.5, 0.5); n = int(d * 30)
        inp = ['-loop', '1', '-t', str(d), '-i', f]
        fc = (f"[0:v]scale=1620:2880:force_original_aspect_ratio=increase,crop=1620:2880,zoompan=z='{z0}+({z1}-{z0})*on/{n}'"
              f":x='max(0,min(iw-iw/zoom,iw*{fx}-iw/zoom/2))':y='max(0,min(ih-ih/zoom,ih*{fy}-ih/zoom/2))':d=1:s=1080x1920:fps=30,setsar=1[v0]")
    else:
        inp = ['-ss', str(u['ss']), '-t', str(d), '-i', f]; fc = f"[0:v]{u['kd'] or kadr()}[v0]"
    last = 'v0'; k = 1
    if u['logo']: inp += ['-i', LOGO]; fc += f';[{k}:v]scale=1080:1920[l];[{last}][l]overlay=0:0[v1]'; last = 'v1'; k += 1
    if u['w']:
        inp += ['-loop', '1', '-t', str(d), '-i', f"{WL}/{u['w']}"]
        fc += f";[{k}:v]format=rgba,fade=t=in:st={u['wa']}:d=0.3:alpha=1{f',fade=t=out:st={u['wb']}:d=0.3:alpha=1' if u['wb'] < 90 else ''}[w];[{last}][w]overlay=0:0[v2]"; last = 'v2'
    sh('ffmpeg', '-nostdin', '-v', 'error', '-y', *inp, '-filter_complex', fc, '-map', f'[{last}]', '-an', '-t', str(d), *ENC, out); lista.append(out)
DL = t
open(f'{T}/l.txt', 'w').write(''.join(f"file '{x}'\n" for x in lista))
sh('ffmpeg', '-nostdin', '-v', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', f'{T}/l.txt', '-c', 'copy', f'{T}/obraz.mp4')
TZ, IN, S1, S2, PZ, S3, S4, CZ, ZS, SO = (start[i] for i in (4, 8, 9, 11, 17, 19, 27, 30, 31, 34))
MUZ = f'{P1}/czesc4_wideo/muz_intryga.mp3'; MUZ2 = f'{P1}/czesc4_wideo/muz_zapowiedz_wolniej.mp3'
AMB = f'{P1}/czesc3_wideo/amb_recepcja_n.mp3'; AMBG = f'{P1}/czesc4_wideo/amb_gabinet.mp3'
DZ = []   # (start, plik, ss, t, głośność)
for i, u in enumerate(UJ):
    g = u['glos']
    if g is True: DZ.append((start[i], u['src'], u['ss'], u['t'], 1.5))
    elif g: DZ.append((start[i] + (0.25 if g[0].endswith('.mp3') else 0), g[0], g[1], g[2] or dl(g[0]) - g[1], 1.3 if '_tel' in g[0] else 1.5))
DZ += [
 (0, MUZ, 0, TZ, 0.5),                                                     # pod „W poprzednim odcinku”
 (TZ, AMBG, 0, IN - TZ + 0.3, 0.8),
 (start[5] + 0.15, f'{P1}/czesc4_wideo/sfx_dlugopis.mp3', 1.27, 0.25, 2.0),  # pióro Heleny obwodzi „w/w” (tylko czysty klik)
 (IN, INTRO, 0, dl(INTRO), 1.0),
 (S1, AMB, 5, S2 - S1 + 0.4, 0.85),
 (S2, AMBG, 0, S3 - S2 + 0.4, 0.8),
 (start[12] + 0.3, f'{P1}/czesc4_wideo/sfx_dlugopis.mp3', 1.27, 0.25, 1.6),
 (S3, AMB, 30, S4 - S3 + 0.4, 0.85),
 (start[24] + 0.6, f'{P1}/czesc2_wideo/sfx_tap.mp3', 0, 0.5, 0.8),        # „Popraw i sporządź ponownie”
 (S4, AMBG, 4, CZ + 0.9 - S4, 0.8),
 (start[29], MUZ, 0, CZ + 0.9 - start[29], 0.45),                           # intryga: „Przekażę mu to od razu”
 (CZ + 0.15, f'{P1}/czesc1_wideo/sfx_drzwi.mp3', 0, 1.0, 0.7),             # Basia zamyka drzwi (na czerni)
 (ZS, MUZ2, 0, SO - ZS + 0.3, 0.7),
 (SO, OUTRO, 0, dl(OUTRO), 1.0),
]
inp = ['-i', f'{T}/obraz.mp4']; fc = []
for i, (st, f, ss, d, g) in enumerate(DZ, 1):
    tlo = 'amb_' in f or 'muz_' in f
    inp += (['-stream_loop', '-1'] if 'amb_' in f else []) + ['-i', f]; ms = int(st * 1000)
    fade = f',afade=t=in:d=0.4,afade=t=out:st={d - 0.6:.2f}:d=0.6' if tlo else ''
    lp = ',lowpass=f=2500' if 'amb_gabinet' in f else ''
    fc.append(f'[{i}:a]atrim={ss}:{ss + d},asetpts=PTS-STARTPTS{fade}{lp},volume={g},aformat=sample_rates=48000:channel_layouts=stereo,adelay={ms}|{ms}[a{i}]')
fc.append(''.join(f'[a{i}]' for i in range(1, len(DZ) + 1)) + f'amix=inputs={len(DZ)}:duration=longest:normalize=0,apad,atrim=0:{DL},loudnorm=I=-16:TP=-1.5:LRA=11,afade=t=out:st={DL - 1.2:.2f}:d=1.2[a]')
wyj = f'{K}/podglady/ODC03_U_nas_sie_tak_nie_pisze.mp4'
sh('ffmpeg', '-nostdin', '-v', 'error', '-y', *inp, '-filter_complex', ';'.join(fc), '-map', '0:v', '-map', '[a]', '-c:v', 'libx264', '-preset', 'slow',
   '-crf', '23', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-ar', '48000', '-b:a', '192k', '-movflags', '+faststart', '-t', str(DL), wyj)
print(f'{wyj}  {DL:.2f} s | trzęsienie {TZ:.2f}, intro {IN:.2f}, sc01 {S1:.2f}, sc02 {S2:.2f}, pauza {PZ:.2f}-{PZ + UJ[17]["t"]:.2f}, '
      f'sc03 {S3:.2f}, sc04 {S4:.2f}, czerń {CZ:.2f}, zapowiedź {ZS:.2f}, outro {SO:.2f}')
