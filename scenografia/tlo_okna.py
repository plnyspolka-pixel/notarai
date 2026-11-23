#!/usr/bin/env python3
"""Tło za oknem: perspektywiczny wycinek panoramy CC0 (Poly Haven, tonemapped JPG) z rozmyciem.

    python scenografia/tlo_okna.py <panorama.jpg> <wynik.jpg> <u0> <pochylenie_st> <pole_widzenia_st> <rozmycie_px>
s02: cobblestone_parish_road (CC0, https://polyhaven.com/a/cobblestone_parish_road), u0=0.575, 14, 80, 7
→ scenografia/tla/widok_podworze.jpg (czytelnego tekstu brak po rozmyciu).
"""
from PIL import Image, ImageFilter
src, out, u0, pitch, hfov, rozm = sys.argv[1], sys.argv[2], float(sys.argv[3]), float(sys.argv[4]), float(sys.argv[5]), float(sys.argv[6])
E = np.asarray(Image.open(src).convert('RGB')).astype(np.float32)
H, W = E.shape[:2]
w, h = 1800, 1200
f = (w/2)/np.tan(np.radians(hfov)/2)
xs, ys = np.meshgrid(np.arange(w)-w/2, np.arange(h)-h/2)
d = np.stack([xs, -ys, np.full_like(xs, f, dtype=float)], -1)
d /= np.linalg.norm(d, axis=-1, keepdims=True)
p = np.radians(pitch); c, s = np.cos(p), np.sin(p)
y2 = d[...,1]*c + d[...,2]*s; z2 = -d[...,1]*s + d[...,2]*c
lon = np.arctan2(d[...,0], z2) + (u0-0.5)*2*np.pi
lat = np.arcsin(np.clip(y2, -1, 1))
u = ((lon/(2*np.pi)+0.5) % 1.0)*W; v = (0.5-lat/np.pi)*H
img = E[np.clip(v.astype(int),0,H-1), np.clip(u.astype(int),0,W-1)]
im = Image.fromarray(img.astype(np.uint8)).filter(ImageFilter.GaussianBlur(rozm))
im.save(out, quality=92)
