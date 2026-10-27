#!/usr/bin/env python3
"""Chequeo EKF2 + GPS RTK con el dron ARMADO en tierra, SIN despegue.

Antes de un vuelo real: confirma que, ya armado y quieto en el suelo, el EKF2
tiene posicion global ABSOLUTA valida y estable con el GPS (RTK si hay NTRIP),
sin glitches, con buena exactitud y heading. No despega.

IMPORTANTE - seguridad:
  - El script NO ARMA. Lo arma Kevin (RC o QGC). El script espera a detectar el
    armado, monitoriza --hold segundos y luego AUTO-DESARMA (como las pruebas de
    banco). SIGINT desde la webui -> desarma y cierra.
  - Pensado con HELICES QUITADAS. En tierra los motores pueden ir al ralenti.

Que mide (por MAVLink, GPS_RAW_INT + ESTIMATOR_STATUS + GLOBAL/LOCAL_POSITION):
  fix_type (RTK 5/6?), satelites, eph; flags del EKF POS_HORIZ_ABS / VELOCITY /
  ATTITUDE / GPS_GLITCH; exactitud horizontal del EKF, mag_ratio, y la deriva de
  la posicion local estando quieto. Escribe CSV + resumen con veredicto.

Uso:
  FC_DEV=/dev/ttyACM0 python3 ekf_rtk_armed_check.py --hold 15 --eph-max 1.0 \
     --auto-disarm 1 --out-dir /ruta
"""
import os, sys, time, csv, math, signal, argparse, datetime
from pymavlink import mavutil

FIX = {0: "no-GPS", 1: "sin-fix", 2: "2D", 3: "3D", 4: "DGPS",
       5: "RTK-float", 6: "RTK-fixed", 7: "static", 8: "PPP"}
# ESTIMATOR_STATUS_FLAGS
F_ATT = 1; F_VELH = 2; F_POSHR = 8; F_POSHA = 16; F_GLITCH = 1024; F_ACCERR = 2048
ARMED_BIT = mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED  # 128

ap = argparse.ArgumentParser()
ap.add_argument("--hold", type=float, default=15, help="segundos armado a monitorizar")
ap.add_argument("--eph-max", type=float, default=1.0, help="eph bueno (m)")
ap.add_argument("--max-wait", type=float, default=180, help="espera max al armado (s)")
ap.add_argument("--hz", type=float, default=2.0)
ap.add_argument("--auto-disarm", type=float, default=1, help="1=auto-desarma al cumplir --hold")
ap.add_argument("--out-dir", default=".")
a = ap.parse_args()

DEV = os.environ.get("FC_DEV", "/dev/ttyACM0")
BAUD = int(os.environ.get("FC_BAUD", "115200"))
os.makedirs(a.out_dir, exist_ok=True)
stamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
csv_path = os.path.join(a.out_dir, f"{stamp}_ekf_rtk_armed.csv")
sum_path = os.path.join(a.out_dir, f"{stamp}_ekf_rtk_armed_summary.txt")

_stop = {"flag": False}
def _sig(*_): _stop["flag"] = True
signal.signal(signal.SIGINT, _sig)
signal.signal(signal.SIGTERM, _sig)

st = {"fix": 0, "sats": 0, "eph": float("nan"), "lat": None, "lon": None,
      "flags": 0, "pos_acc": float("nan"), "mag_ratio": float("nan"),
      "lx": None, "ly": None, "lz": None, "armed": False}


def connect():
    m = mavutil.mavlink_connection(DEV, baud=BAUD, source_system=250, source_component=190)
    t0 = time.time()
    while time.time() - t0 < 45 and not _stop["flag"]:
        m.mav.heartbeat_send(mavutil.mavlink.MAV_TYPE_GCS,
                             mavutil.mavlink.MAV_AUTOPILOT_INVALID, 0, 0, 0)
        try:
            hb = m.recv_match(type="HEARTBEAT", blocking=True, timeout=0.5)
        except Exception:
            continue
        if hb and hb.get_srcSystem() != 250:
            return m
    raise SystemExit("sin heartbeat del FC (revisa USB/puerto)")


def drain(m, secs):
    """Lee mensajes durante ~secs actualizando st; manda heartbeat."""
    t_end = time.time() + secs
    m.mav.heartbeat_send(mavutil.mavlink.MAV_TYPE_GCS,
                         mavutil.mavlink.MAV_AUTOPILOT_INVALID, 0, 0, 0)
    while time.time() < t_end:
        try:
            msg = m.recv_match(blocking=True, timeout=0.2, type=[
                "HEARTBEAT", "GPS_RAW_INT", "ESTIMATOR_STATUS",
                "GLOBAL_POSITION_INT", "LOCAL_POSITION_NED"])
        except Exception:
            continue
        if msg is None:
            continue
        t = msg.get_type()
        if t == "HEARTBEAT" and msg.get_srcSystem() != 250:
            st["armed"] = bool(msg.base_mode & ARMED_BIT)
        elif t == "GPS_RAW_INT":
            st["fix"] = msg.fix_type; st["sats"] = msg.satellites_visible
            st["eph"] = msg.eph / 100.0 if msg.eph != 65535 else float("nan")
            st["lat"] = msg.lat / 1e7; st["lon"] = msg.lon / 1e7
        elif t == "ESTIMATOR_STATUS":
            st["flags"] = msg.flags
            st["pos_acc"] = msg.pos_horiz_accuracy
            st["mag_ratio"] = msg.mag_ratio
        elif t == "LOCAL_POSITION_NED":
            st["lx"] = msg.x; st["ly"] = msg.y; st["lz"] = msg.z


def req(m, mid, hz):
    m.mav.command_long_send(m.target_system, m.target_component,
        mavutil.mavlink.MAV_CMD_SET_MESSAGE_INTERVAL, 0, mid, int(1e6 / hz), 0, 0, 0, 0, 0)


def disarm(m):
    print("# AUTO-DESARMANDO (force)...", flush=True)
    for _ in range(3):
        m.mav.command_long_send(m.target_system, m.target_component,
            mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM, 0, 0, 21196, 0, 0, 0, 0, 0)
        drain(m, 1.0)
        if not st["armed"]:
            print("# desarmado OK", flush=True); return True
    print("# AVISO: sigue armado -> baja el switch de ARM del RC", flush=True)
    return False


def fl(v, n=2): return "--" if v != v else f"{v:.{n}f}"


m = connect()
for mid, hz in ((mavutil.mavlink.MAVLINK_MSG_ID_GPS_RAW_INT, a.hz),
                (mavutil.mavlink.MAVLINK_MSG_ID_ESTIMATOR_STATUS, a.hz),
                (mavutil.mavlink.MAVLINK_MSG_ID_GLOBAL_POSITION_INT, a.hz),
                (mavutil.mavlink.MAVLINK_MSG_ID_LOCAL_POSITION_NED, a.hz)):
    req(m, mid, hz)

est_seen = {"any": False}
print("# EKF2 + GPS RTK armado en tierra. NO despega. Kevin arma (RC/QGC).", flush=True)
print(f"# esperando ARMADO (max {a.max_wait:.0f}s). Objetivo: EKF POS_HORIZ_ABS + eph<={a.eph_max:.1f} m.", flush=True)
print("# %-6s %-10s %-4s %-7s %-9s %-9s %-7s %-6s" %
      ("t(s)", "fix", "sat", "eph", "POS_ABS", "exact(m)", "magR", "ARM"), flush=True)

# --- fase PREARM: esperar a que Kevin arme ---
t0 = time.time()
while not _stop["flag"] and not st["armed"] and (time.time() - t0) < a.max_wait:
    drain(m, 1.0 / a.hz)
    if st["flags"]:
        est_seen["any"] = True
    posabs = bool(st["flags"] & F_POSHA)
    print("  %-6.0f %-10s %-4d %-7s %-9s %-9s %-7s %-6s" % (
        time.time() - t0, FIX.get(st["fix"], st["fix"]), st["sats"], fl(st["eph"]),
        "SI" if posabs else "no", fl(st["pos_acc"]), fl(st["mag_ratio"]), "no"), flush=True)

armed_detected = st["armed"]
rows = []
samp = {"poshr_all": True, "att_all": True, "velh_all": True,
        "glitch": 0, "eph_min": math.inf, "eph_max": 0, "acc_max": 0,
        "mag_max": 0, "best_fix": 0, "fix_dist": {}, "lx0": None, "ly0": None, "drift_max": 0}

if armed_detected:
    print(f"# ARMADO detectado -> monitorizando {a.hold:.0f}s...", flush=True)
    with open(csv_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["t_s", "fix_type", "fix_label", "sats", "eph_m", "pos_horiz_abs",
                    "pos_acc_m", "mag_ratio", "gps_glitch", "lx", "ly", "lz", "drift_m"])
        ta = time.time()
        while not _stop["flag"] and (time.time() - ta) < a.hold and st["armed"]:
            drain(m, 1.0 / a.hz)
            t = time.time() - ta
            fx = st["fix"]; flags = st["flags"]
            posabs = bool(flags & F_POSHA); glit = bool(flags & F_GLITCH)
            if samp["lx0"] is None and st["lx"] is not None:
                samp["lx0"], samp["ly0"] = st["lx"], st["ly"]
            drift = 0.0
            if samp["lx0"] is not None and st["lx"] is not None:
                drift = math.hypot(st["lx"] - samp["lx0"], st["ly"] - samp["ly0"])
            w.writerow([f"{t:.1f}", fx, FIX.get(fx, fx), st["sats"], fl(st["eph"]),
                        int(posabs), fl(st["pos_acc"], 3), fl(st["mag_ratio"], 3), int(glit),
                        fl(st["lx"], 3) if st["lx"] is not None else "",
                        fl(st["ly"], 3) if st["ly"] is not None else "",
                        fl(st["lz"], 3) if st["lz"] is not None else "", f"{drift:.3f}"])
            f.flush()
            samp["poshr_all"] &= posabs
            samp["att_all"] &= bool(flags & F_ATT)
            samp["velh_all"] &= bool(flags & F_VELH)
            samp["glitch"] += int(glit)
            if st["eph"] == st["eph"]:
                samp["eph_min"] = min(samp["eph_min"], st["eph"]); samp["eph_max"] = max(samp["eph_max"], st["eph"])
            if st["pos_acc"] == st["pos_acc"]:
                samp["acc_max"] = max(samp["acc_max"], st["pos_acc"])
            if st["mag_ratio"] == st["mag_ratio"]:
                samp["mag_max"] = max(samp["mag_max"], st["mag_ratio"])
            samp["best_fix"] = max(samp["best_fix"], fx)
            samp["fix_dist"][fx] = samp["fix_dist"].get(fx, 0) + 1
            samp["drift_max"] = max(samp["drift_max"], drift)
            print("  %-6.1f %-10s %-4d %-7s %-9s %-9s %-7s %-6s" % (
                t, FIX.get(fx, fx), st["sats"], fl(st["eph"]),
                "SI" if posabs else "NO", fl(st["pos_acc"], 2), fl(st["mag_ratio"], 2),
                "SI" + ("!glitch" if glit else "")), flush=True)
    if a.auto_disarm >= 0.5 and st["armed"]:
        disarm(m)

# --- resumen ---
L = ["=== EKF2 + GPS RTK armado en tierra ===", f"fecha: {stamp}"]
if not armed_detected:
    L.append("RESULTADO: no se detecto ARMADO (lo arma Kevin). Nada que evaluar.")
    if _stop["flag"]:
        L.append("(parado desde la webui / SIGINT)")
else:
    ns = sum(samp["fix_dist"].values())
    fixd = ", ".join(f"{FIX.get(k,k)}:{v}" for k, v in sorted(samp["fix_dist"].items()))
    L.append(f"muestras armado: {ns}   (parado: {'si' if _stop['flag'] else 'no'})")
    L.append(f"mejor fix: {FIX.get(samp['best_fix'], samp['best_fix'])}   distribucion: {fixd}")
    L.append(f"RTK: {'SI (' + FIX[samp['best_fix']] + ')' if samp['best_fix'] in (5,6) else 'NO (autonomo; activa NTRIP en QGC)'}")
    L.append(f"eph: min {fl(samp['eph_min']) if samp['eph_min']!=math.inf else 'n/d'} / max {fl(samp['eph_max'])} m (objetivo <= {a.eph_max:.1f})")
    L.append(f"exactitud EKF horiz. max: {fl(samp['acc_max'])} m")
    L.append(f"mag_ratio max: {fl(samp['mag_max'])} (bueno < 1.0)")
    L.append(f"deriva de la pos. local estando quieto: {samp['drift_max']:.3f} m")
    L.append(f"EKF POS_HORIZ_ABS sostenido: {'SI' if samp['poshr_all'] else 'NO (perdio posicion absoluta!)'}")
    L.append(f"EKF ATTITUDE/VEL_HORIZ sostenidos: att={'si' if samp['att_all'] else 'NO'} velH={'si' if samp['velh_all'] else 'NO'}")
    L.append(f"GPS glitches: {samp['glitch']}")
    if not est_seen["any"] and not samp["poshr_all"]:
        L.append("(nota: no llego ESTIMATOR_STATUS; las flags del EKF pueden no ser fiables)")
    ok = (samp["poshr_all"] and samp["att_all"] and samp["velh_all"] and samp["glitch"] == 0
          and samp["eph_max"] <= a.eph_max and (samp["mag_max"] < 1.0 or samp["mag_max"] != samp["mag_max"]))
    rtk = samp["best_fix"] in (5, 6)
    L.append(f"VEREDICTO: {'EKF2+GPS LISTO para volar' if ok else 'REVISAR antes de volar'}"
             + (" (RTK fixed)" if samp["best_fix"] == 6 else " (RTK float)" if samp["best_fix"] == 5 else " (sin RTK)"))
summary = "\n".join(L)
try:
    with open(sum_path, "w") as f:
        f.write(summary + "\n")
except OSError:
    pass
print("\n" + summary, flush=True)
if armed_detected:
    print(f"\n# CSV:     {csv_path}", flush=True)
    print(f"# resumen: {sum_path}", flush=True)
