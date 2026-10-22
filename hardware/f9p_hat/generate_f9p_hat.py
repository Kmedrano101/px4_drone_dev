#!/usr/bin/env python3
"""STL final del HAT F9P sobre RPi + plano 2D a juego. Cotas en mm."""
import numpy as np, trimesh
from shapely.geometry import box, Point
from shapely.ops import unary_union
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, Rectangle, FancyBboxPatch
OUT="."

# ---- cotas finales ----
PW,PH,PT,CR = 65.0, 56.0, 3.0, 3.0
RPI=[(3.5,3.5),(61.5,3.5),(3.5,52.5),(61.5,52.5)]; RPI_D=2.75   # M2.5 pasante
SLOT_X0,SLOT_X1,SLOT_Y0 = 6.5,58.5,48.5                         # ranura header abierta al borde
SQ=38.0; F_D=3.2; FCX,FCY=38.0,26.25                            # F9P: cuadrado 38, agujero M3
F9H=[(FCX-SQ/2,FCY-SQ/2),(FCX+SQ/2,FCY-SQ/2),(FCX-SQ/2,FCY+SQ/2),(FCX+SQ/2,FCY+SQ/2)]
F9OUT=(43.5,43.2)

def rrect(w,h,r,cx,cy): return box(cx-w/2+r,cy-h/2+r,cx+w/2-r,cy+h/2-r).buffer(r,resolution=24)

plate=rrect(PW,PH,CR,PW/2,PH/2)
cuts=[Point(x,y).buffer(RPI_D/2,resolution=32) for (x,y) in RPI]
cuts+=[Point(x,y).buffer(F_D/2,resolution=32) for (x,y) in F9H]
slot=box(SLOT_X0,SLOT_Y0,SLOT_X1,PH+5).buffer(-2,join_style=1).buffer(2,join_style=1)  # fillet inferior r2
cuts.append(slot)
poly=plate.difference(unary_union(cuts))
part=trimesh.creation.extrude_polygon(poly,height=PT)
part.export(f"{OUT}/f9p_hat.stl")

# ---- comprobaciones de holgura ----
def wall(a,b,ra,rb): 
    import math; return math.dist(a,b)-ra-rb
checks=[("F9P-inf-der vs RPi-inf-der",(FCX+SQ/2,FCY-SQ/2),(61.5,3.5),F_D/2,RPI_D/2),
        ("F9P-sup-der vs RPi-sup-der",(FCX+SQ/2,FCY+SQ/2),(61.5,52.5),F_D/2,RPI_D/2)]
print("STL:",f"{OUT}/f9p_hat.stl")
print(" watertight:",part.is_watertight," bbox:",np.round(part.extents,2)," vol(cm3):",round(part.volume/1000,2))
print(" F9P sup-holes y=%.2f  -> borde ranura %.2f  (holgura %.2f mm)"%(FCY+SQ/2, SLOT_Y0, SLOT_Y0-(FCY+SQ/2)-F_D/2))
for n,a,b,ra,rb in checks: print("  %-30s pared=%.2f mm"%(n,wall(a,b,ra,rb)))

# ---- plano 2D final ----
fig,ax=plt.subplots(figsize=(11,7.2))
ax.add_patch(Rectangle((0,0),85,56,fc="#eee",ec="#bbb",lw=1,zorder=0))
ax.text(74,28,"RPi 4\n(85 x 56)",ha="center",va="center",fontsize=8,color="#999")
for yy in (6,20,34): ax.add_patch(Rectangle((85,yy),6,12,fc="#9db8d2",ec="#5a7fa5",lw=1,zorder=0))
ax.text(88,52,"lado USB /\nEthernet",ha="center",va="bottom",fontsize=8,color="#35587a",fontweight="bold")
ax.add_patch(FancyBboxPatch((0,0),PW,PH,boxstyle="round,pad=0,rounding_size=3",fc="none",ec="k",lw=2.2,zorder=2))
for (x,y) in RPI: ax.add_patch(Circle((x,y),RPI_D/2,fc="white",ec="b",lw=1.6,zorder=3))
ax.text(1.0,53.5,"M2.5 x4 pasante",ha="left",va="bottom",fontsize=8,color="b")
ax.add_patch(Rectangle((SLOT_X0,SLOT_Y0),SLOT_X1-SLOT_X0,PH-SLOT_Y0,fc="#ffe0e0",ec="r",lw=1.5,zorder=3))
ax.plot([SLOT_X0,SLOT_X1],[PH,PH],color="white",lw=3,zorder=4)
ax.text((SLOT_X0+SLOT_X1)/2,SLOT_Y0+1.8,"ranura header 40p — abierta al borde",ha="center",va="bottom",fontsize=8,color="r")
ax.add_patch(Rectangle((FCX-F9OUT[0]/2,FCY-F9OUT[1]/2),F9OUT[0],F9OUT[1],fc="#e3f0ff",ec="#2a6",lw=1.2,ls="--",alpha=.55,zorder=2))
ax.text(FCX,FCY-F9OUT[1]/2-1.0,"placa F9P 43.5 x 43.2",ha="center",va="top",fontsize=8,color="#2a6")
for (x,y) in F9H: ax.add_patch(Circle((x,y),F_D/2,fc="white",ec="g",lw=1.8,zorder=4))
ax.text(FCX,FCY,"M3 (F9P x4)",ha="center",va="center",fontsize=9,color="g",fontweight="bold")
def dim(x0,y0,x1,y1,t,off=0,vert=False):
    ax.annotate("",xy=(x1,y1),xytext=(x0,y0),arrowprops=dict(arrowstyle="<->",color="#333"))
    ax.text((x0+x1)/2+(0 if not vert else off),(y0+y1)/2+(off if not vert else 0),t,ha="center",va="center",
            fontsize=8,color="#333",rotation=(90 if vert else 0),bbox=dict(fc="white",ec="none",pad=0.5))
dim(0,-4,PW,-4,"65.0",off=-2); dim(-4,0,-4,PH,"56.0 (= Pi)",off=-2,vert=True)
dim(FCX-SQ/2,FCY-SQ/2-2.5,FCX+SQ/2,FCY-SQ/2-2.5,"38.0 (M3 c-c)",off=-2)
dim(FCX+SQ/2+2.5,FCY-SQ/2,FCX+SQ/2+2.5,FCY+SQ/2,"38.0",off=2.5,vert=True)
ax.set_xlim(-10,100);ax.set_ylim(-10,64);ax.set_aspect("equal");ax.axis("off")
ax.set_title("HAT F9P — FINAL (65 x 56 x 3 mm · M3 cuadrado 38 · M2.5 pasante)",fontsize=11)
fig.tight_layout();fig.savefig(f"{OUT}/f9p_hat_plano.png",dpi=135)
print("PNG:",f"{OUT}/f9p_hat_plano.png")
