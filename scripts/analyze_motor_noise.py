#!/usr/bin/env python3
"""
Análisis del "ruido al armar" (motores a 100%) con plots.

Clasifica cada log armar/desarmar como "idle limpio" vs "SATURADO", identifica
el eje (roll/pitch/yaw) por los pares de motores, y GENERA PLOTS:
  - motores.png : salida de los 4 motores en el tiempo (resalta saturación >95%)
  - torque.png  : torque setpoint roll/pitch/yaw en el tiempo

Geometría quad-X (de CA_ROTOR): 0=FR CCW, 1=RL CCW, 2=FL CW, 3=RR CW.
Motores {0,1} o {2,3} al 100% = saturación de YAW (diagonal mismo sentido).

Uso:
    python3 analyze_motor_noise.py <log.ulg | carpeta>

Salida: scripts/output/<log>/motores.png, torque.png  + resumen por consola.
"""
import sys
import _common as C

SAT = 0.95
MOTOR_POS = {0: "FR", 1: "RL", 2: "FL", 3: "RR"}
SPIN = {0: "CCW", 1: "CCW", 2: "CW", 3: "CW"}


def axis_guess(sat):
    s = set(sat)
    if s in ({0, 1}, {2, 3}):
        return "YAW (diagonal mismo sentido a tope)"
    if s in ({0, 3}, {1, 2}):
        return "ROLL"
    if s in ({0, 2}, {1, 3}):
        return "PITCH"
    return f"mixto {sorted(sat)}" if sat else "-"


def plot_motors(ulog, path, outdir):
    m = C.get(ulog, "actuator_motors")
    if m is None:
        return None
    t0 = ulog.start_timestamp
    x = C.secs(m["timestamp"], t0)
    C.setup_style()
    fig, ax = C.plt.subplots()
    saturated = []
    for i in range(4):
        c = C.field(m, f"control[{i}]")
        if c is None:
            continue
        y = [float(v) if not C.isnan(v) else 0.0 for v in c]
        ax.plot(x, y, color=C.PALETTE[i], label=f"motor {i} ({MOTOR_POS[i]}/{SPIN[i]})")
        if max(y) >= SAT:
            saturated.append(i)
    ax.axhline(SAT, color=C.CRIT, lw=1.0, ls="--")
    ax.text(ax.get_xlim()[1], SAT, " saturación 95%", color=C.CRIT,
            va="bottom", ha="right", fontsize=8)
    ax.set_xlabel("tiempo (s)")
    ax.set_ylabel("salida de motor (0–1)")
    ax.set_ylim(-0.05, 1.05)
    ax.legend(loc="upper right", ncol=2)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    cls = "SATURADO" if saturated else "idle limpio"
    C.title_block(fig, f"Salida de motores — {cls}",
                  f"{path.split('/')[-1]} · eje: {axis_guess(saturated)}")
    C.save(fig, outdir, "motores")
    return saturated


def plot_torque(ulog, path, outdir):
    tq = C.get(ulog, "vehicle_torque_setpoint")
    if tq is None:
        return
    t0 = ulog.start_timestamp
    x = C.secs(tq["timestamp"], t0)
    C.setup_style()
    fig, ax = C.plt.subplots()
    for i, (fld, label) in enumerate([("xyz[0]", "roll"), ("xyz[1]", "pitch"), ("xyz[2]", "yaw")]):
        c = C.field(tq, fld)
        if c is None:
            continue
        y = [float(v) if not C.isnan(v) else 0.0 for v in c]
        ax.plot(x, y, color=C.PALETTE[i], label=label)
    ax.axhline(0, color=C.MUTED, lw=0.8)
    ax.set_xlabel("tiempo (s)")
    ax.set_ylabel("torque setpoint (norm)")
    ax.legend(loc="upper right", ncol=3)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    C.title_block(fig, "Torque setpoint (roll/pitch/yaw)", path.split("/")[-1])
    C.save(fig, outdir, "torque")


def analyze(path):
    ulog = C.load(path)
    print(f"\n=== {path}  ({C.duration(ulog):.1f}s) ===")
    outdir = C.outdir_for(path)
    sat = plot_motors(ulog, path, outdir)
    plot_torque(ulog, path, outdir)
    if sat is None:
        print("   (sin actuator_motors)")
        return
    cls = "SATURADO" if sat else "idle limpio"
    print(f"   clase: {cls}")
    if sat:
        detail = ", ".join(f"{i}({MOTOR_POS[i]}/{SPIN[i]})" for i in sat)
        print(f"   motores saturados: {detail}")
        print(f"   eje probable: {axis_guess(sat)}")


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
