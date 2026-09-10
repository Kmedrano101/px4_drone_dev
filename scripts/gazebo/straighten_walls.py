#!/usr/bin/env python3
# OBSOLETO: sustituido por muros_cv.py.
# Este script enderezaba la malla YA exportada. El problema es que esa malla venia
# de una exportacion vieja y recortada a la que le faltaba entero el brazo inferior
# derecho del edificio (~63 m2), asi que enderezarla no podia completarla.
# muros_cv.py rehace la planta desde la nube con OpenCV. Se conserva este fichero
# solo como referencia del ajuste manual a las 9 medidas.
"""
Rehace las paredes del entorno como RECTAS.

Las paredes que salen de scan2bim siguen el ruido de la nube de puntos: sus normales
se reparten por todos los angulos (0-165 grados), cuando un edificio real tiene sus
paredes en dos o tres direcciones dominantes. Ademas de no parecerse, eso ensucia lo
que ve el LiDAR 2D.

Metodo:
  1. Sacar el contorno del edificio de la losa del suelo (mas limpia que los muros).
  2. Ordenarlo en un poligono cerrado.
  3. Simplificar con Douglas-Peucker.
  4. Ajustar la orientacion de cada tramo a las direcciones dominantes del propio
     edificio, y recalcular los vertices como interseccion de rectas consecutivas.
  5. Extruir a la altura de pared, con UV para la textura de ladrillo.

Se valida contra las medidas tomadas a mano sobre la nube (ver MEDIDAS).
"""
import math
import os
import struct
from collections import Counter, defaultdict

import numpy as np

SCAN = os.path.expanduser('~/src/3d_modeling/IndoorZone/scan2bim/output/gazebo/indoor_clean_less_dense')
MESHES = os.path.join(SCAN, 'meshes')
SUELO = os.path.join(MESHES, 'indoor_clean_less_dense_suelo.stl')
OUT_OBJ = os.path.join(MESHES, 'indoor_clean_less_dense_muros.obj')

WALL_H = 2.50          # altura de pared, la que ya tenia el modelo
WALL_T = 0.15          # espesor
SIMPLIFY_TOL = 0.30    # m, tolerancia de Douglas-Peucker
SNAP_TOL_DEG = 12.0    # cuanto se puede girar un tramo para alinearlo
TEX_M = 2.0            # metros por repeticion de la textura de ladrillo

# Medidas tomadas a mano sobre la nube de puntos (vista superior).
# Sirven para comprobar que el resultado se parece a la realidad.
MEDIDAS = [
    ("08-26-35", 13.515519, 11.869571, -6.463048),
    ("08-26-53",  8.062910, -5.570658, -5.828075),
    ("08-27-09", 20.838687, 14.347978, -15.112348),
    ("08-39-13", 18.103068,  8.634177,  15.906898),
    ("08-57-06", 13.423388, -11.663732, -6.643953),
    ("08-57-55",  7.290874,  -6.187666, -3.850365),
    ("08-58-07", 11.401913,  -8.429264,  7.677956),
    ("09-20-28",  2.268494,   1.622377,  1.585481),   # el escalon del lado izquierdo: es REAL
    ("09-20-37",  8.881556,   5.347342, -7.090507),
]


def leer_stl(path):
    with open(path, 'rb') as f:
        f.read(80)
        n = struct.unpack('<I', f.read(4))[0]
        d = np.frombuffer(f.read(n * 50), dtype=np.uint8).reshape(n, 50)
        T = np.zeros((n, 3, 3), dtype=np.float64)
        for i in range(3):
            T[:, i, :] = d[:, 12 + i * 12:24 + i * 12].copy().view(np.float32).reshape(n, 3)
    return T


def contorno(T):
    """Aristas que solo pertenecen a un triangulo = borde de la losa."""
    top = T[:, :, 2].max(1) > T[:, :, 2].min() + 0.05
    if top.sum() > 10:
        T = T[top]
    cnt = Counter()
    for t in T:
        for a, b in ((0, 1), (1, 2), (2, 0)):
            # OJO: la clave debe ser 3D. Proyectando a 2D antes de contar, las caras
            # superior e inferior de la losa se solapan y toda arista sale duplicada,
            # con lo que el contorno queda vacio.
            k = tuple(sorted([tuple(np.round(t[a], 3)), tuple(np.round(t[b], 3))]))
            cnt[k] += 1
    borde = [k for k, c in cnt.items() if c == 1]
    return [((a[0], a[1]), (b[0], b[1])) for a, b in borde]


def mayor_anillo(aristas):
    """Encadena las aristas y devuelve el anillo cerrado mas largo."""
    ady = defaultdict(list)
    for a, b in aristas:
        ady[a].append(b)
        ady[b].append(a)
    visto = set()
    mejor = []
    for ini in ady:
        if ini in visto:
            continue
        ciclo = [ini]
        visto.add(ini)
        act, prev = ini, None
        while True:
            sig = [v for v in ady[act] if v != prev and v not in visto]
            if not sig:
                break
            prev, act = act, sig[0]
            visto.add(act)
            ciclo.append(act)
        if len(ciclo) > len(mejor):
            mejor = ciclo
    return np.array(mejor)


def douglas_peucker(pts, tol):
    if len(pts) < 3:
        return pts
    a, b = pts[0], pts[-1]
    ab = b - a
    L = np.linalg.norm(ab)
    if L < 1e-9:
        d = np.linalg.norm(pts - a, axis=1)
    else:
        d = np.abs(np.cross(np.tile(ab, (len(pts), 1)), pts - a)) / L
    i = int(np.argmax(d))
    if d[i] > tol:
        izq = douglas_peucker(pts[:i + 1], tol)
        der = douglas_peucker(pts[i:], tol)
        return np.vstack([izq[:-1], der])
    return np.vstack([a, b])


def direcciones_medidas(medidas, sep=6.0):
    """Direcciones de pared tomadas de las medidas hechas a mano sobre la nube.

    Se prefieren a las deducidas del contorno: el contorno lleva el ruido del escaneo,
    las medidas las tomo una persona sobre las aristas reales del edificio.
    Se agrupan las que estan a menos de `sep` grados.
    """
    angs = sorted(math.degrees(math.atan2(dy, dx)) % 180 for _, _, dx, dy in medidas)
    grupos = []
    for a in angs:
        if grupos and min(abs(a - grupos[-1][-1]), 180 - abs(a - grupos[-1][-1])) < sep:
            grupos[-1].append(a)
        else:
            grupos.append([a])
    return [sum(g) / len(g) for g in grupos]


def puntuar(poly, medidas):
    """Cuanto se parece el poligono a las medidas: suma de errores de longitud."""
    v = np.roll(poly, -1, axis=0) - poly
    L = np.linalg.norm(v, axis=1)
    ang = np.degrees(np.arctan2(v[:, 1], v[:, 0])) % 180
    total = 0.0
    for _, dist, dx, dy in medidas:
        a = math.degrees(math.atan2(dy, dx)) % 180
        da = np.minimum(np.abs(ang - a), 180 - np.abs(ang - a))
        pen = np.abs(L - dist) + 0.20 * da
        total += pen.min()
    return total


def desviacion_contorno(poly, anillo):
    """Cuanto se aleja el poligono del contorno real del escaneo (metros, p95).

    Hace falta como segundo criterio: ajustando SOLO contra las medidas, la
    simplificacion se lleva por delante escalones reales del edificio con tal de
    alargar un muro. Las medidas mandan en las longitudes, pero el escaneo manda en
    la forma.
    """
    n = len(poly)
    seg_a = poly
    seg_b = np.roll(poly, -1, axis=0)
    d = []
    for p in anillo:
        v = seg_b - seg_a
        L2 = (v ** 2).sum(1)
        L2[L2 < 1e-12] = 1e-12
        t = np.clip(((p - seg_a) * v).sum(1) / L2, 0, 1)
        proj = seg_a + t[:, None] * v
        d.append(np.linalg.norm(proj - p, axis=1).min())
    return float(np.percentile(d, 95))


def direcciones_dominantes(poly):
    """Angulos (mod 180) donde se acumula mas longitud de pared."""
    v = np.roll(poly, -1, axis=0) - poly
    L = np.linalg.norm(v, axis=1)
    ang = np.degrees(np.arctan2(v[:, 1], v[:, 0])) % 180
    h, edges = np.histogram(ang, bins=180, range=(0, 180), weights=L)
    # suavizar para que un pico repartido entre dos bins no se pierda
    k = np.ones(5) / 5
    hs = np.convolve(np.r_[h[-2:], h, h[:2]], k, mode='same')[2:-2]
    picos = []
    for i in range(180):
        if hs[i] > 0 and hs[i] >= hs[(i - 1) % 180] and hs[i] >= hs[(i + 1) % 180] and hs[i] > hs.max() * 0.15:
            picos.append((hs[i], i + 0.5))
    picos.sort(reverse=True)
    # quedarse con picos separados entre si
    dom = []
    for _, a in picos:
        if all(min(abs(a - b), 180 - abs(a - b)) > 15 for b in dom):
            dom.append(a)
    return dom


def enderezar(poly, dom):
    """Gira cada tramo a su direccion dominante y recalcula los vertices."""
    n = len(poly)
    rectas = []
    for i in range(n):
        p, q = poly[i], poly[(i + 1) % n]
        v = q - p
        L = np.linalg.norm(v)
        ang = math.degrees(math.atan2(v[1], v[0])) % 180
        # direccion dominante mas cercana
        mejor = min(dom, key=lambda a: min(abs(ang - a), 180 - abs(ang - a)))
        err = min(abs(ang - mejor), 180 - abs(ang - mejor))
        if err > SNAP_TOL_DEG:
            mejor = ang                      # tramo genuinamente oblicuo: se respeta
        th = math.radians(mejor)
        d = np.array([math.cos(th), math.sin(th)])
        c = (p + q) / 2                      # la recta pasa por el centro del tramo
        rectas.append((c, d, L))
    # vertices = interseccion de rectas consecutivas
    out = []
    for i in range(n):
        c1, d1, _ = rectas[i - 1]
        c2, d2, _ = rectas[i]
        A = np.array([d1, -d2]).T
        if abs(np.linalg.det(A)) < 1e-6:
            out.append(poly[i])              # paralelas: no hay interseccion util
            continue
        t = np.linalg.solve(A, c2 - c1)
        out.append(c1 + t[0] * d1)
    return np.array(out)


def quitar_entrantes(poly, min_seg=1.2, tol_deg=8.0):
    """Elimina tramos cortos que separan dos paredes que en realidad son la misma.

    El contorno de la nube tiene entrantes de ruido de pocos decimetros. Douglas-Peucker
    los conserva, y parten un muro largo en varios trozos que luego no se fusionan por
    no ser consecutivos. Aqui se borra el tramo corto si sus dos vecinos son casi
    colineales entre si.
    """
    cambio = True
    while cambio and len(poly) > 4:
        cambio = False
        n = len(poly)
        for i in range(n):
            a, b, c, d = poly[i], poly[(i+1) % n], poly[(i+2) % n], poly[(i+3) % n]
            if np.linalg.norm(c - b) > min_seg:
                continue                      # el tramo del medio no es corto
            d1, d2 = b - a, d - c             # los dos vecinos
            if np.linalg.norm(d1) < 1e-6 or np.linalg.norm(d2) < 1e-6:
                continue
            a1 = math.degrees(math.atan2(d1[1], d1[0])) % 180
            a2 = math.degrees(math.atan2(d2[1], d2[0])) % 180
            if min(abs(a1 - a2), 180 - abs(a1 - a2)) < tol_deg:
                # borrar b y c: los vecinos se prolongan hasta cortarse
                poly = np.delete(poly, [(i+1) % n, (i+2) % n], axis=0)
                cambio = True
                break
    return poly


def fusionar_colineales(poly, tol_deg=3.0):
    """Une tramos consecutivos con la misma direccion.

    Tras enderezar, un muro largo puede haber quedado partido en varios tramos con
    identica orientacion: el contorno de la nube tiene entrantes de ruido que
    Douglas-Peucker conserva. Sin esta fusion, las longitudes no se parecen a las
    medidas reales aunque las paredes ya sean rectas.
    """
    cambio = True
    while cambio and len(poly) > 3:
        cambio = False
        n = len(poly)
        for i in range(n):
            a, b, c = poly[i], poly[(i + 1) % n], poly[(i + 2) % n]
            d1, d2 = b - a, c - b
            if np.linalg.norm(d1) < 1e-6 or np.linalg.norm(d2) < 1e-6:
                continue
            a1 = math.degrees(math.atan2(d1[1], d1[0])) % 180
            a2 = math.degrees(math.atan2(d2[1], d2[0])) % 180
            if min(abs(a1 - a2), 180 - abs(a1 - a2)) < tol_deg:
                poly = np.delete(poly, (i + 1) % n, axis=0)   # sobra el vertice central
                cambio = True
                break
    return poly


def escribir_obj(poly, path):
    """Extruye el poligono a paredes con espesor, con UV para el ladrillo."""
    n = len(poly)
    # normal exterior de cada tramo (el poligono se recorre en un sentido)
    area = 0.5 * sum(poly[i][0] * poly[(i + 1) % n][1] - poly[(i + 1) % n][0] * poly[i][1]
                     for i in range(n))
    sentido = 1.0 if area > 0 else -1.0

    V, VT, Fc = [], [], []
    for i in range(n):
        p, q = poly[i], poly[(i + 1) % n]
        v = q - p
        L = np.linalg.norm(v)
        if L < 1e-6:
            continue
        d = v / L
        nrm = np.array([d[1], -d[0]]) * sentido     # hacia fuera
        for off in (WALL_T / 2, -WALL_T / 2):       # cara exterior e interior
            a = p + nrm * off
            b = q + nrm * off
            base = len(V) + 1
            V += [[a[0], a[1], 0], [b[0], b[1], 0], [b[0], b[1], WALL_H], [a[0], a[1], WALL_H]]
            VT += [[0, 0], [L / TEX_M, 0], [L / TEX_M, WALL_H / TEX_M], [0, WALL_H / TEX_M]]
            if off > 0:
                Fc += [(base, base + 1, base + 2), (base, base + 2, base + 3)]
            else:
                Fc += [(base, base + 2, base + 1), (base, base + 3, base + 2)]

    with open(path, 'w') as f:
        f.write("# Muros rectos, generados por straighten_walls.py\n")
        f.write(f"# {n} tramos, altura {WALL_H} m, espesor {WALL_T} m\n")
        f.write("mtllib indoor_clean_less_dense_muros.mtl\nusemtl ladrillo\n")
        for v in V:
            f.write(f"v {v[0]:.4f} {v[1]:.4f} {v[2]:.4f}\n")
        for t in VT:
            f.write(f"vt {t[0]:.4f} {t[1]:.4f}\n")
        for a, b, c in Fc:
            f.write(f"f {a}/{a} {b}/{b} {c}/{c}\n")
    return len(Fc)


def triangular(poly):
    """Ear clipping: triangula el poligono del suelo."""
    idx = list(range(len(poly)))
    area = 0.5 * sum(poly[i][0] * poly[(i + 1) % len(poly)][1] -
                     poly[(i + 1) % len(poly)][0] * poly[i][1] for i in range(len(poly)))
    if area < 0:
        idx.reverse()
    tris = []
    guard = 0
    while len(idx) > 3 and guard < 5000:
        guard += 1
        for k in range(len(idx)):
            i0, i1, i2 = idx[k - 1], idx[k], idx[(k + 1) % len(idx)]
            a, b, c = poly[i0], poly[i1], poly[i2]
            cr = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
            if cr <= 0:
                continue                       # reflejo: no es una oreja
            dentro = False
            for j in idx:
                if j in (i0, i1, i2):
                    continue
                p_ = poly[j]
                d1 = (b[0]-a[0])*(p_[1]-a[1]) - (b[1]-a[1])*(p_[0]-a[0])
                d2 = (c[0]-b[0])*(p_[1]-b[1]) - (c[1]-b[1])*(p_[0]-b[0])
                d3 = (a[0]-c[0])*(p_[1]-c[1]) - (a[1]-c[1])*(p_[0]-c[0])
                if d1 >= 0 and d2 >= 0 and d3 >= 0:
                    dentro = True
                    break
            if not dentro:
                tris.append((i0, i1, i2))
                idx.pop(k)
                break
        else:
            break
    if len(idx) == 3:
        tris.append(tuple(idx))
    return tris


def escribir_suelo(poly, path, tex_m=1.0):
    """Reescribe la losa con el MISMO contorno recto que las paredes.

    Si no, el suelo conserva el borde ondulado del escaneo y asoma por dentro y por
    fuera de las paredes rectas, dejando un fleco dentado bien visible en Gazebo.
    """
    tris = triangular(poly)
    with open(path, 'w') as f:
        f.write("# Suelo recto, generado por straighten_walls.py\n")
        f.write("mtllib indoor_clean_less_dense_suelo.mtl\nusemtl baldosa\n")
        for v in poly:
            f.write(f"v {v[0]:.4f} {v[1]:.4f} 0.0000\n")
        for v in poly:
            f.write(f"vt {v[0]/tex_m:.4f} {v[1]/tex_m:.4f}\n")
        for a, b, c in tris:
            f.write(f"f {a+1}/{a+1} {b+1}/{b+1} {c+1}/{c+1}\n")
    return len(tris)


def escribir_collision_mixta(poly, orig, path):
    """Suelo original + paredes rectas.

    Los triangulos horizontales de la colision original son el suelo del edificio y
    hay que conservarlos: sin ellos el dron atraviesa el piso.
    """
    with open(orig, 'rb') as f:
        f.read(80)
        n = struct.unpack('<I', f.read(4))[0]
        d = np.frombuffer(f.read(n * 50), dtype=np.uint8).reshape(n, 50)
        N = d[:, 0:12].copy().view(np.float32).reshape(n, 3)
        T = np.zeros((n, 3, 3), dtype=np.float32)
        for i in range(3):
            T[:, i, :] = d[:, 12 + i * 12:24 + i * 12].copy().view(np.float32).reshape(n, 3)
    L = np.linalg.norm(N, axis=1)
    ok = L > 1e-9
    Nn = np.zeros_like(N)
    Nn[ok] = N[ok] / L[ok, None]
    tris = [tuple(map(tuple, t)) for t in T[np.abs(Nn[:, 2]) > 0.8]]   # suelo original
    for i in range(len(poly)):                                          # paredes rectas
        a2, b2 = poly[i], poly[(i + 1) % len(poly)]
        a0 = (a2[0], a2[1], 0.0); b0 = (b2[0], b2[1], 0.0)
        a1 = (a2[0], a2[1], WALL_H); b1 = (b2[0], b2[1], WALL_H)
        tris += [(a0, b0, b1), (a0, b1, a1)]
    with open(path, 'wb') as f:
        f.write(b'suelo original + paredes rectas'.ljust(80, b'\0'))
        f.write(struct.pack('<I', len(tris)))
        for t in tris:
            v0, v1, v2 = (np.array(x, dtype=float) for x in t)
            nr = np.cross(v1 - v0, v2 - v0)
            L2 = np.linalg.norm(nr)
            nr = nr / L2 if L2 > 1e-9 else np.zeros(3)
            f.write(struct.pack('<3f', *nr))
            for v in (v0, v1, v2):
                f.write(struct.pack('<3f', *v))
            f.write(struct.pack('<H', 0))
    return len(tris)


def escribir_collision_stl(poly, path):
    """Colision con la misma geometria recta.

    Importante: el LiDAR 2D de gz raycastea contra la escena de RENDER (los visuales),
    pero los choques fisicos usan la malla de colision. Si solo se cambian los visuales,
    el dron seguiria chocando contra las paredes onduladas viejas.
    """
    n = len(poly)
    tris = []
    for i in range(n):
        a2, b2 = poly[i], poly[(i + 1) % n]
        a0 = (a2[0], a2[1], 0.0); b0 = (b2[0], b2[1], 0.0)
        a1 = (a2[0], a2[1], WALL_H); b1 = (b2[0], b2[1], WALL_H)
        tris += [(a0, b0, b1), (a0, b1, a1)]
    with open(path, 'wb') as f:
        f.write(b'muros rectos - colision'.ljust(80, b'\0'))
        f.write(struct.pack('<I', len(tris)))
        for t in tris:
            v0, v1, v2 = (np.array(x) for x in t)
            nr = np.cross(v1 - v0, v2 - v0)
            L = np.linalg.norm(nr)
            nr = nr / L if L > 1e-9 else np.zeros(3)
            f.write(struct.pack('<3f', *nr))
            for v in (v0, v1, v2):
                f.write(struct.pack('<3f', *v))
            f.write(struct.pack('<H', 0))
    return len(tris)


if __name__ == '__main__':
    T = leer_stl(SUELO)
    aristas = contorno(T)
    anillo = mayor_anillo(aristas)
    print(f"contorno: {len(aristas)} aristas -> anillo de {len(anillo)} vertices")

    dom = direcciones_medidas(MEDIDAS)
    print(f"direcciones tomadas de las medidas: {', '.join(f'{a:.1f}' for a in dom)} grados")

    # Barrido de tolerancia: las medidas son el criterio, no una tolerancia elegida a ojo.
    # Con tolerancia baja los muros largos salen partidos por entrantes de ruido; con
    # tolerancia alta se pierden esquinas reales. Se elige la que menos error deja.
    mejor = None
    for tol in np.arange(0.3, 2.61, 0.1):
        for mseg in (0.8, 1.5, 2.5):
            q = douglas_peucker(anillo, float(tol))
            if np.allclose(q[0], q[-1]):
                q = q[:-1]
            if len(q) < 4:
                continue
            q = enderezar(q, dom)
            q = quitar_entrantes(q, min_seg=mseg)
            q = enderezar(q, dom)
            q = fusionar_colineales(q)
            err_med = puntuar(q, MEDIDAS)
            desv = desviacion_contorno(q, anillo)
            # las medidas pesan, pero separarse del escaneo penaliza fuerte
            sc = err_med + 6.0 * desv
            if mejor is None or sc < mejor[0]:
                mejor = (sc, float(tol), mseg, q, err_med, desv)
    sc, tol, mseg, poly, err_med, desv = mejor
    print(f"mejor ajuste: tol {tol:.1f} m, entrantes < {mseg} m  ->  {len(poly)} vertices")
    print(f"  error contra medidas: {err_med:.2f}   desviacion del escaneo (p95): {desv:.2f} m")

    v = np.roll(poly, -1, axis=0) - poly
    L = np.linalg.norm(v, axis=1)
    ang = np.degrees(np.arctan2(v[:, 1], v[:, 0])) % 180
    print(f"\ntramos resultantes ({len(poly)}), los mas largos:")
    for i in np.argsort(-L)[:10]:
        print(f"   {L[i]:6.2f} m  a {ang[i]:6.1f} grados")

    print("\ncontraste con las medidas tomadas a mano:")
    for nombre, dist, dx, dy in MEDIDAS:
        a = math.degrees(math.atan2(dy, dx)) % 180
        # tramo mas parecido en longitud Y orientacion
        pen = np.abs(L - dist) + 0.15 * np.minimum(np.abs(ang - a), 180 - np.abs(ang - a))
        j = int(np.argmin(pen))
        print(f"   {nombre}: medido {dist:6.2f} m a {a:5.1f}  ->  modelo {L[j]:6.2f} m a {ang[j]:5.1f}"
              f"   (dif {abs(L[j]-dist):4.2f} m)")

    ntri = escribir_obj(poly, OUT_OBJ)
    print(f"\nmuros escritos:  {os.path.basename(OUT_OBJ)}  ({ntri} triangulos, antes 1048)")
    # Colision: se CONSERVAN los triangulos horizontales originales (el suelo) y solo
    # se sustituyen los verticales por las paredes rectas.
    # Reemplazar la colision entera fue un error: se quedo sin suelo, 674 -> 20
    # triangulos, y el dron se caia por el.
    col = os.path.join(MESHES, 'indoor_clean_less_dense_collision.stl')
    if not os.path.exists(col + '.bak'):
        import shutil; shutil.copy(col, col + '.bak')
    nc = escribir_collision_mixta(poly, col + '.bak', col)
    print(f"colision escrita: {os.path.basename(col)}  ({nc} triangulos: suelo original + paredes rectas)")
    print("suelo: NO se toca. Lo genera gen_floor_texture.py con el contorno original.")
