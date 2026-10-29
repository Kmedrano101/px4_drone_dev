# Protocolo: comparación PID vs MPC en takeoff – hold – land

**Actualización 2026-10-20:** en la Pi, los launches de ciclo PID y MPC usan
`slam_health_enabled=false`: la sigma y la antigüedad de `/pose` no bloquean ni
abortan estas pruebas; siguen las comprobaciones de posición del FC. La zona
ciega es un círculo de **0.70 m de diámetro** centrado en el LiDAR
(`obstacle_blind_radius_m=0.35`), en los 360°, el debounce sube a
**3 barridos** (`obstacle_debounce_scans=3`) y se añade un **ancho mínimo de
obstáculo** de 0.15 m (`obstacle_min_width_m`), que es el filtro que de verdad
separa polvo de obstáculo: con la zona ciega sola el PID habría vuelto a abortar. Los dos abortos del 16-oct eran **falsos positivos**
del LiDAR 2D con las hélices girando, no obstáculos
([análisis](../../reports/2026-10-20_falsos-obstaculos-al-despegar.md)). Por indicación posterior del
usuario, la guarda de obstáculos actúa **desde TAKEOFF**, con chequeo de espacio
libre y barrido utilizable antes de armar. Esta configuración sustituye las descripciones de esas guardas
en las secciones históricas siguientes. Ver el
[reporte de revisión](../../reports/2026-10-20_zona-ciega-circular-ciclos.md).

Plan de la primera prueba de vuelo con el MPC y de su línea base con el PID.
Se escribe **antes** de volar para que las dos pruebas sean comparables y para
que los números salgan listos para el paper.

**Estado:** 🔄 prueba de seguridad ejecutada el 2026-10-16; comparación pendiente.
PID y MPC alcanzaron OFFBOARD y armaron a 0.8 m, pero PID aterrizó por salud del
SLAM y MPC por la parada de obstáculo. **El aborto por obstáculo era falso** y está
corregido y validado contra los bags; queda por explicar el `sigma_xy = 0.311 m` del SLAM. Los intentos a 1.2 m fueron rechazados antes
de armar por el techo fiable del LiDAR 1D. No hubo hold de 30 s ni una pareja
comparable; ver el [reporte](../../reports/2026-10-19_pid-mpc-pruebas-guardas-rpi.md).

---

## 1. Qué se quiere demostrar

Que con **misma misión, mismas guardas y mismos logs**, cambiar el controlador
exterior (cascada P/PID de PX4 ↔ MPC con límite de jerk en la Pi) mejora de
forma medible el perfil del ciclo takeoff–hold–land, y que el MPC **cabe en una
Raspberry Pi 4** en tiempo real.

Es comparable porque `takeoff_hold_land_mpc` hereda de
`takeoff_position_hold_ev`: lo único distinto es cómo se genera el setpoint.
Ver [`MPC_CICLO_COMPLETO.md`](../referencia/MPC_CICLO_COMPLETO.md) §4.

## 2. Por qué 0.8 m y no 1.5 m

Tres límites independientes coinciden en la misma respuesta:

1. **El LiDAR 1D se satura sobre el hormigón oscuro.** A 0.8 m el error es de
   ~3 cm; a 1.5 m es del 17 %. Ver
   [`reports/2026-10-16_lidar1d-saturacion-reflectividad.md`](../../reports/2026-10-16_lidar1d-saturacion-reflectividad.md).
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
| 5 | `git pull` + `./scripts/mpc/build_on_this_machine.sh` en la Pi | ✅ 2026-10-16, `FIN_RC=0` sin errores; los dos binarios recompilados **después** del cambio de cabecera (`takeoff_position_hold_ev` 11:09, `takeoff_hold_land_mpc` 12:51), y la webui reiniciada |
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

**El switch del RC manda.** El nodo no fuerza OFFBOARD: espera a que el switch
del piloto esté ahí, y desde `px4_drone@f5e1ab2` lo revisa **cada ciclo hasta que
sale el ARM** (antes solo una vez, y en los hasta 13 s siguientes el dron armaba
aunque el piloto hubiese movido el switch). Si el switch se mueve en vuelo, el
nodo deja de publicar y no le pisa el control. Detalle en
[`SOFTWARE_ROS2_PX4_DRONE.md`](../referencia/SOFTWARE_ROS2_PX4_DRONE.md) §3.

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

## 8. Pendiente acordado: separar trayectoria y controlador (2026-10-19)

**Objetivo de producto:** conseguir vuelo suave, estable y repetible. La
comparación sirve al ajuste del dron. Ver el [plan de tuning por capas y fases](2026-10-19_plan_tuning_takeoff_hold_land.md)
para prerrequisitos, medidas y objetivos candidatos.

**Actualización 2026-10-20:** la variante **C** tiene ahora tres formas, todas instaladas en la
Pi: **C0** MPC cinemático (como estaba), **C1** MPC+ con estado de perturbación y compensación
de retardo (mismo binario, `mpc_dist_gain=0.5`), y **C2** MPC moderno CTBR (tasas + empuje,
engancha solo en el hold). Ver [MPC del ciclo completo §9](../referencia/MPC_CICLO_COMPLETO.md#9-las-tres-variantes-de-mpc-2026-10-20).
Orden de vuelo propuesto: A → C0 → C1 (son el mismo riesgo) → calibrar el empuje → C2.

**Estado: pendiente de implementar/verificar las referencias y ejecutar las pruebas.**
La comparación debe distinguir cuánto aporta suavizar la trayectoria y cuánto
aporta cambiar el controlador exterior. No se presupone una ventaja del MPC.

- [ ] Resolver las condiciones que interrumpieron las pruebas del 2026-10-16:
  SLAM estable e inspección del retorno trasero del LiDAR. Mantener las guardas
  activas; las corridas abortadas se registran, pero no sustituyen una pareja
  completa y comparable.
- [ ] Preparar tres variantes: **A**, línea base actual P/PID de PX4 con
  consignas de posición; **B**, la misma cascada con una referencia suave de
  posición, velocidad y aceleración, usando estas dos últimas como feedforward;
  **C**, MPC exterior en la Pi con consignas de aceleración, conservando la
  estabilización de actitud y tasas de PX4.
- [ ] Verificar en PX4 1.14.3 y en los mensajes publicados que B mantiene
  activo el control de posición y que C desactiva los lazos de posición y
  velocidad (campos correspondientes en `NaN` y modo Offboard de aceleración).
  La variante B es una propuesta pendiente, no una capacidad ya comprobada.
- [ ] Comparar **A frente a B** para medir el efecto de la trayectoria suave;
  comparar **B frente a C** con la misma referencia temporal y límites
  nominales de velocidad, aceleración y jerk para evaluar el cambio de
  controlador. Registrar los límites que realmente aplica cada variante;
  las saturaciones de PX4 y las restricciones del MPC no son equivalentes.
- [ ] Mantener misión, estimador, ganancias internas de PX4, guardas, lugar,
  altura de 0.8 m, hold de 30 s y registro iguales. Anotar batería, carga útil,
  condiciones y versiones/configuración de cada corrida. Alternar el orden
  B/C una vez validada la línea base para reducir el sesgo de batería u orden.
- [ ] Obtener al menos tres corridas completas por variante. Separar las
  ventanas de despegue, hold y descenso, y documentar cuándo se entrega el
  control a `NAV_LAND` para no atribuir al controlador externo su fase final.
- [ ] Medir error RMS y máximo de posición/altura, sobrepasamiento, tiempo de
  asentamiento, deriva y variabilidad durante hold; aceleración y jerk
  comandados y, cuando sea posible, respuesta medida con el mismo filtrado.
  Distinguir suavidad de la consigna y suavidad del movimiento real.
- [ ] Registrar tiempo de solver medio, p95 y máximo, fallos del solver,
  periodo efectivo del lazo, incumplimientos del plazo y edad de la odometría
  y las consignas. Añadir CPU por núcleo, RAM, temperatura y throttling bajo
  carga real con SLAM, DDS y grabación activos. El tiempo del solver aislado
  no demuestra que todo el lazo cumpla el plazo de 50 ms a 20 Hz.
- [ ] Presentar resultados por corrida y su dispersión, incluidos abortos;
  concluir mejora solo si supera la variabilidad observada. Si B iguala a C,
  dejar registrado que no hay ventaja demostrada del MPC en esta misión.

El MPC actual usa un triple integrador con jerk como entrada: la prueba evalúa
ese controlador exterior, no un NMPC con la dinámica completa del multirrotor.
Las pruebas del 2026-10-16 todavía no permiten comparar rendimiento (§1 y reporte).

## 9. Después de los vuelos

Reporte en `reports/2026-MM-DD_comparacion-pid-mpc.md` con las tablas de §7, y
actualizar el hito del README.
