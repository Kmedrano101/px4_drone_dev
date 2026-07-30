# scripts/ — Análisis de logs `.ulog` con plots

Herramientas para analizar logs de vuelo PX4 y **generar plots visuales**.
Ejecución manual, cada script hace una cosa. Paleta colorblind-safe (Okabe-Ito),
estilo consistente vía `_common.py`.

## Instalación

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install pyulog matplotlib numpy
```

## Flujo de uso

1. Copia tus `.ulg` a [`input/`](input/) (o pasa una ruta explícita).
2. Ejecuta el script que necesites.
3. Los plots salen en `output/<carpeta>__<log>/*.png`.

```bash
cd scripts
cp /home/kmedrano/Documents/QGroundControl/Logs/2026-07-22/*.ulg input/
python3 analyze_temperature.py          # todos los .ulg de input/
python3 analyze_motor_noise.py          # idem
python3 analyze_takeoff.py 09_41_55.ulg # un log concreto (en input/ o ruta)
```

## Scripts

| Script | Qué analiza | Plots que genera |
|---|---|---|
| `analyze_temperature.py` | Temperatura del FC (baro SPL06 + IMU BMI088) | `temperatura.png` (tendencia + umbrales 80°/85°) |
| `analyze_motor_noise.py` | "Ruido al armar" / saturación de motores | `motores.png` (4 motores + saturación), `torque.png` (roll/pitch/yaw) |
| `analyze_takeoff.py` | Por qué (no) despegó | `despegue.png` (altura + motores + validez del EKF) |

`_common.py` no se ejecuta directo: estilo, paleta, carga de ULog y helpers compartidos.

## Entrada / salida

| Carpeta | Contenido | Versionado |
|---|---|---|
| `input/` | `.ulg` a analizar | ❌ (solo README) |
| `output/` | plots `.png` generados | ❌ (regenerables) |

> Para conservar un plot en la documentación, cópialo a `docs/images/`.

## Añadir un análisis nuevo

1. Crea `analyze_<tema>.py`.
2. `import _common as C` → usa `C.setup_style()`, `C.PALETTE`, `C.get()`, `C.save()`.
3. Acepta `C.resolve_logs(arg)` (sin arg = lee de `input/`).
4. Documenta el script en la tabla de arriba.
