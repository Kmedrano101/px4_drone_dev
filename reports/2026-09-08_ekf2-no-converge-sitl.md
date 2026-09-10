# Reporte: EKF2 no converge de forma intermitente en el SITL con el modelo RJX F450

**Fecha:** 2026-09-08
**Autor / origen:** dev machine (PX4 SITL + Gazebo Sim 8.10)
**Estado:** ✅ **resuelto** (2026-09-08) — eran tres parámetros EKF2 mal migrados. Ciclo completo verificado en vuelo. Queda aparte un fallo de arranque intermitente (§7).

**Contexto:** primer intento del ciclo `takeoff → hold → land` contra el simulador,
con el nodo `takeoff_position_hold_indoor` de la rama `gazebo-sim` de `px4_drone`.
Modelo `rjx_f450_indoor`, mundo `indoor_zone`, PX4 `main` @ `82e3322e`.

**Objetivo bloqueado:** validar el ciclo completo en simulación. El nodo aborta antes
de tocar OFFBOARD/ARM porque la fuente de posición nunca se declara válida.

---

## 1. Síntoma

El nodo conecta bien y lee estado del FC:

```
[takeoff_position_hold_indoor] nav_state: UNKNOWN(255) -> AUTO_LOITER
[takeoff_position_hold_indoor] arming_state: DISARMED
[ERROR] Fuente de posicion (flujo optico + lidar 1D: xy/z/v_xy/dist_bottom
        validos) no disponible tras 10 s. Abortando (no se toca OFFBOARD/ARM).
```

Estado interno de PX4 en ese momento:

```
ekf2:0  EKF dt: 0.0100s, attitude: 0, local position: 0, global position: 0
ekf2:   EKF update: 0 events                    <- nunca actualizo
sensors validator: best: -1, prev best: -1      <- ningun IMU seleccionado
sensor_accel:  z=-9.799, timestamp fresco       <- el dato SI llega de Gazebo
vehicle_imu:   never published                  <- VehicleIMU no lo empareja
failsafe_flags: attitude_invalid / local_position_invalid / local_altitude_invalid = True
```

La cadena se rompe **dentro de PX4**: los datos entran desde Gazebo
(`sensor_accel` y `sensor_gyro` publican, con gravedad correcta y timestamps
frescos) pero `VehicleIMU` nunca produce `vehicle_imu`, así que EKF2 se queda sin
actualizar y ninguna bandera de posición se valida.

## 2. Lo intermitente es lo que despista

**El mismo modelo, sin cambios, dio el resultado bueno antes:**

```
ekf2:0  EKF dt: 0.0100s, attitude: 1, local position: 1, global position: 0
ekf2:   EKF update: 970 events
failsafe_flags: attitude/local_position/local_altitude/local_velocity_invalid = False
```

Y en esa corrida buena se llegó a armar y despegar por Offboard hasta 0.89 m
(ver §5). O sea: **no es un error determinista del SDF**.

## 3. Hipótesis descartadas

| Hipótesis | Cómo se descartó |
|---|---|
| Es `ros2 launch` / el `sitl.launch.py` nuevo | Con `make px4_sitl gz_rjx_f450_indoor` directo falla igual |
| Es el bloque de sensores del modelo | `diff` del `imu_sensor` contra `x500_base`: **idéntico**, y está dentro de `base_link` |
| Es el mundo `indoor_zone` | El `x500` de stock en ese mismo mundo da `attitude: 1, local position: 1, global position: 1` y validador `best: 0` |
| Es el `topic_version_suffix` | El nodo lee `vehicle_status_v1` sin problema; el fallo es anterior, en EKF2 |
| Es falta de plugins del mundo | Ya resuelto aparte: el mundo no declara `<plugin>` y usa el `server.config` de PX4 |

⚠️ El A/B contra el `x500` es **una sola muestra**. Dada la intermitencia, no basta
para culpar al modelo.

## 4. Hipótesis a investigar

1. **Condición de carrera en el arranque** — `sensors` levantando antes de que
   lleguen las primeras muestras del bridge, y `VehicleIMU` no reintentando el
   emparejamiento. Es la que mejor explica que el mismo fichero dé los dos
   resultados. Mirar si el orden de arranque cambia entre corridas.
2. **La inclusión de `optical_flow`** en `rjx_f450_indoor` (añade `flow_link` con
   cámara y un sensor custom). Probar `gz_x500_flow` en `indoor_zone`.
3. **Carga de render** — 4 mallas de protector de 54k triángulos cada una más la
   malla del edificio. Aunque el RTF medido era ~1.0, conviene confirmarlo.

**Bisect propuesto**, 3 repeticiones de cada uno por la intermitencia:

```bash
make px4_sitl gz_rjx_f450        # frame solo, sin sensores
make px4_sitl gz_x500_flow       # flow de stock en indoor_zone
make px4_sitl gz_rjx_f450_indoor # el completo
```

## 5. Qué SÍ quedó verificado

- **El dron vuela en el simulador.** En la corrida buena: armó por Offboard,
  "Takeoff detected", subió de 0.18 a 0.89 m, y bajó por un failsafe cuya causa
  tampoco se identificó (sospechoso: `NAV_DLL_ACT=2`).
- **La rama `gazebo-sim` funciona hasta la puerta de entrada**: transporte UDP,
  `px4_msgs release/1.17` y `topic_version_suffix=_v1` correctos, 65 topics `/fmu/`
  visibles desde ROS 2 con CycloneDDS y con FastDDS en `ROS_DOMAIN_ID=10`.
- **Los sensores del modelo publican**: los dos LiDAR y el flujo óptico, en los
  topics fijos que espera `GZBridge`.

## 6. Qué NO se tocó

- No se modificó el modelo para intentar arreglarlo: no hay causa identificada.
- `NAV_DLL_ACT=2` sigue en el airframe (sospechoso del failsafe de §5).
- `COM_RC_IN_MODE` sigue por defecto; se cambió a 4 en caliente en una corrida.

## Documentos relacionados

- [`docs/SIMULACION_GAZEBO_INDOOR.md`](../docs/SIMULACION_GAZEBO_INDOOR.md)
- `px4_drone` rama `gazebo-sim`, `docs/gazebo_sim.md`


---

# ✅ RESOLUCIÓN (2026-09-08)

## Ciclo completo verificado

`arm → takeoff → hold 8 s → land → disarm`, contra **la verdad de simulación**, no
la estimación del EKF:

```
altura REAL maxima : 1.07 m   (objetivo 1.0)
altura REAL final  : 0.169 m  (suelo)
deriva XY real     : 0.13 m   en todo el vuelo, sin GPS
error EKF vs real  : 0.071 m
failsafe           : ninguno
cs_opt_flow / cs_rng_terrain / dist_bottom_valid = 1
```

## La causa: tres params EKF2 mal migrados

Vinieron de la migración del 2026-09-04 desde el FC#1 y se asumieron válidos para
simulación. **Rompen la cadena del flujo óptico**:

| Param | Migrado | Default PX4 | Efecto del valor migrado |
|---|---|---|---|
| `EKF2_RNG_CTRL` | **2** | **1** | El láser se consume como ALTURA (`rng_hgt`) y **nunca alimenta la estimación de terreno** (`rng_terrain`) |
| `EKF2_HGT_REF` | **2** | **1** | Refuerza lo mismo |
| `EKF2_OF_QMIN` | **30** | **1** | Descarta casi todas las muestras de flujo |

**La dependencia circular:** el flujo óptico necesita una estimación de terreno
válida para escalar el desplazamiento; el terreno se alimenta del láser *como
terreno*. Con `RNG_CTRL=2` el láser va a altura absoluta, el terreno nunca se
valida, `cs_opt_flow` **nunca** se activa y `dist_bottom_valid` se queda en 0 —
que es justo la bandera que `takeoff_position_hold_indoor` exige para despegar.

La pista decisiva: el airframe de referencia de PX4 para flujo óptico
(`4021_gz_x500_flow`) **no toca ninguno de esos tres** — solo apaga el GPS.

### ⚠️ Implicación para el FC#2 real

El FC#2 lleva **`EKF2_RNG_CTRL=2` y `EKF2_HGT_REF=2`**. Si esa combinación impide
la fusión de flujo también en hardware, sería una explicación concreta del hold de
posición indoor bloqueado desde [2026-07-23](2026-07-23_mtf01-ekf2-tuning.md), en
la que `heading_good_for_control=false` sería síntoma y no causa única.
**Pendiente de verificar en el FC real** leyendo `estimator_status_flags.cs_opt_flow`.

## Segundo hallazgo: el suelo sin textura

El flujo óptico mide por correlación de imagen. El suelo del escaneo era de color
plano y no había nada que correlacionar. Se texturó con la baldosa real del local
(`scripts/gazebo/gen_floor_texture.py`).

Dimensionar el detalle **contra lo que la cámara resuelve** fue clave:

```
camara de flujo 100x100 px, FOV 0.733 rad
  a 0.40 m ve 31 cm  ->  3.1 mm por pixel
```

El primer intento tenía grano de 1 mm — invisible. Y con baldosa de 25 cm, el
parche de 31 cm **puede caer entero dentro de una baldosa** sin ver ninguna junta:
de ahí que la calidad saltara entre 0 y 255. La solución fue veteado multiescala a
1-8 cm dentro de cada baldosa. Calidad de flujo: **mediana 38 → 248**.

## Correcciones a lo que este reporte afirmaba antes

1. **`HEADLESS=1` NO rompe los sensores GPU.** Medido: 4/4 corridas headless con
   flujo y LiDAR publicando. El aviso anterior salía de una comprobación temprana
   no repetida. Los `libEGL warning` del log son ruido.
2. **"El x500 descarta el mundo" no estaba justificado** cuando se escribió: era
   **una sola corrida** frente a un fallo que aparece ~1 de cada 3. Repetido
   después con 4 corridas (4/4), ahora sí sostiene la conclusión.
3. **Las alturas reportadas antes (0.89 m, 0.41 m) eran ficción del EKF.** Se
   estaba leyendo `vehicle_local_position`, la estimación, no
   `vehicle_local_position_groundtruth`. La altura real máxima en aquellas corridas
   fue **0.34 m**. Toda validación de vuelo debe ir contra groundtruth.

## §7 — Lo que sigue abierto

**Fallo de arranque intermitente, ~2 de cada 7.** `VehicleIMU` no empareja
acelerómetro y giróscopo, se queda en `validator best: -1` y EKF2 no actualiza.
Medido: `rjx_f450_indoor` 2/3 con GUI y 3/4 headless; `x500` de stock 4/4.
Apunta al modelo pero no es concluyente (4/4 por azar tiene un 25% de
probabilidad con esa tasa). **Mitigación en uso:** comprobar `attitude: 1` a los
30 s del arranque y relanzar si no. Con eso el ciclo es fiable hoy.
