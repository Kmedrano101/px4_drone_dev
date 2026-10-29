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
- ✅ Heading y posición sin magnetómetro por **SLAM 2D (LD19) → visión externa**, fusión EV validada y armado en tierra en Offboard
- ✅ Parada por obstáculo en 360° con el LiDAR 2D, varianza honesta del EV y monitor de carga de la Pi
- 🔄 **Tres variantes de MPC** en la Pi: cinemático (4.4–9.3 ms), **MPC+** con estado de perturbación (mismo binario, sin sesgo permanente) y **CTBR** con actitud en el modelo (2.7 ms de media, 5.9 máx; engancha solo en el hold) — ninguno volado aún
- 🔄 Hold de altura limitado por la **saturación del LiDAR 1D** sobre hormigón oscuro: zona útil ≤1 m
- ✅ **Falsos obstáculos al despegar** resueltos: la ráfaga del LiDAR 2D mientras giran las hélices (0 con hélices paradas) se separa por el **ancho real del obstáculo** — polvo 0.03–0.09 m, pilar de 40 cm 0.40 m, obstáculo real 1.18–1.83 m
- ✅ **Banco sin hélices (21-oct):** los cuatro ciclos arman y llegan al TAKEOFF; desarme forzado aceptado en 12 ms
- ✅ **SLAM de 1 Hz a 6.3 Hz**: karto rechazaba el 70–80 % de los barridos del LD19 (número de rayos variable, el 1.2 Hz del accidente del 18-sep); un relay a tamaño fijo los deja pasar todos — medido en banco, vuelo pendiente
- ⏳ Comparación en vuelo PID vs MPC (takeoff – hold 30 s – land a 0.8 m) — salida del 20-oct perdida entera: CycloneDDS clavado a `eth0` sin Ethernet en el campo (corregido y verificado el 21-oct)
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
- [Informe de puesta a punto y vuelo](historico/INFORME_VUELO_DRONE.md)
- [Ruido de motores = saturación de yaw](historico/DIAGNOSTICO_RUIDO_MOTORES_YAW.md)
- [Plataforma: hardware, firmware y comunicaciones](referencia/PLATAFORMA_HARDWARE.md) — ficha técnica + referencia SUPER
- [Parámetros indoor](referencia/PARAMETROS_INDOOR.md) — todos los parámetros sin GPS, por orden de importancia
- [Conexión MAVLink con scripts](referencia/CONEXION_MAVLINK_SCRIPTS.md) — hablar con el FC por cable o radio sin QGC
- [Metodología de trabajo](referencia/METODOLOGIA_TRABAJO.md) — cómo se analiza, dónde queda cada hallazgo y reglas al tocar el FC
- [Plan de test LiDAR 2D + EV](planes/2026-09-16_test_lidar2d_ev_offboard.md) — odometría externa con LiDAR 2D y altura con LiDAR 1D
- [Lo que está verificado en el fuente de PX4 1.14.3](referencia/PX4_1143_FUENTE_VERIFICADO.md) — hechos leídos en el código del tag que corre el FC, con archivo y línea: control, offboard, EV, altura y lo que el firmware de fábrica no expone
- [El software de la Raspberry Pi](referencia/SOFTWARE_ROS2_PX4_DRONE.md) — qué nodo corre, qué protege cada guarda y el incidente que la pagó
- [MPC del ciclo completo](referencia/MPC_CICLO_COMPLETO.md) — el control predictivo que corre en la Pi: modelo, por qué aceleración y no posición, coste de cómputo y deuda abierta
- [Protocolo PID vs MPC](planes/2026-10-16_protocolo_pid_vs_mpc.md) — cómo se vuela y qué se mide para que la comparación de controladores signifique algo
- [Plan de ajuste: vuelo suave y repetible](planes/2026-10-19_plan_tuning_takeoff_hold_land.md) — el orden de capas (mecánica → estimación → tasas → empuje → control exterior), qué medir en cada fase y los objetivos candidatos
- [Parámetros del FC para vuelo suave](planes/2026-10-20_parametros_vuelo_suave_produccion.md) — qué hay hoy en el FC (volcado de 903), qué le hace PX4 a nuestros setpoints durante el despegue, y qué tocar por orden de efecto
- [Pruebas en banco sin hélices](planes/2026-10-21_pruebas_banco_sin_helices.md) — modo banco: desarme forzado N s tras el TAKEOFF (21196) para que los motores no se vayan al 100 %; orden de pruebas antes de volver al campo
- [Outdoor con GPS ZED-F9P: Position/Altitude hold](planes/2026-10-21_outdoor_gps_zedf9p_position_hold.md) — el F9P da posición pero no rumbo; **perfil outdoor aplicado** (GPS fusionado), perfiles indoor↔outdoor conmutables (QGC/CLI), cableado y checklist de prearmado
- [Mapeo de motores y geometría](referencia/PLATAFORMA_HARDWARE.md) — geometría Quad-X (`CA_ROTOR*`) vs mapeo de salidas (`PWM_MAIN_FUNC*`); el arreglo del cruce de cable motor 2↔3 (2026-10-27)
- [Companion para MID-360S y SLAM interior](planes/2026-10-19_companion_mid360s_slam.md) — qué ordenador sustituiría a la Pi con un LiDAR 3D: evidencia encontrada, alternativas y prueba de aceptación antes de comprar
- [Gaps de investigación para publicar](publicaciones/2026-10-01_gaps_publicacion.md) — literatura reciente frente a lo que ya hay medido; hacia dónde enfocar el próximo paper
- [Offboard RPi ⇄ FC (uXRCE-DDS)](referencia/CONFIGURACION_OFFBOARD_RPI4.md)
- [Integración MTF-01P flujo + LiDAR](referencia/INTEGRACION_MTF-01P_FLOW_LIDAR.md)

**Reportes de diagnóstico** (companion / RPi) — ver [`reports/`](../reports/README.md)
- [Tuning EKF2 del MTF-01 — flow indoor](../reports/2026-07-23_mtf01-ekf2-tuning.md)

**Versiones de firmware** — ver [backups/firmware/INDEX.md](../backups/firmware/INDEX.md).

**Perfiles y backups de parámetros** (`backups/`)
- [Perfil indoor](../backups/profiles/perfil_indoor_flujo-lidar.params) — flujo óptico + LiDAR, GPS off (`EKF2_GPS_CTRL=0`, altura por rango)
- [Perfil outdoor](../backups/profiles/perfil_outdoor_gps.params) — GPS fusionado + brújula, flujo/rango off (`EKF2_GPS_CTRL=7`, altura por baro) — **aplicado 2026-10-27**
- Ficheros de carga **parcial** (9 params: estimación + failsafe RC/datalink → **Land**) para conmutar por QGC *Tools → Load from file* o `scripts/mavlink/load_params.py`; no tocan motores/tuning/batería. Reiniciar el FC al cambiar.
- Volcados completos (939 params, ambos con el arreglo del mapeo de motores): `backup_fc_2026-10-27_outdoor-motorfix.params` (actual) e `..._indoor-motorfix.params`.
Cada versión incluye el `.px4` flasheable (QGC → Custom firmware) y su
`board_config.diff` para reconstruir; `.bin`/`.elf` se omiten.

## Licencia

Distribuido bajo la [Licencia MIT](../LICENSE).

## Contacto

Kevin Medrano — [kevin.ejem18@gmail.com](mailto:kevin.ejem18@gmail.com) · [@Kmedrano101](https://github.com/Kmedrano101)
