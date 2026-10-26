#!/usr/bin/env python3
"""Validacion del GPS (F9P) en campo abierto por MAVLink. SOLO LECTURA.

Pensado para arrancar/parar desde la webui (tarjeta 'script'): muestrea
GPS_RAW_INT (fix, satelites, eph/epv, lat/lon, hdop/vdop) a una CSV, imprime
una linea por muestra para seguirlo en vivo, y escribe un RESUMEN cuando:
  - alcanza un buen fix SOSTENIDO (fix>=3D, sats>=target, eph<=eph-max) durante
    --dwell segundos  -> parada automatica (exito), o
  - se alcanza --max-duration, o
  - lo paras desde la webui (SIGINT) -> cierra limpio y resume lo capturado.

No arma, no cambia parametros. OJO RTK: sin inyeccion de RTCM (NTRIP/base) el
F9P va en autonomo (~1-2 m); el script registra igual y captura fix_type 5/6
(RTK float/fixed) si llegan correcciones.

Uso directo:
  FC_DEV=/dev/ttyACM0 python3 gps_rtk_validate.py \
     --target-sats 15 --eph-max 2.0 --dwell 20 --max-duration 1800 \
     --hz 1 --out-dir /ruta/salida
"""
import os, sys, time, csv, json, math, signal, argparse, datetime
from pymavlink import mavutil

FIX = {0: "no-GPS", 1: "sin-fix", 2: "2D", 3: "3D", 4: "DGPS",
       5: "RTK-float", 6: "RTK-fixed", 7: "static", 8: "PPP"}

ap = argparse.ArgumentParser()
ap.add_argument("--target-sats", type=float, default=15)
ap.add_argument("--eph-max", type=float, default=2.0)
ap.add_argument("--dwell", type=float, default=20)
ap.add_argument("--max-duration", type=float, default=1800)
ap.add_argument("--hz", type=float, default=1.0)
ap.add_argument("--out-dir", default=".")
a = ap.parse_args()

DEV = os.environ.get("FC_DEV", "/dev/ttyACM0")
BAUD = int(os.environ.get("FC_BAUD", "115200"))
os.makedirs(a.out_dir, exist_ok=True)
stamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
csv_path = os.path.join(a.out_dir, f"{stamp}_gps_rtk.csv")
sum_path = os.path.join(a.out_dir, f"{stamp}_gps_rtk_summary.txt")

_stop = {"flag": False}
def _sig(*_):          # la webui manda SIGINT para parar -> cerramos limpio
    _stop["flag"] = True
signal.signal(signal.SIGINT, _sig)
signal.signal(signal.SIGTERM, _sig)


def connect():
    """Abre MAVLink y 'despierta' el USB del PX4 mandando heartbeats."""
    m = mavutil.mavlink_connection(DEV, baud=BAUD, source_system=250, source_component=190)
    t0 = time.time()
    while time.time() - t0 < 45 and not _stop["flag"]:
        m.mav.heartbeat_send(mavutil.mavlink.MAV_TYPE_GCS,
                             mavutil.mavlink.MAV_AUTOPILOT_INVALID, 0, 0, 0)
        try:
            hb = m.recv_match(type='HEARTBEAT', blocking=True, timeout=0.5)
        except Exception:
            continue          # frame corrupto al sincronizar -> reintentar
        if hb and hb.get_srcSystem() != 250:
            return m
    raise SystemExit("sin heartbeat del FC (revisa USB/puerto)")


m = connect()
m.mav.command_long_send(m.target_system, m.target_component,
    mavutil.mavlink.MAV_CMD_SET_MESSAGE_INTERVAL, 0,
    mavutil.mavlink.MAVLINK_MSG_ID_GPS_RAW_INT, int(1e6 / a.hz), 0, 0, 0, 0, 0)

print(f"# GPS validate -> {csv_path}", flush=True)
print(f"# objetivo: fix>=3D, sats>={a.target_sats:.0f}, eph<={a.eph_max:.1f} m sostenido {a.dwell:.0f}s", flush=True)
print("# %-7s %-9s %-4s %-13s %-13s %-8s %-7s %-6s" %
      ("t(s)", "fix", "sat", "lat", "lon", "eph(m)", "hdop", "estado"), flush=True)

t0 = time.time()
n = 0
best_fix = 0
best_sats = 0
min_eph = math.inf
t_first3d = None
good_since = None
last_row = None
last_hb = 0.0
stop_reason = "max-duration"

with open(csv_path, "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["t_s", "fix_type", "fix_label", "sats", "lat_deg", "lon_deg",
                "alt_m", "eph_m", "epv_m", "hdop", "vdop"])

    while not _stop["flag"] and (time.time() - t0) < a.max_duration:
        if time.time() - last_hb > 1.0:
            m.mav.heartbeat_send(mavutil.mavlink.MAV_TYPE_GCS,
                                 mavutil.mavlink.MAV_AUTOPILOT_INVALID, 0, 0, 0)
            last_hb = time.time()
        try:
            msg = m.recv_match(type='GPS_RAW_INT', blocking=True, timeout=1.5)
        except Exception:
            continue          # frame corrupto -> ignorar esta muestra
        if msg is None:
            continue
        t = time.time() - t0
        fix = msg.fix_type
        sats = msg.satellites_visible
        lat = msg.lat / 1e7
        lon = msg.lon / 1e7
        alt = msg.alt / 1e3
        eph = msg.eph / 100.0 if msg.eph != 65535 else float("nan")
        epv = msg.epv / 100.0 if msg.epv != 65535 else float("nan")
        n += 1
        w.writerow([f"{t:.1f}", fix, FIX.get(fix, fix), sats,
                    f"{lat:.7f}", f"{lon:.7f}", f"{alt:.2f}",
                    "" if eph != eph else f"{eph:.2f}",
                    "" if epv != epv else f"{epv:.2f}", "", ""])
        f.flush()

        best_fix = max(best_fix, fix)
        best_sats = max(best_sats, sats)
        if eph == eph:
            min_eph = min(min_eph, eph)
        if fix >= 3 and t_first3d is None:
            t_first3d = t
        last_row = (t, fix, sats, lat, lon, eph)

        good = (fix >= 3 and sats >= a.target_sats and (eph != eph or eph <= a.eph_max))
        if good:
            good_since = good_since if good_since is not None else t
            held = t - good_since
            estado = f"OK {held:.0f}/{a.dwell:.0f}s"
        else:
            good_since = None
            estado = "esperando"

        print("  %-7.1f %-9s %-4d %-13.7f %-13.7f %-8s %-7s %-6s" %
              (t, FIX.get(fix, str(fix)), sats, lat, lon,
               ("--" if eph != eph else f"{eph:.2f}"), "", estado), flush=True)

        if good_since is not None and (t - good_since) >= a.dwell:
            stop_reason = "buen-fix-sostenido"
            break

if _stop["flag"]:
    stop_reason = "parado-desde-webui"

# ---- resumen ----
lines = []
lines.append("=== Resumen validacion GPS (F9P) ===")
lines.append(f"fecha: {stamp}   duracion: {time.time()-t0:.0f} s   muestras: {n}")
lines.append(f"motivo de parada: {stop_reason}")
lines.append(f"mejor fix: {best_fix} ({FIX.get(best_fix, best_fix)})")
lines.append(f"max satelites: {best_sats}")
lines.append(f"min eph: {'n/d' if min_eph is math.inf else f'{min_eph:.2f} m'}")
lines.append(f"tiempo hasta fix 3D: {'no alcanzado' if t_first3d is None else f'{t_first3d:.0f} s'}")
lines.append(f"RTK: {'SI (' + FIX[best_fix] + ')' if best_fix in (5, 6) else 'no (autonomo; sin inyeccion RTCM)'}")
if last_row:
    t, fix, sats, lat, lon, eph = last_row
    lines.append(f"ultima posicion: {lat:.7f}, {lon:.7f}  (fix {FIX.get(fix, fix)}, {sats} sats)")
    lines.append(f"Google Maps: https://maps.google.com/?q={lat:.7f},{lon:.7f}")
veredicto = "OK" if (best_fix >= 3 and best_sats >= a.target_sats) else "INSUFICIENTE"
lines.append(f"VEREDICTO: {veredicto}")
summary = "\n".join(lines)
with open(sum_path, "w") as f:
    f.write(summary + "\n")
print("\n" + summary, flush=True)
print(f"\n# CSV:     {csv_path}", flush=True)
print(f"# resumen: {sum_path}", flush=True)
