#!/usr/bin/env python3
"""
Diagnóstico de despegue (por qué (no) despegó) con plots.

Reporta modo de vuelo, armado, GPS, validez de posición (EKF) y actividad de
motores, y GENERA UN PLOT multipanel:
  - despegue.png:
      (1) altura: z (local, NED invertido) + dist_bottom (LiDAR)
      (2) salida de motores (los 4)
      (3) validez del estimador: xy_valid / z_valid / dist_bottom_valid

Uso:
    python3 analyze_takeoff.py <log.ulg | carpeta>

Salida: scripts/output/<log>/despegue.png  + resumen por consola.
"""
import sys
import math
import _common as C

NAV = {0: "Manual", 1: "Altitude", 2: "Position", 3: "Mission", 4: "Loiter",
       5: "RTL", 10: "Acro", 14: "Offboard", 15: "Stabilized", 17: "Takeoff",
       18: "Land"}


def frac_true(arr):
    a = [x for x in arr if x is not None]
    return sum(1 for x in a if x) / len(a) if a else None


def analyze(path):
    ulog = C.load(path)
    dur = C.duration(ulog)
    t0 = ulog.start_timestamp
    print(f"\n=== {path}  ({dur:.1f}s) ===")

    # --- texto: modo, armado, motores ---
    vs = C.get(ulog, "vehicle_status")
    if vs is not None:
        ns = C.field(vs, "nav_state")
        if ns is not None:
            modes = sorted(set(int(v) for v in ns))
            print(f"   modos: {[NAV.get(m, m) for m in modes]}")
    lp = C.get(ulog, "vehicle_local_position")
    if lp is not None:
        for fld in ("xy_valid", "z_valid", "dist_bottom_valid"):
            v = C.field(lp, fld)
            if v is not None:
                fr = frac_true([bool(x) for x in v])
                print(f"   {fld}: {fr:.0%}")

    # --- plot multipanel ---
    C.setup_style()
    fig, axes = C.plt.subplots(3, 1, figsize=(11, 9), sharex=True)

    # (1) altura
    ax = axes[0]
    if lp is not None:
        z = C.field(lp, "z")
        if z is not None:
            x = C.secs(lp["timestamp"], t0)
            alt = [-float(v) if not C.isnan(v) else 0.0 for v in z]
            ax.plot(x, alt, color=C.PALETTE[0], label="altura EKF (-z, NED)")
        db = C.field(lp, "dist_bottom")
        dbv = C.field(lp, "dist_bottom_valid")
        if db is not None:
            x = C.secs(lp["timestamp"], t0)
            d = [float(v) if not C.isnan(v) else float("nan") for v in db]
            ax.plot(x, d, color=C.PALETTE[2], label="dist_bottom (LiDAR)")
    ax.axhline(0, color=C.MUTED, lw=0.8)
    ax.set_ylabel("altura (m)")
    ax.legend(loc="upper left", ncol=2)

    # (2) motores
    ax = axes[1]
    m = C.get(ulog, "actuator_motors")
    if m is not None:
        x = C.secs(m["timestamp"], t0)
        for i in range(4):
            c = C.field(m, f"control[{i}]")
            if c is None:
                continue
            y = [float(v) if not C.isnan(v) else 0.0 for v in c]
            ax.plot(x, y, color=C.PALETTE[i], label=f"motor {i}")
    ax.set_ylabel("salida motor (0–1)")
    ax.set_ylim(-0.05, 1.05)
    ax.legend(loc="upper left", ncol=4)

    # (3) validez del estimador (escalonado 0/1)
    ax = axes[2]
    if lp is not None:
        x = C.secs(lp["timestamp"], t0)
        for i, fld in enumerate(("xy_valid", "z_valid", "dist_bottom_valid")):
            v = C.field(lp, fld)
            if v is None:
                continue
            y = [1 if x_ else 0 for x_ in v]
            # desplazar verticalmente para no solapar
            ax.plot(x, [yy + i * 1.2 for yy in y], color=C.PALETTE[i],
                    drawstyle="steps-post", label=fld)
    ax.set_yticks([])
    ax.set_ylabel("validez")
    ax.set_xlabel("tiempo (s)")
    ax.legend(loc="center left", ncol=3)

    for a in axes:
        for sp in ("top", "right"):
            a.spines[sp].set_visible(False)
    C.title_block(fig, "Diagnóstico de despegue",
                  f"{path.split('/')[-1]} · {dur:.0f}s")
    outdir = C.outdir_for(path)
    C.save(fig, outdir, "despegue")


def main():
    arg = sys.argv[1] if len(sys.argv) > 1 else None
    logs = C.resolve_logs(arg)
    if not logs:
        print("No hay .ulg. Pon logs en scripts/input/ o pasa una ruta/carpeta.")
        sys.exit(1)
    print(f"Analizando {len(logs)} log(s)")
    for l in logs:
        try:
            analyze(l)
        except Exception as e:
            print(f"   ERROR en {l}: {e}")


if __name__ == "__main__":
    main()
