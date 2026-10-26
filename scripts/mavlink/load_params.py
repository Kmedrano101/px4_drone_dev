#!/usr/bin/env python3
"""Carga un .params (formato QGC) en el FC por MAVLink: escribe los que existen,
verifica con reintento y guarda en la NVM.

Uso:  FC_DEV=/dev/ttyACM0 python3 load_params.py archivo.params

- Trae primero la lista completa de params del FC -> solo escribe los que existen
  en este firmware (los que no existan, p.ej. módulos quitados en V3, se saltan).
- Usa el TIPO que declara el FC (no el del archivo) para codificar (el int32 va
  bit a bit dentro del campo float de PARAM_SET; fc.encode lo maneja).
- No guarda si quedan fallos tras el reintento: deja claro qué revisar.
- NO reinicia el FC (hazlo con reboot_fc.py si hay params @reboot_required).
"""
import sys, time
import fc
from pymavlink import mavutil

REAL32 = mavutil.mavlink.MAV_PARAM_TYPE_REAL32

if len(sys.argv) < 2:
    raise SystemExit(__doc__)
path = sys.argv[1]

# --- parsear archivo QGC: "ver\tsys\tcomp\tNAME\tVALUE\tTYPE" ---
desired = {}
with open(path) as fh:
    for line in fh:
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        p = line.split('\t') if '\t' in line else line.split()
        if len(p) < 5:
            continue
        # formato QGC: ver(0) sysid(1) NAME(2) VALUE(3) TYPE(4)
        desired[p[2]] = float(p[3])
print(f"params en el archivo: {len(desired)}")

m = fc.connect()


def fetch_all():
    m.mav.param_request_list_send(m.target_system, m.target_component)
    cur, total, t = {}, None, time.time()
    while time.time() - t < 6:
        msg = m.recv_match(type='PARAM_VALUE', blocking=True, timeout=1)
        if msg is None:
            continue
        t = time.time()
        total = msg.param_count
        cur[msg.param_id.strip('\x00')] = msg
        if total and len(cur) >= total:
            break
    return cur, total


def matches(msg, want):
    now = fc.decode(msg)
    if msg.param_type == REAL32:
        return abs(float(now) - want) < 1e-6
    return int(round(now)) == int(round(want))


cur, total = fetch_all()
print(f"params en el FC: {len(cur)} / {total}")

on_fc = set(cur)
skipped = sorted(n for n in desired if n not in on_fc)
to_set = [n for n in desired if n in on_fc and not matches(cur[n], desired[n])]
print(f"a escribir (difieren): {len(to_set)}   saltados (no existen en este FW): {len(skipped)}")


def write(names, type_src):
    for name in names:
        ptype = type_src[name].param_type
        m.mav.param_set_send(m.target_system, m.target_component,
                             name.encode(), fc.encode(desired[name], ptype), ptype)
        time.sleep(0.02)


# pasada 1
write(to_set, cur)
time.sleep(1.5)

# verificar + reintentar
failed = to_set
for intento in (1, 2):
    chk, _ = fetch_all()
    failed = [n for n in failed if n not in chk or not matches(chk[n], desired[n])]
    if not failed:
        break
    print(f"reintento {intento}: {len(failed)} pendientes")
    write(failed, chk)
    time.sleep(1.5)

ok = len(to_set) - len(failed)
print(f"\nRESULTADO: escritos OK {ok} | fallos {len(failed)} | saltados {len(skipped)}")
if skipped:
    print("SALTADOS (no en este FW):", ", ".join(skipped[:40]) + (" ..." if len(skipped) > 40 else ""))
if failed:
    print("FALLARON:", ", ".join(failed[:40]))
    print("NO se guarda (hay fallos). Revisa antes de persistir.")
    sys.exit(1)

# persistir a NVM
m.mav.command_long_send(m.target_system, m.target_component,
                        mavutil.mavlink.MAV_CMD_PREFLIGHT_STORAGE, 0, 1, -1, 0, 0, 0, 0, 0)
ack = m.recv_match(type='COMMAND_ACK', blocking=True, timeout=5)
print("guardado en NVM:", "OK" if ack and ack.result == 0 else f"ack={ack.result if ack else 'sin ack'}")
print("Recuerda: reiniciar el FC (reboot_fc.py) para los params @reboot_required.")
