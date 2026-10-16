# El software de la Raspberry Pi: qué corre, qué protege y por qué

Mapa del repo [`px4_drone`](https://github.com/Kmedrano101/px4_drone), que vive en
la Pi 4 en `~/drone_ws/src/px4_drone`. Cada pieza existe por un incidente
concreto: esta página enlaza una con otro, porque un guard sin su historia se
acaba quitando "porque molesta".

---

## 1. La cadena de datos

```
LD19 (LiDAR 2D, arriba)  ──►  slam_toolbox  ──►  /pose  ──┐
                         └──►  /scan  ──► parada por obstáculo
                                                          ▼
                                            ev_odometry_bridge  (20 Hz)
                                                          │
                                   VehicleOdometry (EV, NED) por uXRCE-DDS
                                                          ▼
                                                    EKF2 del FC
MTF-01P (flujo + LiDAR 1D)  ──MAVLink TEL4──►  FC  ◄──────┘   altura: baro + rango
```

- **x, y y yaw** vienen del SLAM 2D por visión externa. **No hay magnetómetro.**
- **La altura NO viene del LiDAR 2D**: barre un plano horizontal y no ve el
  suelo. Viene de barómetro + LiDAR 1D en su zona honesta (≤1 m).
- **La altura tampoco puede venir de la IMU sola**: hace falta doble integración.
  La deriva de 3 mm/s medida con el barómetro plano *es* esa fusión derivando
  ([reporte](../reports/2026-10-16_baro-temperatura-deriva-z.md)).

## 2. Los nodos de vuelo

Todos comparten la misma clase base, `TakeoffPositionHoldBase`, y por tanto la
misma máquina de estados, las mismas guardas y los mismos logs.

| Nodo | Qué hace | Controlador |
|---|---|---|
| `takeoff_position_hold_ev` | arm → takeoff → hold → land → disarm | setpoint de **posición** → cascada P/PID de PX4 |
| `cross_pattern_ev` | lo anterior + patrón en cruz | posición |
| `takeoff_hold_land_mpc` | el ciclo completo con descenso controlado | setpoint de **aceleración** → MPC propio ([doc](MPC_CICLO_COMPLETO.md)) |

`takeoff_hold_land_mpc` **hereda** de `takeoff_position_hold_ev` y solo
sobreescribe cómo se genera el setpoint. Eso es lo que hace que comparar PID y
MPC signifique algo ([protocolo](2026-10-16_protocolo_pid_vs_mpc.md)).

Estados: `kWaitPosition → kWaitSwitch → kArm → kTakeoff → kHold [→ kPattern]
→ kControlledDescent → kLand → kDisarm`, con `kObstacleStop` como desvío desde
cualquier estado de vuelo. `kControlledDescent` solo lo usa el MPC: baja con su
propio perfil hasta 0.25 m y **entrega a `NAV_LAND`**, que detecta el contacto y
desarma — el toque de suelo se le deja a PX4 porque su detector usa información
que el MPC no tiene.

## 3. Las guardas, y el incidente que las pagó

| Guarda | Qué hace | De dónde viene |
|---|---|---|
| **Parada por obstáculo** (`obstacle_guard`) | 36 sectores sobre `/scan` **crudo**; umbral `X + v·0.35 + v²/(2·2)`; no arma si hay algo a menos de 1.0 m, en vuelo frena 2 s y aterriza | Log 158: el SLAM dijo que el dron estaba quieto mientras recorría ~3 m; **lo único que vio el obstáculo acercarse fue `/scan`** |
| **Varianza honesta del EV** | `var = cov(/pose) + (antigüedad · 1.5)²`; z/roll/pitch con 1e4 **finito** | El mismo vuelo: el puente **ocultaba** la covarianza del SLAM y el EKF se creía una pose perdida |
| **Salud del SLAM** | aterriza si σ > 0.3 m o si `/pose` falta 2.5 s | ídem |
| **Techo de altura** | el nodo **se niega a arrancar** por encima de 1.0 m | El LiDAR 1D satura: por encima no hay referencia de altura |
| **Rechazo del suelo** | descarta los rayos que medirían el suelo con el dron inclinado | Falsos positivos del guard al inclinarse |
| **`/scan` inservible** | sin `/scan`, con más de 0.5 s de antigüedad o con <10 % de rayos válidos: no arma, y en vuelo para | *Sin LiDAR no se puede garantizar la distancia* |
| **Escape por RC** | ch6/ch8 | Los sticks **no** sacan de Offboard (`COM_RC_OVERRIDE`) |

⚠️ La parada por obstáculo **se puede desactivar** poniendo 0 en la webui. Antes
de cada prueba hay que leer en el log `Parada por obstaculo ACTIVA`.

⚠️ El rechazo del suelo saca la altura del plano del láser de
`dist_bottom + 0.134 m`, o sea **del LiDAR 1D que satura**. Subestimar la altura
hace que descarte como suelo rayos que no lo son. A 0.8 m el efecto es de ~3 %;
a 1.66 m habría sido del 24 %.

## 4. La webui (puerto 5000)

Lanza cada prueba con su rosbag, su log y su monitor de carga, y **no ofrece una
tarjeta cuyo launch o ejecutable no esté instalado** — eso nació de un error real
al lanzar una prueba en medio de una compilación.

- **HOLD y ATERRIZAR**: `SIGUSR1`/`SIGUSR2` **al ejecutable del nodo**, nunca al
  envoltorio `ros2 launch`. Mandarla a `timeout` dejó una vez **el nodo volando
  solo**: la señal mató al envoltorio y el nodo siguió publicando setpoints.
- **sysmon**: con cada prueba deja `<run>_sysmon.csv` (CPU por núcleo,
  temperatura, throttling, RAM, procesos y tasas de `/scan` y `/pose`) y un
  resumen al final del log. Una prueba sin esto no se puede defender: no se sabe
  si la Pi iba al límite.

## 5. Compilar

```bash
cd ~/drone_ws/src/px4_drone
./scripts/mpc/build_on_this_machine.sh     # genera el solver MPC y compila
```

El C de acados **no se versiona**: desktop v0.5.3, Pi v0.6.0, y el código
generado no es compatible entre versiones. El script lleva
`--cmake-force-configure`, sin el cual CMake no detecta el solver recién
generado y **deja el nodo MPC fuera en silencio**. Detalle en
[`MPC_CICLO_COMPLETO.md`](MPC_CICLO_COMPLETO.md) §8.

Las constantes de seguridad (el techo de 1.0 m, por ejemplo) son `constexpr`:
**cambiarlas exige recompilar**, no basta con tocar el launch.

## 6. Herramientas MAVLink en la Pi

En `~/mavlink_tools/`, con `pymavlink` en el venv `~/.venvs/mav`. Hacen falta
porque el firmware de fábrica **no exporta flujo ni rango por DDS**, y porque el
FC está conectado por USB a la Pi (`/dev/ttyACM0`).

```bash
FC_DEV=/dev/ttyACM0 ~/.venvs/mav/bin/python ~/mavlink_tools/dump_params.py out.params
```

| Script | Para qué |
|---|---|
| `fc.py` | conexión común; el USB del PX4 **solo responde si le hablas** (heartbeats para despertar `ttyACM0`) |
| `shell.py` | consola nsh por `SERIAL_CONTROL` dev 10 |
| `logs.py` | lista y baja los `.ulg` de la MicroSD |
| `dump_params.py` / `set_params.py` | volcado completo y escritura verificada |
| `monitor_sensors.py` | flujo y rango en vivo a CSV; es con el que se midió la saturación |

⚠️ **Nunca `pkill -f <patrón>`** en la Pi: coincide con la propia sesión SSH y la
mata (pasó tres veces). Usar `pkill -x <comm>`.

## 7. Reglas de datos

- **Ningún log de más de 5 MB al repo** — `.ulg`, rosbags y cualquier dato crudo.
- Los comentarios de `.gitignore`, siempre en su propia línea.
