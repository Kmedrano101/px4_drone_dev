#!/usr/bin/env python3
"""
Analizador avanzado del problema de "ruido al armar" (motores a 100%).
Clasifica cada log armar/desarmar y, en los saturados, identifica el eje
(roll/pitch/yaw) y la causa probable: windup por error de heading,
stick de yaw descentrado, o airmode.

Uso:  python3 analyze_motor_noise.py [carpeta_logs]
"""
import sys, os, glob, math
from pyulog import ULog

LOGDIR = sys.argv[1] if len(sys.argv) > 1 else \
    '/home/kmedrano/Documents/QGroundControl/Logs'

# Geometria del quad (de CA_ROTORx): mapeo motor -> posicion y sentido
# 0=FR(CCW) 1=RL(CCW) 2=FL(CW) 3=RR(CW)
MOTOR_POS = {0: 'front-right', 1: 'rear-left', 2: 'front-left', 3: 'rear-right'}
SPIN = {0: 'CCW', 1: 'CCW', 2: 'CW', 3: 'CW'}
NAV_STATE = {0: 'Manual', 1: 'Altitude', 2: 'Position', 3: 'Mission',
             4: 'Loiter', 5: 'RTL', 10: 'Acro', 14: 'Offboard',
             15: 'Stabilized', 17: 'Takeoff', 18: 'Land', 19: 'FollowTarget'}

SAT = 0.95   # umbral de saturacion (95%)


def get(ulog, topic, inst=0):
    for d in ulog.data_list:
        if d.name == topic and d.multi_id == inst:
            return d.data
    return None


def field(data, *names):
    for n in names:
        if data is not None and n in data:
            return data[n]
    return None


def stats(arr):
    arr = [x for x in arr if not math.isnan(x)]
    if not arr:
        return (0, 0, 0)
    return (min(arr), sum(arr) / len(arr), max(arr))


def analyze(path):
    base = os.path.basename(path)
    try:
        ulog = ULog(path)
    except Exception as e:
        print(f'{base}: ERROR {e}')
        return None

    p = ulog.initial_parameters
    rep = {'name': base, 'params': {
        'DSHOT_MIN': p.get('DSHOT_MIN'),
        'DSHOT_BIDIR_EN': p.get('DSHOT_BIDIR_EN'),
        'MC_AIRMODE': p.get('MC_AIRMODE'),
        'MC_YAW_P': p.get('MC_YAW_P'),
        'MC_YAWRATE_I': p.get('MC_YAWRATE_I'),
    }}

    m = get(ulog, 'actuator_motors')
    if m is None:
        rep['class'] = 'sin actuator_motors'
        return rep

    mx = []
    for i in range(4):
        c = field(m, f'control[{i}]')
        mx.append(max([v for v in c if not math.isnan(v)], default=0.0))
    rep['motor_max'] = mx
    saturated = [i for i, v in enumerate(mx) if v >= SAT]
    rep['saturated_motors'] = saturated
    rep['class'] = 'SATURADO' if saturated else 'idle limpio'

    if not saturated:
        return rep

    # Eje saturado segun los pares
    setA, setB = {0, 1}, {2, 3}
    s = set(saturated)
    if s == setA or s == setB:
        rep['axis_guess'] = 'YAW (diagonal mismo sentido a tope)'
    elif s == {0, 3} or s == {1, 2}:
        rep['axis_guess'] = 'ROLL'
    elif s == {0, 2} or s == {1, 3}:
        rep['axis_guess'] = 'PITCH'
    else:
        rep['axis_guess'] = f'mixto {saturated}'

    # Confirmar con torque setpoint
    tq = get(ulog, 'vehicle_torque_setpoint')
    if tq is not None:
        rep['torque'] = {
            'roll': stats(field(tq, 'xyz[0]')),
            'pitch': stats(field(tq, 'xyz[1]')),
            'yaw': stats(field(tq, 'xyz[2]')),
        }

    # Sticks del piloto (RC)
    mc = get(ulog, 'manual_control_setpoint')
    if mc is not None:
        rep['sticks'] = {
            'roll': stats(field(mc, 'roll', 'y')),
            'pitch': stats(field(mc, 'pitch', 'x')),
            'yaw': stats(field(mc, 'yaw', 'r')),
            'throttle': stats(field(mc, 'throttle', 'z')),
        }

    # Rate setpoint vs medido (yaw) -> windup?
    rs = get(ulog, 'vehicle_rates_setpoint')
    if rs is not None:
        rep['yaw_rate_sp'] = stats(field(rs, 'yaw'))
    av = get(ulog, 'vehicle_angular_velocity')
    if av is not None:
        yawspeed = field(av, 'xyz[2]')
        if yawspeed is not None:
            rep['yaw_rate_meas'] = stats(yawspeed)

    # Modo de vuelo
    vs = get(ulog, 'vehicle_status')
    if vs is not None:
        ns = field(vs, 'nav_state')
        if ns is not None:
            modes = sorted(set(int(x) for x in ns))
            rep['modes'] = [NAV_STATE.get(x, str(x)) for x in modes]

    return rep


def main():
    logs = sorted(glob.glob(f'{LOGDIR}/*.ulg'))
    print(f'Analizando {len(logs)} logs en {LOGDIR}\n' + '=' * 70)
    reps = [analyze(l) for l in logs]
    reps = [r for r in reps if r]

    print('\n### RESUMEN ###')
    print(f"{'log':<16}{'clase':<14}{'motores sat.':<18}{'eje'}")
    for r in reps:
        sm = ','.join(str(i) for i in r.get('saturated_motors', [])) or '-'
        print(f"{r['name'][:15]:<16}{r['class']:<14}{sm:<18}{r.get('axis_guess','')}")

    sats = [r for r in reps if r['class'] == 'SATURADO']
    if not sats:
        print('\nNo hay logs saturados.')
        return

    print('\n' + '=' * 70)
    print('### DETALLE DE LOS SATURADOS ###')
    for r in sats:
        print(f"\n--- {r['name']} ---")
        print(f"  motores saturados: {r['saturated_motors']} "
              f"({', '.join(MOTOR_POS[i]+'/'+SPIN[i] for i in r['saturated_motors'])})")
        print(f"  eje probable: {r.get('axis_guess')}")
        print(f"  modos de vuelo: {r.get('modes')}")
        if 'torque' in r:
            print("  torque setpoint (min,avg,max):")
            for k, v in r['torque'].items():
                flag = '  <== DOMINANTE' if abs(v[2]) > 0.5 or abs(v[0]) > 0.5 else ''
                print(f"     {k:<6} {tuple(round(x,3) for x in v)}{flag}")
        if 'sticks' in r:
            print("  sticks RC (min,avg,max):")
            for k, v in r['sticks'].items():
                flag = ''
                if k == 'yaw' and (abs(v[1]) > 0.05):
                    flag = '  <== YAW STICK DESCENTRADO!'
                print(f"     {k:<8} {tuple(round(x,3) for x in v)}{flag}")
        if 'yaw_rate_sp' in r:
            print(f"  yaw rate setpoint (min,avg,max): {tuple(round(x,3) for x in r['yaw_rate_sp'])}")
        if 'yaw_rate_meas' in r:
            print(f"  yaw rate medido   (min,avg,max): {tuple(round(x,3) for x in r['yaw_rate_meas'])}")

    print('\n' + '=' * 70)
    print('### PARAMETROS RELEVANTES (del primer log) ###')
    for k, v in reps[0]['params'].items():
        print(f"  {k:<16} = {v}")


if __name__ == '__main__':
    main()
