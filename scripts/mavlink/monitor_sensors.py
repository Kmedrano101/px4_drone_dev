#!/usr/bin/env python3
"""Muestrea distance_sensor + vehicle_optical_flow por la consola nsh y escribe CSV.

Uso:  FC_DEV=/dev/ttyUSB0 FC_BAUD=57600 python3 monitor_sensors.py 600 barrido.csv

Espera a que aparezca el puerto, asi que se puede lanzar ANTES de enchufar el FC.
Tasa real: ~1 muestra cada 2 s por cable, ~3 s por radio a 57600.
FC_WAIT ajusta la espera por comando (1.0 cable / 1.4 radio).
"""
import os, re, sys, time, csv
import fc, shell

DEV = os.environ.get('FC_DEV', '/dev/ttyACM0')
WAIT = float(os.environ.get('FC_WAIT', '1.4'))
DURACION = float(sys.argv[1]) if len(sys.argv) > 1 else 600.0
OUT = sys.argv[2] if len(sys.argv) > 2 else 'sensores.csv'

t0 = time.time()
while not os.path.exists(DEV):
    if time.time() - t0 > 900:
        raise SystemExit("timeout esperando el FC")
    time.sleep(2)
print(f"[{time.strftime('%H:%M:%S')}] puerto detectado, conectando...", flush=True)
time.sleep(2)

m = fc.connect(timeout=60)
shell.pump(m, 0.5)
print(f"[{time.strftime('%H:%M:%S')}] consola lista. Muestreando {DURACION:.0f}s\n", flush=True)

def num(txt, campo):
    mm = re.search(rf'^\s*{re.escape(campo)}:\s*([-\d.]+)', txt, re.M)
    try:
        return float(mm.group(1)) if mm else None
    except ValueError:
        return None

f = open(OUT, 'w', newline='')
w = csv.writer(f)
w.writerow(['t_s','hora','rng_m','rng_var','rng_min','rng_max','flow_q','flow_dist_m','px_x','px_y'])
print(f"{'t':>7} {'hora':>9} {'rango':>8} {'var':>8} {'flow_q':>7} {'flow_d':>8}  pixel_flow")

t_ini = time.time()
while time.time() - t_ini < DURACION:
    ds = shell.run(m, 'listener distance_sensor -n 1', wait=WAIT)
    of = shell.run(m, 'listener vehicle_optical_flow -n 1', wait=WAIT)
    t = time.time() - t_ini
    rng, var = num(ds, 'current_distance'), num(ds, 'variance')
    rmin, rmax = num(ds, 'min_distance'), num(ds, 'max_distance')
    q, fdist = num(of, 'quality'), num(of, 'distance_m')
    px = re.search(r'pixel_flow:\s*\[([-\d.]+),\s*([-\d.]+)\]', of)
    pxx, pxy = (float(px.group(1)), float(px.group(2))) if px else (None, None)
    hora = time.strftime('%H:%M:%S')
    w.writerow([f"{t:.1f}", hora, rng, var, rmin, rmax, q, fdist, pxx, pxy]); f.flush()
    fmt = lambda v, n=2: ('  —  ' if v is None else f"{v:.{n}f}")
    print(f"{t:>7.1f} {hora:>9} {fmt(rng,3):>8} {fmt(var,4):>8} {fmt(q,0):>7} {fmt(fdist,3):>8}"
          f"  [{fmt(pxx,4)}, {fmt(pxy,4)}]", flush=True)
f.close()
print("\nfin. CSV:", OUT)
