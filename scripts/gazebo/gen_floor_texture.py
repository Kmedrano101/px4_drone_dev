#!/usr/bin/env python3
"""
Genera la textura de baldosa de barro cocido del local real y se la aplica al suelo.

Por que hace falta: el flujo optico del MTF-01P mide desplazamiento por correlacion de
imagen. Sobre un suelo de color plano no hay nada que correlacionar y la calidad se va a
cero, asi que el EKF no puede fusionarlo. Las juntas de la baldosa son justo el patron
que le da textura.

Dos pasos:
  1. Textura PNG sin costuras, con los colores muestreados de la foto del local
     (IMG_20260908_140936.jpg): baldosa RGB(194,138,107), junta RGB(184,178,177).
  2. El suelo es un STL, que NO tiene coordenadas UV, asi que no se le puede pegar una
     textura. Se convierte a OBJ proyectando XY -> UV (proyeccion planar), que es exacta
     para un suelo horizontal.

    python3 gen_floor_texture.py
"""
import math
import os
import struct

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

SCAN = os.path.expanduser('~/src/3d_modeling/IndoorZone/scan2bim/output/gazebo/indoor_clean_less_dense')
MESHES = os.path.join(SCAN, 'meshes')
STL = os.path.join(MESHES, 'indoor_clean_less_dense_suelo.stl')
OBJ = os.path.join(MESHES, 'indoor_clean_less_dense_suelo.obj')
PNG = os.path.join(MESHES, 'baldosa.png')

# --- medidas reales ---
TILE_M = 0.25          # lado de la baldosa, metros
GROUT_M = 0.006        # ancho de junta, metros
PATCH_M = 1.0          # la textura cubre 1 m x 1 m -> UV = metros
PX = 1024              # resolucion del parche

# --- colores muestreados de la foto ---
TILE_RGB = (194, 138, 107)
TILE_LO = (187, 133, 100)   # p20
TILE_HI = (202, 144, 115)   # p80
GROUT_RGB = (184, 178, 177)


def make_texture():
    """Parche de PATCH_M x PATCH_M, sin costuras al repetirse."""
    n = int(round(PATCH_M / TILE_M))            # baldosas por lado
    assert abs(n * TILE_M - PATCH_M) < 1e-9, "PATCH_M debe ser multiplo de TILE_M"
    px_tile = PX // n
    grout_px = max(2, int(round(GROUT_M / PATCH_M * PX)))

    img = Image.new('RGB', (PX, PX), GROUT_RGB)
    d = ImageDraw.Draw(img)
    rng = np.random.default_rng(20260908)

    for iy in range(n):
        for ix in range(n):
            # cada baldosa con su tono, como en la foto (cocidas desigual)
            t = rng.random()
            col = tuple(int(round(lo + (hi - lo) * t)) for lo, hi in zip(TILE_LO, TILE_HI))
            x0 = ix * px_tile + grout_px // 2
            y0 = iy * px_tile + grout_px // 2
            x1 = (ix + 1) * px_tile - grout_px // 2 - 1
            y1 = (iy + 1) * px_tile - grout_px // 2 - 1
            d.rectangle([x0, y0, x1, y1], fill=col)

    a = np.asarray(img).astype(np.float32)

    # Veteado multiescala DENTRO de la baldosa. Es la parte que de verdad importa
    # para el flujo optico, y hay que dimensionarla contra lo que la camara resuelve:
    #   camara de flujo 100x100 px, FOV 0.733 rad
    #   a 0.40 m ve 31 cm  ->  3.1 mm por pixel de imagen
    # Con baldosa de 25 cm, ese parche puede caer ENTERO dentro de una baldosa y no
    # ver ninguna junta. Si ahi no hay veteado a escala de centimetros, no hay nada
    # que correlacionar y la calidad se va a 0.
    # Por eso el ruido va a 1.5-8 cm, no a 1 mm: por debajo de ~4 mm es invisible.
    # MOTTLE calibrado contra la foto real: la desviacion tipica DENTRO de una
    # baldosa en IMG_20260908_140936.jpg es 13.9 (medida en 4 zonas: 9.2-16.8).
    # Ni mas (queda sucio y no se parece) ni menos (el flujo optico se queda sin
    # nada que correlacionar cuando el parche cae dentro de una baldosa).
    MOTTLE = 0.62
    for escala_cm, amp in ((8, 7.0 * MOTTLE), (4, 5.5 * MOTTLE),
                           (2, 4.0 * MOTTLE), (1.0, 2.5 * MOTTLE)):
        lado = max(4, int(round(PATCH_M * 100 / escala_cm)))
        n_low = rng.normal(0, 1, (lado, lado)).astype(np.float32)
        n_low = np.asarray(
            Image.fromarray(((n_low - n_low.min()) / (np.ptp(n_low) + 1e-9) * 255)
                            .astype(np.uint8)).resize((PX, PX), Image.BICUBIC)
        ).astype(np.float32)[:, :, None]
        a += (n_low - n_low.mean()) / 128.0 * amp * 8.0

    # grano fino residual (queda por debajo de la resolucion, pero no molesta)
    a += rng.normal(0, 1.5, a.shape).astype(np.float32)

    img = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))
    img = img.filter(ImageFilter.GaussianBlur(0.4))
    img.save(PNG)
    return n, px_tile, grout_px


def stl_to_obj_with_uv():
    """El STL no lleva UV. Proyeccion planar XY -> UV, exacta para un suelo horizontal."""
    with open(STL, 'rb') as f:
        f.read(80)
        n = struct.unpack('<I', f.read(4))[0]
        data = np.frombuffer(f.read(n * 50), dtype=np.uint8).reshape(n, 50)
        tris = np.zeros((n, 3, 3), dtype=np.float32)
        for i in range(3):
            tris[:, i, :] = data[:, 12 + i * 12:24 + i * 12].copy().view(np.float32).reshape(n, 3)
        normals = data[:, 0:12].copy().view(np.float32).reshape(n, 3)

    verts = tris.reshape(-1, 3)
    with open(OBJ, 'w') as f:
        f.write("# Suelo del local, generado por gen_floor_texture.py\n")
        f.write("# UV = proyeccion planar XY, 1 repeticion de textura por metro.\n")
        f.write("mtllib indoor_clean_less_dense_suelo.mtl\n")
        f.write("usemtl baldosa\n")
        for v in verts:
            f.write(f"v {v[0]:.5f} {v[1]:.5f} {v[2]:.5f}\n")
        for v in verts:
            f.write(f"vt {v[0] / PATCH_M:.5f} {v[1] / PATCH_M:.5f}\n")
        for nv in normals:
            f.write(f"vn {nv[0]:.5f} {nv[1]:.5f} {nv[2]:.5f}\n")
        for t in range(n):
            a, b, c = 3 * t + 1, 3 * t + 2, 3 * t + 3
            f.write(f"f {a}/{a}/{t+1} {b}/{b}/{t+1} {c}/{c}/{t+1}\n")

    with open(os.path.join(MESHES, 'indoor_clean_less_dense_suelo.mtl'), 'w') as f:
        f.write("newmtl baldosa\nKa 0.4 0.3 0.25\nKd 0.76 0.54 0.42\nKs 0.02 0.02 0.02\n"
                "Ns 8\nd 1\nillum 2\nmap_Kd baldosa.png\n")
    return n


if __name__ == '__main__':
    n, px_tile, grout_px = make_texture()
    tris = stl_to_obj_with_uv()
    print(f"textura : {PNG}")
    print(f"          {PX}x{PX} px = {PATCH_M} m -> {n}x{n} baldosas de {TILE_M*100:.0f} cm")
    print(f"          junta {grout_px} px = {GROUT_M*1000:.0f} mm")
    print(f"malla   : {OBJ}  ({tris} triangulos, con UV)")
    print()
    print("Falta apuntar el model.sdf al .obj con el albedo_map (lo hace apply_floor_texture.py)")
