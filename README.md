**Languages:** [English](README.md) | [Español](docs/README.es.md)

# px4_drone_dev

Development journal, tooling, and configuration for bringing up a custom PX4
drone toward autonomous **indoor navigation** — optical flow + LiDAR altitude,
magnetometer-free heading, and offboard control from a Raspberry Pi 4 companion
over ROS 2 / uXRCE-DDS.

> Work-in-progress engineering log: every fix is diagnosed from `.ulog` flight
> logs and documented step by step.

## Table of Contents

- [Overview](#overview)
- [Installation](#installation)
- [Usage](#usage)
- [Project Resources](#project-resources)
- [Contributing](#contributing)
- [License](#license)
- [Contact](#contact)

## Overview

**Hardware**
- **FC:** HKUST NxtPX4v2 (STM32H7) · FC#1 PX4 v1.17.0 (custom board build) · FC#2 PX4 v1.14.3 (vendor stock, 2nd drone)
- **Companion:** Raspberry Pi 4 · Ubuntu 24.04 · ROS 2 Jazzy
- **Sensors:** MicoAir MTF-01P (optical flow + 12 m LiDAR) · M100-5883 GPS/compass
- **Airframe:** Quad-X · T-Motor F90 2806.5 · HQProp 7040 · 6S

**Milestones**
- ✅ First flights (Stabilized / Altitude / Position outdoor, 0.71 m GPS hold)
- ✅ MTF-01P optical-flow + LiDAR integrated over MAVLink (TEL4/UART8)
- ✅ Offboard link RPi ⇄ FC via uXRCE-DDS (domain-id + px4_msgs aligned)
- ✅ Firmware optimized (removed FW/VTOL modules → FLASH 98.5% → 92%)
- ✅ 2nd drone (FC#2, vendor PX4 1.14.3) brought up — MTF-01P on TEL4 via SD `extras.txt`, 97 params migrated from FC#1
- 🔄 Indoor position hold — flow-only path blocked (no yaw without EV) on **both** FCs; FC#2 has no compass at all; **next: Livox + FAST-LIO → EV**
- ⏳ Full indoor navigation with 3D LiDAR (Livox + FAST-LIO)

## Installation

Analysis tooling (Python) for the `.ulog` scripts:

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install pyulog matplotlib numpy
```

## Usage

Log analysis tools live in [`scripts/`](scripts/README.md) and generate **visual
plots**. Drop `.ulg` files in `scripts/input/` and run:

```bash
cd scripts
cp <your>.ulg input/
python3 analyze_temperature.py   # FC temperature (baro + IMU) with thresholds
python3 analyze_motor_noise.py   # motor outputs / saturation + torque
python3 analyze_takeoff.py       # takeoff diagnosis (altitude/motors/estimator)
```

Plots are written to `scripts/output/<log>/*.png`. See [`scripts/README.md`](scripts/README.md).

## Project Resources

**Documentation — engineering reports** (`docs/`)
- [Platform: hardware, firmware & comms](docs/PLATAFORMA_HARDWARE.md) — full spec sheet + SUPER reference
- [Flight bring-up report](docs/INFORME_VUELO_DRONE.md) — 4 problems solved, reference config, lessons
- [Motor-noise = yaw saturation](docs/DIAGNOSTICO_RUIDO_MOTORES_YAW.md) — "loud motors on arming" root cause
- [Offboard RPi ⇄ FC (uXRCE-DDS)](docs/CONFIGURACION_OFFBOARD_RPI4.md) — companion link setup
- [MTF-01P flow + LiDAR integration](docs/INTEGRACION_MTF-01P_FLOW_LIDAR.md) — sensor bring-up saga
- [Indoor parameter reference](docs/PARAMETROS_INDOOR.md) — every GPS-free indoor param, ranked by importance
- [Direct MAVLink scripting](docs/CONEXION_MAVLINK_SCRIPTS.md) — talk to the FC over USB cable or radio without QGC

**Diagnostic reports** (companion / RPi) — see [`reports/`](reports/README.md)
- [MTF-01 EKF2 tuning — indoor flow](reports/2026-07-23_mtf01-ekf2-tuning.md)
- [FC#2 vendor 1.14.3 — MTF-01P + param migration](reports/2026-09-04_fc2-vendor-1143-mtf01p-migracion.md)

**Firmware versions** — see [backups/firmware/INDEX.md](backups/firmware/INDEX.md).

**Reference platform** — this build replicates the [SUPER](https://github.com/hku-mars/SUPER) MAV
platform from HKU MaRS Lab ([hardware BOM](https://github.com/hku-mars/SUPER-Hardware)) as a base
for further work. Differences are tracked in [docs/PLATAFORMA_HARDWARE.md](docs/PLATAFORMA_HARDWARE.md) §7.
Each version ships the flashable `.px4` (QGC → Custom firmware) plus its
`board_config.diff` to rebuild; `.bin`/`.elf` are skipped.

## Contributing

Personal R&D journal — issues and suggestions welcome. See the reports in
`docs/` for the current state and open questions.

## License

Distributed under the [MIT License](LICENSE).

## Contact

Kevin Medrano — [kevin.ejem18@gmail.com](mailto:kevin.ejem18@gmail.com) · [@Kmedrano101](https://github.com/Kmedrano101)
