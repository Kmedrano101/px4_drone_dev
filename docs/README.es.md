**Idiomas:** [English](../README.md) | [Español](README.es.md)

# px4_drone_dev

Diario de desarrollo, herramientas y configuración para poner a punto un dron
PX4 custom hacia la **navegación autónoma indoor** — flujo óptico + altura por
LiDAR, heading sin magnetómetro, y control offboard desde una Raspberry Pi 4
por ROS 2 / uXRCE-DDS.

> Registro de ingeniería en progreso: cada fix se diagnostica desde logs de
> vuelo `.ulog` y se documenta paso a paso.

## Contenido

- [Resumen](#resumen)
- [Instalación](#instalación)
- [Uso](#uso)
- [Recursos del proyecto](#recursos-del-proyecto)
- [Licencia](#licencia)
- [Contacto](#contacto)

## Resumen

**Hardware**
- **FC:** HKUST NxtPX4v2 (STM32H7) · PX4 v1.17.0 (build de board custom)
- **Companion:** Raspberry Pi 4 · Ubuntu 24.04 · ROS 2 Jazzy
- **Sensores:** MicoAir MTF-01P (flujo óptico + LiDAR 12 m) · M100-5883 GPS/brújula
- **Airframe:** Quad-X · T-Motor F90 2806.5 · HQProp 7040 · 6S

**Hitos**
- ✅ Primeros vuelos (Stabilized / Altitude / Position outdoor, hold GPS 0.71 m)
- ✅ MTF-01P flujo óptico + LiDAR integrado por MAVLink (TEL4/UART8)
- ✅ Enlace offboard RPi ⇄ FC por uXRCE-DDS (domain-id + px4_msgs alineados)
- ✅ Firmware optimizado (quitados módulos FW/VTOL → FLASH 98.5% → 92%)
- 🔄 Hold de posición indoor (flujo + LiDAR, heading sin mag)
- ⏳ Navegación indoor completa con LiDAR 3D (Livox + FAST-LIO)

## Instalación

Herramientas de análisis (Python) para los scripts de `.ulog`:

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install pyulog matplotlib numpy
```

## Uso

Las herramientas de análisis viven en [`scripts/`](../scripts/README.md) y generan
**plots visuales**. Suelta los `.ulg` en `scripts/input/` y ejecuta:

```bash
cd scripts
cp <tu>.ulg input/
python3 analyze_temperature.py   # temperatura del FC (baro + IMU) con umbrales
python3 analyze_motor_noise.py   # salida de motores / saturación + torque
python3 analyze_takeoff.py       # diagnóstico de despegue (altura/motores/EKF)
```

Los plots salen en `scripts/output/<log>/*.png`. Ver [`scripts/README.md`](../scripts/README.md).

## Recursos del proyecto

**Documentación — informes de ingeniería** (`docs/`)
- [Informe de puesta a punto y vuelo](INFORME_VUELO_DRONE.md)
- [Ruido de motores = saturación de yaw](DIAGNOSTICO_RUIDO_MOTORES_YAW.md)
- [Plataforma: hardware, firmware y comunicaciones](PLATAFORMA_HARDWARE.md) — ficha técnica + referencia SUPER
- [Parámetros indoor](PARAMETROS_INDOOR.md) — todos los parámetros sin GPS, por orden de importancia
- [Conexión MAVLink con scripts](CONEXION_MAVLINK_SCRIPTS.md) — hablar con el FC por cable o radio sin QGC
- [Metodología de trabajo](METODOLOGIA_TRABAJO.md) — cómo se analiza, dónde queda cada hallazgo y reglas al tocar el FC
- [Offboard RPi ⇄ FC (uXRCE-DDS)](CONFIGURACION_OFFBOARD_RPI4.md)
- [Integración MTF-01P flujo + LiDAR](INTEGRACION_MTF-01P_FLOW_LIDAR.md)

**Reportes de diagnóstico** (companion / RPi) — ver [`reports/`](../reports/README.md)
- [Tuning EKF2 del MTF-01 — flow indoor](../reports/2026-07-23_mtf01-ekf2-tuning.md)

**Versiones de firmware** — ver [backups/firmware/INDEX.md](../backups/firmware/INDEX.md).
Cada versión incluye el `.px4` flasheable (QGC → Custom firmware) y su
`board_config.diff` para reconstruir; `.bin`/`.elf` se omiten.

## Licencia

Distribuido bajo la [Licencia MIT](../LICENSE).

## Contacto

Kevin Medrano — [kevin.ejem18@gmail.com](mailto:kevin.ejem18@gmail.com) · [@Kmedrano101](https://github.com/Kmedrano101)
