#!/usr/bin/env python3
"""
Analiza por qué un intento de takeoff falló / no armó.
Reporta: modo de vuelo, estado de armado, calidad GPS, validez de la
estimación de posición (EKF), flags de failsafe y actividad de motores.

Uso:  python3 analyze_takeoff_fail.py <carpeta_logs>
"""
import sys, os, glob, math
from pyulog import ULog

LOGDIR = sys.argv[1] if len(sys.argv) > 1 else \
    '/home/kmedrano/Documents/QGroundControl/Logs/2026-06-23'

NAV = {0: 'Manual', 1: 'Altitude', 2: 'Position', 3: 'Mission', 4: 'Loiter',
       5: 'RTL', 10: 'Acro', 14: 'Offboard', 15: 'Stabilized', 17: 'Takeoff',
       18: 'Land', 19: 'FollowTarget'}
ARM = {1: 'Disarmed', 2: 'Armed'}
GPS_FIX = {0: 'no-fix', 1: 'no-fix', 2: '2D', 3: '3D', 4: 'DGPS', 5: 'RTK-float', 6: 'RTK-fixed'}


def get(ulog, topic, inst=0):
    for d in ulog.data_list:
        if d.name == topic and d.multi_id == inst:
            return d.data
    return None


def f(data, *names):
    for n in names:
        if data is not None and n in data:
            return data[n]
    return None


def frac_true(arr):
    if arr is None or len(arr) == 0:
        return None
    return sum(1 for x in arr if x) / len(arr)


def stats(arr):
    arr = [x for x in arr if not (isinstance(x, float) and math.isnan(x))]
    if not arr:
        return None
    return (round(min(arr), 3), round(sum(arr) / len(arr), 3), round(max(arr), 3))


def analyze(path):
    base = os.path.basename(path)
    print(f'\n{"="*70}\n### {base} ###')
    try:
        ulog = ULog(path)
    except Exception as e:
        print(f'  ERROR: {e}')
        return

    dur = (ulog.last_timestamp - ulog.start_timestamp) / 1e6
    print(f'  duración: {dur:.1f} s')

    # Modos y armado
    vs = get(ulog, 'vehicle_status')
    if vs is not None:
        ns = f(vs, 'nav_state')
        if ns is not None:
            modes = [NAV.get(int(x), str(int(x))) for x in sorted(set(int(v) for v in ns))]
            print(f'  modos de vuelo vistos: {modes}')
        ar = f(vs, 'arming_state')
        if ar is not None:
            armed = any(int(x) == 2 for x in ar)
            print(f'  ¿llegó a ARMAR?: {"SÍ" if armed else "NO"}')

    aa = get(ulog, 'actuator_armed')
    if aa is not None:
        armd = f(aa, 'armed')
        print(f'  armed (actuator): {frac_true(armd):.0%} del log' if armd is not None else '')

    # GPS
    gps = get(ulog, 'vehicle_gps_position') or get(ulog, 'sensor_gps')
    if gps is not None:
        ft = f(gps, 'fix_type')
        sats = f(gps, 'satellites_used')
        eph = f(gps, 'eph')
        if ft is not None:
            fixes = sorted(set(int(x) for x in ft))
            print(f'  GPS fix: {[GPS_FIX.get(x, x) for x in fixes]}')
        if sats is not None:
            print(f'  satélites (min,avg,max): {stats([float(x) for x in sats])}')
        if eph is not None:
            print(f'  EPH m (min,avg,max): {stats([float(x) for x in eph])}')

    # Validez de estimación de posición
    lp = get(ulog, 'vehicle_local_position')
    if lp is not None:
        for fld, label in [('xy_valid', 'XY válido'), ('v_xy_valid', 'Vel XY válida'),
                           ('z_valid', 'Z válido'), ('heading_good_for_control', 'heading OK ctrl')]:
            v = f(lp, fld)
            if v is not None:
                fr = frac_true(v)
                flag = '  <== PROBLEMA' if fld in ('xy_valid', 'v_xy_valid') and fr is not None and fr < 0.99 else ''
                print(f'  {label}: {fr:.0%} del log{flag}')
        eph_lp = f(lp, 'eph')
        if eph_lp is not None:
            print(f'  local_pos eph (min,avg,max): {stats([float(x) for x in eph_lp])}')

    # Failsafe flags activos
    ff = get(ulog, 'failsafe_flags')
    if ff is not None:
        print('  failsafe/condition flags ACTIVOS en algún momento:')
        any_flag = False
        for key in sorted(ff.keys()):
            if key in ('timestamp',):
                continue
            vals = ff[key]
            try:
                if any(bool(x) for x in vals):
                    fr = frac_true(vals)
                    print(f'     - {key}: {fr:.0%}')
                    any_flag = True
            except Exception:
                pass
        if not any_flag:
            print('     (ninguno)')

    # Throttle / intento de despegue
    mc = get(ulog, 'manual_control_setpoint')
    if mc is not None:
        thr = f(mc, 'throttle', 'z')
        if thr is not None:
            print(f'  throttle stick (min,avg,max): {stats([float(x) for x in thr])}')
    am = get(ulog, 'actuator_motors')
    if am is not None:
        mx = 0.0
        for i in range(4):
            c = f(am, f'control[{i}]')
            if c is not None:
                mx = max(mx, max([v for v in c if not math.isnan(v)], default=0))
        print(f'  salida máx de motor: {mx:.2f}  ({"hubo empuje alto" if mx > 0.3 else "solo idle/bajo"})')

    # Eventos/mensajes
    ev = get(ulog, 'vehicle_command')
    if ev is not None:
        cmds = f(ev, 'command')
        if cmds is not None:
            cset = sorted(set(int(x) for x in cmds))
            print(f'  comandos MAVLink: {cset}  (22=Takeoff, 400=Arm/Disarm)')


def main():
    logs = sorted(glob.glob(f'{LOGDIR}/*.ulg'))
    print(f'Analizando {len(logs)} logs en {LOGDIR}')
    for l in logs:
        analyze(l)


if __name__ == '__main__':
    main()
