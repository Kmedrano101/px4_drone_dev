# Protocolo: comparación PID vs MPC en takeoff – hold – land

Plan de la primera prueba de vuelo con el MPC y de su línea base con el PID.
Se escribe **antes** de volar para que las dos pruebas sean comparables y para
que los números salgan listos para el paper.

**Estado:** ⏳ **no ejecutado**. Confirmado el 2026-10-16 contra la Pi: no se ha
hecho ninguna prueba de takeoff–hold–land, ni con PID ni con MPC. Los logs más
recientes de `tools/webui/logs/` son de `sensor_eval` del 14 de octubre a las
14:41, y los dos únicos `mpc_cycle` son los intentos del día 14 que abortaron
antes de pedir armado ([reporte](../reports/2026-10-14_mpc-compilado-rpi.md)).
Este documento es el plan, no un resultado.

---

## 1. Qué se quiere demostrar

Que con **misma misión, mismas guardas y mismos logs**, cambiar el controlador
exterior (cascada P/PID de PX4 ↔ MPC con límite de jerk en la Pi) mejora de
forma medible el perfil del ciclo takeoff–hold–land, y que el MPC **cabe en una
Raspberry Pi 4** en tiempo real.

Es comparable porque `takeoff_hold_land_mpc` hereda de
`takeoff_position_hold_ev`: lo único distinto es cómo se genera el setpoint.
Ver [`MPC_CICLO_COMPLETO.md`](MPC_CICLO_COMPLETO.md) §4.

## 2. Por qué 0.8 m y no 1.5 m

Tres límites independientes coinciden en la misma respuesta:

1. **El LiDAR 1D se satura sobre el hormigón oscuro.** A 0.8 m el error es de
   ~3 cm; a 1.5 m es del 17 %. Ver
   [`reports/2026-10-16_lidar1d-saturacion-reflectividad.md`](../reports/2026-10-16_lidar1d-saturacion-reflectividad.md).
2. **La ayuda de rango del EKF2 solo debe entrar donde el sensor es honesto.**
   Con `EKF2_RNG_A_HMAX = 1.0` engancha por debajo de 0.70 m (histéresis 0.7×) y
   se mantiene hasta 1.0 m: subiendo a 0.8 m se pasa por la zona de enganche, así
   que la ayuda entra y se queda.
3. **El SLAM 2D prefiere altura constante.** El LD19 barre un plano horizontal:
   cambiar de altura mueve el corte del entorno y empeora el *scan matching*. La
   altura estable no es solo el objetivo del control, es un requisito del
   estimador que le da x, y y yaw.

**La altura no puede venir del LiDAR 2D ni de la IMU.** El LiDAR 2D no ve el
suelo. Y la IMU sola necesita doble integración: la deriva de 3 mm/s que se midió
con el barómetro plano (11 cm en 32 s, dron quieto en el suelo) *es* esa fusión
IMU+baro derivando. La altura sigue siendo barómetro + LiDAR 1D en su zona buena.

## 3. Precondiciones (antes de salir al parking)

| # | Qué | Estado |
|---|---|---|
| 1 | **Prueba de la pared** del LiDAR 1D, para cerrar el diagnóstico de reflectividad | ⏳ |
| 2 | `EKF2_RNG_A_HMAX` 1.5 → **1.0** en el FC | ✅ 2026-10-16, verificado en un volcado completo (908/908) |
| 3 | Techo de altura de los nodos `kMaxHeightM` 1.2 → **1.0** | ✅ `px4_drone@54ade05`; las tres tarjetas de vuelo de la webui pasan a 0.8 m por defecto y 1.0 m de máximo |
| 4 | Traer al repo los dos arreglos de acados v0.6.0 que viven solo en la Pi | ✅ `px4_drone@9f1b9a3` (2026-10-16), sin push todavía |
| 5 | `git pull` + `./scripts/mpc/build_on_this_machine.sh` en la Pi (~6 min) | ⏳ **obligatorio ahora**: el techo de 1.0 m es una constante de compilación |
| 6 | Cliente DDS del FC arrancando **solo**, sin tener que lanzarlo desde QGC | ⏳ |
| 7 | `EKF2_EV_CTRL = 9` en el FC | ✅ |
| 8 | Baro: SPL06 a 79 °C con motores parados (IMUs a 64–66 °C). Vigilar, no bloquea | ⚠️ |

**Sitio:** en el intento del 2026-10-14 el LiDAR 2D vio un obstáculo a
0.50–0.53 m, por debajo del mínimo de 1.0 m, y eso **por sí solo impide armar**.
Colocar el dron con ≥1.5 m libres en los 360°, no junto a una pared o una columna.

## 4. Perfil de vuelo (idéntico en las dos corridas)

```
takeoff_height_m         = 0.8
hold_seconds             = 30
obstacle_stop_distance_m = 1.0
mpc_descent_agl_m        = 0.25    (solo MPC; luego entrega a NAV_LAND)
```

Las dos corridas se lanzan desde la **webui de la Pi (puerto 5000)**, que es la
que deja rosbag, log y `sysmon.csv` con cada prueba. Lanzarlas a mano por
`ros2 launch` vuela igual pero **no recoge nada**, así que no sirve para comparar.

| | Corrida A — **PID** (línea base) | Corrida B — **MPC** |
|---|---|---|
| Tarjeta de la webui | **Ciclo completo con PID (takeoff-hold-land)** | **Ciclo completo con MPC (takeoff-hold-land)** |
| `launch_file` | `takeoff_position_hold_ev.launch.py` | `takeoff_hold_land_mpc.launch.py` |
| Ejecutable (el que recibe HOLD/ATERRIZAR) | `takeoff_position_hold_ev` | `takeoff_hold_land_mpc` |
| Controlador | cascada P/PID de PX4, setpoints de **posición** | MPC en la Pi, setpoints de **aceleración** |

**Primero la A.** Es la línea base: si falla, no se vuela el MPC, porque el
problema no estaría en el controlador. Luego la B, mismo perfil, mismo sitio, y
misma batería si da (o anotar el voltaje de inicio de cada una).

Las dos tarjetas comparten ya los mismos valores por defecto —0.8 m de altura,
30 s de hold, parada por obstáculo a 1.0 m— precisamente para que lanzarlas "con
lo que viene puesto" produzca dos corridas comparables (`px4_drone@66d78be`; antes
una tenía 5 s de hold y la otra 10 s). Lo único que debe cambiar entre A y B es
el controlador.

Equivalente por consola, si alguna vez hace falta sin la webui:

```bash
ros2 launch px4_drone takeoff_position_hold_ev.launch.py \
  confirm_takeoff:=true takeoff_height_m:=0.8 hold_seconds:=30 \
  obstacle_stop_distance_m:=1.0
```

Repetir cada corrida **3 veces** si el tiempo y la batería lo permiten: con una
sola no se distingue una mejora de la variabilidad entre vuelos.

**Seguridad:** el armado lo lanza siempre Kevin, nunca el asistente. Escape de
Offboard por **ch6/ch8** del RC (los sticks no sacan de Offboard:
`COM_RC_OVERRIDE`). HOLD y ATERRIZAR disponibles en la webui.

## 5. Protección anticolisión con el LiDAR 2D — verificado el 2026-10-16

Se revisó el código en la Pi, no la documentación. Resultado: **la protección
está activa por defecto en las dos corridas y es la misma en las dos**, pero
*se puede desactivar a mano desde la webui*, así que hay que mirarla antes de
cada vuelo.

| Qué | Resultado |
|---|---|
| Valor por defecto en el launch del PID y del MPC | **1.0 m**, idéntico (`obstacle_stop_distance_m`) |
| Valor por defecto en las tres tarjetas de vuelo de la webui | **1.0 m** (`ev_takeoff`, `cross_pattern`, `mpc_cycle`) |
| ¿El nodo MPC la hereda sin cambios? | **Sí.** `takeoff_hold_land_mpc` solo sobreescribe la generación del setpoint; `obstacleClearForTakeoff()` y `obstacleTooClose()` vienen de la base sin tocar |
| ¿Se puede desactivar? | **Sí: con 0 en la webui** (el campo admite 0–3 m). El nodo lo avisa con `PARADA POR OBSTACULO DESACTIVADA` en el log |
| Valores intermedios inválidos | Rechazados: debe ser 0 o ≥0.3 m, o el nodo **se niega a arrancar** |

Y falla hacia el lado seguro, que es lo que importa:

- **No ha llegado ningún `/scan`** → no arma; en vuelo, para.
- **`/scan` lleva más de 0.5 s sin publicar** (`obstacle_scan_timeout_s`) → no
  arma; en vuelo, para. *"Sin LiDAR no se puede garantizar la distancia."*
- **Menos del 10 % de rayos válidos** (sensor tapado o roto) → no arma; en vuelo,
  para.
- **Obstáculo más cerca de 1.0 m antes de armar** → no arma, e indica distancia y
  rumbo. Esto es lo que bloqueó el intento del 2026-10-14 (algo a 0.50–0.53 m).
- **En vuelo**: umbral dinámico `1.0 + v·0.35 + v²/(2·2)` por sector (36 sectores
  de 10°), con 3 rayos mínimos y 2 barridos de *debounce*; al disparar frena
  2 s (`obstacle_brake_seconds`) y después pide LAND. En el MPC la frenada la
  resuelve el propio solver con su límite de jerk, no es un corte en seco.

Usa **`/scan` crudo, nunca el SLAM ni la posición del EKF**, por el log 158: el
SLAM dijo que el dron estaba quieto mientras recorría ~3 m y el EKF se lo creyó;
lo único que vio el obstáculo acercarse fue `/scan`.

⚠️ **Interacción con la saturación del LiDAR 1D, a vigilar.** El rechazo del
suelo necesita saber a qué altura está el plano del láser, y lo calcula como
`dist_bottom + 0.134 m` — o sea, **a partir del LiDAR 1D que satura**. Si la
altura se subestima, la distancia al suelo también, y el guard descarta como
"suelo" rayos que están más cerca de lo que debería: la detección se debilita.
A 0.8 m el error del LiDAR 1D es de ~3 cm y el efecto es despreciable; a 1.66 m
habría sido del 24 %. Es otra razón para volar en la zona buena del sensor, y
otra cosa que se arreglaría sola compensando la curva.

**Comprobación antes de cada corrida:** que el log del nodo diga
`Parada por obstaculo ACTIVA: ... 1.00 m`. Si dice `DESACTIVADA`, el vuelo no
cuenta para la comparación.

## 6. Qué se recoge en cada corrida

| Dato | De dónde |
|---|---|
| `.ulg` del FC | MicroSD, por USB con `scripts/mavlink/logs.py` (≤5 MB al repo) |
| rosbag | lo lanza la webui con la prueba |
| `<run>_sysmon.csv` | CPU por núcleo, temperatura, throttling, RAM, tasas `/scan` y `/pose` |
| `mpc_status` | dentro del rosbag (solo corrida B) |
| Voltaje de batería al inicio y al final | anotar a mano |
| Altura real del hover con el láser, si se puede | verdad independiente del LiDAR |

## 7. Métricas de la comparación

Sobre el tramo de hold, y con la altura **corregida por la curva de saturación**
(a 0.8 m la corrección es de ~3 cm, pero hay que aplicarla a las dos igual):

- **Altura:** error RMS y error máximo respecto a 0.8 m.
- **Despegue:** sobrepasamiento (%), tiempo de asentamiento al ±5 %, y
  aceleración y jerk máximos comandados.
- **Hold:** deriva en xy, error RMS en xy, desviación típica de la altura.
- **Aterrizaje:** velocidad de contacto, y si hubo rebote.
- **Suavidad:** espectro de la aceleración comandada y de la salida de motores —
  es el argumento central a favor del límite de jerk.
- **Cómputo:** tiempo de solver medio y máximo, y carga de la Pi durante el vuelo.
- **Estimador, igual en las dos:** `eph`, σ del SLAM, tasa de `/pose`,
  `dist_bottom_valid`, y si hubo cambio de instancia del EKF.

Un resultado negativo también vale y se publica igual: si el PID iguala al MPC a
0.8 m con 30 s de hold, lo honesto es decir que a esta escala la ganancia no
aparece, y buscarla donde el límite de jerk importe (trayectorias más agresivas,
el patrón en cruz, vuelo cerca de obstáculos).

## 8. Después de los vuelos

Reporte en `reports/2026-MM-DD_comparacion-pid-mpc.md` con las tablas de §7, y
actualizar el hito del README.
