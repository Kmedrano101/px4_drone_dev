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
- **FC:** HKUST NxtPX4v2 (STM32H7) · PX4 v1.17.0 (custom board build)
- **Companion:** Raspberry Pi 4 · Ubuntu 24.04 · ROS 2 Jazzy
- **Sensors:** MicoAir MTF-01P (optical flow + 12 m LiDAR) · M100-5883 GPS/compass
- **Airframe:** Quad-X · T-Motor F90 2806.5 · HQProp 7040 · 6S

**Milestones**
- ✅ First flights (Stabilized / Altitude / Position outdoor, 0.71 m GPS hold)
- ✅ MTF-01P optical-flow + LiDAR integrated over MAVLink (TEL4/UART8)
- ✅ Offboard link RPi ⇄ FC via uXRCE-DDS (domain-id + px4_msgs aligned)
- ✅ Firmware optimized (removed FW/VTOL modules → FLASH 98.5% → 92%)
- 🔄 Indoor position hold (flow + LiDAR, mag-free heading)
- ⏳ Full indoor navigation with 3D LiDAR (Livox + FAST-LIO)

## Installation

Analysis tooling (Python) for the `.ulog` scripts:

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install pyulog matplotlib numpy
```

## Usage

Classify arming / motor-noise logs (idle vs saturation, per-axis):

```bash
python3 analyze_motor_noise.py <logs_folder>
```

Diagnose a failed takeoff (mode, GPS, position validity, failsafe flags, motors):

```bash
python3 analyze_takeoff_fail.py <logs_folder>
```

## Project Resources

**Documentation — engineering reports** (`docs/`)
- [Flight bring-up report](docs/INFORME_VUELO_DRONE.md) — 4 problems solved, reference config, lessons
- [Motor-noise = yaw saturation](docs/DIAGNOSTICO_RUIDO_MOTORES_YAW.md) — "loud motors on arming" root cause
- [Offboard RPi ⇄ FC (uXRCE-DDS)](docs/CONFIGURACION_OFFBOARD_RPI4.md) — companion link setup
- [MTF-01P flow + LiDAR integration](docs/INTEGRACION_MTF-01P_FLOW_LIDAR.md) — sensor bring-up saga
- [MTF-01 EKF2 tuning report](docs/mtf01_ekf2_tuning_report.md) — indoor position-hold tuning

**Firmware versions** — see [backups/firmware/INDEX.md](backups/firmware/INDEX.md)
(binaries are git-ignored; reproducible from each version's `board_config.diff`).

## Contributing

Personal R&D journal — issues and suggestions welcome. See the reports in
`docs/` for the current state and open questions.

## License

Distributed under the [MIT License](LICENSE).

## Contact

Kevin Medrano — [kevin.ejem18@gmail.com](mailto:kevin.ejem18@gmail.com) · [@Kmedrano101](https://github.com/Kmedrano101)
