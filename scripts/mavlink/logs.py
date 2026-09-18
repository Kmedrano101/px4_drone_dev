#!/usr/bin/env python3
"""Lista y descarga los logs .ulg de la SD del FC por MAVLink (cable USB o radio).

    python logs.py                  # lista: id, fecha, tamano
    python logs.py get 12 [out.ulg] # descarga el log 12

Por USB va a ~100-200 KB/s; por la radio de 57600 un log de vuelo tarda
minutos. Los huecos se piden de nuevo hasta completar el fichero.

Ojo con SDLOG_MODE=2 (graba desde el arranque): el ultimo log de la lista es
el de la sesion en curso y sigue creciendo mientras el FC este encendido. No
se puede bajar entero; reinicia el FC antes si lo necesitas.
"""
import sys, time, datetime
from pymavlink import mavutil
import fc

CHUNK = 90  # bytes por LOG_DATA
GAP_MAX = 512  # paquetes por re-peticion de hueco (~46 KB)


def list_logs(m, timeout=10):
    m.mav.log_request_list_send(m.target_system, m.target_component, 0, 0xFFFF)
    logs, total, t0 = {}, None, time.time()
    while time.time() - t0 < timeout:
        msg = m.recv_match(type='LOG_ENTRY', blocking=True, timeout=1)
        if msg is None:
            continue
        total = msg.num_logs
        if msg.num_logs == 0:
            break
        logs[msg.id] = msg
        t0 = time.time()
        if len(logs) >= total:
            break
    return [logs[k] for k in sorted(logs)]


def download(m, entry, path):
    size = entry.size
    buf = bytearray(size)
    have = [False] * ((size + CHUNK - 1) // CHUNK)
    m.mav.log_request_data_send(m.target_system, m.target_component, entry.id, 0, size)
    t0 = last = time.time()
    while not all(have):
        msg = m.recv_match(type='LOG_DATA', blocking=True, timeout=1)
        if msg is not None and msg.id == entry.id and msg.count > 0:
            buf[msg.ofs:msg.ofs + msg.count] = bytes(msg.data[:msg.count])
            have[msg.ofs // CHUNK] = True
            last = time.time()
        elif time.time() - last > 0.5:
            # Pedir solo el primer hueco, no todo lo que queda: con un log grande,
            # re-pedir hasta el final inunda el enlace y cada reintento va peor.
            first = have.index(False)
            end = first
            while end < len(have) and not have[end] and end - first < GAP_MAX:
                end += 1
            ofs = first * CHUNK
            m.mav.log_request_data_send(m.target_system, m.target_component,
                                        entry.id, ofs, min(end * CHUNK, size) - ofs)
            last = time.time()
        n = sum(have)
        if n % 500 == 0:
            el = time.time() - t0
            sys.stderr.write(f"\r  {n * CHUNK / 1e6:6.2f}/{size / 1e6:.2f} MB  "
                             f"{n * CHUNK / 1e3 / max(el, 1e-3):6.0f} KB/s")
    m.mav.log_request_end_send(m.target_system, m.target_component)
    with open(path, 'wb') as f:
        f.write(buf)
    sys.stderr.write(f"\n  guardado {path} ({size} bytes, {time.time() - t0:.0f} s)\n")


def main():
    m = fc.connect()
    logs = list_logs(m)
    if len(sys.argv) >= 3 and sys.argv[1] == 'get':
        want = int(sys.argv[2])
        e = next((l for l in logs if l.id == want), None)
        if e is None:
            raise SystemExit(f"no existe el log {want}")
        download(m, e, sys.argv[3] if len(sys.argv) > 3 else f"log{want}.ulg")
        return
    for l in logs:
        ts = (datetime.datetime.fromtimestamp(l.time_utc).strftime('%Y-%m-%d %H:%M:%S')
              if l.time_utc else '(sin fecha)')
        print(f"{l.id:4d}  {ts}  {l.size / 1e6:8.2f} MB")
    print(f"{len(logs)} logs")


if __name__ == '__main__':
    main()
