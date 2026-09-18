# Log 158 — takeoff EV a 1 m correcto; el patrón en cruz se escapó ~3 m porque el SLAM 2D perdió el tracking

**Fecha del análisis:** 2026-09-18 · **Log:** SD `sess182/log100.ulg` (id MAVLink 158, bajado por USB con
`scripts/mavlink/logs.py`; `SDLOG_MODE=2`, graba desde el arranque) · **FC#2** PX4 1.14.3 vendor
**Estado:** ⛔ causa raíz identificada: el SLAM 2D perdió el tracking y el puente ocultó su covarianza · ⚠️ mapa de modos del RC peligroso

**Fuentes cruzadas:** log del FC (158), logs ROS de la Pi (`~/.ros/log/*_1789649204*`) y el rosbag del vuelo
`cross_pattern_1789649199_bag` (copiado a `logs/2026-09-18/`; truncado por el golpe, `metadata.yaml` vacío, se
lee en streaming con la librería `mcap`).

El log 159, el último de la SD, es el de la sesión en curso por USB: con `SDLOG_MODE=2` crecía
durante la descarga (de 24.7 a 78.8 MB). **Las dos últimas pruebas de vuelo son los dos intentos de este log.**

## 1. Qué pasó

| | Intento A (166–189 s) | Intento B (277–301 s) |
|---|---|---|
| Armado | por comando externo (Pi) | por comando externo (Pi) |
| Setpoint | `z_armado − 1.0` = −1.73 | `z_armado − 1.0` = −1.46 |
| Subida según EKF | 0.98 m (z −0.73 → −1.71) | 0.99 m (z −0.46 → −1.45) |
| LiDAR 1D en hover | 1.34–1.37 m (patas a ~1.18 m) | 1.38–1.42 m (patas a ~1.24 m) |
| Tiempo hasta la altura | ~9 s (vz máx 0.24 m/s) | ~10 s (vz máx 0.28 m/s) |
| Nodo | `takeoff_position_hold_ev` (subir, hold 5 s, LAND) | **`cross_pattern_ev`**: tramo 1/8 "adelante" → NED (−0.01, **0.99**) a 290.5 s |
| Final | LAND de la Pi a 181.5 s, aterrizaje suave, desarme | **se escapa ~3 m → cambio de modo a 294.0 s → caída y vuelco** |

**La altura de 1 m se alcanzó las dos veces.** Si acaso se pasó un poco: el EKF (referencia baro,
rango como ayuda condicional) mide ~1.0 m de subida y el LiDAR ~1.2 m. La subida es lenta
(~10 s), lo que en campo puede parecer que "no llega".

## 2. El LiDAR 1D funcionó bien

- 32 016 muestras en 320 s = **100 Hz continuos**, sin huecos.
- 0.17–0.18 m en tierra antes y después de cada vuelo (= `EKF2_MIN_RNG`).
- Durante la subida la lectura crece de forma monótona y sigue al EKF con un desfase casi constante.
- `cs_rng_hgt` entra al despegar y se mantiene en todo el vuelo, sin `rng_fault`.
- Ni valores clavados, ni caídas a 0.02 m (la firma de obstrucción), ni saltos.

## 3. Causa raíz del intento B: el SLAM 2D perdió el tracking en el primer tramo de la cruz

El piloto vio el dron avanzar mucho más de 1 m. Los tres registros coinciden:

| t desde el inicio del tramo | LiDAR 2D: distancia mínima | Flujo óptico (vy) | SLAM `/pose` (ENU x) | Covarianza SLAM | EKF y |
|---|---|---|---|---|---|
| hover | 3.4 m | ~0 | ±0.2 m | 0.003 | ~0 |
| 1.2 s | 3.3 m | 0.56 m/s | +0.04 | 0.003 | 0.05 |
| 2.1 s | 2.8 m | 1.05 m/s | +0.12 | **0.17** | 0.36 |
| 3.1 s | 1.8 m | 0.65 m/s | +0.10 | **0.14** | 0.40 |
| 3.5 s | ~1.1 m | 1.57 m/s | — | — | 0.40 ← piloto cambia de modo |
| 3.8 s | 0.9 m | — | +0.14 | **0.23** | — |
| 4.0 s | **0.47 m** | — | — | — | — |

- **El movimiento real fue de ~3 m a ~1.2 m/s**: lo dicen los barridos crudos (el obstáculo pasa de 3.4 a 0.47 m) y el flujo óptico. El flujo midió bien.
- **El SLAM creyó que no se movía** (+0.1 m) y **lo sabía**: su covarianza subió ×50–70.
- **El puente descarta esa covarianza** (`position_variance = NaN` fijo). El EKF cae entonces en
  `EKF2_EVP_NOISE = 0.1 m` y fusiona la pose mala como si fuera buena. La innovación EV (0.29 m) queda dentro de la puerta.
- **El EKF se queda clavado en y = 0.40** entre el flujo, que dice "avanzas", y el EV, que dice "no". El controlador ve
  0.6 m de error hasta el setpoint y sigue empujando hasta `MPC_XY_VEL_MAX = 1.0`. Como su estimación de velocidad
  (0.35–0.65) es más baja que la real, la velocidad real llega a 1.57 m/s. Es una **fuga horizontal**: el mismo patrón
  que la vertical del vuelo 2.

**Por qué pierde el tracking.** `/scan` llega a 9.9 Hz, pero slam_toolbox publica `/pose` a **1.2 Hz**: procesa uno de
cada ocho barridos. Sin odometría (TF `odom → base_link` estática), cada emparejamiento parte de "no me he movido", y
`correlation_search_space_dimension: 0.5` solo busca **±0.25 m** alrededor de ese punto. A 0.5–1.5 m/s, entre dos
barridos procesados el dron recorre 0.5–1.3 m: fuera de la ventana. El matcher devuelve un emparejamiento falso cerca
de cero, penalizado además por `distance_variance_penalty`. La inclinación al acelerar (pitch hasta −10°) probablemente
empeora la calidad del barrido, pero la ventana basta por sí sola para explicarlo.

## 3b. La caída al final (intento B)

Secuencia medida:
1. Hover estable en OFFBOARD a ~1 m. Gas del mando **al mínimo (−1.00) todo el vuelo**: en Offboard se ignora.
2. **293.99 s** — el canal 6 (`RC_MAP_FLTMODE=6`) pasa de 999 a 2000: slot 1 → 4 → **6** en 60 ms.
3. `COM_FLTMODE4=1` (Altitude) solo dura 50 ms; **`COM_FLTMODE6=8` = Stabilized** a 294.06 s.
4. En Stabilized el gas va directo al empuje: con el stick abajo, el empuje cae de 0.33 a 0.05 → vz +3.6 m/s.
5. **295.0 s** — golpe y vuelco (roll 173°) → *Attitude failure (roll)* → failsafe. El piloto sube el gas a
   +0.93 en ese mismo instante, ya tarde. Kill switch a 296.2 s.

Horizontalmente iba derivando ±0.3–0.4 m (y +0.40 al final), lo que puede explicar por qué el piloto intervino.

## 4. Pose EV: 20 Hz de mensajes, 1.2–1.6 Hz de información

`vehicle_visual_odometry` llega a 20 Hz, pero la posición solo cambia 1.6 veces/s (A) y 1.2 veces/s (B):
**~93% de los mensajes repiten una pose vieja con sello de tiempo actual**, con `EKF2_EV_DELAY=0`.
Confirma en vuelo la sección 1 de la revisión del 18-sep: el puente republica la TF a 20 Hz aunque el
SLAM solo la actualice a 1–2 Hz. Es candidato directo a la deriva horizontal de ±0.4 m.

## 5. Cambios recomendados (no aplicados)

**Críticos, antes de volver a mover el dron en horizontal con EV:**

| Dónde | Cambio | Por qué |
|---|---|---|
| `ev_odometry_bridge` | pasar la covarianza de `/pose` a `position_variance` en vez de NaN | el SLAM avisó ×50–70 y el EKF no se enteró |
| `ev_odometry_bridge` + nodos | cortar el EV y abortar (hold/land) si la covarianza pasa de un umbral | que un SLAM perdido no pueda arrastrar el control |
| `ev_odometry_bridge` | publicar solo cuando llega `/pose` nueva, con su sello | 93% de los mensajes eran poses repetidas |
| slam_toolbox | dar un prior de movimiento (odometría del FC o del flujo) **o** ampliar la ventana y abaratar el matcher (`correlation_search_space_resolution` 0.01 → 0.025–0.05) | a 1.2 Hz y ±0.25 m no se puede seguir nada que vaya a más de ~0.3 m/s |
| `MPC_XY_VEL_MAX` | 1.0 → **0.3–0.5** (lo propuesto para el parking, nunca aplicado) | acota el daño si la estimación vuelve a fallar |
| `cross_pattern_ev` | rampa de setpoint, no escalón 0 → 1 m | el escalón pide aceleración máxima y máxima inclinación |

**Seguridad del piloto:**

| Param / código | Ahora | Propuesto | Por qué |
|---|---|---|---|
| `COM_FLTMODE6` | 8 (Stabilized) | **2 (Position)** o 1 (Altitude) | Con gas abajo, Position/Altitude bajan a `MPC_Z_VEL_MAX_DN` (0.8 m/s) controlado; Stabilized corta el empuje |
| Procedimiento | — | **gas al centro antes de salir de Offboard** | En Offboard el stick no hace nada, y se queda donde lo dejaste |
| `ev_odometry_bridge` | republica la TF a 20 Hz | publicar solo cuando el SLAM actualiza, con su sello | Evitar alimentar el EKF con poses viejas como si fueran nuevas |
| `EKF2_EV_DELAY` | 0 | medir | Latencia real del SLAM |
