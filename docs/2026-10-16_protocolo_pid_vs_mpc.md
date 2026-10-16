# Protocolo: comparación PID vs MPC en takeoff – hold – land

Plan de la primera prueba de vuelo con el MPC y de su línea base con el PID.
Se escribe **antes** de volar para que las dos pruebas sean comparables y para
que los números salgan listos para el paper.

**Estado:** ⏳ no ejecutado. El dron no se ha armado con el MPC.

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
| 2 | `EKF2_RNG_A_HMAX` 1.5 → **1.0** por USB (`set_params.py`), verificado y guardado | ⏳ |
| 3 | Techo de altura de los nodos `kMaxHeightM` 1.2 → **1.0** | ⏳ |
| 4 | Traer al repo los dos arreglos de acados v0.6.0 que viven solo en la Pi | ⏳ |
| 5 | `git pull` + `./scripts/mpc/build_on_this_machine.sh` en la Pi (~6 min) | ⏳ |
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

Orden de las corridas:

1. **Corrida A — PID** (`takeoff_position_hold_ev`): es la línea base. Si falla,
   no se vuela el MPC: el problema no sería del controlador.
2. **Corrida B — MPC** (`takeoff_hold_land_mpc`), mismo perfil, mismo sitio,
   misma batería si da (o anotar el voltaje de inicio de cada una).

Repetir cada corrida **3 veces** si el tiempo y la batería lo permiten: con una
sola no se distingue una mejora de la variabilidad entre vuelos.

**Seguridad:** el armado lo lanza siempre Kevin, nunca el asistente. Escape de
Offboard por **ch6/ch8** del RC (los sticks no sacan de Offboard:
`COM_RC_OVERRIDE`). HOLD y ATERRIZAR disponibles en la webui.

## 5. Qué se recoge en cada corrida

| Dato | De dónde |
|---|---|
| `.ulg` del FC | MicroSD, por USB con `scripts/mavlink/logs.py` (≤5 MB al repo) |
| rosbag | lo lanza la webui con la prueba |
| `<run>_sysmon.csv` | CPU por núcleo, temperatura, throttling, RAM, tasas `/scan` y `/pose` |
| `mpc_status` | dentro del rosbag (solo corrida B) |
| Voltaje de batería al inicio y al final | anotar a mano |
| Altura real del hover con el láser, si se puede | verdad independiente del LiDAR |

## 6. Métricas de la comparación

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

## 7. Después de los vuelos

Reporte en `reports/2026-MM-DD_comparacion-pid-mpc.md` con las tablas de §6, y
actualizar el hito del README.
