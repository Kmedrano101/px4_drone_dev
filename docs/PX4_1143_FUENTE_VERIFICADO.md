# Lo que está verificado en el fuente de PX4 1.14.3

Hechos leídos **en el código del tag que corre el FC#2**, no en la wiki ni de
memoria. Cada uno lleva el archivo donde está. Existe porque varias decisiones
del proyecto (publicar aceleración, el puente EV a 20 Hz, el techo de altura, la
varianza honesta) solo se entienden con esto delante, y porque la documentación
oficial de PX4 describe `main`, que ya no es lo que lleva este dron.

> **Regla:** si un comportamiento del FC no está en esta lista, no está
> verificado. Ver [`METODOLOGIA_TRABAJO.md`](METODOLOGIA_TRABAJO.md).

---

## 1. Control: no hay ningún MPC dentro del FC

`MPC_*` significa **Multicopter Position Control**, no Model Predictive Control.
La cadena real es una cascada clásica:

| Etapa | Dónde | Qué es |
|---|---|---|
| Posición | `PositionControl::_positionControl` | P |
| Velocidad | `PositionControl::_velocityControl` | PID |
| Aceleración → empuje/actitud | `PositionControl::_accelerationControl` | usa `MPC_THR_HOVER` |
| Actitud | control de actitud | P sobre cuaternión |
| Tasas | `rate_control.cpp` | PID + feed-forward |

## 2. Offboard: tres cosas que condicionan todo

1. **No hay suavizado.** En 1.14.3 **no existe un FlightTask de offboard**, así
   que un escalón en el setpoint de posición pide **aceleración máxima** desde el
   primer ciclo. El perfil del vuelo lo dibuja el error, no una trayectoria.
   → es la razón de ser del MPC con jerk acotado
   ([`MPC_CICLO_COMPLETO.md`](MPC_CICLO_COMPLETO.md)).
2. **El heartbeat decide qué lazos corren.** En `control_mode.cpp`, rama
   `NAVIGATION_STATE_OFFBOARD`: si el heartbeat pide `acceleration`, PX4
   **apaga** sus lazos de posición y velocidad. Es lo que permite que el
   controlador exterior sea el nuestro, y también la trampa: pedir aceleración
   sin querer deja el dron sin lazo de posición.
3. **PX4 no satura el setpoint de aceleración.** `MPC_ACC_*` no lo acota
   (issues 18033 y 18855). El valor va en **m/s² en NED**, no normalizado, y el
   FC lo obedece tal cual. El recorte tiene que estar del lado del companion.

## 3. Visión externa (EV)

- **`EV_MAX_INTERVAL = 200 ms`** (`ev_control.cpp:56`). Si dos muestras de EV se
  separan más, **el EKF deja de fusionar**. Por eso el puente publica a 20 Hz
  pase lo que pase, y no solo cuando el SLAM da una pose nueva: la pose se
  reenvía con su antigüedad metida en la varianza.
- **Las varianzas enviadas solo se usan si las tres son finitas** y
  `EKF2_EV_NOISE_MD = 0` (`EKF2.cpp:2106` y `2141`). Si una es `NaN` o infinita,
  el EKF descarta las tres y usa sus parámetros `EKF2_EVP_NOISE`/`EVV_NOISE`. De
  ahí que z, roll y pitch se manden con un valor **grande pero finito** (1e4) en
  vez de infinito: "no te creas esto" se dice con un número, no con un `NaN`.
- **Con `pose_frame = FRD`, `yaw_align` queda `false` por diseño** y
  `heading_good_for_control` nunca llega a ser `true`. Hay que publicar en
  **NED**. Esto costó una sesión entera.

## 4. Altura y rango

- **Histéresis del modo condicional** (`range_height_control.cpp:220`): la ayuda
  de rango **engancha por debajo de 0.7 × `EKF2_RNG_A_HMAX`** y se mantiene hasta
  `HMAX`. Con `HMAX = 1.0` engancha por debajo de 0.70 m. Un vuelo que nunca baje
  de ese umbral **no recibe ayuda de rango aunque esté dentro de `HMAX`**.
- **`EKF2_MIN_RNG` es el suelo del HAGL** (`terrain_estimator.cpp:78`) y de la
  medida de rango (`range_height_control.cpp:101`). Con un valor menor que la
  lectura real del dron apoyado, el EKF cree estar por debajo del suelo al
  despegar.
- **`EKF2_HGT_REF = 2` (rango como referencia) es peligroso con un sensor que
  satura**: si la lectura deja de crecer, el EKF interpreta que el dron baja y
  sube más. Es el mecanismo del escape vertical a ~25 m del 2026-09-11.

## 5. Lo que el firmware de fábrica NO expone

- **No publica `estimator_status_flags` por DDS.** La lista de topics DDS se
  compila en el firmware y no lo incluye. Por eso la salud del estimador se mira
  en `vehicle_local_position`: `xy_valid`, `z_valid`,
  `heading_good_for_control`, `!dead_reckoning` y `eph`.
- **No exporta flujo óptico ni rango por DDS.** Para evaluarlos hay que ir por
  MAVLink ([`CONEXION_MAVLINK_SCRIPTS.md`](CONEXION_MAVLINK_SCRIPTS.md)).
- **`dist_bottom_valid` solo es `true` en vuelo.** En tierra es `false` y **no es
  un fallo**.
- **No trae el driver `qmc5883p`** ni hay magnetómetro conectado: el heading sale
  del SLAM 2D por EV.
- **`MAV_1_CONFIG = 104` no existe** en este firmware; el MTF-01P se arranca con
  `mavlink start -d /dev/ttyS7` desde el `extras.txt` de la SD.

## 6. Drivers de rango que SÍ están compilados

Consultado con `help` en la consola nsh:

```
lightware_laser_i2c · lightware_laser_serial · ll40ls · ll40ls_pwm
tfmini · tf02pro · cm8jl65 · leddar_one · teraranger
vl53l0x · vl53l1x · mb12xx · srf02 · ulanding_radar
```

El conector **GPS1 expone I2C** (SDA/SCL/5V/GND), así que **un telémetro I2C
entra sin recompilar el firmware**, arrancándolo desde `extras.txt`. Importa
porque el LiDAR 1D actual satura a 2.53 m sobre hormigón oscuro
([reporte](../reports/2026-10-16_lidar1d-saturacion-reflectividad.md)). Al añadir
un segundo telémetro habrá **dos fuentes de rango** y hay que comprobar cuál
elige el EKF2.

## 7. Firmware: lo que no se puede recuperar

**El `.px4` no se puede leer del board.** El bootloader rev 5 no implementa
`READ_MULTI`. Si no se guardó el `.px4` al compilar, ese binario se ha perdido.
Ver [`backups/firmware/INDEX.md`](../backups/firmware/INDEX.md).
