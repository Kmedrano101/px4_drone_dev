#!/usr/bin/env python3
"""Cliente NTRIP (VRS) + reenvio de RTCM al FC por MAVLink (GPS_RTCM_DATA).

Para RTK: trae correcciones RTCM3 de un caster NTRIP (p.ej. IGN SPTR) y las
inyecta en el F9P a traves del FC. Para VRS manda tu posicion como NMEA GGA.

Modos:
  --test     Solo valida el enlace NTRIP: conecta al caster, manda una GGA fija
             (--lat/--lon) y mide el caudal de RTCM unos segundos. NO necesita el
             FC -> para probar en un equipo con internet (desktop) primero.
  --sources  Pide el sourcetable y lista los mountpoints del caster.
  (default)  Conecta al FC (MAVLink), usa su posicion para la GGA (VRS real) y le
             reenvia el RTCM como GPS_RTCM_DATA.

Config (ntrip.conf, formato clave=valor; NO commitear, lleva la contrasena):
  host=...            port=2101
  mountpoint=...      user=...      password=...
Tambien por CLI (--host/--port/--mountpoint/--user/--password) o env NTRIP_*.

Uso tipico:
  # 1) probar el caster en el desktop (internet), sin FC:
  python3 ntrip_rtcm.py --config ntrip.conf --test --lat 40.6510 --lon -4.6786
  # 2) listar mountpoints:
  python3 ntrip_rtcm.py --config ntrip.conf --sources
  # 3) en la Pi, inyectar al FC:
  FC_DEV=/dev/ttyACM0 python3 ntrip_rtcm.py --config ntrip.conf
"""
import os, sys, time, socket, base64, argparse, threading

def load_config(path):
    cfg = {}
    if path and os.path.exists(path):
        for ln in open(path):
            ln = ln.strip()
            if ln and not ln.startswith('#') and '=' in ln:
                k, v = ln.split('=', 1)
                cfg[k.strip()] = v.strip()
    return cfg

def nmea_checksum(body):
    c = 0
    for ch in body:
        c ^= ord(ch)
    return f"{c:02X}"

def build_gga(lat, lon, alt=200.0, fix=1, sats=10, hdop=1.0):
    """NMEA GGA a partir de lat/lon decimales. fix: 1=GPS,2=DGPS,4=RTKfix,5=RTKfloat."""
    t = time.gmtime()
    hhmmss = time.strftime("%H%M%S", t) + ".00"
    la = abs(lat); lo = abs(lon)
    lad = int(la); lam = (la - lad) * 60.0
    lod = int(lo); lom = (lo - lod) * 60.0
    lat_s = f"{lad:02d}{lam:08.5f},{'N' if lat>=0 else 'S'}"
    lon_s = f"{lod:03d}{lom:08.5f},{'E' if lon>=0 else 'W'}"
    body = f"GPGGA,{hhmmss},{lat_s},{lon_s},{fix},{sats:02d},{hdop:.1f},{alt:.1f},M,0.0,M,,"
    return f"${body}*{nmea_checksum(body)}\r\n"

def ntrip_connect(cfg, mountpoint, send_sourcetable=False, timeout=15):
    """Abre el socket NTRIP. Si send_sourcetable, pide '/' (lista mountpoints)."""
    host = cfg['host']; port = int(cfg.get('port', 2101))
    mp = '' if send_sourcetable else mountpoint
    auth = base64.b64encode(f"{cfg['user']}:{cfg['password']}".encode()).decode()
    req = (f"GET /{mp} HTTP/1.1\r\n"
           f"Host: {host}:{port}\r\n"
           f"Ntrip-Version: Ntrip/2.0\r\n"
           f"User-Agent: NTRIP px4-drone/1.0\r\n"
           f"Authorization: Basic {auth}\r\n"
           f"Connection: close\r\n\r\n")
    s = socket.create_connection((host, port), timeout=timeout)
    s.sendall(req.encode())
    # leer cabecera de respuesta
    hdr = b""
    s.settimeout(timeout)
    while b"\r\n\r\n" not in hdr and b"\n\n" not in hdr:
        chunk = s.recv(1)
        if not chunk:
            break
        hdr += chunk
        if len(hdr) > 8192:
            break
    head = hdr.decode(errors='replace')
    ok = ("200" in head.split("\r\n")[0]) or head.startswith("ICY 200") or "SOURCETABLE 200" in head
    return s, head, ok

def cmd_sources(cfg):
    s, head, ok = ntrip_connect(cfg, '', send_sourcetable=True)
    print("--- respuesta caster ---"); print(head.split("\r\n")[0])
    if not ok:
        print("FALLO: el caster no acepto la conexion (revisa host/user/pass)"); return 1
    s.settimeout(8); data = b""
    try:
        while True:
            c = s.recv(4096)
            if not c: break
            data += c
            if b"ENDSOURCETABLE" in data: break
    except socket.timeout:
        pass
    s.close()
    mps = []
    for ln in data.decode(errors='replace').splitlines():
        if ln.startswith("STR;"):
            p = ln.split(';')
            # STR;mountpoint;identifier;format;...
            mps.append((p[1], p[3] if len(p) > 3 else '', p[2] if len(p) > 2 else ''))
    print(f"--- {len(mps)} mountpoints ---")
    for mp, fmt, ident in mps:
        print(f"  {mp:16s} {fmt:14s} {ident}")
    return 0

def cmd_test(cfg, lat, lon, duration):
    mp = cfg['mountpoint']
    print(f"conectando a {cfg['host']}:{cfg.get('port',2101)} / {mp} ...")
    s, head, ok = ntrip_connect(cfg, mp)
    print("respuesta:", head.split("\r\n")[0])
    if not ok:
        print("FALLO: el caster rechazo (revisa mountpoint/credenciales)"); return 1
    gga = build_gga(lat, lon)
    print("GGA ->", gga.strip())
    s.sendall(gga.encode())
    t0 = time.time(); total = 0; last_gga = t0; frames = 0
    s.settimeout(2)
    print(f"midiendo RTCM {duration}s (la VRS tarda unos segundos en arrancar)...")
    while time.time() - t0 < duration:
        try:
            c = s.recv(4096)
        except socket.timeout:
            c = b""
        if c:
            total += len(c)
            frames += c.count(b"\xd3")  # preambulo RTCM3 (aprox)
        if time.time() - last_gga > 10:      # reenviar GGA (VRS)
            try: s.sendall(gga.encode())
            except OSError: pass
            last_gga = time.time()
        el = time.time() - t0
        print(f"  t={el:4.0f}s  RTCM {total:7d} B  ({total/max(el,1):6.0f} B/s)  ~{frames} frames", end="\r")
    s.close()
    print()
    rate = total / max(duration, 1)
    print(f"RESULTADO: {total} B en {duration}s = {rate:.0f} B/s",
          "-> NTRIP OK ✅" if total > 200 else "-> SIN datos ❌ (mountpoint/GGA/baseline?)")
    return 0 if total > 200 else 1

# ---- reenvio al FC (solo si no es --test/--sources) ----
def rtcm_to_mavlink(cfg):
    import fc
    from pymavlink import mavutil
    m = fc.connect()
    print("FC conectado. Pidiendo GLOBAL_POSITION_INT / GPS_RAW_INT para la GGA...")
    m.mav.command_long_send(m.target_system, m.target_component,
        mavutil.mavlink.MAV_CMD_SET_MESSAGE_INTERVAL, 0,
        mavutil.mavlink.MAVLINK_MSG_ID_GPS_RAW_INT, 1000000, 0,0,0,0,0)
    pos = {'lat': None, 'lon': None, 'alt': 200.0, 'fix': 1, 'sats': 10}

    def read_fc():
        while True:
            msg = m.recv_match(type=['GPS_RAW_INT','GLOBAL_POSITION_INT'], blocking=True, timeout=2)
            if msg is None: continue
            if msg.get_type() == 'GPS_RAW_INT' and msg.fix_type >= 2:
                pos.update(lat=msg.lat/1e7, lon=msg.lon/1e7, alt=msg.alt/1e3,
                           fix=max(1,min(msg.fix_type,2)), sats=msg.satellites_visible)
    threading.Thread(target=read_fc, daemon=True).start()

    # esperar primera posicion
    print("esperando fix del FC para arrancar la VRS...")
    while pos['lat'] is None:
        time.sleep(0.5)
    s, head, ok = ntrip_connect(cfg, cfg['mountpoint'])
    print("NTRIP:", head.split("\r\n")[0])
    if not ok:
        print("FALLO NTRIP"); return 1
    s.sendall(build_gga(pos['lat'], pos['lon'], pos['alt'], pos['fix'], pos['sats']).encode())
    s.settimeout(2); seq = 0; last_gga = time.time(); total = 0; t0 = time.time()
    print("inyectando RTCM al FC... (Ctrl-C para parar)")
    while True:
        try:
            data = s.recv(4096)
        except socket.timeout:
            data = b""
        if data:
            total += len(data)
            # fragmentar en <=180 B -> GPS_RTCM_DATA
            frags = [data[i:i+180] for i in range(0, len(data), 180)]
            fragmented = len(frags) > 1
            for i, fr in enumerate(frags):
                flags = 0
                if fragmented:
                    flags = 1 | ((i & 0x3) << 1) | ((seq & 0x1f) << 3)
                buf = fr + b"\x00" * (180 - len(fr))
                m.mav.gps_rtcm_data_send(flags, len(fr), buf)
            seq = (seq + 1) & 0x1f
        if time.time() - last_gga > 5:
            try: s.sendall(build_gga(pos['lat'], pos['lon'], pos['alt'], pos['fix'], pos['sats']).encode())
            except OSError: pass
            last_gga = time.time()
            el = time.time() - t0
            print(f"  RTCM {total} B ({total/max(el,1):.0f} B/s)  fix_FC={pos['fix']} sats={pos['sats']}", end="\r")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--config'); ap.add_argument('--host'); ap.add_argument('--port', type=int)
    ap.add_argument('--mountpoint'); ap.add_argument('--user'); ap.add_argument('--password')
    ap.add_argument('--test', action='store_true'); ap.add_argument('--sources', action='store_true')
    ap.add_argument('--lat', type=float, default=40.6510); ap.add_argument('--lon', type=float, default=-4.6786)
    ap.add_argument('--duration', type=float, default=30)
    a = ap.parse_args()
    cfg = load_config(a.config)
    for k in ('host','port','mountpoint','user','password'):
        v = getattr(a, k) or os.environ.get('NTRIP_' + k.upper())
        if v is not None: cfg[k] = str(v)
    missing = [k for k in ('host','user','password') if not cfg.get(k)]
    if missing:
        raise SystemExit(f"faltan en la config: {missing} (usa --config ntrip.conf)")
    if a.sources:  return cmd_sources(cfg)
    if a.test:     return cmd_test(cfg, a.lat, a.lon, a.duration)
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    return rtcm_to_mavlink(cfg)

if __name__ == '__main__':
    sys.exit(main() or 0)
