# Reporte: estimador y sensores en los vuelos offboard — selector EKF, estado EKF, flujo, LiDAR y magnetómetro

**Fecha:** 2026-09-11 · **Logs:** `logs/log100v2.ulg` (519 s, 93 s armado, 77 s en el aire) y `logs/sess168/log100.ulg` (1053 s, del 2026-09-10, sin vuelo)
**Autor / origen:** análisis de `.ulg` (FC#2, PX4 1.14.3 de fábrica `micoair743-v1.14.3`)
**Estado:** ✅ resumen completo · ⚠️ **hallazgo nuevo: los saltos de altura son cambios de instancia del EKF**, provocados por datos malos del acelerómetro vertical

Complementa a los reportes de los [vuelos 1](2026-09-11_offboard-vuelo1-flujo-failsafe.md) y [2](2026-09-11_offboard-vuelo2-runaway-rango.md).
Los bits de cada máscara están verificados contra `msg/EstimatorStatus.msg` y `ekf_helper.cpp` del tag `v1.14.3`.

---

## 1. `estimator_selector_status` — dos EKF, y el selector saltando entre ellos

Hay **dos instancias del EKF**, una por cada BMI088 (`EKF2_MULTI_IMU=3` con 2 IMU):

| | EKF0 | EKF1 |
|---|---|---|
| Acelerómetro / giróscopo | 6946826 / 6684682 | 6946850 / 6684706 |
| Barómetro | 5207817 (SPL06), compartido | |
| Magnetómetro | **`mag_device_id = 0`** (ninguno) | |
| Sano (log100v2) | **84.7%** | 97.6% |
| `combined_test_ratio` mediana / p95 / máx | 0.53 / 1.09 / **5.94** | 0.53 / 1.02 / **5.66** |
| Sano (sess168, en tierra) | 99.9% | 99.8% |

El selector **cambió la instancia primaria 5 veces** durante el log100v2, y cada cambio coincide al décimo de segundo con un salto de `z` en `vehicle_local_position`:

| t (s) | Cambio | Salto de z | Contexto |
|---|---|---|---|
| **269.2** | EKF0 → EKF1 | **−21.63 m** | sesión 2, en POSCTL a ~22 m |
| 300.6 | EKF1 → EKF0 | +1.37 m | sesión 2, tras el kill |
| 331.2 | EKF0 → EKF1 | −3.80 m | en tierra, desarmado |
| **430.6** | EKF1 → EKF0 | **+3.81 m** | sesión 4, **al tocar suelo en LAND** |
| 450.0 | EKF0 → EKF1 | −3.81 m | en tierra |

⚠️ **Corrige a los reportes anteriores.** El "reset de altura al baro (dz −21.6 m)" de la sesión 2 y el "salto de +3.8 m al tocar suelo" de la sesión 4 **no fueron resets dentro del EKF: fueron cambios de instancia**. Las dos instancias llegaron a discrepar en **21.6 m** de altura, y al conmutar de una a otra la salida saltó.

El selector no detectó fallo de giróscopo ni de acelerómetro: `gyro_fault_detected` y `accel_fault_detected` en false, errores acumulados a 0.

## 2. `estimator_status` — por qué EKF0 se declaraba no sano

Métricas en el aire (log100v2):

| | EKF0 | EKF1 |
|---|---|---|
| `vel_test_ratio` mediana / máx | 0.14 / **6.85** | 0.13 / 2.76 |
| `hgt_test_ratio` mediana / máx | 0.37 / **6.00** | 0.11 / **5.97** |
| `hagl_test_ratio` mediana / máx | 0.10 / 1.52 | 0.00 / **17.73** |
| `pos_horiz_accuracy` mediana / máx | 0.26 / 0.66 m | 0.26 / **6.28 m** |
| `pos_vert_accuracy` mediana / máx | 0.04 / 0.62 m | 0.52 / 0.63 m |
| **`filter_fault_flags`** | **bit 16 el 43% del vuelo** | bit 16 el 14% |
| `innovation_check_flags` | bits 9, 10, 11 (2%) | bits 9, 11 (13%) |
| Resets de velocidad/posición NE | **191** | **229** |
| `time_slip` | 0.006 s | 0.000 s |

### La cadena que explica los saltos

1. **`filter_fault_flags` bit 16 = "bad vertical accelerometer data has been detected"**. EKF0 lo tuvo activo el **43%** del tiempo en el aire, EKF1 el 14%. El bit 17 (*clipping*) no aparece: los datos no saturan, pero son incoherentes. Encaja con la vibración medida (3.1 m/s² de media, 6.5 de pico) y con el sesgo de acelerómetro estimado de +0.35 m/s² del [vuelo 2 §6](2026-09-11_offboard-vuelo2-runaway-rango.md).
2. `ekf_helper.cpp:757-761`: **todos los bits de `solution_status_flags` exigen `_fault_status == 0`**. Con el bit 16 activo, EKF0 deja de dar como válidas la velocidad, la posición y la altura.
3. EKF0 pasa a no sano → el selector conmuta a EKF1 → si las dos instancias discrepan en altura, **la salida salta**.

La discrepancia entre instancias viene del LiDAR: cada EKF acepta o rechaza el rango en momentos distintos, y en la sesión 2 uno siguió la lectura errónea del LiDAR mientras el otro seguía el barómetro.

### Resto de máscaras

- **`innovation_check_flags`**: bit 9 = HAGL rechazada, bits 10-11 = flujo X/Y rechazado. Pocos rechazos (2-13%): el problema no es que el EKF rechace el flujo, sino que el flujo se escala con una HAGL errónea (ver §4).
- **`solution_status_flags`** (OR a lo largo del vuelo: `0x9ee`):
  - bit 0 "actitud buena": **nunca activo**. Exige `yaw_align` (`ekf_helper.cpp:757`), y sin brújula no se alinea. Es solo un indicador: el control usa `attitude_valid()` = `tilt_align` (`estimator_interface.h:156`).
  - bit 7 "modo de posición constante": **aparece en el aire**, es decir, hubo tramos sin ninguna ayuda horizontal.
  - bit 11 "datos de acelerómetro malos": aparece, coherente con el bit 16.
- **191 y 229 resets de posición/velocidad NE en 519 s**: la fusión de flujo arrancó y paró cientos de veces (`reset_vel_to_flow`).

## 3. Flujo óptico — calidad

| Log | Fase | Muestras | Media | Mediana | Mín | < 30 (rechazado) |
|---|---|---|---|---|---|---|
| log100v2 | en el aire | 156 | **97** | 87 | 33 | **0%** |
| log100v2 | en tierra | 882 | 149 | 157 | 9 | 2% |
| sess168 | en tierra | 2105 | **54** | 54 | 43 | 0% |

Sensor `device_id 11665678`, `max_flow_rate` 8 rad/s, `min_ground_distance` 0.08 m.

- En el log100v2 **el flujo fue bueno en vuelo**: ninguna muestra por debajo de `EKF2_OF_QMIN=30`.
- **En sess168, en tierra, la calidad fue un tercio (54 frente a 149)**: otro sitio, otra superficie u otra luz. Refuerza que el fallo de flujo del vuelo 1 era del entorno. Una comprobación útil antes de despegar: la calidad en tierra. Donde funcionó rondaba 150; en sess168, 54.

## 4. `distance_sensor` — el LiDAR no ve el suelo la mayor parte del vuelo

| | log100v2 | sess168 |
|---|---|---|
| `device_id` / orientación | 9699598 / 25 (hacia abajo) | igual |
| Rango declarado | 0.02-12.0 m | igual |
| `signal_quality` | **−1** (no lo reporta) | −1 |
| Varianza declarada | máx **0.0044** | 0.0000 |
| En tierra | mediana 0.02 m | 0.02 m |
| **En el aire: máximo** | **1.71 m** | — |
| En el aire: p95 | 1.32 m | — |
| **En el aire: lecturas ≤ 0.03 m (sin retorno)** | **58%** | — |

- **En más de la mitad del tiempo en el aire el LiDAR no tuvo retorno.** El máximo en todo el vuelo fue 1.71 m, con el dron a más de 20 m.
- El sensor **nunca avisa**: calidad −1 y varianza casi nula incluso con datos basura. El EKF no tiene forma de saber que la lectura es mala.
- A 2 m el LiDAR lee ~40% de menos ([vuelo 2 §6](2026-09-11_offboard-vuelo2-runaway-rango.md)). Esa HAGL escala el flujo, y ahí nace la deriva horizontal.

## 5. `vehicle_magnetometer`

**No existe en ninguno de los dos logs, ni tampoco `sensor_mag`.** `mag_device_id = 0` y `mag_test_ratio = 0` siempre: no hay magnetómetro, como era de esperar en el FC#2.
Consecuencias: el bit de "actitud buena" nunca se activa (§2) y el yaw deriva, aunque poco: **−0.05 °/s** medido, despreciable en vuelos cortos.

## 6. Conclusiones

1. **Los saltos de altura son cambios de instancia del EKF**, disparados por el bit 16 (acelerómetro vertical malo) en EKF0, y amplificados porque las dos instancias discrepaban por el LiDAR.
2. **El acelerómetro está dando datos malos en vuelo**: bit 16 el 43% del tiempo, sesgo de +0.35 m/s² y vibración de 3-6.5 m/s². Es un problema de **vibración y temperatura**, no del EKF.
3. **El LiDAR no puede ser referencia de altura**: 58% de lecturas sin retorno en el aire y techo real de ~1.3-1.7 m.
4. **El flujo depende del sitio**: 150 de calidad en tierra en un sitio y 54 en otro.

## 7. Qué hacer

| Prioridad | Acción | Ataca |
|---|---|---|
| 1 | `EKF2_HGT_REF=0`, `EKF2_RNG_CTRL=1`, `EKF2_RNG_A_HMAX=1.2` | que las instancias discrepen en altura por el LiDAR |
| 2 | **Reducir la vibración**: equilibrar hélices, montar el FC sobre amortiguadores, revisar tornillería de motores | bit 16, sesgo del acelerómetro, cambios de instancia |
| 3 | **Temperatura de la IMU**: disipador 8×8 mm y no dejar el FC encendido en banco sin aire | sesgo térmico del acelerómetro |
| 4 | Vuelos a ≤1.0 m y comprobar la calidad del flujo en tierra antes de despegar | deriva por HAGL y por el entorno |
| 5 | Reiniciar el FC entre vuelos | arrastrar un estado roto del EKF |

`EKF2_MULTI_IMU` se deja como está: el selector hizo su trabajo, pasando a la instancia más sana. Los saltos son el síntoma de que las dos discrepan, y eso se corrige en el origen (puntos 1-3), no quitando la redundancia.

## Archivos

| Archivo | Tamaño | En git |
|---|---|---|
| `logs/log100v2.ulg` | 23.7 MB | no (umbral de 10 MB) |
| `logs/sess168/log100.ulg` | 43.8 MB | no (umbral de 10 MB) |
