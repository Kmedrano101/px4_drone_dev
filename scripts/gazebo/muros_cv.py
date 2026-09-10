#!/usr/bin/env /usr/bin/python3
# -*- coding: utf-8 -*-
"""
Reconstruye paredes y suelo del entorno indoor a partir de la NUBE, con OpenCV.

Por que este script y no el straighten_walls.py anterior:

    El anterior partia de la malla ya exportada y le enderezaba los muros. Pero
    esa malla venia de una exportacion vieja y RECORTADA: le faltaba entero el
    brazo inferior derecho del edificio (medido: le faltan X 3.1..6.5 e
    Y -28.0..-22.4 respecto a la nube). Enderezar una planta incompleta no la
    completa. Hay que volver a la nube.

Aqui la planta sale del pavimento con el mismo metodo del pipeline
(banda a cota de suelo -> raster -> cierre morfologico -> findContours), que da
un poligono cerrado por construccion, y despues se ENDEREZA:

    1. approxPolyDP reduce el contorno a segmentos rectos.
    2. Cada segmento se reajusta por minimos cuadrados totales sobre los puntos
       de contorno que le tocan (no sobre los dos extremos: un extremo mal
       puesto giraria la pared entera).
    3. Los angulos se agrupan en familias con tolerancia angular y cada segmento
       adopta el angulo medio de su familia, ponderado por longitud. NO se fuerza
       una retícula global: este edificio tiene dos alas giradas ~30 grados entre
       si, y forzar dos direcciones ortogonales destruiria una de las dos.
    4. Las rectas consecutivas se cortan entre si -> esquinas limpias.

El suelo se rehace con ESA misma planta (el usuario lo pidio: "ajusta el suelo a
las nuevas paredes"), asi que suelo y muros comparten contorno por construccion
y no puede haber suelo asomando fuera de la pared ni al reves.

El marco de coordenadas se conserva: la nube se traslada por OFFSET, obtenido
registrando por correlacion la malla vieja contra la nueva planta. Asi las
columnas, el mundo y el punto de aparicion del dron siguen donde estaban.

    /usr/bin/python3 muros_cv.py            # necesita cv2 + open3d + trimesh
"""

import os
import struct
import sys

import numpy as np
import cv2
import open3d as o3d
import trimesh
from shapely.geometry import Polygon

# ---------------------------------------------------------------- parametros
PLY = "/home/kmedrano/src/3d_modeling/IndoorZone/Indoor_clean_less_dense.ply"
OUT = ("/home/kmedrano/src/3d_modeling/IndoorZone/scan2bim/output/gazebo/"
       "indoor_clean_less_dense/meshes")
BASE = "indoor_clean_less_dense"

PIXEL = 0.05          # m/px del raster en planta
BANDA_BAJO = 0.15     # banda de puntos alrededor de la cota de suelo
BANDA_ALTO = 0.25
CIERRE = 0.60         # radio del cierre morfologico (sombras del escaner)

EPS_DP = 0.30         # tolerancia de approxPolyDP, en metros
TOL_ANG = 8.0         # grados: dos segmentos son de la misma familia
LADO_MIN = 0.90       # segmentos mas cortos se absorben en sus vecinos

MURO_H = 2.50         # altura de pared
MURO_T = 0.15         # espesor
SUELO_T = 0.10        # espesor de la losa
TEX_MURO = 2.0        # metros por repeticion de ladrillo.png
TEX_SUELO = 1.0       # baldosa.png es un parche de 1 m

# Traslacion nube -> marco del modelo. Ver registrar() mas abajo: se recalcula
# contra la malla vieja para no mover columnas ni punto de despegue del dron.
OFFSET = np.array([7.806, 5.897])

# Las 9 medidas que el usuario tomo sobre la nube real. Son el criterio de
# aceptacion: al final se comprueba cada una contra la planta reconstruida.
MEDIDAS = [
    ("08-26-35", 13.515519,  11.869571,  -6.463048),
    ("08-26-53",  8.062910,  -5.570658,  -5.828075),
    ("08-27-09", 20.838687,  14.347978, -15.112348),
    ("08-39-13", 18.103068,   8.634177,  15.906898),
    ("08-57-06", 13.423388, -11.663732,  -6.643953),
    ("08-57-55",  7.290874,  -6.187666,  -3.850365),
    ("08-58-07", 11.401913,  -8.429264,   7.677956),
    ("09-20-28",  2.268494,   1.622377,   1.585481),
    ("09-20-37",  8.881556,   5.347342,  -7.090507),
]


def log(*a):
    print(*a, flush=True)


# ---------------------------------------------------------------- planta
def planta():
    """Contorno exterior del pavimento, en coordenadas de la nube."""
    pts = np.asarray(o3d.io.read_point_cloud(PLY).points)
    h, e = np.histogram(pts[:, 2], bins=400)
    z0 = 0.5 * (e[h.argmax()] + e[h.argmax() + 1])
    banda = pts[(pts[:, 2] >= z0 - BANDA_BAJO) & (pts[:, 2] <= z0 + BANDA_ALTO)]
    log(f"nube {len(pts):,} pts, cota de suelo z={z0:.3f}, banda {len(banda):,} pts")

    mins = banda[:, :2].min(0)
    w = int(np.ceil((banda[:, 0].max() - mins[0]) / PIXEL)) + 3
    h_ = int(np.ceil((banda[:, 1].max() - mins[1]) / PIXEL)) + 3
    img = np.zeros((h_, w), np.uint8)
    img[np.clip(((banda[:, 1] - mins[1]) / PIXEL).astype(int) + 1, 0, h_ - 1),
        np.clip(((banda[:, 0] - mins[0]) / PIXEL).astype(int) + 1, 0, w - 1)] = 255

    def disco(r):
        k = max(3, int(round(2 * r / PIXEL)) | 1)
        return cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))

    solido = cv2.morphologyEx(img, cv2.MORPH_CLOSE, disco(CIERRE))
    solido = cv2.dilate(solido, disco(PIXEL * 1.5))
    # Rellenar el interior: solo interesa el borde exterior del recinto. Los
    # huecos del pavimento son sombras del recorrido de escaneo, no obstaculos.
    cnts, _ = cv2.findContours(solido, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    c = max(cnts, key=cv2.contourArea)
    lleno = np.zeros_like(solido)
    cv2.fillPoly(lleno, [c], 255)
    log(f"raster {solido.shape[1]}x{solido.shape[0]} px, "
        f"recinto {cv2.contourArea(c) * PIXEL ** 2:.1f} m2, {len(c)} pts de contorno")
    return mins + c.reshape(-1, 2).astype(float) * PIXEL, lleno, mins


# ---------------------------------------------------------------- enderezado
def _tls(p):
    """Recta por minimos cuadrados totales: (punto, direccion unitaria)."""
    c = p.mean(0)
    d = np.linalg.svd(p - c)[2][0]
    return c, d / np.linalg.norm(d)


def _corta(c1, d1, c2, d2):
    """Interseccion de dos rectas. None si son casi paralelas."""
    A = np.array([d1, -d2]).T
    if abs(np.linalg.det(A)) < 1e-9:
        return None
    return c1 + d1 * np.linalg.solve(A, c2 - c1)[0]


def enderezar(cont):
    """Contorno denso -> poligono de lados rectos."""
    idx = cv2.approxPolyDP(
        cont.astype(np.float32).reshape(-1, 1, 2), EPS_DP, True).reshape(-1, 2)
    # approxPolyDP devuelve coordenadas, no indices: se recuperan por vecino mas
    # cercano para poder repartir los puntos del contorno entre los segmentos.
    orden = [int(np.argmin(np.linalg.norm(cont - v, axis=1))) for v in idx]
    n = len(cont)
    log(f"approxPolyDP eps={EPS_DP} m -> {len(orden)} vertices")

    rectas = []
    for k in range(len(orden)):
        a, b = orden[k], orden[(k + 1) % len(orden)]
        tramo = cont[a:b] if b > a else np.vstack([cont[a:], cont[:b]])
        if len(tramo) < 2:
            tramo = np.vstack([cont[a], cont[b]])
        # los extremos del tramo son las esquinas, que estan redondeadas por el
        # cierre morfologico: se recortan antes de ajustar la recta
        m = max(0, int(0.15 * len(tramo)))
        if len(tramo) - 2 * m >= 2:
            tramo = tramo[m:len(tramo) - m]
        c, d = _tls(tramo)
        largo = float(np.linalg.norm(cont[b] - cont[a]))
        rectas.append([c, d, largo])

    # --- familias de angulos ------------------------------------------------
    ang = np.array([np.degrees(np.arctan2(d[1], d[0])) % 180.0 for _, d, _ in rectas])
    pes = np.array([l for _, _, l in rectas])
    orden_pes = np.argsort(-pes)
    fam = []                                    # [(angulo, peso)]
    asign = np.full(len(rectas), -1)
    for i in orden_pes:
        for j, (a0, _) in enumerate(fam):
            dif = abs(ang[i] - a0)
            dif = min(dif, 180 - dif)           # el angulo es modulo 180
            if dif <= TOL_ANG:
                asign[i] = j
                break
        else:
            fam.append([ang[i], 0.0])
            asign[i] = len(fam) - 1
    # media circular (modulo 180) ponderada por longitud
    for j in range(len(fam)):
        s = asign == j
        if not s.any():
            continue
        z = np.exp(2j * np.radians(ang[s])) * pes[s]
        fam[j] = [np.degrees(np.angle(z.sum())) / 2 % 180.0, pes[s].sum()]
    log(f"familias de direccion: " +
        ", ".join(f"{a:.1f}°({p:.0f}m)" for a, p in
                  sorted(fam, key=lambda f: -f[1])[:8]))

    for i, r in enumerate(rectas):
        a = np.radians(fam[asign[i]][0])
        nd = np.array([np.cos(a), np.sin(a)])
        if np.dot(nd, r[1]) < 0:
            nd = -nd
        r[1] = nd

    # --- esquinas por interseccion -----------------------------------------
    def vertices(rs):
        v = []
        for i in range(len(rs)):
            j = (i + 1) % len(rs)
            p = _corta(rs[i][0], rs[i][1], rs[j][0], rs[j][1])
            v.append(rs[j][0] if p is None else p)
        return np.array(v)          # v[i] = esquina entre recta i y recta i+1

    # --- absorber lados cortos ---------------------------------------------
    while True:
        v = vertices(rectas)
        largos = np.linalg.norm(np.roll(v, -1, 0) - v, axis=1)   # lado de recta i+1
        k = int(np.argmin(largos))
        if largos[k] >= LADO_MIN or len(rectas) <= 4:
            break
        del rectas[(k + 1) % len(rectas)]

    v = vertices(rectas)
    # rectas paralelas consecutivas que quedaron: fusionarlas
    fus = [v[-1]]
    for i in range(len(v) - 1):
        a = v[i] - fus[-1]
        b = v[i + 1] - v[i]
        na, nb = np.linalg.norm(a), np.linalg.norm(b)
        if na > 1e-6 and nb > 1e-6 and abs(np.cross(a / na, b / nb)) < 0.02:
            continue                      # colineal: el vertice i sobra
        fus.append(v[i])
    v = np.array(fus)
    log(f"planta enderezada: {len(v)} vertices, perimetro "
        f"{np.linalg.norm(np.roll(v, -1, 0) - v, axis=1).sum():.1f} m")
    return v


# ---------------------------------------------------------------- registro
def registrar(lleno, mins):
    """Traslacion nube -> marco del modelo, por correlacion con la malla vieja.

    Se conserva el marco a proposito: las columnas y el mundo indoor_zone.sdf ya
    estan en el, y el dron aparece en (0,0). Recentrar por el centroide del nuevo
    poligono lo moveria todo varios metros.
    """
    p = os.path.join(OUT, f"{BASE}_suelo.stl")
    if not os.path.exists(p):
        log("no hay malla vieja, se usa el OFFSET fijado en el script")
        return OFFSET
    d = open(p, 'rb').read()
    n = struct.unpack('<I', d[80:84])[0]
    tri = (np.frombuffer(d[84:84 + 50 * n], np.uint8).reshape(n, 50)[:, 12:48]
           .copy().view('<f4').reshape(n, 3, 3))
    horiz = tri[np.abs(tri[:, :, 2] - tri[:, :, 2].mean(1, keepdims=True)).max(1) < 1e-4]
    mn = tri.reshape(-1, 3)[:, :2].min(0)
    mx = tri.reshape(-1, 3)[:, :2].max(0)
    w = int((mx[0] - mn[0]) / PIXEL) + 3
    h = int((mx[1] - mn[1]) / PIXEL) + 3
    viejo = np.zeros((h, w), np.uint8)
    for t in horiz:
        cv2.fillPoly(viejo, [np.round((t[:, :2] - mn) / PIXEL).astype(np.int32)], 255)
    r = cv2.matchTemplate(lleno, viejo, cv2.TM_CCORR_NORMED)
    _, val, _, loc = cv2.minMaxLoc(r)
    off = -(mins + np.array(loc) * PIXEL - mn)
    log(f"registro con la malla vieja: correlacion {val:.3f}, "
        f"offset ({off[0]:.3f}, {off[1]:.3f}) m")
    return off


# ---------------------------------------------------------------- verificacion
def verificar(v):
    """Cada medida del usuario contra el mejor tramo recto de la planta."""
    log("\ncomprobacion contra las 9 medidas tomadas sobre la nube real:")
    n = len(v)
    # Se admite cualquier par de vertices: no todas las medidas del usuario son
    # paredes. 08-58-07, por ejemplo, cruza en diagonal el entrante superior.
    tramos = []
    for i in range(n):
        for j in range(1, n // 2 + 1):     # mas alla es el mismo tramo al reves
            a, b = v[i], v[(i + j) % n]
            d = b - a
            recorrido = sum(np.linalg.norm(v[(i + k + 1) % n] - v[(i + k) % n])
                            for k in range(j))
            pared = recorrido < np.linalg.norm(d) * 1.02   # el tramo va por el muro
            tramos.append((np.linalg.norm(d),
                           np.degrees(np.arctan2(d[1], d[0])) % 180, i, j, pared))
    peor = 0.0
    for nom, L, dx, dy in MEDIDAS:
        a = np.degrees(np.arctan2(dy, dx)) % 180
        best = min(tramos, key=lambda t: abs(t[0] - L) / L
                   + min(abs(t[1] - a), 180 - abs(t[1] - a)) / 15.0)
        err = best[0] - L
        da = min(abs(best[1] - a), 180 - abs(best[1] - a))
        peor = max(peor, abs(err))
        log(f"  {nom}  medido {L:6.2f} m @ {a:6.1f}°   modelo {best[0]:6.2f} m @ "
            f"{best[1]:6.1f}°   error {err:+5.2f} m / {da:4.1f}°   "
            f"{'pared' if best[4] else 'diagonal'}")
    log(f"  peor desviacion en longitud: {peor:.2f} m")


# ---------------------------------------------------------------- geometria
def _obj(path, V, UV, N, F, mtl, mat):
    """OBJ con posicion, UV y NORMAL por vertice.

    Las normales no son opcionales aqui: sin ellas gz carga la malla y la pinta
    BLANCA, sin la textura del <albedo_map> del SDF. Comprobado comparando las
    mallas que si se texturaban (todas llevaban vn) con las que no (ninguna).
    Por eso los indices van en la forma v/vt/vn y no v/vt.
    """
    with open(path, 'w') as f:
        f.write(f"mtllib {mtl}\nusemtl {mat}\n")
        for p in V:
            f.write("v %.4f %.4f %.4f\n" % tuple(p))
        for t in UV:
            f.write("vt %.4f %.4f\n" % tuple(t))
        for n in N:
            f.write("vn %.4f %.4f %.4f\n" % tuple(n))
        for a, b, c in F:
            f.write(f"f {a+1}/{a+1}/{a+1} {b+1}/{b+1}/{b+1} {c+1}/{c+1}/{c+1}\n")
    log(f"  {os.path.basename(path)}: {len(F)} triangulos")


def muros(v):
    """Una caja por lado, alargada media junta a cada extremo para que las
    esquinas cierren sin necesidad de ingletes. UV por longitud de pared."""
    V, UV, N, F = [], [], [], []
    n = len(v)
    for i in range(n):
        a, b = v[i], v[(i + 1) % n]
        d = b - a
        L = np.linalg.norm(d)
        if L < 1e-6:
            continue
        u = d / L
        nrm = np.array([-u[1], u[0]])
        a = a - u * MURO_T / 2
        b = b + u * MURO_T / 2
        L += MURO_T
        for s in (+1, -1):                       # las dos caras verticales
            p0 = a + nrm * s * MURO_T / 2
            p1 = b + nrm * s * MURO_T / 2
            k = len(V)
            V += [[p0[0], p0[1], 0], [p1[0], p1[1], 0],
                  [p1[0], p1[1], MURO_H], [p0[0], p0[1], MURO_H]]
            UV += [[0, 0], [L / TEX_MURO, 0],
                   [L / TEX_MURO, MURO_H / TEX_MURO], [0, MURO_H / TEX_MURO]]
            N += [[nrm[0] * s, nrm[1] * s, 0.0]] * 4
            F += ([[k, k + 1, k + 2], [k, k + 2, k + 3]] if s > 0 else
                  [[k, k + 2, k + 1], [k, k + 3, k + 2]])
        p = [a + nrm * MURO_T / 2, b + nrm * MURO_T / 2,
             b - nrm * MURO_T / 2, a - nrm * MURO_T / 2]      # remate superior
        k = len(V)
        V += [[q[0], q[1], MURO_H] for q in p]
        UV += [[0, 0], [L / TEX_MURO, 0], [L / TEX_MURO, MURO_T / TEX_MURO],
               [0, MURO_T / TEX_MURO]]
        N += [[0.0, 0.0, 1.0]] * 4
        F += [[k, k + 1, k + 2], [k, k + 2, k + 3]]
    return np.array(V), np.array(UV), np.array(N), F


def suelo(v):
    """Losa con el MISMO contorno que las paredes, desbordada medio espesor para
    que el muro apoye encima. UV planar XY: la baldosa es un parche de 1 m."""
    poly = Polygon(v).buffer(0)
    if poly.geom_type != 'Polygon':
        poly = max(poly.geoms, key=lambda g: g.area)
    poly = poly.buffer(MURO_T / 2, join_style=2)
    m = trimesh.creation.extrude_polygon(poly, SUELO_T)
    m.apply_translation([0, 0, -SUELO_T])          # cara vista en z=0
    # Se desueldan los triangulos para dar a cada uno su normal plana: soldados,
    # la normal media del canto se mezclaria con la de la cara vista.
    V = m.vertices[m.faces].reshape(-1, 3)
    N = np.repeat(m.face_normals, 3, axis=0)
    UV = V[:, :2] / TEX_SUELO
    F = np.arange(len(V)).reshape(-1, 3).tolist()
    return V, UV, N, F, poly


def colision(v, poly):
    """Losa + muros como solidos cerrados. Sin UV: no se ve, solo choca."""
    losa = trimesh.creation.extrude_polygon(poly, SUELO_T)
    losa.apply_translation([0, 0, -SUELO_T])
    piezas = [losa]
    n = len(v)
    for i in range(n):
        a, b = v[i], v[(i + 1) % n]
        d = b - a
        L = np.linalg.norm(d)
        if L < 1e-6:
            continue
        u = d / L
        c = (a + b) / 2
        box = trimesh.creation.box(extents=[L + MURO_T, MURO_T, MURO_H])
        ang = np.arctan2(u[1], u[0])
        box.apply_transform(trimesh.transformations.rotation_matrix(ang, [0, 0, 1]))
        box.apply_translation([c[0], c[1], MURO_H / 2])
        piezas.append(box)
    return trimesh.util.concatenate(piezas)


# ---------------------------------------------------------------- main
def main():
    cont, lleno, mins = planta()
    off = registrar(lleno, mins)
    v = enderezar(cont) + off
    verificar(v)

    b = np.array([v.min(0), v.max(0)])
    log(f"\nplanta final en el marco del modelo: X {b[0,0]:.2f}..{b[1,0]:.2f}  "
        f"Y {b[0,1]:.2f}..{b[1,1]:.2f}")
    if not Polygon(v).contains(__import__('shapely.geometry', fromlist=['Point'])
                               .Point(0, 0)):
        log("  AVISO: el origen (donde aparece el dron) queda FUERA del recinto")

    if '--dry-run' in sys.argv:
        log("\n--dry-run: no se escribe nada")
        return

    for f in (f"{BASE}_muros.obj", f"{BASE}_suelo.obj", f"{BASE}_collision.stl"):
        p = os.path.join(OUT, f)
        if os.path.exists(p) and not os.path.exists(p + ".pre_cv"):
            os.replace(p, p + ".pre_cv")

    log("\nescribiendo:")
    Vm, Um, Nm, Fm = muros(v)
    _obj(os.path.join(OUT, f"{BASE}_muros.obj"), Vm, Um, Nm, Fm,
         f"{BASE}_muros.mtl", "ladrillo")
    Vs, Us, Ns, Fs, poly = suelo(v)
    _obj(os.path.join(OUT, f"{BASE}_suelo.obj"), Vs, Us, Ns, Fs,
         f"{BASE}_suelo.mtl", "baldosa")
    col = colision(v, poly)
    col.export(os.path.join(OUT, f"{BASE}_collision.stl"))
    log(f"  {BASE}_collision.stl: {len(col.faces)} triangulos")


if __name__ == '__main__':
    main()
