#!/usr/bin/env python3
"""STL del soporte 'saco' para la antena BT-560. Booleanos con manifold3d."""
import numpy as np, trimesh
from trimesh.creation import extrude_polygon, cylinder, cone, box
from shapely.geometry import box as sbox, Point
OUT="."
U=lambda a,b: trimesh.boolean.union([a,b], engine='manifold')
D=lambda a,b: trimesh.boolean.difference([a,b], engine='manifold')

# ---- cotas ----
BORE=27.8; WALL=2.5; OD=BORE+2*WALL; CUP_H=10.0
PT=4.0; CENTER=12.0   # base 4mm: aloja la cabeza plana de 2.5mm con 1.5mm de suelo
HOLE=2.7; HEAD=4.8; CB_DEPTH=2.5               # M2.5: pasante 2.7, caja PLANA Ø4.8 x 2.5
CY=7.5                                          # centro del saco (desplazado)
SX,SY=18.0,20.0
scr_in=[(-SX/2, SY/2),( SX/2, SY/2)]           # 2 dentro (y=+10)
scr_out=[(-SX/2,-SY/2),( SX/2,-SY/2)]          # 2 fuera (y=-10)
BX,BY,BCY,BR=39.3,42.4,5.95,8.0
Z0,ZT=0.0,PT

def rrect(w,h,r,cx,cy): return sbox(cx-w/2+r,cy-h/2+r,cx+w/2-r,cy+h/2-r).buffer(r,resolution=32)

# base
base=extrude_polygon(rrect(BX,BY,BR,0,BCY), height=PT)
# saco (anillo) sobre la base
ring_poly=Point(0,CY).buffer(OD/2,resolution=96).difference(Point(0,CY).buffer(BORE/2,resolution=96))
ring=extrude_polygon(ring_poly, height=CUP_H); ring.apply_translation([0,0,PT])
part=U(base,ring)

# --- restas ---
# hueco central Ø12
h=cylinder(radius=CENTER/2, height=PT+CUP_H+4, sections=96); h.apply_translation([0,CY,(PT+CUP_H)/2]); part=D(part,h)
# 4 tornillos pasantes Ø2.7
for (x,y) in scr_in+scr_out:
  c=cylinder(radius=HOLE/2, height=PT+6, sections=48); c.apply_translation([x,y,PT/2]); part=D(part,c)
# 4 cajas PLANAS (counterbore) para las cabezas: Ø4.8 x 2.5 desde arriba
for (x,y) in scr_in+scr_out:
  cb=cylinder(radius=HEAD/2, height=CB_DEPTH+0.02, sections=48)
  cb.apply_translation([x,y,PT-CB_DEPTH/2+0.01])          # fondo plano a 2.5mm, boca a ras arriba
  part=D(part,cb)
# 2 ranuras de brida (atraviesan la pared del saco, a los lados y=CY)
for sgn in(-1,1):
  s=box(extents=[OD, 2.4, 5.0]); s.apply_translation([sgn*(BORE/2+ (OD-BORE)/4)*0, CY, PT+5.0])
  s=box(extents=[OD+4, 2.4, 5.0]); s.apply_translation([0, CY, PT+5.0]); # franja completa en Y=CY
  # limitar a los lados: restamos una caja larga en X solo donde hay pared -> usamos la franja y luego recortamos el centro con el propio bore (ya hueco). OK:
  part=D(part,s)

part.export(f"{OUT}/soporte_bt560.stl")
print("STL:",f"{OUT}/soporte_bt560.stl")
print(" watertight:",part.is_watertight," bbox:",np.round(part.extents,2)," vol(cm3):",round(part.volume/1000,2))
