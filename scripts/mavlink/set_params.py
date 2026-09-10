#!/usr/bin/env python3
"""Escribe parametros con verificacion por lectura y los guarda en la NVM.

Uso:  FC_DEV=/dev/ttyACM0 python3 set_params.py EKF2_HGT_REF=0 EKF2_RNG_CTRL=1

No guarda nada si alguna escritura falla: o entran todos o ninguno.
"""
import sys, time
import fc
from pymavlink import mavutil

cambios = []
for arg in sys.argv[1:]:
    if '=' not in arg:
        raise SystemExit(f"formato: NOMBRE=valor  (recibido: {arg})")
    n, v = arg.split('=', 1)
    cambios.append((n.strip(), float(v)))
if not cambios:
    raise SystemExit(__doc__)

m = fc.connect()
ok = True
for name, want in cambios:
    antes = fc.param_get(m, name)
    if antes is None:
        print(f"{name}: NO EXISTE en este firmware"); ok = False; continue
    ptype = antes.param_type
    m.mav.param_set_send(m.target_system, m.target_component,
                         name.encode(), fc.encode(want, ptype), ptype)
    time.sleep(0.3)
    despues = fc.param_get(m, name)
    got = fc.decode(despues) if despues else None
    bien = got is not None and abs(float(got) - want) < 1e-6
    ok = ok and bien
    print(f"{name:18s} {fc.decode(antes)} -> {got}   [{'OK' if bien else 'FALLO'}]")

if ok:
    m.mav.command_long_send(m.target_system, m.target_component,
        mavutil.mavlink.MAV_CMD_PREFLIGHT_STORAGE, 0, 1, -1, 0, 0, 0, 0, 0)
    ack = m.recv_match(type='COMMAND_ACK', blocking=True, timeout=5)
    print("param save ack:", ack.result if ack else "sin ack")
    print("Si algun parametro pide reboot, reinicia con reboot_fc.py")
else:
    print("NO se guarda nada: hubo fallos")
    sys.exit(1)
