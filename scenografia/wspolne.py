"""Wspólne narzędzia scenografii (bpy, Blender 5.x).

Każdy plan zdjęciowy (sety/sNN_*.py) buduje się z kodu tymi funkcjami:
pokój ze ścianami i otworami, okna z prawdziwym światłem dziennym, rekwizyty
CC0 z Poly Haven (manifest.json → .cache), nazwane kamery 9:16 i znaczniki
pozycji postaci. Render: Cycles CPU + OpenImageDenoise, JPG + mapa głębi
(16-bit PNG, wartość = odległość od kamery w milimetrach) + opis.json.

Zasada ZERO TEKSTU: żadnych napisów, logo, emblematów. Kartki puste,
segregatory z gładkimi grzbietami, ekrany jednolicie białe (podmieniane
w montażu prawdziwym nagraniem aplikacji).
"""
from __future__ import annotations

import json
import math
import os
import shutil
import subprocess
import time

import bmesh
import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Euler, Vector

TU = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(TU, ".cache")
RENDERY = os.path.join(TU, "rendery")
ZASOBY = json.load(open(os.path.join(CACHE, "zasoby.json"))) if os.path.exists(os.path.join(CACHE, "zasoby.json")) else None

SZER, WYS = 1080, 1920


# ---------------------------------------------------------------- scena
class Plan:
    """Stan budowanego planu: kamery, znaczniki, warianty oświetlenia."""

    def __init__(self, kod: str, nazwa: str):
        self.kod, self.nazwa = kod, nazwa
        self.kamery: list[dict] = []
        self.znaczniki: list[dict] = []
        self.warianty: dict = {}
        self.swiatla_praktyczne: list = []
        self.portale: list = []
        self.ruch: dict | None = None


def ekspozycja(ev: float):
    bpy.context.scene.view_settings.exposure = ev


def nowa_scena(probki: int = 48) -> bpy.types.Scene:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    c = sc.cycles
    c.device = "CPU"
    c.samples = probki
    c.use_adaptive_sampling = True
    c.adaptive_threshold = 0.03
    c.use_denoising = True
    c.denoiser = "OPENIMAGEDENOISE"
    c.max_bounces = 8
    c.diffuse_bounces = 3
    c.glossy_bounces = 3
    c.transmission_bounces = 6
    c.transparent_max_bounces = 8
    c.caustics_reflective = False
    c.caustics_refractive = False
    c.sample_clamp_indirect = 8.0
    c.blur_glossy = 1.0
    sc.render.use_persistent_data = True
    sc.render.resolution_x, sc.render.resolution_y = SZER, WYS
    sc.render.resolution_percentage = 100
    sc.render.film_transparent = False
    try:
        sc.view_settings.view_transform = "AgX"
        sc.view_settings.look = "AgX - Base Contrast"
    except TypeError:
        pass
    sc.view_layers[0].use_pass_z = True
    sc.unit_settings.system = "METRIC"
    return sc


# ---------------------------------------------------------------- materiały
def _wezly(mat):
    mat.use_nodes = True
    nt = mat.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    nt.links.new(bsdf.outputs[0], out.inputs[0])
    return nt, bsdf, out


def kolor(nazwa: str, rgb, szorstkosc=0.5, metal=0.0, polysk=0.5, normal_tex: str | None = None, skala=1.0, sila_normal=0.3):
    """Jednolity materiał (opcjonalnie z normalną z tekstury dla faktury)."""
    m = bpy.data.materials.get(nazwa) or bpy.data.materials.new(nazwa)
    nt, b, _ = _wezly(m)
    b.inputs["Base Color"].default_value = (*rgb, 1)
    b.inputs["Roughness"].default_value = szorstkosc
    b.inputs["Metallic"].default_value = metal
    b.inputs["Specular IOR Level"].default_value = polysk
    if normal_tex:
        _normal(nt, b, normal_tex, skala, sila_normal)
    return m


def _wsp(nt, skala):
    tc = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (skala, skala, skala)
    nt.links.new(tc.outputs["Object"], mp.inputs["Vector"])
    return mp


def _obraz(nt, sciezka, mp, kolor_dane=True):
    t = nt.nodes.new("ShaderNodeTexImage")
    t.image = bpy.data.images.load(sciezka, check_existing=True)
    if not kolor_dane:
        t.image.colorspace_settings.name = "Non-Color"
    t.projection = "BOX"
    t.projection_blend = 0.25
    nt.links.new(mp.outputs[0], t.inputs["Vector"])
    return t


def _normal(nt, b, tex_id, skala, sila):
    mapy = ZASOBY["tekstury"][tex_id]["mapy"]
    if "nor_gl" not in mapy:
        return
    mp = _wsp(nt, skala)
    t = _obraz(nt, mapy["nor_gl"], mp, kolor_dane=False)
    nm = nt.nodes.new("ShaderNodeNormalMap")
    nm.inputs["Strength"].default_value = sila
    nt.links.new(t.outputs[0], nm.inputs["Color"])
    nt.links.new(nm.outputs[0], b.inputs["Normal"])


def tekstura(nazwa: str, tex_id: str, skala=1.0, odcien=None, jasnosc=1.0, szorstkosc_mnoz=1.0, sila_normal=0.6, polysk=0.5):
    """Materiał PBR z tekstury Poly Haven, rzut pudełkowy w metrach (skala = powtórzenia na metr)."""
    m = bpy.data.materials.get(nazwa) or bpy.data.materials.new(nazwa)
    nt, b, _ = _wezly(m)
    mapy = ZASOBY["tekstury"][tex_id]["mapy"]
    mp = _wsp(nt, skala)
    d = _obraz(nt, mapy["Diffuse"], mp)
    kol = d.outputs[0]
    if odcien is not None or jasnosc != 1.0:
        mix = nt.nodes.new("ShaderNodeMix")
        mix.data_type = "RGBA"
        mix.blend_type = "MULTIPLY"
        mix.inputs["Factor"].default_value = 1.0
        nt.links.new(kol, mix.inputs[6])
        c = odcien or (1, 1, 1)
        mix.inputs[7].default_value = (c[0] * jasnosc, c[1] * jasnosc, c[2] * jasnosc, 1)
        kol = mix.outputs[2]
    nt.links.new(kol, b.inputs["Base Color"])
    if "Rough" in mapy:
        r = _obraz(nt, mapy["Rough"], mp, kolor_dane=False)
        mm = nt.nodes.new("ShaderNodeMath")
        mm.operation = "MULTIPLY"
        mm.inputs[1].default_value = szorstkosc_mnoz
        nt.links.new(r.outputs[0], mm.inputs[0])
        nt.links.new(mm.outputs[0], b.inputs["Roughness"])
    b.inputs["Specular IOR Level"].default_value = polysk
    _normal(nt, b, tex_id, skala, sila_normal)
    return m


def ekran(nazwa="ekran_bialy", sila=1.6):
    """Ekran monitora: jednolita, lekko chłodna biel (do podmiany w montażu)."""
    m = bpy.data.materials.get(nazwa) or bpy.data.materials.new(nazwa)
    nt, b, out = _wezly(m)
    nt.nodes.remove(b)
    e = nt.nodes.new("ShaderNodeEmission")
    e.inputs["Color"].default_value = (0.93, 0.96, 1.0, 1)
    e.inputs["Strength"].default_value = sila
    nt.links.new(e.outputs[0], out.inputs[0])
    return m


def swiecenie(nazwa, rgb, sila):
    m = bpy.data.materials.get(nazwa) or bpy.data.materials.new(nazwa)
    nt, b, out = _wezly(m)
    nt.nodes.remove(b)
    e = nt.nodes.new("ShaderNodeEmission")
    e.inputs["Color"].default_value = (*rgb, 1)
    e.inputs["Strength"].default_value = sila
    nt.links.new(e.outputs[0], out.inputs[0])
    return m


def szyba(nazwa="szyba"):
    """Szkło okienne przepuszczające słońce bez kaustyk (promienie cienia widzą przezroczystość)."""
    m = bpy.data.materials.get(nazwa) or bpy.data.materials.new(nazwa)
    nt, b, out = _wezly(m)
    b.inputs["Transmission Weight"].default_value = 1.0
    b.inputs["Roughness"].default_value = 0.02
    b.inputs["IOR"].default_value = 1.45
    b.inputs["Base Color"].default_value = (0.95, 0.98, 0.98, 1)
    lp = nt.nodes.new("ShaderNodeLightPath")
    tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    mix = nt.nodes.new("ShaderNodeMixShader")
    mx = nt.nodes.new("ShaderNodeMath")
    mx.operation = "MAXIMUM"
    nt.links.new(lp.outputs["Is Shadow Ray"], mx.inputs[0])
    nt.links.new(lp.outputs["Is Diffuse Ray"], mx.inputs[1])
    nt.links.new(mx.outputs[0], mix.inputs[0])
    nt.links.new(b.outputs[0], mix.inputs[1])
    nt.links.new(tr.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs[0])
    return m


def obraz_abstrakcyjny(nazwa, kolory, ziarno=1.0):
    """Obraz na ścianę: miękkie plamy koloru z szumu (bez treści do przeczytania)."""
    m = bpy.data.materials.get(nazwa) or bpy.data.materials.new(nazwa)
    nt, b, _ = _wezly(m)
    tc = nt.nodes.new("ShaderNodeTexCoord")
    n = nt.nodes.new("ShaderNodeTexNoise")
    n.inputs["Scale"].default_value = 3.0
    n.inputs["Detail"].default_value = 2.0
    n.noise_dimensions = "4D"
    n.inputs["W"].default_value = ziarno
    nt.links.new(tc.outputs["Generated"], n.inputs["Vector"])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    el = ramp.color_ramp.elements
    el[0].color = (*kolory[0], 1)
    el[1].color = (*kolory[-1], 1)
    el[0].position = 0.32
    el[1].position = 0.68
    for i, k in enumerate(kolory[1:-1], 1):
        e = el.new(0.32 + 0.36 * i / (len(kolory) - 1))
        e.color = (*k, 1)
    nt.links.new(n.outputs["Fac"], ramp.inputs[0])
    nt.links.new(ramp.outputs[0], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.7
    return m


# ---------------------------------------------------------------- geometria
def _kolekcja(nazwa):
    k = bpy.data.collections.get(nazwa)
    if not k:
        k = bpy.data.collections.new(nazwa)
        bpy.context.scene.collection.children.link(k)
    return k


def skrzynka(nazwa, rozmiar, srodek, mat=None, obrot_z=0.0, kolekcja="architektura", fazka=0.0):
    """Prostopadłościan: rozmiar (x, y, z) w metrach, środek podstawy dolnej = srodek? Nie: środek bryły."""
    me = bpy.data.meshes.new(nazwa)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co.x *= rozmiar[0]
        v.co.y *= rozmiar[1]
        v.co.z *= rozmiar[2]
    if fazka > 0:
        bmesh.ops.bevel(bm, geom=list(bm.edges), offset=fazka, segments=2, affect="EDGES")
    bm.to_mesh(me)
    bm.free()
    o = bpy.data.objects.new(nazwa, me)
    o.location = Vector(srodek)
    o.rotation_euler = Euler((0, 0, math.radians(obrot_z)))
    _kolekcja(kolekcja).objects.link(o)
    if mat:
        o.data.materials.append(mat)
    for p in o.data.polygons:
        p.use_smooth = False
    return o


def walec(nazwa, r, h, srodek, mat=None, wierzcholki=32, kolekcja="rekwizyty_wlasne"):
    me = bpy.data.meshes.new(nazwa)
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=wierzcholki, radius1=r, radius2=r, depth=h)
    bm.to_mesh(me)
    bm.free()
    o = bpy.data.objects.new(nazwa, me)
    o.location = Vector(srodek)
    _kolekcja(kolekcja).objects.link(o)
    if mat:
        o.data.materials.append(mat)
    for p in o.data.polygons:
        p.use_smooth = True
    return o


def plaszczyzna(nazwa, szer, wys, srodek, obrot=(0, 0, 0), mat=None, kolekcja="architektura"):
    me = bpy.data.meshes.new(nazwa)
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=0.5)
    for v in bm.verts:
        v.co.x *= szer
        v.co.y *= wys
    bm.to_mesh(me)
    bm.free()
    o = bpy.data.objects.new(nazwa, me)
    o.location = Vector(srodek)
    o.rotation_euler = Euler(tuple(math.radians(a) for a in obrot))
    _kolekcja(kolekcja).objects.link(o)
    if mat:
        o.data.materials.append(mat)
    return o


GRUB = 0.2  # grubość ścian


def sciana(nazwa, os_, stala, od, do, wys, mat, otwory=(), grub=GRUB, z0=0.0):
    """Ściana wzdłuż osi 'x' (y = stala) albo 'y' (x = stala), od..do, z otworami (a, b, dol, gora)."""
    kawalki = []
    otw = sorted(otwory)
    pozycja = od

    def dodaj(a, b, z_dol, z_gora):
        if b - a < 1e-3 or z_gora - z_dol < 1e-3:
            return
        dl, h = b - a, z_gora - z_dol
        sr = (a + b) / 2
        if os_ == "x":
            o = skrzynka(f"{nazwa}_{len(kawalki)}", (dl, grub, h), (sr, stala, z0 + z_dol + h / 2), mat)
        else:
            o = skrzynka(f"{nazwa}_{len(kawalki)}", (grub, dl, h), (stala, sr, z0 + z_dol + h / 2), mat)
        kawalki.append(o)

    for a, b, dol, gora in otw:
        dodaj(pozycja, a, 0, wys)
        dodaj(a, b, 0, dol)
        dodaj(a, b, gora, wys)
        pozycja = b
    dodaj(pozycja, do, 0, wys)
    return kawalki


def okno(nazwa, os_, stala, a, b, dol, gora, strona_wew=+1, mat_rama=None, szczeble=True, parapet=True):
    """Rama, szyba i parapet w otworze ściany. strona_wew: +1 gdy wnętrze ma większą współrzędną."""
    mat_rama = mat_rama or kolor("rama_biala", (0.88, 0.88, 0.86), 0.35)
    sz = szyba()
    r = 0.085
    dl = b - a
    sr = (a + b) / 2
    h = gora - dol
    zc = dol + h / 2

    def bryla(n, roz, pos):
        if os_ == "x":
            return skrzynka(n, roz, pos, mat_rama, kolekcja="okna")
        return skrzynka(n, (roz[1], roz[0], roz[2]), (pos[1], pos[0], pos[2]), mat_rama, kolekcja="okna")

    def p(u, w, z):  # u wzdłuż ściany, w w głąb
        return (u, stala + w, z) if os_ == "x" else (u, stala + w, z)

    off = 0.0
    bryla(f"{nazwa}_rama_d", (dl, 0.1, r), (sr, stala + off, dol + r / 2))
    bryla(f"{nazwa}_rama_g", (dl, 0.1, r), (sr, stala + off, gora - r / 2))
    bryla(f"{nazwa}_rama_l", (r, 0.104, h), (a + r / 2, stala + off, zc))
    bryla(f"{nazwa}_rama_p", (r, 0.104, h), (b - r / 2, stala + off, zc))
    if szczeble:
        bryla(f"{nazwa}_slupek", (r * 0.8, 0.09, h - 2 * r), (sr, stala + off, zc))
        bryla(f"{nazwa}_powiemik", (dl - 2 * r, 0.08, r * 0.8), (sr, stala + off, dol + h * 0.72))
    if os_ == "x":
        g = plaszczyzna(f"{nazwa}_szyba", dl, h, (sr, stala, zc), (90, 0, 0), sz, kolekcja="okna")
    else:
        g = plaszczyzna(f"{nazwa}_szyba", h, dl, (stala, sr, zc), (0, 90, 0), sz, kolekcja="okna")
    if parapet:
        par = kolor("parapet", (0.92, 0.91, 0.88), 0.3)
        if os_ == "x":
            skrzynka(f"{nazwa}_parapet", (dl + 0.1, 0.3, 0.04), (sr, stala + strona_wew * 0.14, dol - 0.02), par, kolekcja="okna")
        else:
            skrzynka(f"{nazwa}_parapet", (0.3, dl + 0.1, 0.04), (stala + strona_wew * 0.14, sr, dol - 0.02), par, kolekcja="okna")
    return g


def kaloryfer(nazwa, os_, stala, srodek_u, dl=1.2, strona_wew=+1, z=0.25):
    mat = kolor("kaloryfer", (0.92, 0.92, 0.9), 0.35, polysk=0.6)
    n = int(dl / 0.05)
    for i in range(n):
        u = srodek_u - dl / 2 + (i + 0.5) * dl / n
        if os_ == "x":
            skrzynka(f"{nazwa}_{i}", (0.03, 0.08, 0.5), (u, stala + strona_wew * 0.16, z + 0.25), mat, kolekcja="instalacje")
        else:
            skrzynka(f"{nazwa}_{i}", (0.08, 0.03, 0.5), (stala + strona_wew * 0.16, u, z + 0.25), mat, kolekcja="instalacje")


def drzwi(nazwa, os_, stala, a, b, wys=2.1, mat=None, otwarte=0.0, strona_wew=+1, klamka=True):
    """Skrzydło płycinowe w otworze (otwarte: kąt w stopniach)."""
    mat = mat or kolor("drzwi_biale", (0.9, 0.89, 0.86), 0.4)
    oscieznica = kolor("oscieznica", (0.88, 0.87, 0.84), 0.4)
    dl = b - a
    if os_ == "x":
        skrzynka(f"{nazwa}_osc_l", (0.06, GRUB + 0.04, wys), (a + 0.03, stala, wys / 2), oscieznica, kolekcja="drzwi")
        skrzynka(f"{nazwa}_osc_p", (0.06, GRUB + 0.04, wys), (b - 0.03, stala, wys / 2), oscieznica, kolekcja="drzwi")
        skrzynka(f"{nazwa}_osc_g", (dl, GRUB + 0.04, 0.06), (a + dl / 2, stala, wys - 0.03), oscieznica, kolekcja="drzwi")
        s = skrzynka(f"{nazwa}_skrzydlo", (dl - 0.12, 0.045, wys - 0.06), (0, 0, 0), mat, kolekcja="drzwi")
        piv = bpy.data.objects.new(f"{nazwa}_zawias", None)
        _kolekcja("drzwi").objects.link(piv)
        piv.location = (a + 0.06, stala + strona_wew * 0.05, 0)
        s.parent = piv
        s.location = ((dl - 0.12) / 2, 0, (wys - 0.06) / 2)
        piv.rotation_euler = Euler((0, 0, math.radians(otwarte * strona_wew)))
        for i, (zz, hh) in enumerate(((0.45, 0.55), (1.35, 0.95))):
            pl = skrzynka(f"{nazwa}_plycina{i}", (dl - 0.4, 0.06, hh), (0, 0, 0), mat, kolekcja="drzwi", fazka=0.01)
            pl.parent = piv
            pl.location = ((dl - 0.12) / 2, 0, zz)
        if klamka:
            k = skrzynka(f"{nazwa}_klamka", (0.13, 0.08, 0.02), (0, 0, 0), kolor("mosiadz", (0.75, 0.6, 0.35), 0.25, metal=1.0), kolekcja="drzwi")
            k.parent = piv
            k.location = (dl - 0.22, 0, 1.02)
    else:
        skrzynka(f"{nazwa}_osc_l", (GRUB + 0.04, 0.06, wys), (stala, a + 0.03, wys / 2), oscieznica, kolekcja="drzwi")
        skrzynka(f"{nazwa}_osc_p", (GRUB + 0.04, 0.06, wys), (stala, b - 0.03, wys / 2), oscieznica, kolekcja="drzwi")
        skrzynka(f"{nazwa}_osc_g", (GRUB + 0.04, dl, 0.06), (stala, a + dl / 2, wys - 0.03), oscieznica, kolekcja="drzwi")
        s = skrzynka(f"{nazwa}_skrzydlo", (0.045, dl - 0.12, wys - 0.06), (0, 0, 0), mat, kolekcja="drzwi")
        piv = bpy.data.objects.new(f"{nazwa}_zawias", None)
        _kolekcja("drzwi").objects.link(piv)
        piv.location = (stala + strona_wew * 0.05, a + 0.06, 0)
        s.parent = piv
        s.location = (0, (dl - 0.12) / 2, (wys - 0.06) / 2)
        piv.rotation_euler = Euler((0, 0, math.radians(-otwarte * strona_wew)))
        for i, (zz, hh) in enumerate(((0.45, 0.55), (1.35, 0.95))):
            pl = skrzynka(f"{nazwa}_plycina{i}", (0.06, dl - 0.4, hh), (0, 0, 0), mat, kolekcja="drzwi", fazka=0.01)
            pl.parent = piv
            pl.location = (0, (dl - 0.12) / 2, zz)
        if klamka:
            k = skrzynka(f"{nazwa}_klamka", (0.08, 0.13, 0.02), (0, 0, 0), kolor("mosiadz", (0.75, 0.6, 0.35), 0.25, metal=1.0), kolekcja="drzwi")
            k.parent = piv
            k.location = (0, dl - 0.22, 1.02)
    return piv


def pokoj(nazwa, W, D, H, mat_podloga, mat_sciany, mat_sufit=None, otwory=None, gzyms=True, cokol=True, z0=0.0):
    """Pokój x∈[0,W], y∈[0,D]. otwory: {'S'|'N'|'W'|'E': [(a, b, dol, gora), ...]}.
    S: y=0, N: y=D (oś x); W: x=0, E: x=W (oś y)."""
    otwory = otwory or {}
    mat_sufit = mat_sufit or kolor("sufit", (0.93, 0.93, 0.92), 0.9, polysk=0.2)
    skrzynka(f"{nazwa}_podloga", (W + 0.4, D + 0.4, 0.1), (W / 2, D / 2, z0 - 0.05), mat_podloga)
    skrzynka(f"{nazwa}_sufit", (W + 0.4, D + 0.4, 0.1), (W / 2, D / 2, z0 + H + 0.05), mat_sufit)
    g = GRUB / 2
    sciana(f"{nazwa}_scS", "x", -g, -GRUB, W + GRUB, H, mat_sciany, otwory.get("S", ()), z0=z0)
    sciana(f"{nazwa}_scN", "x", D + g, -GRUB, W + GRUB, H, mat_sciany, otwory.get("N", ()), z0=z0)
    sciana(f"{nazwa}_scW", "y", -g, 0, D, H, mat_sciany, otwory.get("W", ()), z0=z0)
    sciana(f"{nazwa}_scE", "y", W + g, 0, D, H, mat_sciany, otwory.get("E", ()), z0=z0)
    listwa = kolor("listwa", (0.9, 0.89, 0.86), 0.4)
    if gzyms:
        for n, roz, pos in (("gN", (W, 0.12, 0.14), (W / 2, D - 0.06, H - 0.07)), ("gS", (W, 0.12, 0.14), (W / 2, 0.06, H - 0.07)),
                            ("gW", (0.12, D, 0.14), (0.06, D / 2, H - 0.07)), ("gE", (0.12, D, 0.14), (W - 0.06, D / 2, H - 0.07))):
            skrzynka(f"{nazwa}_{n}", roz, (pos[0], pos[1], z0 + pos[2]), listwa, fazka=0.02)
    if cokol:
        for n, roz, pos in (("cN", (W, 0.02, 0.1), (W / 2, D - 0.01, 0.05)), ("cS", (W, 0.02, 0.1), (W / 2, 0.01, 0.05)),
                            ("cW", (0.02, D, 0.1), (0.01, D / 2, 0.05)), ("cE", (0.02, D, 0.1), (W - 0.01, D / 2, 0.05))):
            skrzynka(f"{nazwa}_{n}", roz, (pos[0], pos[1], z0 + pos[2]), listwa)


# ---------------------------------------------------------------- rekwizyty CC0
_ZALADOWANE: dict = {}


def wstaw(aid, polozenie, obrot_z=0.0, skala=1.0, tylko=None, wyklucz=None, nazwa=None, mat_nadpisz=None):
    """Wstawia model CC0 (kopię) z Poly Haven. tylko/wyklucz: fragmenty nazw obiektów (warianty w pliku)."""
    wpis = ZASOBY["modele"][aid]
    katalog = os.path.dirname(wpis["blend"])
    with bpy.data.libraries.load(wpis["blend"], link=False) as (a, b):
        b.objects = list(a.objects)
    obj = [o for o in b.objects if o is not None]
    for o in obj:
        if o.type == "MESH" or o.type == "CURVE":
            for slot in o.material_slots:
                if slot.material and slot.material.use_nodes:
                    for n in slot.material.node_tree.nodes:
                        if n.type == "TEX_IMAGE" and n.image and n.image.filepath.startswith("//"):
                            n.image.filepath = os.path.join(katalog, n.image.filepath[2:])
    if tylko:
        obj = [o for o in obj if any(t in o.name for t in tylko)]
    if wyklucz:
        obj = [o for o in obj if not any(t in o.name for t in wyklucz)]
    obj = [o for o in obj if not o.name.startswith("wdg_")]
    k = _kolekcja("rekwizyty")
    for o in obj:
        k.objects.link(o)
    bpy.context.view_layer.update()
    mn = Vector((1e9, 1e9, 1e9))
    mx = -mn
    for o in obj:
        if o.type == "MESH":
            for c in o.bound_box:
                w = o.matrix_world @ Vector(c)
                mn = Vector(map(min, mn, w))
                mx = Vector(map(max, mx, w))
    piv = bpy.data.objects.new(nazwa or f"R_{aid}", None)
    k.objects.link(piv)
    sr = Vector(((mn.x + mx.x) / 2, (mn.y + mx.y) / 2, mn.z))
    for o in obj:
        if o.parent is None:
            o.parent = piv
            o.location -= sr
        if mat_nadpisz and o.type == "MESH":
            o.data.materials.clear()
            o.data.materials.append(mat_nadpisz)
    piv.location = Vector(polozenie)
    piv.rotation_euler = Euler((0, 0, math.radians(obrot_z)))
    piv.scale = (skala, skala, skala)
    return piv


# ---------------------------------------------------------------- rekwizyty własne (bez tekstu)
def segregatory(nazwa, start, kierunek_x=True, ile=8, obrot_z=0.0, kolory=None, wys=0.32, gl=0.28):
    """Rząd segregatorów z gładkimi grzbietami (bez etykiet)."""
    kolory = kolory or [(0.025, 0.04, 0.1), (0.12, 0.12, 0.13), (0.2, 0.035, 0.035), (0.03, 0.09, 0.1), (0.32, 0.28, 0.22), (0.05, 0.05, 0.06), (0.4, 0.4, 0.38)]
    x, y, z = start
    ziarno = sum(ord(ch) for ch in nazwa)
    for i in range(ile):
        c = kolory[(ziarno + i * 3 + (i * i) % 5) % len(kolory)]
        m = kolor(f"segregator_{c}", c, 0.55)
        szer = 0.075 if i % 3 else 0.05
        if kierunek_x:
            skrzynka(f"{nazwa}_{i}", (szer, gl, wys), (x + szer / 2, y, z + wys / 2), m, kolekcja="rekwizyty_wlasne", fazka=0.004)
            x += szer + 0.004
        else:
            skrzynka(f"{nazwa}_{i}", (gl, szer, wys), (x, y + szer / 2, z + wys / 2), m, kolekcja="rekwizyty_wlasne", fazka=0.004)
            y += szer + 0.004
    return x if kierunek_x else y


def teczki(nazwa, srodek, ile=3, obrot_z=0.0, kolory=None):
    """Stos zamkniętych teczek na biurku (gładkie okładki)."""
    kolory = kolory or [(0.62, 0.55, 0.42), (0.18, 0.25, 0.4), (0.7, 0.68, 0.62)]
    x, y, z = srodek
    for i in range(ile):
        m = kolor(f"teczka_{i}_{nazwa}", kolory[i % len(kolory)], 0.7)
        skrzynka(f"{nazwa}_{i}", (0.24, 0.32, 0.012), (x + 0.01 * i, y - 0.008 * i, z + 0.006 + i * 0.013), m, obrot_z=obrot_z + i * 4, kolekcja="rekwizyty_wlasne")


def kartki(nazwa, srodek, ile=4, obrot_z=0.0):
    m = kolor("papier", (0.92, 0.92, 0.9), 0.8, polysk=0.2)
    x, y, z = srodek
    for i in range(ile):
        skrzynka(f"{nazwa}_{i}", (0.21, 0.297, 0.0008), (x, y, z + 0.0005 + i * 0.0009), m, obrot_z=obrot_z + (i - ile / 2) * 3, kolekcja="rekwizyty_wlasne")


def monitor(nazwa, polozenie, obrot_z=0.0, szer=0.6, wys=0.36):
    """Monitor na nóżce z jednolicie białym ekranem."""
    piv = bpy.data.objects.new(nazwa, None)
    _kolekcja("rekwizyty_wlasne").objects.link(piv)
    czarny = kolor("obudowa", (0.03, 0.03, 0.035), 0.4)
    o1 = skrzynka(f"{nazwa}_obudowa", (szer, 0.03, wys), (0, 0, 0.13 + wys / 2), czarny, kolekcja="rekwizyty_wlasne", fazka=0.004)
    o2 = plaszczyzna(f"{nazwa}_ekran", szer - 0.02, wys - 0.02, (0, -0.0155, 0.13 + wys / 2), (90, 0, 0), ekran(), kolekcja="rekwizyty_wlasne")
    o3 = skrzynka(f"{nazwa}_noga", (0.05, 0.04, 0.16), (0, 0.03, 0.08), czarny, kolekcja="rekwizyty_wlasne")
    o4 = skrzynka(f"{nazwa}_stopa", (0.22, 0.16, 0.012), (0, 0.02, 0.006), czarny, kolekcja="rekwizyty_wlasne", fazka=0.003)
    k = skrzynka(f"{nazwa}_klawiatura", (0.42, 0.13, 0.02), (0, -0.25, 0.01), kolor("klawiatura", (0.12, 0.12, 0.13), 0.5), kolekcja="rekwizyty_wlasne", fazka=0.004)
    mysz = skrzynka(f"{nazwa}_mysz", (0.06, 0.1, 0.03), (0.3, -0.25, 0.015), kolor("klawiatura", (0.12, 0.12, 0.13), 0.5), kolekcja="rekwizyty_wlasne", fazka=0.012)
    for o in (o1, o2, o3, o4, k, mysz):
        o.parent = piv
    piv.location = Vector(polozenie)
    piv.rotation_euler = Euler((0, 0, math.radians(obrot_z)))
    return piv


def telefon_biurkowy(nazwa, polozenie, obrot_z=0.0):
    piv = bpy.data.objects.new(nazwa, None)
    _kolekcja("rekwizyty_wlasne").objects.link(piv)
    m = kolor("telefon", (0.06, 0.06, 0.07), 0.35)
    a = skrzynka(f"{nazwa}_baza", (0.2, 0.18, 0.05), (0, 0, 0.025), m, kolekcja="rekwizyty_wlasne", fazka=0.01)
    b = skrzynka(f"{nazwa}_sluchawka", (0.05, 0.2, 0.04), (-0.07, 0, 0.07), m, kolekcja="rekwizyty_wlasne", fazka=0.015)
    c = plaszczyzna(f"{nazwa}_wyswietlacz", 0.07, 0.03, (0.04, 0.05, 0.051), (0, 0, 0), kolor("szybka", (0.02, 0.02, 0.02), 0.1), kolekcja="rekwizyty_wlasne")
    for o in (a, b, c):
        o.parent = piv
    piv.location = Vector(polozenie)
    piv.rotation_euler = Euler((0, 0, math.radians(obrot_z)))
    return piv


def kubek(nazwa, polozenie, rgb=(0.92, 0.92, 0.9)):
    w = walec(nazwa, 0.04, 0.1, (polozenie[0], polozenie[1], polozenie[2] + 0.05), kolor(f"kubek_{rgb}", rgb, 0.2, polysk=0.7))
    walec(f"{nazwa}_kawa", 0.036, 0.002, (polozenie[0], polozenie[1], polozenie[2] + 0.092), kolor("kawa", (0.12, 0.06, 0.03), 0.05))
    return w


def obraz_na_scianie(nazwa, srodek, szer, wys, normal, kolory, ziarno=1.0):
    """Rama z abstrakcyjnym płótnem; normal: 'S','N','W','E' – na którą stronę patrzy obraz."""
    rama = kolor("rama_obrazu", (0.08, 0.07, 0.06), 0.4)
    pl = obraz_abstrakcyjny(f"plotno_{nazwa}", kolory, ziarno)
    x, y, z = srodek
    if normal in ("S", "N"):
        sgn = -1 if normal == "S" else 1
        skrzynka(f"{nazwa}_rama", (szer + 0.06, 0.03, wys + 0.06), (x, y, z), rama, kolekcja="rekwizyty_wlasne")
        plaszczyzna(f"{nazwa}_plotno", szer, wys, (x, y + sgn * 0.016, z), (90 if sgn < 0 else -90, 0, 0 if sgn < 0 else 180), pl, kolekcja="rekwizyty_wlasne")
    else:
        sgn = -1 if normal == "W" else 1
        skrzynka(f"{nazwa}_rama", (0.03, szer + 0.06, wys + 0.06), (x, y, z), rama, kolekcja="rekwizyty_wlasne")
        plaszczyzna(f"{nazwa}_plotno", wys, szer, (x + sgn * 0.016, y, z), (0, 90 * (1 if sgn > 0 else -1), 0), pl, kolekcja="rekwizyty_wlasne")


# ---------------------------------------------------------------- światło
def niebo(hdri_id, sila=1.0, obrot_z=0.0, tlo_sila=None):
    """Świat z HDRI; tlo_sila – osobna jasność tego, co widać w oknach."""
    sc = bpy.context.scene
    w = bpy.data.worlds.new("swiat")
    sc.world = w
    w.use_nodes = True
    nt = w.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputWorld")
    tc = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Rotation"].default_value = (0, 0, math.radians(obrot_z))
    env = nt.nodes.new("ShaderNodeTexEnvironment")
    env.image = bpy.data.images.load(ZASOBY["hdri"][hdri_id]["plik"], check_existing=True)
    nt.links.new(tc.outputs["Generated"], mp.inputs["Vector"])
    nt.links.new(mp.outputs[0], env.inputs["Vector"])
    bg = nt.nodes.new("ShaderNodeBackground")
    bg.inputs["Strength"].default_value = sila
    nt.links.new(env.outputs[0], bg.inputs["Color"])
    if tlo_sila is not None:
        bg2 = nt.nodes.new("ShaderNodeBackground")
        bg2.inputs["Strength"].default_value = tlo_sila
        nt.links.new(env.outputs[0], bg2.inputs["Color"])
        lp = nt.nodes.new("ShaderNodeLightPath")
        mix = nt.nodes.new("ShaderNodeMixShader")
        nt.links.new(lp.outputs["Is Camera Ray"], mix.inputs[0])
        nt.links.new(bg.outputs[0], mix.inputs[1])
        nt.links.new(bg2.outputs[0], mix.inputs[2])
        nt.links.new(mix.outputs[0], out.inputs[0])
    else:
        nt.links.new(bg.outputs[0], out.inputs[0])
    return w


def slonce(kierunek=(0.3, -1.0, -0.6), sila=3.0, kat=1.5, kolor_k=5600):
    """Słońce; kierunek = wektor, w którą stronę biegnie światło (np. z okna na północy do wnętrza: (0,-1,-0.6))."""
    d = bpy.data.lights.new("slonce", "SUN")
    d.energy = sila
    d.angle = math.radians(kat)
    d.color = kelwin(kolor_k)
    o = bpy.data.objects.new("slonce", d)
    _kolekcja("swiatlo").objects.link(o)
    o.rotation_euler = Vector(kierunek).normalized().to_track_quat("-Z", "Y").to_euler()
    return o


def kelwin(k):
    """Przybliżony kolor RGB dla temperatury barwowej."""
    t = k / 100.0
    if t <= 66:
        r = 1.0
        g = max(0, min(1, (99.47 * math.log(t) - 161.12) / 255))
        b = 0 if t <= 19 else max(0, min(1, (138.52 * math.log(t - 10) - 305.04) / 255))
    else:
        r = max(0, min(1, 329.7 * ((t - 60) ** -0.1332) / 255))
        g = max(0, min(1, 288.12 * ((t - 60) ** -0.0755) / 255))
        b = 1.0
    return (r, g, b)


def lampa_obszar(nazwa, srodek, rozmiar, moc, kolor_k=4000, obrot=(0, 0, 0), ksztalt="RECTANGLE", widoczna=False, rozmiar_y=None):
    d = bpy.data.lights.new(nazwa, "AREA")
    d.shape = ksztalt
    d.size = rozmiar
    if rozmiar_y and ksztalt == "RECTANGLE":
        d.size_y = rozmiar_y
    d.energy = moc
    d.color = kelwin(kolor_k)
    o = bpy.data.objects.new(nazwa, d)
    o.location = Vector(srodek)
    o.rotation_euler = Euler(tuple(math.radians(a) for a in obrot))
    o.visible_camera = widoczna
    _kolekcja("swiatlo").objects.link(o)
    return o


def lampa_punkt(nazwa, srodek, moc, kolor_k=2900, promien=0.05):
    d = bpy.data.lights.new(nazwa, "POINT")
    d.energy = moc
    d.shadow_soft_size = promien
    d.color = kelwin(kolor_k)
    o = bpy.data.objects.new(nazwa, d)
    o.location = Vector(srodek)
    _kolekcja("swiatlo").objects.link(o)
    return o


def portal_okna(plan: Plan, nazwa, os_, stala, a, b, dol, gora, strona_wew=+1, moc=60.0, kolor_k=6500):
    """Miękkie światło nieba wpadające przez okno (lampa powierzchniowa w otworze, skierowana do wnętrza)."""
    sr = (a + b) / 2
    zc = (dol + gora) / 2
    if os_ == "x":
        rot = (-90, 0, 0) if strona_wew > 0 else (90, 0, 0)
        o = lampa_obszar(nazwa, (sr, stala - strona_wew * 0.02, zc), b - a, moc, kolor_k, rot, rozmiar_y=gora - dol)
    else:
        rot = (0, 90, 0) if strona_wew > 0 else (0, -90, 0)
        o = lampa_obszar(nazwa, (stala - strona_wew * 0.02, sr, zc), gora - dol, moc, kolor_k, rot, rozmiar_y=b - a)
    plan.portale.append(o)
    return o


# ---------------------------------------------------------------- kamery i znaczniki
def kamera(plan: Plan, nazwa, polozenie, cel, obiektyw=35.0, uzycie=""):
    c = bpy.data.cameras.new(nazwa)
    c.lens = obiektyw
    c.sensor_width = 36.0
    c.sensor_fit = "AUTO"
    c.clip_start = 0.05
    c.clip_end = 300
    o = bpy.data.objects.new(nazwa, c)
    _kolekcja("kamery").objects.link(o)
    o.location = Vector(polozenie)
    kier = Vector(cel) - Vector(polozenie)
    o.rotation_euler = kier.to_track_quat("-Z", "Y").to_euler()
    plan.kamery.append({"nazwa": nazwa, "obiektyw_mm": obiektyw, "polozenie": list(polozenie), "cel": list(cel), "uzycie": uzycie})
    return o


def znacznik(plan: Plan, nazwa, polozenie, obrot_z=0.0, opis=""):
    """Pusty obiekt: miejsce postaci (z = poziom oczu albo siedziska, podany w opisie)."""
    e = bpy.data.objects.new(nazwa, None)
    e.empty_display_type = "SINGLE_ARROW"
    e.empty_display_size = 0.4
    e.location = Vector(polozenie)
    e.rotation_euler = Euler((0, 0, math.radians(obrot_z)))
    _kolekcja("znaczniki").objects.link(e)
    plan.znaczniki.append({"nazwa": nazwa, "polozenie": list(polozenie), "obrot_z": obrot_z, "opis": opis})
    return e


# ---------------------------------------------------------------- render
def _mat_glebia():
    m = bpy.data.materials.get("_glebia") or bpy.data.materials.new("_glebia")
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    cd = nt.nodes.new("ShaderNodeCameraData")
    em = nt.nodes.new("ShaderNodeEmission")
    nt.links.new(cd.outputs["View Distance"], em.inputs["Color"])
    nt.links.new(em.outputs[0], out.inputs[0])
    return m


def _render_glebia(png):
    """Druga, szybka klatka: każda powierzchnia świeci swoją odległością od kamery (m) → 16-bit PNG w mm."""
    import numpy as np
    import OpenEXR
    from PIL import Image

    sc = bpy.context.scene
    vl = sc.view_layers[0]
    stan = (vl.material_override, sc.world, sc.cycles.samples, sc.cycles.use_denoising, sc.cycles.max_bounces,
            sc.cycles.filter_width, sc.view_settings.view_transform, sc.view_settings.exposure, sc.cycles.use_adaptive_sampling)
    czarny = bpy.data.worlds.get("_czarny") or bpy.data.worlds.new("_czarny")
    czarny.use_nodes = False
    czarny.color = (0, 0, 0)
    vl.material_override = _mat_glebia()
    sc.world = czarny
    sc.cycles.samples, sc.cycles.use_denoising, sc.cycles.max_bounces, sc.cycles.filter_width = 1, False, 0, 0.01
    sc.cycles.use_adaptive_sampling = False
    sc.view_settings.view_transform, sc.view_settings.exposure = "Standard", 0.0
    ukryte = [o for o in sc.objects if o.type == "LIGHT"]
    try:
        bpy.ops.render.render(write_still=False)
        s = sc.render.image_settings
        s.media_type, s.file_format, s.color_depth = "IMAGE", "OPEN_EXR", "32"
        exr = png[:-4] + "_tmp.exr"
        bpy.data.images["Render Result"].save_render(exr, scene=sc)
        with OpenEXR.File(exr) as f:
            ch = f.channels()
            k = next(k for k in ch if k in ("R", "RGB", "RGBA") or k.endswith(".R"))
            z = np.array(ch[k].pixels, dtype=np.float32)
        os.remove(exr)
        if z.ndim == 3:
            z = z[..., 0]
        z = np.where(z <= 0, 65.535, z)
        im = Image.fromarray(np.clip(z * 1000.0, 0, 65535).astype(np.uint16))
        im.resize((im.width // 2, im.height // 2), Image.NEAREST).save(png)
    finally:
        (vl.material_override, sc.world, sc.cycles.samples, sc.cycles.use_denoising, sc.cycles.max_bounces,
         sc.cycles.filter_width, sc.view_settings.view_transform, sc.view_settings.exposure, sc.cycles.use_adaptive_sampling) = stan
        sc.render.image_settings.media_type = "IMAGE"


def render_stille(plan: Plan, wariant: str, kamery=None, probki=None, glebia=True):
    sc = bpy.context.scene
    if probki:
        sc.cycles.samples = probki
    kat = os.path.join(RENDERY, plan.kod)
    tmp = os.path.join(RENDERY, "_tmp")
    os.makedirs(kat, exist_ok=True)
    os.makedirs(tmp, exist_ok=True)
    czasy = {}
    for k in plan.kamery:
        if kamery and k["nazwa"] not in kamery:
            continue
        sc.camera = bpy.data.objects[k["nazwa"]]
        t = time.time()
        bpy.ops.render.render(write_still=False)
        img = bpy.data.images["Render Result"]
        sc.render.image_settings.media_type = "IMAGE"
        sc.render.image_settings.file_format = "JPEG"
        sc.render.image_settings.quality = 90
        jpg = os.path.join(kat, f"{k['nazwa']}_{wariant}.jpg")
        img.save_render(jpg, scene=sc)
        if glebia:
            _render_glebia(os.path.join(kat, f"{k['nazwa']}_{wariant}_glebia.png"))
        czasy[k["nazwa"]] = round(time.time() - t, 1)
        print(f"[{plan.kod}] {k['nazwa']} {wariant}: {czasy[k['nazwa']]} s", flush=True)
    return czasy


def piksele_znacznikow(plan: Plan):
    sc = bpy.context.scene
    wynik = {}
    for k in plan.kamery:
        cam = bpy.data.objects[k["nazwa"]]
        d = {}
        for z in plan.znaczniki:
            v = world_to_camera_view(sc, cam, Vector(z["polozenie"]))
            if v.z > 0 and 0 <= v.x <= 1 and 0 <= v.y <= 1:
                d[z["nazwa"]] = [round(v.x * SZER), round((1 - v.y) * WYS)]
        wynik[k["nazwa"]] = d
    return wynik


def render_ruch(plan: Plan, kamera_nazwa, cel_koncowy, sekundy=3.0, fps=24, procent=50, probki=12, wariant="dzien"):
    """Powolny najazd kamery (prawdziwa paralaksa) → MP4. cel_koncowy: położenie kamery na końcu."""
    sc = bpy.context.scene
    cam = bpy.data.objects[kamera_nazwa]
    p0 = cam.location.copy()
    p1 = Vector(cel_koncowy)
    n = int(sekundy * fps)
    sc.frame_start, sc.frame_end = 1, n
    sc.render.fps = fps
    cam.location = p0
    cam.keyframe_insert("location", frame=1)
    cam.location = p1
    cam.keyframe_insert("location", frame=n)
    if cam.animation_data and cam.animation_data.action:
        try:
            for fc in cam.animation_data.action.fcurves:
                for kp in fc.keyframe_points:
                    kp.interpolation = "BEZIER"
                    kp.easing = "EASE_IN_OUT"
        except AttributeError:
            pass
    sc.camera = cam
    stare = (sc.render.resolution_percentage, sc.cycles.samples)
    sc.render.resolution_percentage = procent
    sc.cycles.samples = probki
    tmp = os.path.join(RENDERY, "_tmp", f"{plan.kod}_ruch")
    shutil.rmtree(tmp, ignore_errors=True)
    os.makedirs(tmp)
    sc.render.image_settings.media_type = "IMAGE"
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_depth = "8"
    sc.render.filepath = os.path.join(tmp, "k_")
    t = time.time()
    bpy.ops.render.render(animation=True)
    czas = round(time.time() - t, 1)
    mp4 = os.path.join(RENDERY, plan.kod, f"ruch_{kamera_nazwa}_{wariant}.mp4")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(fps), "-i", os.path.join(tmp, "k_%04d.png"),
                    "-c:v", "libx264", "-crf", "20", "-pix_fmt", "yuv420p", "-movflags", "+faststart", mp4], check=True)
    shutil.rmtree(tmp, ignore_errors=True)
    sc.render.resolution_percentage, sc.cycles.samples = stare
    cam.animation_data_clear()
    cam.location = p0
    print(f"[{plan.kod}] ruch {kamera_nazwa}: {czas} s ({n} klatek)", flush=True)
    return {"plik": os.path.basename(mp4), "klatki": n, "fps": fps, "rozdzielczosc": [SZER * procent // 100, WYS * procent // 100], "czas_s": czas}


def zapisz_opis(plan: Plan, czasy: dict, ruch: dict | None):
    kat = os.path.join(RENDERY, plan.kod)
    os.makedirs(kat, exist_ok=True)
    stary = {}
    p = os.path.join(kat, "opis.json")
    if os.path.exists(p):
        stary = json.load(open(p, encoding="utf-8"))
    opis = {
        "kod": plan.kod,
        "nazwa": plan.nazwa,
        "rozdzielczosc": [SZER, WYS],
        "jednostki": "metry; mapa głębi: 16-bit PNG w połowie rozdzielczości (540x960), wartość = odległość od kamery w mm (65535 = tło/niebo)",
        "kamery": plan.kamery,
        "znaczniki": plan.znaczniki,
        "znaczniki_w_kadrze_px": piksele_znacznikow(plan),
        "warianty": sorted(set(stary.get("warianty", [])) | set(czasy)),
        "czasy_renderu_s": {**stary.get("czasy_renderu_s", {}), **czasy},
        "ruch": ruch or stary.get("ruch"),
    }
    json.dump(opis, open(p, "w", encoding="utf-8"), indent=1, ensure_ascii=False)


def zapisz_blend(plan: Plan):
    os.makedirs(os.path.join(TU, "blend"), exist_ok=True)
    p = os.path.join(TU, "blend", f"{plan.kod}.blend")
    bpy.ops.wm.save_as_mainfile(filepath=p, compress=True, relative_remap=True)
    return p


def regal_akt(nazwa, x0, y0, szer, wys=2.2, polki=5, gl=0.36, wzdluz_x=True, mat=None, wypelnienie=0.85):
    """Regał z półkami wypełnionymi segregatorami (gładkie grzbiety). wzdluz_x: regał stoi przy ścianie N/S."""
    mat = mat or tekstura("regal_dab", "oak_veneer_01", skala=1.0, jasnosc=0.85)
    deska = 0.025
    if wzdluz_x:
        skrzynka(f"{nazwa}_bokL", (deska, gl, wys), (x0 + deska / 2, y0, wys / 2), mat, kolekcja="meble")
        skrzynka(f"{nazwa}_bokP", (deska, gl, wys), (x0 + szer - deska / 2, y0, wys / 2), mat, kolekcja="meble")
        skrzynka(f"{nazwa}_plecy", (szer, 0.01, wys), (x0 + szer / 2, y0 + gl / 2 * (1 if y0 > 1 else -1), wys / 2), mat, kolekcja="meble")
    else:
        skrzynka(f"{nazwa}_bokL", (gl, deska, wys), (x0, y0 + deska / 2, wys / 2), mat, kolekcja="meble")
        skrzynka(f"{nazwa}_bokP", (gl, deska, wys), (x0, y0 + szer - deska / 2, wys / 2), mat, kolekcja="meble")
        skrzynka(f"{nazwa}_plecy", (0.01, szer, wys), (x0 + gl / 2 * (1 if x0 > 1 else -1), y0 + szer / 2, wys / 2), mat, kolekcja="meble")
    for i in range(polki + 1):
        z = 0.08 + i * (wys - 0.1) / polki
        if wzdluz_x:
            skrzynka(f"{nazwa}_polka{i}", (szer, gl, deska), (x0 + szer / 2, y0, z), mat, kolekcja="meble")
        else:
            skrzynka(f"{nazwa}_polka{i}", (gl, szer, deska), (x0, y0 + szer / 2, z), mat, kolekcja="meble")
        if i < polki:
            dl = (szer - 0.06) * wypelnienie * (0.7 + 0.3 * ((i * 37) % 10) / 10)
            ile = int(dl / 0.075)
            h = min(0.32, (wys - 0.1) / polki - 0.05)
            if wzdluz_x:
                segregatory(f"{nazwa}_seg{i}", (x0 + 0.04, y0, z + deska / 2), True, ile, wys=h, gl=gl * 0.8)
            else:
                segregatory(f"{nazwa}_seg{i}", (x0, y0 + 0.04, z + deska / 2), False, ile, wys=h, gl=gl * 0.8)


def dywan(nazwa, srodek, szer, dl, tex_id="denim_fabric", odcien=(0.3, 0.22, 0.2), obrot_z=0.0):
    m = kolor(f"dywan_{nazwa}", odcien, 0.95, polysk=0.1, normal_tex="fabric_pattern_05", skala=3.0, sila_normal=0.6)
    return skrzynka(nazwa, (szer, dl, 0.012), (srodek[0], srodek[1], 0.006), m, obrot_z=obrot_z, kolekcja="rekwizyty_wlasne", fazka=0.004)


def _grupa(nazwa, polozenie, obrot_z, elementy):
    piv = bpy.data.objects.new(nazwa, None)
    _kolekcja("rekwizyty_wlasne").objects.link(piv)
    for o in elementy:
        o.parent = piv
    piv.location = Vector(polozenie)
    piv.rotation_euler = Euler((0, 0, math.radians(obrot_z)))
    return piv


def biurko(nazwa, polozenie, szer=1.4, gl=0.7, obrot_z=0.0, mat_blat=None, mat_nogi=None, wys=0.75, szafka=True):
    """Biurko: blat na metalowych nogach, opcjonalnie kontener z szufladami (lokalnie: przód biurka to -y)."""
    mat_blat = mat_blat or kolor("blat_bialy", (0.88, 0.87, 0.84), 0.35)
    mat_nogi = mat_nogi or kolor("nogi_grafit", (0.08, 0.08, 0.09), 0.4, metal=0.6)
    el = [skrzynka(f"{nazwa}_blat", (szer, gl, 0.03), (0, 0, wys - 0.015), mat_blat, kolekcja="meble", fazka=0.003)]
    for i, (x, y) in enumerate(((-szer / 2 + 0.05, -gl / 2 + 0.05), (szer / 2 - 0.05, -gl / 2 + 0.05), (-szer / 2 + 0.05, gl / 2 - 0.05), (szer / 2 - 0.05, gl / 2 - 0.05))):
        el.append(skrzynka(f"{nazwa}_noga{i}", (0.04, 0.04, wys - 0.03), (x, y, (wys - 0.03) / 2), mat_nogi, kolekcja="meble"))
    el.append(skrzynka(f"{nazwa}_blenda", (szer - 0.1, 0.015, 0.35), (0, gl / 2 - 0.04, wys - 0.2), mat_blat, kolekcja="meble"))
    if szafka:
        el.append(skrzynka(f"{nazwa}_kontener", (0.42, 0.55, 0.58), (szer / 2 - 0.3, 0.0, 0.31), mat_blat, kolekcja="meble", fazka=0.004))
        for j in range(3):
            el.append(skrzynka(f"{nazwa}_uchwyt{j}", (0.14, 0.015, 0.012), (szer / 2 - 0.3, -0.283, 0.5 - j * 0.18), mat_nogi, kolekcja="meble"))
    return _grupa(nazwa, polozenie, obrot_z, el)


def drukarka(nazwa, polozenie, obrot_z=0.0):
    m = kolor("drukarka", (0.82, 0.82, 0.8), 0.45)
    c = kolor("drukarka_ciemna", (0.1, 0.1, 0.11), 0.5)
    el = [skrzynka(f"{nazwa}_korpus", (0.46, 0.4, 0.3), (0, 0, 0.15), m, kolekcja="rekwizyty_wlasne", fazka=0.01),
          skrzynka(f"{nazwa}_skaner", (0.46, 0.38, 0.06), (0, 0.01, 0.33), c, kolekcja="rekwizyty_wlasne", fazka=0.006),
          skrzynka(f"{nazwa}_tacka", (0.3, 0.16, 0.012), (0, -0.25, 0.12), m, kolekcja="rekwizyty_wlasne"),
          skrzynka(f"{nazwa}_kartka", (0.21, 0.15, 0.002), (0, -0.25, 0.128), kolor("papier", (0.92, 0.92, 0.9), 0.8, polysk=0.2), kolekcja="rekwizyty_wlasne")]
    return _grupa(nazwa, polozenie, obrot_z, el)


def zegar_scienny(nazwa, srodek, normal="S", godz=8, minuty=57, r=0.17):
    """Zegar bez cyfr: tarcza, 12 kresek, wskazówki ustawione na podaną godzinę (domyślnie 8:57)."""
    tarcza = kolor("tarcza", (0.92, 0.91, 0.88), 0.6)
    czarny = kolor("wskazowki", (0.03, 0.03, 0.03), 0.4)
    el = [walec(f"{nazwa}_obudowa", r + 0.015, 0.04, (0, 0, 0), czarny), walec(f"{nazwa}_tarcza", r, 0.042, (0, 0, 0), tarcza)]
    for i in range(12):
        a = math.radians(i * 30)
        dl = 0.035 if i % 3 == 0 else 0.02
        k = skrzynka(f"{nazwa}_kreska{i}", (0.008, dl, 0.002), (math.sin(a) * (r - 0.03), math.cos(a) * (r - 0.03), 0.022), czarny, kolekcja="rekwizyty_wlasne")
        k.rotation_euler = Euler((0, 0, -a))
        el.append(k)
    for n, kat, dl, gr in (("min", minuty * 6, r * 0.85, 0.008), ("godz", (godz % 12) * 30 + minuty * 0.5, r * 0.55, 0.012)):
        a = math.radians(kat)
        k = skrzynka(f"{nazwa}_{n}", (gr, dl, 0.003), (math.sin(a) * dl / 2, math.cos(a) * dl / 2, 0.025 + (0.003 if n == "min" else 0)), czarny, kolekcja="rekwizyty_wlasne")
        k.rotation_euler = Euler((0, 0, -a))
        el.append(k)
    piv = bpy.data.objects.new(nazwa, None)
    _kolekcja("rekwizyty_wlasne").objects.link(piv)
    for o in el:
        o.parent = piv
    piv.location = Vector(srodek)
    # normal = kierunek, w który patrzy tarcza (S: -y, N: +y, W: -x, E: +x)
    obr = {"S": (math.radians(90), 0, 0), "N": (math.radians(90), 0, math.radians(180)), "W": (math.radians(90), 0, math.radians(-90)), "E": (math.radians(90), 0, math.radians(90))}[normal]
    piv.rotation_euler = Euler(obr)
    return piv


def lada(nazwa, polozenie, szer=2.0, gl=0.75, obrot_z=0.0, mat=None, mat_blat=None):
    """Lada recepcji: wysoki front 1,1 m od strony klienta (lokalnie -y), blat roboczy 0,75 m za nim."""
    mat = mat or tekstura("lada_dab", "oak_veneer_01", skala=1.0, jasnosc=0.9)
    mat_blat = mat_blat or kolor("blat_bialy", (0.88, 0.87, 0.84), 0.35)
    el = [skrzynka(f"{nazwa}_front", (szer, 0.06, 1.1), (0, -gl / 2, 0.55), mat, kolekcja="meble"),
          skrzynka(f"{nazwa}_polka_klienta", (szer + 0.04, 0.3, 0.03), (0, -gl / 2 - 0.05, 1.115), mat_blat, kolekcja="meble", fazka=0.004),
          skrzynka(f"{nazwa}_blat", (szer, gl, 0.03), (0, 0, 0.735), mat_blat, kolekcja="meble"),
          skrzynka(f"{nazwa}_bok", (0.05, gl, 1.1), (szer / 2, 0, 0.55), mat, kolekcja="meble"),
          skrzynka(f"{nazwa}_cokol", (szer, 0.04, 0.1), (0, -gl / 2 - 0.02, 0.05), kolor("nogi_grafit", (0.08, 0.08, 0.09), 0.4, metal=0.6), kolekcja="meble")]
    return _grupa(nazwa, polozenie, obrot_z, el)


def wieszak(nazwa, polozenie):
    m = kolor("nogi_grafit", (0.08, 0.08, 0.09), 0.4, metal=0.6)
    el = [walec(f"{nazwa}_slup", 0.02, 1.75, (0, 0, 0.875), m), walec(f"{nazwa}_stopa", 0.22, 0.02, (0, 0, 0.01), m)]
    plaszcz = kolor("plaszcz", (0.12, 0.13, 0.16), 0.85, polysk=0.2)
    el.append(skrzynka(f"{nazwa}_plaszcz", (0.38, 0.14, 0.9), (0.1, 0, 1.25), plaszcz, kolekcja="rekwizyty_wlasne", fazka=0.05))
    return _grupa(nazwa, polozenie, 0, el)


def schody(nazwa, x0, x1, y0, kier_y, z0, stopnie, wznios=0.17, glebokosc=0.28, mat=None, mat_pion=None, porecz_x=None, mat_porecz=None):
    """Bieg schodów wzdłuż osi y: od (y0, z0) w kierunku kier_y (+1/-1), w górę (wznios>0) albo w dół (wznios<0).
    porecz_x: współrzędna x balustrady (np. od strony duszy klatki)."""
    mat = mat or tekstura("stopnie", "terrazzo_tiles", skala=1.2, sila_normal=0.2)
    mat_pion = mat_pion or kolor("podstopnica", (0.62, 0.6, 0.55), 0.6)
    szer = x1 - x0
    for i in range(stopnie):
        y = y0 + kier_y * (i + 0.5) * glebokosc
        z_top = z0 + (i + 1) * wznios if wznios > 0 else z0 + i * wznios
        h = abs(wznios) * (i + 1) if wznios > 0 else 0.0
        if wznios > 0:
            skrzynka(f"{nazwa}_st{i}", (szer, glebokosc + 0.02, 0.04), ((x0 + x1) / 2, y, z_top - 0.02), mat, kolekcja="schody")
            skrzynka(f"{nazwa}_pion{i}", (szer, 0.02, wznios), ((x0 + x1) / 2, y - kier_y * glebokosc / 2, z_top - wznios / 2), mat_pion, kolekcja="schody")
            skrzynka(f"{nazwa}_pod{i}", (szer, glebokosc, max(0.05, z_top - 0.04 - z0)), ((x0 + x1) / 2, y, z0 + max(0.05, z_top - 0.04 - z0) / 2), mat_pion, kolekcja="schody")
        else:
            zt = z0 + (i + 1) * wznios
            skrzynka(f"{nazwa}_st{i}", (szer, glebokosc + 0.02, 0.04), ((x0 + x1) / 2, y, zt - 0.02), mat, kolekcja="schody")
            skrzynka(f"{nazwa}_pion{i}", (szer, 0.02, -wznios), ((x0 + x1) / 2, y - kier_y * glebokosc / 2, zt - wznios / 2), mat_pion, kolekcja="schody")
    if porecz_x is not None:
        mat_porecz = mat_porecz or tekstura("porecz", "dark_wood", skala=2.0, szorstkosc_mnoz=0.6)
        zelazo = kolor("tralki", (0.06, 0.06, 0.06), 0.4, metal=0.7)
        dl = stopnie * glebokosc
        dz = stopnie * wznios
        for i in range(stopnie * 2 + 1):
            t = i / (stopnie * 2)
            y = y0 + kier_y * t * dl
            zb = z0 + t * dz
            skrzynka(f"{nazwa}_tralka{i}", (0.02, 0.02, 0.92), (porecz_x, y, zb + 0.46), zelazo, kolekcja="schody")
        dlug = math.hypot(dl, dz)
        p = skrzynka(f"{nazwa}_porecz", (0.06, dlug, 0.05), (porecz_x, y0 + kier_y * dl / 2, z0 + dz / 2 + 0.94), mat_porecz, kolekcja="schody", fazka=0.01)
        p.rotation_euler = Euler((math.atan2(dz, dl) * kier_y, 0, 0))


def stolik_bistro(nazwa, polozenie, r=0.32, wys=0.75, mat_blat=None):
    mat_blat = mat_blat or kolor("marmur_jasny", (0.86, 0.85, 0.82), 0.18, polysk=0.6, normal_tex="marble_tiles", skala=0.3, sila_normal=0.03)
    zel = kolor("zeliwo", (0.05, 0.05, 0.05), 0.4, metal=0.8)
    el = [walec(f"{nazwa}_blat", r, 0.025, (0, 0, wys - 0.0125), mat_blat, 40),
          walec(f"{nazwa}_noga", 0.03, wys - 0.04, (0, 0, (wys - 0.04) / 2), zel),
          walec(f"{nazwa}_stopa", 0.22, 0.02, (0, 0, 0.01), zel)]
    return _grupa(nazwa, polozenie, 0, el)


def krzeslo_bistro(nazwa, polozenie, obrot_z=0.0, mat=None):
    """Krzesło kawiarniane: siedzisko, 4 nogi, oparcie (lokalnie przód = -y)."""
    mat = mat or tekstura("krzeslo_buk", "oak_veneer_01", skala=2.0, odcien=(0.45, 0.28, 0.16), szorstkosc_mnoz=0.6)
    el = [walec(f"{nazwa}_siedzisko", 0.21, 0.03, (0, 0, 0.46), mat, 32)]
    for i, (x, y) in enumerate(((-0.15, -0.15), (0.15, -0.15), (-0.15, 0.15), (0.15, 0.15))):
        el.append(walec(f"{nazwa}_noga{i}", 0.014, 0.45, (x, y, 0.225), mat, 12))
    el.append(skrzynka(f"{nazwa}_oparcie", (0.38, 0.03, 0.12), (0, 0.18, 0.82), mat, kolekcja="rekwizyty_wlasne", fazka=0.01))
    for i, x in enumerate((-0.16, 0.16)):
        el.append(walec(f"{nazwa}_szczebel{i}", 0.012, 0.4, (x, 0.18, 0.66), mat, 12))
    return _grupa(nazwa, polozenie, obrot_z, el)


def firanka(nazwa, os_, stala, a, b, dol, gora, strona_wew=-1):
    """Półprzezroczysta firanka w oknie (jasna tkanina, światło przechodzi)."""
    m = bpy.data.materials.get("firanka") or bpy.data.materials.new("firanka")
    nt, bs, out = _wezly(m)
    bs.inputs["Base Color"].default_value = (0.95, 0.94, 0.9, 1)
    bs.inputs["Roughness"].default_value = 0.9
    bs.inputs["Transmission Weight"].default_value = 0.0
    tr = nt.nodes.new("ShaderNodeBsdfTranslucent")
    tr.inputs["Color"].default_value = (0.95, 0.94, 0.9, 1)
    przez = nt.nodes.new("ShaderNodeBsdfTransparent")
    mix1 = nt.nodes.new("ShaderNodeMixShader")
    mix1.inputs[0].default_value = 0.4
    nt.links.new(bs.outputs[0], mix1.inputs[1])
    nt.links.new(tr.outputs[0], mix1.inputs[2])
    mix2 = nt.nodes.new("ShaderNodeMixShader")
    mix2.inputs[0].default_value = 0.45
    nt.links.new(mix1.outputs[0], mix2.inputs[1])
    nt.links.new(przez.outputs[0], mix2.inputs[2])
    nt.links.new(mix2.outputs[0], out.inputs[0])
    sr, h = (a + b) / 2, gora - dol
    if os_ == "x":
        return plaszczyzna(nazwa, b - a + 0.2, h + 0.15, (sr, stala + strona_wew * 0.18, dol + h / 2 + 0.05), (90, 0, 0), m, kolekcja="okna")
    return plaszczyzna(nazwa, h + 0.15, b - a + 0.2, (stala + strona_wew * 0.18, sr, dol + h / 2 + 0.05), (0, 90, 0), m, kolekcja="okna")


def samochod(nazwa, polozenie, obrot_z=0.0, kolor_rgb=(0.08, 0.1, 0.14)):
    """Uogólniony samochód osobowy bez marki i bez tablic z tekstem (tablica gładka). Przód = +x lokalnie."""
    lak = bpy.data.materials.get(f"lakier_{kolor_rgb}") or bpy.data.materials.new(f"lakier_{kolor_rgb}")
    nt, b, _ = _wezly(lak)
    b.inputs["Base Color"].default_value = (*kolor_rgb, 1)
    b.inputs["Metallic"].default_value = 0.6
    b.inputs["Roughness"].default_value = 0.18
    b.inputs["Coat Weight"].default_value = 1.0
    b.inputs["Coat Roughness"].default_value = 0.03
    szk = kolor("szyba_auto", (0.02, 0.025, 0.03), 0.05, polysk=1.0)
    opona = kolor("opona", (0.03, 0.03, 0.03), 0.8)
    felga = kolor("felga", (0.55, 0.56, 0.58), 0.25, metal=1.0)
    chrom = kolor("lampa_auta", (0.9, 0.9, 0.9), 0.05, polysk=1.0)
    tyl_sw = kolor("swiatlo_tyl", (0.4, 0.02, 0.02), 0.2)
    tab = kolor("tablica", (0.85, 0.85, 0.85), 0.5)
    el = [skrzynka(f"{nazwa}_dol", (4.5, 1.8, 0.62), (0, 0, 0.55), lak, kolekcja="auto", fazka=0.12),
          skrzynka(f"{nazwa}_kabina", (2.4, 1.6, 0.55), (-0.25, 0, 1.12), lak, kolekcja="auto", fazka=0.16),
          skrzynka(f"{nazwa}_szyba_p", (0.05, 1.42, 0.42), (0.98, 0, 1.12), szk, kolekcja="auto"),
          skrzynka(f"{nazwa}_szyba_t", (0.05, 1.42, 0.4), (-1.47, 0, 1.12), szk, kolekcja="auto"),
          skrzynka(f"{nazwa}_szyby_bok", (2.1, 1.62, 0.36), (-0.25, 0, 1.15), szk, kolekcja="auto"),
          skrzynka(f"{nazwa}_lampa_l", (0.04, 0.35, 0.1), (2.25, 0.6, 0.68), chrom, kolekcja="auto"),
          skrzynka(f"{nazwa}_lampa_p", (0.04, 0.35, 0.1), (2.25, -0.6, 0.68), chrom, kolekcja="auto"),
          skrzynka(f"{nazwa}_tyl_l", (0.04, 0.3, 0.1), (-2.25, 0.62, 0.72), tyl_sw, kolekcja="auto"),
          skrzynka(f"{nazwa}_tyl_p", (0.04, 0.3, 0.1), (-2.25, -0.62, 0.72), tyl_sw, kolekcja="auto"),
          skrzynka(f"{nazwa}_tablica_p", (0.02, 0.52, 0.11), (2.26, 0, 0.42), tab, kolekcja="auto"),
          skrzynka(f"{nazwa}_tablica_t", (0.02, 0.52, 0.11), (-2.26, 0, 0.5), tab, kolekcja="auto")]
    for i, (x, y) in enumerate(((1.45, 0.82), (1.45, -0.82), (-1.4, 0.82), (-1.4, -0.82))):
        o = walec(f"{nazwa}_kolo{i}", 0.33, 0.22, (x, y, 0.33), opona, 32, kolekcja="auto")
        o.rotation_euler = Euler((math.radians(90), 0, 0))
        f = walec(f"{nazwa}_felga{i}", 0.2, 0.235, (x, y, 0.33), felga, 24, kolekcja="auto")
        f.rotation_euler = Euler((math.radians(90), 0, 0))
        el += [o, f]
    for i, y in enumerate((0.95, -0.95)):
        el.append(skrzynka(f"{nazwa}_lusterko{i}", (0.12, 0.12, 0.09), (0.8, y, 1.0), lak, kolekcja="auto", fazka=0.03))
    return _grupa(nazwa, polozenie, obrot_z, el)


def fotel_biurowy(nazwa, polozenie, obrot_z=0.0, kolor_rgb=(0.05, 0.05, 0.06)):
    """Krzesło biurowe: podstawa pięcioramienna, kolumna, siedzisko i oparcie z tapicerką (przód = -y lokalnie)."""
    tap = kolor(f"tapicerka_{kolor_rgb}", kolor_rgb, 0.85, polysk=0.2, normal_tex="fabric_pattern_05", skala=6.0, sila_normal=0.3)
    plast = kolor("plastik_czarny", (0.03, 0.03, 0.03), 0.4)
    chrom = kolor("chrom", (0.7, 0.7, 0.72), 0.15, metal=1.0)
    el = []
    for i in range(5):
        a = math.radians(i * 72)
        r = skrzynka(f"{nazwa}_ramie{i}", (0.04, 0.3, 0.03), (math.sin(a) * 0.15, math.cos(a) * 0.15, 0.07), plast, kolekcja="rekwizyty_wlasne")
        r.rotation_euler = Euler((0, 0, -a))
        el.append(r)
        el.append(walec(f"{nazwa}_kolko{i}", 0.025, 0.03, (math.sin(a) * 0.3, math.cos(a) * 0.3, 0.025), plast, 12))
    el.append(walec(f"{nazwa}_kolumna", 0.025, 0.32, (0, 0, 0.24), chrom, 16))
    el.append(skrzynka(f"{nazwa}_siedzisko", (0.5, 0.48, 0.08), (0, 0, 0.46), tap, kolekcja="rekwizyty_wlasne", fazka=0.03))
    op = skrzynka(f"{nazwa}_oparcie", (0.46, 0.07, 0.58), (0, 0.25, 0.83), tap, kolekcja="rekwizyty_wlasne", fazka=0.03)
    op.rotation_euler = Euler((math.radians(-8), 0, 0))
    el.append(op)
    el.append(skrzynka(f"{nazwa}_wspornik", (0.06, 0.04, 0.3), (0, 0.24, 0.55), plast, kolekcja="rekwizyty_wlasne"))
    for i, x in enumerate((-0.27, 0.27)):
        el.append(skrzynka(f"{nazwa}_podlokietnik{i}", (0.05, 0.28, 0.03), (x, 0.03, 0.67), plast, kolekcja="rekwizyty_wlasne", fazka=0.01))
        el.append(skrzynka(f"{nazwa}_podl_noga{i}", (0.03, 0.03, 0.2), (x, 0.1, 0.57), plast, kolekcja="rekwizyty_wlasne"))
    return _grupa(nazwa, polozenie, obrot_z, el)
