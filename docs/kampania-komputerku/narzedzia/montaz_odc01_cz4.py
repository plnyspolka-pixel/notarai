#!/usr/bin/env python3
"""Montaż odc. 01, część 4: sceny 10–12 + outro (sc. 13). Wynik: podglady/odc01_czesc4.mp4 (1080x1920, 30 kl./s).
Sc. 10 przy biurku Marty (gwar recepcji), sc. 11–12 w gabinecie Heleny (gwar przytłumiony jak zza drzwi, bez muzyki).
Największa pauza odcinka: w kwestii Basi przed „bez syna” i po niej, aż do odłożenia długopisu (KANON_ODC01.md)."""
import os, subprocess, tempfile
K = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
P = f'{K}/produkcja-odc01'; V4 = f'{P}/czesc4_wideo'; V3 = f'{P}/czesc3_wideo'; V2 = f'{P}/czesc2_wideo'
KA = f'{P}/czesc4_kadry'; ZAP = f'{P}/zapowiedz_odc02'; WL = f'{P}/czesc1_wideo/warstwy'; OUTRO = f'{K}/intro/OUTRO_siodemka_9x16.mp4'
LOGO = f'{K}/narzedzia/warstwy/warstwa_logo_ai.png'
T = tempfile.mkdtemp(dir=os.environ.get('TMPDIR')); ENC = '-c:v libx264 -preset medium -crf 18 -pix_fmt yuv420p -r 30'.split()
def sh(*a): subprocess.run(a, check=True)
def dl(f): return float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', f], capture_output=True, text=True).stdout)
def kadr(z=1.0, fx=0.5, fy=0.5):
    if z == 1.0: return 'scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps=30,setsar=1'
    return (f"crop=iw/{z}:ih/{z}:'max(0,min(iw-iw/{z},iw*{fx}-iw/{z}/2))':'max(0,min(ih-ih/{z},ih*{fy}-ih/{z}/2))',"
            'scale=1080:1920,fps=30,setsar=1')
KUBA, MARTA = kadr(1.45, 0.6, 0.36), kadr(1.45, 0.6, 0.40)
# (źródło, ss, t, logo, warstwa, w_od, w_do, kadr)
UJ = [
 # sc. 10 „Projekt jest”
 ('G1_powiadomienie.mp4', 0, 2.2, False, None, 0, 0, None),
 ('G2_projekt.mp4', 0, 2.0, False, None, 0, 0, None),
 ('s10_marta.mp4', 0, 1.1, True, None, 0, 0, MARTA),
 ('G3_wybor_brak.mp4', 0, 2.6, False, None, 0, 0, None),
 ('s10_kuba.mp4', 0, 2.32, True, None, 0, 0, KUBA),
 ('G4_pobierz_word.mp4', 0, 1.8, False, None, 0, 0, None),
 # sc. 11 „Dobrze, że nie zgaduje”
 ('s11_helena_1.mp4', 0, 7.04, True, None, 0, 0, None),
 ('s11_marta.mp4', 0, 2.4, True, None, 0, 0, None),
 ('s11_helena_2.mp4', 0, 5.44, True, None, 0, 0, None),
 # sc. 12 „Pani Irena prosiła…”
 ('s12_basia_1.mp4', 0, 7.76, True, None, 0, 0, None),
 ('s12_helena.mp4', 0.2, 1.7, True, None, 0, 0, None),
 ('s12_basia_2.mp4', 0, 5.5, True, None, 0, 0, None),
 (f'{KA}/t9_helena_projekt_2.jpg', 0, 1.6, True, None, 0, 0, None),
 ('b13_dlugopis.mp4', 0.3, 3.0, True, None, 0, 0, None),
 ('CZERN', 0, 0.6, False, None, 0, 0, None),
 # zapowiedź odc. 02 „Proszę nie przy nim”: Paweł czeka pod drzwiami, Helena z Ireną (Irena poza kadrem), plansza tytułu
 (f'{ZAP}/pawel_czeka.mp4', 0.3, 3.0, True, 'zap_naglowek.png', 0.1, 1.9, None),
 (f'{ZAP}/helena_zapowiedz.mp4', 0, None, True, None, 0, 0, None),
 ('CZERN', 0, 1.9, False, 'zap_tytul.png', 0.0, 99, None),
 # sc. 13 plansza: outro „Siódemka” + napis końcowy na zatrzymanej ostatniej klatce
 ('OUTRO', 0, 7.4, False, 'outro_napis.png', 4.3, 99, None),
]
start = []; t = 0; lista = []
for i, (f, ss, d, logo, w, a, b, kd) in enumerate(UJ):
    if d is None:
        d = round(dl(f if f.startswith('/') else f'{V4}/{f}') - ss - 0.05, 2); UJ[i] = (f, ss, d, logo, w, a, b, kd)
    d = round(d * 30) / 30; start.append(t); t += d; out = f'{T}/v{i:02d}.mp4'
    if f == 'CZERN':
        inp = ['-f', 'lavfi', '-t', str(d), '-i', 'color=c=black:s=1080x1920:r=30']; fc = '[0:v]setsar=1[v0]'
    elif f == 'OUTRO':
        inp = ['-i', OUTRO]; fc = f'[0:v]tpad=stop_mode=clone:stop_duration={d - dl(OUTRO) + 0.1:.2f},fps=30,setsar=1[v0]'
    elif f.endswith('.jpg'):
        n = int(d * 30); inp = ['-framerate', '30', '-loop', '1', '-t', str(d), '-i', f]
        fc = f"[0:v]scale=1620:2880,zoompan=z='1.0+0.05*on/{n}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s=1080x1920:fps=30,setsar=1[v0]"
    else:
        src = f if f.startswith('/') else f'{V4}/{f}'
        inp = ['-ss', str(ss), '-t', str(d), '-i', src]; fc = f'[0:v]{kd or kadr()}[v0]'
    last = 'v0'; k = 1
    if logo: inp += ['-i', LOGO]; fc += f';[{k}:v]scale=1080:1920[l];[{last}][l]overlay=0:0[v1]'; last = 'v1'; k += 1
    if w: inp += ['-loop', '1', '-t', str(d), '-i', f'{WL}/{w}']; fc += f';[{k}:v]format=rgba,fade=t=in:st={a}:d=0.5:alpha=1{f',fade=t=out:st={b}:d=0.4:alpha=1' if b < 90 else ''}[w];[{last}][w]overlay=0:0[v2]'; last = 'v2'
    sh('ffmpeg', '-v', 'error', '-y', *inp, '-filter_complex', fc, '-map', f'[{last}]', '-an', '-t', str(d), *ENC, out); lista.append(out)
DL = t
open(f'{T}/l.txt', 'w').write(''.join(f"file '{x}'\n" for x in lista))
sh('ffmpeg', '-v', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', f'{T}/l.txt', '-c', 'copy', f'{T}/obraz.mp4')
S11, S12, SO, ZS = start[6], start[9], start[18], start[15]
PEN = start[13]
# (start, plik, ss, t, głośność)
DZ = [
 (start[0] + 0.15, f'{V4}/sfx_powiadomienie.mp3', 0, 1.0, 0.6),
 (start[0] + 1.4, f'{V2}/sfx_tap.mp3', 0, 0.5, 0.8),
 (start[2], f'{V4}/s10_marta.mp4', 0, 1.1, 1.5),
 (start[3] + 0.3, f'{V4}/s10_marta.mp4', 2.05, 1.85, 1.5),
 (start[4], f'{V4}/s10_kuba.mp4', 0, 2.32, 1.5),
 (start[5] + 1.0, f'{V3}/sfx_klik.mp3', 0, 0.5, 1.0),
 (start[6], f'{V4}/s11_helena_1.mp4', 0, 7.04, 1.5),
 (start[7], f'{V4}/s11_marta.mp4', 0, 2.4, 1.5),
 (start[8], f'{V4}/s11_helena_2.mp4', 0, 5.44, 1.5),
 (start[9], f'{V4}/s12_basia_1.mp4', 0, 7.76, 1.5),
 (start[10], f'{V4}/s12_helena.mp4', 0.2, 1.7, 1.5),
 (start[11], f'{V4}/s12_basia_2.mp4', 0, 5.5, 1.6),
 (PEN + 2.45, f'{V4}/sfx_dlugopis.mp3', 1.27, 0.25, 2.2),  # tylko klik odkładanego pióra, bez szumu pliku
 (0, f'{V3}/amb_recepcja_n.mp3', 0, S11 + 0.4, 0.75),
 (S11, f'{V4}/amb_gabinet.mp3', 0, S12 - S11 + 0.4, 0.8),
 (S12, f'{V4}/amb_gabinet.mp3', 8, PEN + 3.6 - S12, 0.55),
 (start[11] + 2.0, f'{V4}/muz_intryga.mp3', 0, PEN + 3.6 - start[11] - 2.0, 0.45),
 (ZS, f'{V4}/muz_zapowiedz_wolniej.mp3', 0, SO - ZS + 0.3, 0.7),
 (start[16], f'{V4}/audio/odc02_zapowiedz_helena.mp3', 0, dl(f'{V4}/audio/odc02_zapowiedz_helena.mp3'), 1.5),
 (SO, OUTRO, 0, dl(OUTRO), 1.0),
]
inp = ['-i', f'{T}/obraz.mp4']; fc = []
for i, (st, f, ss, d, g) in enumerate(DZ, 1):
    amb = 'amb_' in f or 'muz_' in f
    inp += (['-stream_loop', '-1'] if amb else []) + ['-i', f]; ms = int(st * 1000)
    fade = f',afade=t=in:d=0.3,afade=t=out:st={d - 0.5:.2f}:d=0.5' if amb else ''
    fc.append(f'[{i}:a]atrim={ss}:{ss + d},asetpts=PTS-STARTPTS{fade},volume={g},aformat=sample_rates=48000:channel_layouts=stereo,adelay={ms}|{ms}[a{i}]')
fc.append(''.join(f'[a{i}]' for i in range(1, len(DZ) + 1)) + f'amix=inputs={len(DZ)}:duration=longest:normalize=0,apad,atrim=0:{DL},loudnorm=I=-16:TP=-1.5:LRA=11,afade=t=out:st={DL - 1.2:.2f}:d=1.2[a]')
wyj = f'{K}/podglady/odc01_czesc4.mp4'
sh('ffmpeg', '-v', 'error', '-y', *inp, '-filter_complex', ';'.join(fc), '-map', '0:v', '-map', '[a]', '-c:v', 'copy', '-c:a', 'aac', '-ar', '48000', '-b:a', '192k', '-movflags', '+faststart', '-t', str(DL), wyj)
print(f'{wyj}  {DL:.2f} s, sc. 11 od {S11:.2f} s, sc. 12 od {S12:.2f} s, outro od {SO:.2f} s')
