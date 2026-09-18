# Plan de test: navegación offboard con LiDAR 2D (odometría externa) + LiDAR 1D (altura)

**Fecha:** 2026-09-16 · **Estado:** 📋 plan, sin ejecutar
**Plataforma:** RJX F450 · FC HKUST NxtPX4v2 · **PX4 1.14.3 de fábrica** (`micoair743-v1.14.3`) · RPi 4 · ROS 2 Jazzy · `px4_msgs` rama `release/1.14` (commit `ffb6e80`)
**Zona:** parking abandonado, **poca iluminación**

> Historial y análisis de los vuelos previos:
> [vuelo 1](../reports/2026-09-11_offboard-vuelo1-flujo-failsafe.md) ·
> [vuelo 2](../reports/2026-09-11_offboard-vuelo2-runaway-rango.md) ·
> [resumen del estimador](../reports/2026-09-11_estimador-sensores-offboard.md)
>
> El **nodo ROS 2** de este test irá en el workspace (`xtract-px4-drones`); aquí vive el plan y su análisis.

---

## 1. Por qué cambia la arquitectura

El flujo óptico **no sirve en este escenario**: necesita luz y textura, y en los vuelos anteriores su calidad cayó de 158 a 14 al despegar en un sitio con mala superficie. En un parking oscuro será peor.

El LiDAR 2D no depende de la luz y, además, **da rumbo**: es lo que resuelve el bloqueo del yaw que arrastra el proyecto desde julio, porque este FC no tiene magnetómetro.

| Magnitud | Fuente nueva |
|---|---|
| x, y, **yaw** | LiDAR 2D 360° → odometría por scan matching → `/fmu/in/vehicle_visual_odometry` |
| Altura | LiDAR 1D hacia abajo (`distance_sensor`) + barómetro |
| Flujo óptico | **desactivado** (`EKF2_OF_CTRL=0`) |

## 2. Parámetros de PX4

Verificados contra el tag `v1.14.3` del fuente.

| Param | Valor | Motivo |
|---|---|---|
| `EKF2_EV_CTRL` | **9** | bit 0 posición horizontal + bit 3 yaw. **Un LiDAR 2D no da altura**: el bit 1 queda apagado. El bit 2 (velocidad 3D) solo si el SLAM publica velocidad fiable |
| `EKF2_EV_DELAY` | **medir** | por defecto 0 ms; un SLAM 2D en una Pi 4 puede ir 50-200 ms retrasado. Si no se declara, el dron oscila |
| `EKF2_EV_POS_X/Y/Z` | **0 / 0 / −0.114** | medido: el plano de barrido está 11.4 cm **encima** del FC. Ojo al signo, ver §4.1 |
| `EKF2_EVP_NOISE` / `EKF2_EVP_GATE` | 0.1 m / 5 | punto de partida |
| `EKF2_OF_CTRL` | **0** | el flujo solo metería ruido a oscuras |
| `EKF2_HGT_REF` | **0** (barómetro) | **no** usar rango como referencia: provocó el escape vertical a 25 m del vuelo 2. Tampoco Vision (3): el 2D no da altura |
| `EKF2_RNG_CTRL` | **1** (condicional) | el 1D entra como ayuda cerca del suelo |
| `EKF2_RNG_A_HMAX` | **1.2** | techo fiable del 1D, a validar en el parking |
| `COM_RC_OVERRIDE` | **3** | que los sticks saquen también del offboard |
| `COM_RCL_EXCEPT` | **0** | failsafe por pérdida de RC también en offboard |

Límites de velocidad para este escenario: `MPC_XY_VEL_MAX` y `MPC_VEL_MANUAL` 0.5 m/s, `MPC_MAN_TILT_MAX` 12°, `MPC_TILTMAX_AIR` 15°, `MPC_ACC_HOR` 1.0, `MPC_Z_VEL_MAX_UP/DN` 0.5/0.4.

## 3. Contrato del mensaje `VehicleOdometry`

Los errores más habituales están aquí. Campos según `msg/VehicleOdometry.msg` de la 1.14.3:

- 🔴 **`pose_frame = POSE_FRAME_NED` (1), NO FRD.** *(Corregido el 2026-09-17; la recomendación
  inicial de usar FRD era errónea.)* Semánticamente FRD encaja —origen y rumbo arbitrarios—
  pero en `ev_yaw_control.cpp` la rama FRD hace **`_control_status.flags.yaw_align = false`**
  a propósito, mientras la rama NED lo pone en `true`. Sin magnetómetro,
  `heading_good_for_control` **es** `yaw_align`, así que **con FRD nunca será true** y el yaw
  queda inservible para control aunque se esté fusionando. Verificado igual en **v1.15.0**
  (línea 166): actualizar el firmware no lo cambia.
  Declarar NED significa que "el norte" del EKF es el eje X del mapa del SLAM. Sin GPS ni
  brújula nada lo contradice y todo es relativo de todos modos: es lo habitual en SLAM indoor.
- **Conversión ROS → PX4**: el SLAM trabaja en ENU/FLU y PX4 en NED/FRD. Hay que convertir posición **y** cuaternión.
- **`q`**: rotación del cuerpo FRD al marco de referencia. Con un 2D solo hay yaw → roll y pitch a cero. PX4 usa solo la componente de yaw.
- **Lo desconocido va a `NaN`**, nunca a cero. Un `0.0` en `position[2]` significa "estoy en el origen" y se fusionaría.
- **`reset_counter`**: incrementarlo cuando el SLAM salte. Mejor aún: publicar la **odometría continua**, no la pose corregida por cierre de bucle, porque un loop closure mueve la pose de golpe y el EKF lo toma por movimiento real.
- **`timestamp_sample`**: instante de la medida, no de la publicación.

## 4. Montaje del LiDAR 2D

### 4.1 Offsets medidos y el cambio de signo

| Elemento | TF de ROS (FLU, Z **arriba**) | Parámetro de PX4 (FRD, Z **abajo**) |
|---|---|---|
| **LiDAR 2D**, plano de barrido | `base_link → laser` = (0, 0, **+0.114**) | `EKF2_EV_POS_X=0`, `Y=0`, **`Z=−0.114`** |
| **Láser 1D** MTF-01P | (0.055, 0, **−0.020**) | `EKF2_RNG_POS_X=0.055`, `Y=0`, **`Z=+0.020`** |
| **Flujo óptico** MTF-01P | (0.055, 0, **−0.018**) | `EKF2_OF_POS_X=0.055`, `Y=0`, **`Z=+0.018`** |

⚠️ **El signo de Z se invierte entre ROS y PX4.** El LiDAR está *encima*, así que lleva
**+0.114 en el TF y −0.114 en el parámetro**. Equivocarse no da ningún aviso: el EKF
corrige el brazo de palanca al revés. A 12° de inclinación, 11.4 cm desplazan el sensor
**2.4 cm** en horizontal.

Los 11.4 cm son **al plano de medición**, no a la base de la carcasa. En el modelo de
simulación el módulo se monta a 0.0995 y el sensor va 0.024 más arriba dentro de él, así
que el plano queda a 0.1235: **el modelo está ~1 cm por encima de la realidad**. Para
cuadrarlo, el `<pose>` del D500 en `rjx_f450_indoor/model.sdf` debería ser **0.090**.

Los 5.5 cm hacia adelante del MTF-01P salen del modelo de simulación, pendientes de
confirmar con cinta en el dron real.


- **Enmascarar los sectores** donde se ve a sí mismo: hélices, brazos y patas. Si no, el scan matching se engancha a ellos.
- **El plano de escaneo se inclina con el dron**: a 12°, una pared a 5 m se desplaza un metro. De ahí el límite bajo de inclinación.
- **Masa alta**: sube el centro de gravedad; reequilibrar.
- **Vibración**: lleva motor propio. Montarlo desacoplado del FC.
- Alimentación: BEC de 5 V o 12 V del FC, 2.5 A cada uno.

## 5. El nodo de test

Máquina de estados explícita, con timeout en cada paso:

```
INIT → ESPERANDO_EV → PREARM → ARM → TAKEOFF → HOLD → LAND → DISARM
```

**Precondiciones antes de armar** (ninguna existía en los nodos anteriores):
- ⚠️ **No usar `estimator_status_flags`**: la 1.14.3 **no lo publica**. Su lista de topics
  se compila en el firmware (`dds_topics.yaml` → `dds_topics.h`) y esta versión publica 14,
  sin incluirlo; `main` publica 28 y sí lo trae, **por eso en el SITL funciona y en el dron
  no**. Hay que usar señales equivalentes de `vehicle_local_position`:
  `xy_valid`, `!dead_reckoning` y un umbral de `eph`.
- `vehicle_local_position.xy_valid`, `z_valid` y `heading_good_for_control`. Este último **por fin debería ser true** al fusionarse el yaw del EV.
- Odometría del SLAM con menos de 200 ms de antigüedad.

**Condiciones de aborto** — cada una viene de un fallo real:
| Condición | Acción | Origen |
|---|---|---|
| `nav_state != OFFBOARD` | dejar de publicar el heartbeat y parar la secuencia | vuelo 1: PX4 volvió solo a OFFBOARD y solo lo frenó el kill |
| `vehicle_status.failsafe` | igual | vuelo 1 |
| Odometría EV parada >0.5 s | aterrizar | nuevo |
| No en OFFBOARD | **no mandar `NAV_LAND`** | vuelo 2: el LAND de la Pi le quitó el control al piloto |

**Setpoints**: altura **absoluta y limitada a ≤1.2 m**, nunca relativa a la z estimada, que puede venir desplazada.

### 5.1 Parada por obstáculo (añadida el 2026-09-18)

`takeoff_position_hold_ev`, que ejecuta tanto el despegue/hold como el patrón en cruz, vigila `/scan`
en 360° con `obstacle_stop_distance_m` (**1.0 m** por defecto, también en la webui):
- **no arma** con nada más cerca de esa distancia;
- **en vuelo frena y aterriza** cuando un obstáculo se acerca tanto que hay que empezar a frenar
  para quedar a esa distancia (`X + v·0.35 s + v²/(2·2 m/s²)`, con `v` medida en los barridos);
- **sin `/scan`** más de 0.5 s: frena y aterriza.

Usa **solo los barridos crudos**, no el SLAM ni la posición del EKF: en el log 158 el SLAM dijo
"quieto" mientras el dron recorría ~3 m, y solo `/scan` vio el obstáculo. El frenado es velocidad
horizontal 0 con la posición horizontal en NaN, que en 1.14.3 no influye (`PositionControl.cpp`).
No depende, por tanto, de la pose del EV.

Validado sin volar:
- **Con el rosbag del accidente:** ninguna parada falsa en despegue ni hover, y parada a t = 3.16 s
  (obstáculo a 1.65 m, acercándose a 1.27 m/s). El piloto intervino a los 3.54 s.
- **El nodo entero contra un FC falso:** no arma con un obstáculo a 0.6 m; frena a 1.56 m ante una
  pared a 1.2 m/s y aterriza; frena al cortarse `/scan`.

Limitaciones: **no rodea** el obstáculo, y solo ve lo que corta el **plano** del LiDAR. Detalle y
cómo repetir la validación en `px4_drone/tools/obstacle_guard/README.md`.

### 5.2 HOLD y ATERRIZAR desde la webui (2026-09-18)

En las pruebas con despegue, el STOP de antes **mataba todo**: nodo, SLAM, puente EV y agente DDS. En
vuelo eso deja al FC en failsafe de Offboard. Ahora hay dos botones que avisan al nodo con una señal,
sin cortar nada:
- **HOLD:** frena 1 s y mantiene la posición donde quedó. Siguen activas la parada por obstáculo, la
  salud del SLAM y la detección de control perdido. Si no llega otra orden, aterriza a los 120 s.
- **ATERRIZAR:** LAND, solo si el nodo aún tiene el control.
- **Antes de armar:** cualquiera de los dos cancela la prueba sin armar.

"MATAR procesos" sigue existiendo, pero en pruebas de vuelo pide confirmación.

## 6. Secuencia de pruebas

| # | Prueba | Criterio de éxito |
|---|---|---|
| 1 | SLAM en tierra: llevar el dron a mano, dar una vuelta y volver al inicio | ✅ **Validado (2026-09-17)**: error de cierre pequeño y sin saltos. Requiere `minimum_travel_distance: 0.0` al no haber odometría de ruedas (ver [reporte](../reports/2026-09-17_slam-manual-ld19-congelado.md)) |
| 2 | EV al EKF, desarmado | ✅ **Validado (2026-09-17)**: EKF2 fusiona EV en `POSE_FRAME_NED` (20 Hz). Medido: `eph = 0.046 m`, `xy_valid=True`, `z_valid=True`, `v_xy_valid=True`, `heading_good_for_control=True` (sin mag), `dead_reckoning=False`. |
| 2b | Armado en tierra Offboard (hold 5 s en origen, sin despegue) | ✅ **Validado (2026-09-17)**: entrada en Offboard, armado por software, 5 s en idle y auto-desarme. SLAM 2D y EKF2 100% estables ante vibración motora ($eph = 0.045\text{ m}$, deriva $<1\text{ mm}$). Ver [reporte](../reports/2026-09-17_prueba2b-armado-tierra-offboard-validado.md). |
| 3 | Hover en Altitude, con piloto | el EV coincide con lo que se ve |
| 4 | Offboard en hold, sin desplazarse (`takeoff_position_hold_ev`) | mantiene posición a ≤1.2 m. 🔄 **Log 158, intento A:** altura alcanzada y aterrizaje suave, con deriva horizontal de ±0.3–0.4 m |
| 5 | Patrón cruz 4 direcciones con SLAM 2D (`cross_pattern_ev`) | recorre 1.0 m (adelante, atrás, izquierda, derecha) volviendo al centro en cada tramo con SLAM 2D y aterriza suave. ❌ **2026-09-17:** en el primer tramo el SLAM perdió el tracking y el dron se escapó ~3 m ([reporte](../reports/2026-09-18_takeoff-ev-log158-caida-stabilized.md)). No repetir hasta corregir el puente EV; ahora con parada por obstáculo (§5.1) |

**Antes de nada, en el sitio:** medir la calidad del flujo y el alcance del LiDAR 1D con [`scripts/mavlink/monitor_sensors.py`](../scripts/mavlink/monitor_sensors.py). A oscuras el 1D debería llegar más lejos que en exterior, donde no pasó de 1.71 m.

## 7. Riesgos conocidos

| Riesgo | Mitigación |
|---|---|
| Cómputo de la Pi 4 (SUPER usa un NUC) | medir el tiempo de ciclo del SLAM antes de volar |
| Escape vertical por el LiDAR 1D | `EKF2_HGT_REF=0`; techo de altura en el nodo |
| Columnas y paredes | parada por obstáculo con `/scan` crudo (§5.1), vuelo lento, protectores de hélice. No rodea: solo frena y aterriza |
| SLAM que pierde el tracking y el EKF se lo cree (log 158) | ✅ 2026-09-18 (`px4_drone` `ed05f52`): el puente sigue a 20 Hz (EKF2 deja el EV si pasan >200 ms, `EV_MAX_INTERVAL`), pero con **varianza = la del SLAM + (antigüedad × 1.5 m/s)²**, así que entre poses manda el flujo; z/roll/pitch van finitos porque EKF2 solo usa las varianzas si las tres lo son. El nodo **no despega y aterriza si la σ del SLAM > 0.3 m** o `/pose` falta 2.5 s (hover 0.06–0.10 m, perdido 0.41–0.48 m en el bag). §5.1 queda como segunda barrera |
| ¿La Pi 4 se queda corta? | cada prueba de la webui guarda la carga (CPU por núcleo, temperatura, throttling, RAM, procesos, `/scan` vs `/pose`) en `logs/<run>_sysmon.csv` con resumen al final del log (`px4_drone/tools/sysmon/`) |
| Estado del EKF arrastrado entre vuelos | reiniciar el FC entre pruebas |

## 8. Pendiente de definir

- ~~Modelo del LiDAR 2D y su driver ROS 2~~ → **LDROBOT LD19/D500**, driver `ldlidar`,
  `/scan` a 10 Hz, 450 muestras, 12 m.
- Paquete de **SLAM / odometría** (scan matching continuo, no pose con cierre de bucle).
- Modelo del **LiDAR 1D** hacia abajo: ¿el del MTF-01P o uno dedicado?
