#!/usr/bin/env python3
"""Lista kontrolna C7: HeyGen (Avatar 6 i Turbo) oddaje wideo ok. 0,16 s krótsze niż nagranie głosu — koniec kwestii się ucina.
Dla każdej pary (ujęcie.mp4, głos.mp3) krótszej niż głos: zachowuje oryginał jako <nazwa>_heygen.mp4, wstawia pełny głos
i przytrzymuje ostatnią klatkę. Użycie: dopelnij_ujecia.py <katalog_ujec> [<katalog_glosow>]
Głos dobierany po nazwie ujęcia: odc0N_<nazwa>[_b|b].mp3 (najnowsza wersja poprawiona ma pierwszeństwo przed odrzuconą)."""
import glob, os, subprocess, sys
D = sys.argv[1]; A = sys.argv[2] if len(sys.argv) > 2 else os.path.join(D, 'audio')
def dl(f): return float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', f], capture_output=True, text=True).stdout)
naprawione = 0
for v in sorted(glob.glob(os.path.join(D, '*.mp4'))):
    n = os.path.basename(v)[:-4]
    if n.endswith('_heygen'): continue
    kand = [p for p in glob.glob(os.path.join(A, f'odc0?_{n}*.mp3')) if not p.endswith(('_pad.mp3', '_tel.mp3'))]
    kand = [p for p in kand if os.path.basename(p)[6:-4].rstrip('b').rstrip('_') == n or os.path.basename(p)[6:-4] == n]
    if not kand: continue
    a = sorted(kand, key=lambda p: (p.endswith(('b.mp3', '_b.mp3')), p))[-1]   # wersja „b” = poprawiona
    zr = os.path.join(D, n + '_heygen.mp4')
    src = zr if os.path.exists(zr) else v
    vd, ad = dl(src), dl(a)
    if vd >= ad - 0.05: continue
    if not os.path.exists(zr): os.replace(v, zr); src = zr
    pad = round(ad - vd + 0.2, 2)
    subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-i', src, '-i', a, '-filter_complex',
                    f'[0:v]tpad=stop_mode=clone:stop_duration={pad}[v];[1:a]aformat=sample_rates=48000:channel_layouts=stereo,apad=pad_dur=0.2[a]',
                    '-map', '[v]', '-map', '[a]', '-c:v', 'libx264', '-preset', 'medium', '-crf', '17', '-pix_fmt', 'yuv420p',
                    '-c:a', 'aac', '-b:a', '192k', '-t', str(round(ad + 0.2, 2)), v], check=True)
    naprawione += 1
    print(f'{n}: wideo {vd:.2f} s -> {dl(v):.2f} s, głos {os.path.basename(a)} {ad:.2f} s')
print(f'{D}: naprawiono {naprawione}')
