#!/usr/bin/env python3
"""
base_rpi4 — placa base para la Raspberry Pi 4 del dron.

Derivada de base_rpi4.stl original (100x75x2.5 mm) con dos cambios:
  1. Los 4 huecos de montaje de la RPi4 pasan a M3 (Ø3.2 holgura).
  2. La placa se reduce a 85 x 71 mm, situando los huecos de la RPi4 en su
     posicion fisica real: 3.5 mm desde el lado D (GPIO) y 23.5 mm de voladizo
     en el lado B (USB/ethernet). Se conservan los 4 huecos del frame.
  3. Las 4 esquinas se redondean con un filete de radio CORNER_R.

Salida: base_rpi4.stl  (placa plana 85 x 71 x 2.5 mm, watertight)
"""
import numpy as np
import trimesh
from shapely.geometry import box, Point

# --- parametros ------------------------------------------------------------
TH      = 2.5            # espesor de la placa (sin cambio vs original)
# contorno (marco original centrado: X -44.86..55.14, Y -37.5..37.5)
X0, X1  = -40.36, 44.64  # 85 mm, huecos RPi4 a 3.5 mm del lado D
Y0, Y1  = -35.5, 35.5    # 71 mm, -2 mm en A y C

CORNER_R = 5.0          # radio de filete en las 4 esquinas

D_RPI   = 3.2            # Ø huecos RPi4 -> M3 holgura
D_FRAME = 3.5            # Ø huecos al frame -> M3

RPI_HOLES = [(-36.86, 24.5), (-36.86, -24.5), (21.12, 24.5), (21.12, -24.5)]
FRAME_HOLES = [(-18.85, 31.49), (-18.85, -31.49), (29.15, 31.49), (29.15, -31.49)]

# --- construccion 2D con agujeros -----------------------------------------
plate = box(X0, Y0, X1, Y1)
# esquinas redondeadas: encoger y expandir con junta redonda (mantiene bbox)
plate = plate.buffer(-CORNER_R, join_style=1).buffer(CORNER_R, join_style=1)
for (x, y) in RPI_HOLES:
    plate = plate.difference(Point(x, y).buffer(D_RPI / 2.0, resolution=64))
for (x, y) in FRAME_HOLES:
    plate = plate.difference(Point(x, y).buffer(D_FRAME / 2.0, resolution=64))

# --- extrusion a solido ----------------------------------------------------
mesh = trimesh.creation.extrude_polygon(plate, height=TH)

assert mesh.is_watertight, "la malla no es watertight"
print("watertight:", mesh.is_watertight)
print("bbox (mm):", np.round(mesh.extents, 3))
print("volumen cm3:", round(mesh.volume / 1000.0, 3))

mesh.export("hardware/base_rpi4/base_rpi4.stl")
print("exportado hardware/base_rpi4/base_rpi4.stl")
