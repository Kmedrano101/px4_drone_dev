#!/usr/bin/env python3
"""
Monitoreo de temperatura del FC desde logs .ulog.

Grafica la temperatura de baro (SPL06) e IMU (BMI088 accel/gyro) a lo largo del
tiempo, con líneas de umbral (aviso 80 °C, límite del sensor 85 °C) y tendencia
(Δ y °C/min). Útil para vigilar el calentamiento del FC (sobre todo en banco,
sin airflow).

Uso:
    python3 analyze_temperature.py <log.ulg | carpeta>

Salida: scripts/output/<log>/temperatura.png  + resumen por consola.
"""
import sys
import _common as C

WARN_C = 80.0   # aviso
LIMIT_C = 85.0  # límite operativo típico de BMI088 / SPL06

# Series a extraer: (topic, instancia, campo, etiqueta)
SERIES = [
    ("sensor_baro",         0, "temperature", "Baro SPL06"),
    ("sensor_accel",        0, "temperature", "IMU accel[0]"),
    ("sensor_accel",        1, "temperature", "IMU accel[1]"),
    ("vehicle_imu_status",  0, "temperature_gyro", "IMU gyro[0]"),
]


def analyze(path):
    ulog = C.load(path)
    dur = C.duration(ulog)
    t0 = ulog.start_timestamp
    print(f"\n=== {path}  ({dur:.1f}s) ===")

    C.setup_style()
    fig, ax = C.plt.subplots()

    plotted = 0
    summary = []
    for i, (topic, inst, fld, label) in enumerate(SERIES):
        data = C.get(ulog, topic, inst)
        vals = C.field(data, fld)
        if data is None or vals is None:
            continue
        ts = data["timestamp"]
        pairs = [(t, float(v)) for t, v in zip(ts, vals) if not C.isnan(v)]
        pairs = [(t, v) for t, v in pairs if v != 0.0]       # 0.0 = sin dato
        if len(pairs) < 2:
            continue
        x = C.secs([t for t, _ in pairs], t0)
        y = [v for _, v in pairs]
        color = C.PALETTE[i % len(C.PALETTE)]
        ax.plot(x, y, color=color, label=label)
        # etiqueta directa al final de la línea
        ax.annotate(f"{y[-1]:.0f}°", (x[-1], y[-1]), color=color,
                    fontsize=9, fontweight="bold", va="center",
                    xytext=(6, 0), textcoords="offset points")
        rate = (y[-1] - y[0]) / (dur / 60.0) if dur > 0 else 0
        summary.append((label, y[0], y[-1], min(y), max(y), y[-1] - y[0], rate))
        plotted += 1

    if plotted == 0:
        print("   (sin datos de temperatura)")
        C.plt.close(fig)
        return

    # Umbrales
    xlim = ax.get_xlim()
    ax.axhline(WARN_C, color=C.WARN, lw=1.2, ls="--")
    ax.axhline(LIMIT_C, color=C.CRIT, lw=1.2, ls="--")
    ax.text(xlim[1], WARN_C, " aviso 80°", color=C.WARN, va="bottom", ha="right", fontsize=8)
    ax.text(xlim[1], LIMIT_C, " límite 85°", color=C.CRIT, va="bottom", ha="right", fontsize=8)

    ax.set_xlabel("tiempo (s)")
    ax.set_ylabel("temperatura (°C)")
    ax.legend(loc="lower right", ncol=2)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    C.title_block(fig, "Temperatura del FC",
                  f"{path.split('/')[-1]} · {dur:.0f}s · aviso 80° / límite 85°")

    outdir = C.outdir_for(path)
    C.save(fig, outdir, "temperatura")

    # Resumen por consola
    print(f"   {'serie':16}{'ini':>7}{'fin':>7}{'min':>7}{'max':>7}{'Δ':>7}{'°C/min':>9}")
    for label, ini, fin, mn, mx, delta, rate in summary:
        flag = ""
        if mx >= LIMIT_C:
            flag = "  🔴 >límite"
        elif mx >= WARN_C:
            flag = "  🟠 >aviso"
        print(f"   {label:16}{ini:7.1f}{fin:7.1f}{mn:7.1f}{mx:7.1f}{delta:+7.1f}{rate:9.1f}{flag}")


def main():
    arg = sys.argv[1] if len(sys.argv) > 1 else None
    logs = C.resolve_logs(arg)
    if not logs:
        print("No hay .ulg. Pon logs en scripts/input/ o pasa una ruta/carpeta.")
        sys.exit(1)
    print(f"Analizando temperatura en {len(logs)} log(s)")
    for l in logs:
        try:
            analyze(l)
        except Exception as e:
            print(f"   ERROR en {l}: {e}")


if __name__ == "__main__":
    main()
