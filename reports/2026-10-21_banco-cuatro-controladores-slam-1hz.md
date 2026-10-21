# Banco sin hélices: los cuatro ciclos arman, y el SLAM va a 1 Hz porque karto rechaza los barridos

**Fecha:** 2026-10-21 · **Origen:** cinco corridas de banco (09:53–09:58) en la Pi, logs y bags
**Estado:** ✅ secuencia hasta el despegue demostrada en los cuatro controladores · ⛔ **hallazgo:**
el EV al EKF llega a ~1 Hz por un rechazo sistemático de barridos en `slam_toolbox`

## Las cinco corridas

| Corrida | Qué pasó | Lectura |
|---|---|---|
| `bench_pid` (3 s) | OFFBOARD → switch → ARM → TAKEOFF → **desarme forzado a los 3.0 s** → `DISARMED` 12 ms después | El modo banco funciona; PX4 aceptó el 21196 en el acto |
| `bench_mpc` #1 | *"El FC no confirmó ARMED tras 5 s"*, abortó sin armar | PX4 denegó el armado y el nodo **no puede ver por qué**: `vehicle_command_ack` no está entre lo que el 1.14.3 exporta por DDS. Causa más probable: el **kill switch seguía engranado** de la corrida anterior |
| `bench_mpc` #2 (5 s) | ARM → TAKEOFF → `solver 9.93 ms media, 24.98 máx` → desarme a los 5.0 s | Solver **bajo carga real** 2.5× el aislado (4.4–9.3): 50 % del ciclo en el peor caso |
| `bench_mpc_plus` | ARM → TAKEOFF → a los 1.7 s `OFFBOARD → STAB` por el RC → *"control perdido, dejo de publicar"* | Salida correcta del nodo. En el bag, `mpc_status.d_* = 0` todo el rato: **la puerta de 0.35 m del observador funciona** |
| `bench_ctbr` | `CTBR: NMPC con actitud` → ARM → TAKEOFF → a los 4.3 s `OFFBOARD → ALTCTL` por el RC | Primera ejecución del nodo contra un FC real: arranca, carga el solver, no engancha (correcto), no se cae. Su **bag quedó a 0 bytes** pese a "Recording stopped": anomalía a vigilar |

Además: `eth0: optional interface was not found` en todos los logs — **sin Ethernet, todo
arrancó**: la corrección del campo probada en real.

## Lo que faltaba y no se veía: el MTF-01P apagado

En el banco `listener distance_sensor` y `listener sensor_optical_flow` daban *never published*,
la instancia MAVLink de TEL4 recibía 0 B/s, y los `SENS_FLOW_*` habían desaparecido del volcado
de octubre (PX4 solo lista por MAVLink los parámetros que algún módulo ha **usado** desde el
arranque; sin flujo, el módulo no se instancia). El sensor estaba apagado. Encendido: rango
0.14 m, flujo quality 131, 7.4 kB/s en `/dev/ttyS7 @115200`.

`EKF2_OF_CTRL = 1` y `EKF2_EV_CTRL = 9`: el flujo **complementa** (velocidad) al EV (posición +
yaw) solo cuando llega. Y el LiDAR 1D del mismo cable es el ancla de altura a 0.8 m: sin él, la
z va con el barómetro de 79 °C (3 mm/s de deriva) y el aterrizaje a ciegas. Por eso ahora
`tools/check_preflight.sh` lo comprueba por USB antes de cualquier prueba.

## El hallazgo: "LaserRangeScan contains 50x range readings, expected 5xx"

El aviso aparece 36–79 veces por corrida. No es cosmético:

- El LD19 entrega un número **variable** de puntos por vuelta — 498 a 506, mediana 502–503 — y
  su driver (`ldlidar/src/ros2_node/main.cpp`) pone `beam_size = src.size()` y
  `angle_increment = 2π/(beam_size − 1)` en **cada** barrido.
- `slam_toolbox` fija el número de rayos del sensor con el **primer** barrido, y karto, en
  `LaserRangeFinder::Validate`, **rechaza** (`return false`) todo barrido cuyo número no
  coincida. Verificado en el fuente.
- Encima, `minimum_time_interval: 0.2` en la config limita a 5 Hz.

| Corrida | Barridos (9.9 Hz) | Con el mismo n que el primero | Poses `/pose` reales |
|---|---|---|---|
| banco PID | 261 | 53 (**20 %**) | 28 → **1.06 Hz** |
| banco MPC | 151 | 45 (30 %) | **1.25 Hz** |
| banco MPC+ | 147 | 40 (27 %) | **0.88 Hz** |

El sysmon lo tenía escrito desde el principio: `slam_pose_hz 1.0`. Y es el **1.2 Hz del
accidente del 18-sep** ("SLAM 2D perdió el tracking"): el EV al EKF llega a ~1 Hz, el puente lo
penaliza con la varianza por edad, y el EKF vuela entre poses viejas.

Simulado sobre los bags (aceptación de karto × intervalo mínimo):

| Barridos aceptados | `minimum_time_interval` | Procesados (banco PID) |
|---|---|---|
| solo n == primero *(hoy)* | 0.2 s | 1.56 Hz (medido 1.06: hay un tercer limitador, el cómputo) |
| **todos (tamaño fijo)** | 0.2 s | **3.80 Hz** |
| todos | 0.1 s | 6.31 Hz |
| todos | 0.05 s | 9.92 Hz |

`slam_toolbox` va al **17 % de un núcleo** en el banco: hay margen para subir mucho.

### Corrección

Un nodo relay en `px4_drone` que remuestrea `/scan` a una rejilla **fija de 500 rayos** (0.72°),
con el mismo criterio que ya usa el driver (binning por ángulo, el menor rango por celda, NaN en
los huecos), y bajar `minimum_time_interval` por pasos midiendo CPU. Se valida *offline* con los
bags: el contador de "expected" tiene que quedar a cero y `slam_pose_hz` subir.

Dos deudas que aparecen con esto: **`px4_drone_slam` (config y launch del SLAM) no está
versionado en ningún sitio** — vive solo en la SD de la Pi — y el driver del LD19 tampoco. El
relay va en `px4_drone`; el cambio de intervalo queda documentado como deuda hasta que ese
paquete tenga repo.

## Qué no se tocó

No se voló; el armado y el kill los hizo el piloto. No se escribió ningún parámetro en el FC.
Los bags (2.7–4.8 MB) se quedan en la Pi.
