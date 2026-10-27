#!/usr/bin/env python3
"""Compara dos tomas de GPS en el MISMO punto: autonomo (sin correcciones) vs
RTK (con correcciones NTRIP). SOLO LECTURA de ficheros, no habla con el FC.

Lee los CSV que genera gps_rtk_validate.py (--label sin_corr / con_corr) y saca,
por toma: fix alcanzado, satelites, eph, dispersion horizontal (precision: RMS y
max respecto al centroide) y el centroide (lat/lon). Luego compara:
  - offset entre centroides  = cuanto se movio el punto estimado del autonomo
    respecto al RTK (con el RTK como 'verdad', es ~el error absoluto del autonomo).
  - mejora de precision (dispersion) y de eph.

Uso (webui o CLI):
  python3 gps_rtk_compare.py --dir <carpeta_logs>          # coge las ultimas sin_corr/con_corr
  python3 gps_rtk_compare.py --a toma_auton.csv --b toma_rtk.csv
"""
import os, sys, csv, math, glob, argparse, datetime

FIX = {0: "no-GPS", 1: "sin-fix", 2: "2D", 3: "3D", 4: "DGPS",
       5: "RTK-float", 6: "RTK-fixed", 7: "static", 8: "PPP"}


def load(path):
    rows = []
    with open(path) as f:
        for r in csv.DictReader(f):
            try:
                lat = float(r["lat_deg"]); lon = float(r["lon_deg"])
            except (ValueError, KeyError):
                continue
            fix = int(r.get("fix_type") or 0)
            sats = int(r.get("sats") or 0)
            eph = r.get("eph_m")
            eph = float(eph) if eph not in (None, "") else None
            rows.append((lat, lon, fix, sats, eph))
    return rows


def stats(rows):
    n = len(rows)
    lats = [r[0] for r in rows]; lons = [r[1] for r in rows]
    lat0 = sum(lats) / n; lon0 = sum(lons) / n
    # dispersion horizontal respecto al centroide (equirectangular local)
    kx = 111320.0 * math.cos(math.radians(lat0)); ky = 111320.0
    dists = [math.hypot((la - lat0) * ky, (lo - lon0) * kx) for la, lo, *_ in rows]
    rms = math.sqrt(sum(d * d for d in dists) / n)
    fixd = {}
    for r in rows:
        fixd[r[2]] = fixd.get(r[2], 0) + 1
    ephs = [r[4] for r in rows if r[4] is not None]
    sats = [r[3] for r in rows]
    return {
        "n": n, "lat0": lat0, "lon0": lon0,
        "rms": rms, "max": max(dists),
        "best_fix": max(r[2] for r in rows),
        "fix_dist": fixd,
        "sats_mean": sum(sats) / n, "sats_max": max(sats),
        "eph_mean": (sum(ephs) / len(ephs)) if ephs else None,
        "eph_min": min(ephs) if ephs else None,
        "eph_max": max(ephs) if ephs else None,
    }


def haversine(a, b):
    la1, lo1 = math.radians(a[0]), math.radians(a[1])
    la2, lo2 = math.radians(b[0]), math.radians(b[1])
    dla = la2 - la1; dlo = lo2 - lo1
    h = math.sin(dla / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin(dlo / 2) ** 2
    return 2 * 6371000.0 * math.asin(min(1.0, math.sqrt(h)))


def fixstr(d):
    return ", ".join(f"{FIX.get(k, k)}:{v}" for k, v in sorted(d.items()))


def latest(dir_, label):
    g = sorted(glob.glob(os.path.join(dir_, f"*_{label}_gps_rtk.csv")))
    return g[-1] if g else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=None, help="carpeta con los CSV (por defecto = --out-dir)")
    ap.add_argument("--a", help="CSV toma autonoma (sin correcciones)")
    ap.add_argument("--b", help="CSV toma RTK (con correcciones)")
    ap.add_argument("--out-dir")
    args = ap.parse_args()

    # la webui inyecta --out-dir; si no se da --dir, buscamos ahi mismo
    search = args.dir or args.out_dir or "."
    pa = args.a or latest(search, "sin_corr")
    pb = args.b or latest(search, "con_corr")
    if not pa or not pb:
        print("FALTA una toma: necesito *_sin_corr_gps_rtk.csv y *_con_corr_gps_rtk.csv", flush=True)
        print(f"  (buscado en {os.path.abspath(search)})  sin={pa}  con={pb}", flush=True)
        return 1
    ra, rb = load(pa), load(pb)
    if len(ra) < 2 or len(rb) < 2:
        print(f"tomas con muy pocas muestras (sin={len(ra)}, con={len(rb)})", flush=True)
        return 1
    A, B = stats(ra), stats(rb)
    off = haversine((A["lat0"], A["lon0"]), (B["lat0"], B["lon0"]))

    L = []
    L.append("=== Comparacion GPS: autonomo (sin corr.) vs RTK (con corr.) ===")
    L.append(f"fecha: {datetime.datetime.now():%Y-%m-%d %H:%M:%S}")
    L.append(f"A (sin corr.): {os.path.basename(pa)}")
    L.append(f"B (con corr.): {os.path.basename(pb)}")
    L.append("")
    hdr = f"{'metrica':<26}{'A autonomo':>18}{'B con RTK':>18}"
    L.append(hdr); L.append("-" * len(hdr))
    L.append(f"{'muestras':<26}{A['n']:>18d}{B['n']:>18d}")
    fa = FIX.get(A['best_fix'], A['best_fix']); fb = FIX.get(B['best_fix'], B['best_fix'])
    L.append(f"{'mejor fix':<26}{fa:>18}{fb:>18}")
    sa = f"{A['sats_mean']:.0f}/{A['sats_max']}"; sb = f"{B['sats_mean']:.0f}/{B['sats_max']}"
    L.append(f"{'sats (media/max)':<26}{sa:>18}{sb:>18}")
    def m(x): return "n/d" if x is None else f"{x:.2f}"
    L.append(f"{'eph media (m)':<26}{m(A['eph_mean']):>18}{m(B['eph_mean']):>18}")
    L.append(f"{'eph min (m)':<26}{m(A['eph_min']):>18}{m(B['eph_min']):>18}")
    L.append(f"{'dispersion RMS (m)':<26}{A['rms']:>18.3f}{B['rms']:>18.3f}")
    L.append(f"{'dispersion max (m)':<26}{A['max']:>18.3f}{B['max']:>18.3f}")
    L.append("")
    L.append(f"distribucion fix A: {fixstr(A['fix_dist'])}")
    L.append(f"distribucion fix B: {fixstr(B['fix_dist'])}")
    L.append("")
    L.append(f"centroide A: {A['lat0']:.7f}, {A['lon0']:.7f}  -> https://maps.google.com/?q={A['lat0']:.7f},{A['lon0']:.7f}")
    L.append(f"centroide B: {B['lat0']:.7f}, {B['lon0']:.7f}  -> https://maps.google.com/?q={B['lat0']:.7f},{B['lon0']:.7f}")
    L.append("")
    L.append(f">> OFFSET entre centroides (A->B): {off:.3f} m")
    L.append("   (con el RTK como verdad, ~= error absoluto del GPS autonomo)")
    if A["rms"] > 0:
        L.append(f">> Precision (dispersion) RMS: {A['rms']:.3f} m -> {B['rms']:.3f} m  (x{A['rms']/max(B['rms'],1e-6):.1f} mejor)")
    if A["eph_mean"] and B["eph_mean"]:
        L.append(f">> eph media: {A['eph_mean']:.2f} m -> {B['eph_mean']:.2f} m  (x{A['eph_mean']/max(B['eph_mean'],1e-6):.1f} mejor)")
    rtk = B["best_fix"] in (5, 6)
    L.append(f">> RTK en la toma B: {'SI, ' + FIX[B['best_fix']] if rtk else 'NO (no llego correccion; revisa NTRIP en QGC)'}")
    verdict = "RTK MEJORA" if (rtk and B["rms"] <= A["rms"]) else ("RTK sin fix" if not rtk else "sin mejora clara")
    L.append(f"VEREDICTO: {verdict}")
    out = "\n".join(L)

    print("\n" + out, flush=True)
    odir = args.out_dir or search
    try:
        os.makedirs(odir, exist_ok=True)
        p = os.path.join(odir, datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S") + "_gps_rtk_compare.txt")
        with open(p, "w") as f:
            f.write(out + "\n")
        print(f"\n# comparacion: {p}", flush=True)
    except OSError as e:
        print(f"(no se pudo guardar el resumen: {e})", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
