"""
Utilidades compartidas para los scripts de análisis de logs .ulog.

- Carga de ULog + helpers de acceso a topics/campos.
- Estilo de matplotlib consistente (limpio, ejes recesivos).
- Paleta categórica colorblind-safe (Okabe-Ito) en orden fijo.
- Gestión del directorio de salida de plots.

No se ejecuta directo; lo importan los analyze_*.py.
"""
import os
import math
import glob
import matplotlib
matplotlib.use("Agg")  # sin display, guarda PNG
import matplotlib.pyplot as plt
from pyulog import ULog

# --- Paleta categórica colorblind-safe (Okabe-Ito), orden FIJO ---
# Asigna colores por identidad de serie en este orden; nunca ciclar >8.
PALETTE = [
    "#0072B2",  # azul
    "#E69F00",  # naranja
    "#009E73",  # verde
    "#D55E00",  # bermellón
    "#56B4E9",  # celeste
    "#CC79A7",  # púrpura
    "#F0E442",  # amarillo
    "#000000",  # negro
]
INK = "#222222"
MUTED = "#888888"
GRID = "#DDDDDD"
WARN = "#E69F00"
CRIT = "#D55E00"


def setup_style():
    """Estilo limpio y consistente para todos los plots."""
    plt.rcParams.update({
        "figure.figsize": (11, 5),
        "figure.dpi": 130,
        "savefig.dpi": 130,
        "savefig.bbox": "tight",
        "font.size": 10,
        "axes.titlesize": 13,
        "axes.titleweight": "bold",
        "axes.labelsize": 10,
        "axes.edgecolor": MUTED,
        "axes.linewidth": 0.8,
        "axes.grid": True,
        "axes.axisbelow": True,
        "grid.color": GRID,
        "grid.linewidth": 0.7,
        "grid.linestyle": "-",
        "text.color": INK,
        "axes.labelcolor": INK,
        "xtick.color": MUTED,
        "ytick.color": MUTED,
        "legend.frameon": False,
        "legend.fontsize": 9,
        "lines.linewidth": 2.0,
    })


# --- Acceso a ULog ---
def load(path):
    return ULog(path)


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


def isnan(x):
    """NaN-safe también para escalares numpy (float32)."""
    try:
        return math.isnan(float(x))
    except (TypeError, ValueError):
        return False


def clean(arr):
    """Quita NaN, devuelve lista de floats (numpy-safe)."""
    if arr is None:
        return []
    return [float(x) for x in arr if not isnan(x)]


def secs(ts, t0):
    """timestamps (us) -> segundos desde t0."""
    return [(t - t0) / 1e6 for t in ts]


def duration(ulog):
    return (ulog.last_timestamp - ulog.start_timestamp) / 1e6


# --- Salida de plots ---
def outdir_for(logpath, base=None):
    """Crea scripts/output/<nombre_log>/ y devuelve la ruta."""
    if base is None:
        base = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
    name = os.path.splitext(os.path.basename(logpath))[0]
    # incluir carpeta padre para no colisionar (ej. sess109/log102)
    parent = os.path.basename(os.path.dirname(os.path.abspath(logpath)))
    d = os.path.join(base, f"{parent}__{name}")
    os.makedirs(d, exist_ok=True)
    return d


def save(fig, outdir, name):
    path = os.path.join(outdir, name if name.endswith(".png") else name + ".png")
    fig.savefig(path)
    plt.close(fig)
    print(f"   📊 {path}")
    return path


def title_block(fig, title, subtitle=None):
    fig.suptitle(title, fontsize=14, fontweight="bold", ha="left", x=0.02, y=0.99)
    if subtitle:
        fig.text(0.02, 0.945, subtitle, fontsize=9, color=MUTED, ha="left")


INPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "input")


def resolve_logs(arg=None):
    """Resuelve qué .ulg procesar:
      - sin argumento        -> todos los .ulg de scripts/input/
      - carpeta              -> todos los .ulg de esa carpeta
      - archivo existente    -> ese archivo
      - nombre suelto        -> se busca en scripts/input/<nombre>
    """
    if not arg:
        return sorted(glob.glob(os.path.join(INPUT_DIR, "*.ulg")))
    if os.path.isdir(arg):
        return sorted(glob.glob(os.path.join(arg, "*.ulg")))
    if os.path.isfile(arg):
        return [arg]
    cand = os.path.join(INPUT_DIR, arg)
    if os.path.isfile(cand):
        return [cand]
    return [arg]  # que falle abajo con mensaje claro
