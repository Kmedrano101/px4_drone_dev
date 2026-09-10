#!/usr/bin/env python3
"""Vuelca TODOS los parametros del FC a un .params con formato QGC.

Uso:  FC_DEV=/dev/ttyACM0 python3 dump_params.py salida.params
"""
import sys, time
import fc
from pymavlink import mavutil

out = sys.argv[1] if len(sys.argv) > 1 else 'backup.params'

m = fc.connect()
m.mav.param_request_list_send(m.target_system, m.target_component)

params, total, t_last = {}, None, time.time()
while time.time() - t_last < 5:          # corta tras 5 s sin recibir nada
    msg = m.recv_match(type='PARAM_VALUE', blocking=True, timeout=1)
    if msg is None:
        continue
    t_last = time.time()
    total = msg.param_count
    params[msg.param_id.strip('\x00')] = (fc.decode(msg), msg.param_type)
    if total and len(params) >= total:
        break

print(f"recibidos {len(params)} / {total}")
if total and len(params) < total:
    print("AVISO: volcado incompleto, repite el comando")

ver = fc.autopilot_version(m)
fw = "desconocida"
if ver:
    v = ver.flight_sw_version
    fw = f"{(v>>24)&0xff}.{(v>>16)&0xff}.{(v>>8)&0xff}"

with open(out, 'w') as f:
    f.write("# Onboard parameters for Vehicle 1\n#\n# Stack: PX4 Pro\n# Vehicle: Multi-Rotor\n")
    f.write(f"# Version: {fw}\n#\n# Vehicle-Id Component-Id Name Value Type\n")
    for name in sorted(params):
        val, ptype = params[name]
        if ptype == mavutil.mavlink.MAV_PARAM_TYPE_REAL32:
            f.write(f"1\t1\t{name}\t{val:.18f}\t9\n")
        else:
            f.write(f"1\t1\t{name}\t{int(val)}\t6\n")
print("escrito:", out)
