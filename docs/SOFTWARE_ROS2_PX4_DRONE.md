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
| **Entrada solo por RC** | el nodo **nunca fuerza OFFBOARD**: espera a que el switch del piloto esté en OFFBOARD (`nav_state_user_intention`) y lo revisa **cada ciclo hasta que sale el ARM**; si no, aborta sin armar | El modo lo decide el piloto, no el companion |
| **Salida simétrica en vuelo** | cada ciclo comprueba `nav_state`, failsafe y armado; si el control ya no es nuestro, **deja de publicar** y no toca `NAV_LAND` ni `ARM` | Vuelo 2 (2026-09-11): un LAND de la Pi **pisó al piloto** |
| **Escape por RC** | ch6/ch8 | Los sticks **no** sacan de Offboard (`COM_RC_OVERRIDE`) |

⚠️ La parada por obstáculo **se puede desactivar** poniendo 0 en la webui. Antes
de cada prueba hay que leer en el log `Parada por obstaculo ACTIVA`.

### La puerta del switch del RC, en detalle

Es la guarda más crítica, así que conviene tenerla clara:

| Momento | Qué se exige |
|---|---|
| Antes de pedir OFFBOARD | `nav_state_user_intention == OFFBOARD`, o sea el switch del piloto ya puesto. Timeout de **10 s** y aborta sin tocar OFFBOARD ni ARM |
| Entre esa confirmación y el ARM | **Se vuelve a comprobar cada ciclo** (`px4_drone@f5e1ab2`). Antes solo se miraba una vez, y en los **hasta 13 s** que pasan —10 esperando la confirmación del FC más 3 de `kArmDelayCycles`— el piloto podía mover el switch y el dron armaba igual, porque `offboard_confirmed_` es un pestillo que no se suelta |
| Después de enviar el ARM | Lo cubre el chequeo de vuelo desde `kTakeoff`: deja de publicar sin quitarle el control al piloto |
| En vuelo, cada ciclo | `nav_state` sigue en OFFBOARD, sin failsafe y armado |

Que `nav_state_user_intention` **funciona en el 1.14.3 de fábrica** no es una
suposición: lo demuestra la prueba de armado en tierra del 2026-09-17, que pasó
esta puerta. Si el firmware no rellenara el campo, el nodo abortaría siempre a
los 10 s.

⚠️ El rechazo del suelo saca la altura del plano del láser de
`dist_bottom + 0.134 m`, o sea **del LiDAR 1D que satura**. Subestimar la altura
hace que descarte como suelo rayos que no lo son. A 0.8 m el efecto es de ~3 %;
a 1.66 m habría sido del 24 %.

## 4. La webui (puerto 5000)

Lanza cada prueba con su rosbag, su log y su monitor de carga, y **no ofrece una
tarjeta cuyo launch o ejecutable no esté instalado** — eso nació de un error real
al lanzar una prueba en medio de una compilación.

- **Cada prueba es un panel desplegable** (`<details>` nativo) y solo hay **uno
  abierto a la vez**: nueve tarjetas abiertas no caben en un móvil con una mano,
  y bajar hasta la de abajo pasaba el dedo por encima del *Lanzar* de un despegue
  real. La cabecera del panel ya dice lo que hace falta saber sin abrirlo: el
  nombre, el distintivo **VUELO REAL** si esa prueba arma, y **no disponible** si
  falta su ejecutable. Recuerda cuál estaba abierto (`localStorage`), y la prueba
  en marcha se marca en amarillo y se abre una vez, al empezar.
- Las dos tarjetas de la comparación se llaman **"Ciclo completo con PID"** y
  **"Ciclo completo con MPC"**, con los mismos valores por defecto, para no
  confundir corridas ([protocolo](2026-10-16_protocolo_pid_vs_mpc.md) §4).

- **HOLD y ATERRIZAR**: `SIGUSR1`/`SIGUSR2` **al ejecutable del nodo**, nunca al
  envoltorio `ros2 launch`. Mandarla a `timeout` dejó una vez **el nodo volando
  solo**: la señal mató al envoltorio y el nodo siguió publicando setpoints.
- **Limpiar** (panel de logs): limpia **solo la pantalla**. No trunca nada: la
  página recuerda por qué línea iba y pide el log desde ahí, así que el archivo
  de la prueba queda entero — es el registro y es lo que se analiza después del
  vuelo. Al empezar otra prueba se vuelve a mostrar todo, porque el log es otro
  archivo.
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

⚠️ El workspace usa **`--symlink-install`**, así que lo que hay en
`install/px4_drone/lib/px4_drone/` son **enlaces simbólicos** a `build/`, creados
una sola vez. Su fecha es la del enlace, no la del binario: para saber si algo se
recompiló hay que mirar el destino (`stat -L`, o directamente `build/`). Mirar la
fecha del enlace hace creer que el binario es de hace un mes.

### Comprobar que una prueba arrancará, sin volar

El error *"`<launch>` was not found in the share directory"* salía al lanzar
durante una compilación: `install/.../share/px4_drone/launch/` se queda vacío
mientras colcon trabaja. La webui ya no ofrece una tarjeta en ese estado, pero
después de compilar conviene comprobarlo en un **entorno limpio**, igual que
quedaría tras reiniciar la Pi, con los mismos tres `source` que usa la webui:

```bash
env -i HOME=/home/kevin bash -c '
  source /opt/ros/jazzy/setup.bash
  source /home/kevin/evarobot_ws/install/setup.bash
  source /home/kevin/drone_ws/install/setup.bash
  ros2 launch px4_drone takeoff_hold_land_mpc.launch.py --show-args
  ldd /home/kevin/drone_ws/install/px4_drone/lib/px4_drone/takeoff_hold_land_mpc | grep "not found"
'
```

`--show-args` resuelve el launch y **no vuela nada**: si imprime los argumentos,
el launch está instalado. El `ldd` debe dar cero líneas: confirma que
`acados/lib` entra por el hook de entorno. Verificado así el 2026-10-16.

⚠️ La webui es un servicio systemd (`px4-webui`): las plantillas se releen en
cada petición, pero **`app.py` solo se lee al arrancar**. Tras cambiar las
tarjetas hay que reiniciar el servicio o los valores por defecto siguen siendo
los viejos aunque la página parezca nueva.

## 6. Ver el LiDAR 2D de la Pi en RViz (desktop)

El desktop y los procesos ROS lanzados por la webui de la Pi deben usar exactamente:

```bash
ROS_DOMAIN_ID=0            # = UXRCE_DDS_DOM_ID del FC. NO es una eleccion libre.
RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
```

⚠️ **El dominio lo fija el FC, no nosotros.** El cliente uXRCE-DDS del FC crea sus topics en
`UXRCE_DDS_DOM_ID` (hoy **0**). Un nodo de la Pi en otro dominio no ve `vehicle_status` ni la
posición, y sus setpoints no llegan: el ciclo se queda esperando para siempre. El 2026-10-19
se puso `10` en la webui para el RViz del escritorio sin tocar el FC, y el 20-oct en el campo
ningún ciclo pudo arrancar ([reporte](../reports/2026-10-21_cinco-corridas-sin-dds-eth0.md)).
En `tools/webui/app.py` es una sola constante, `ROS_DOMAIN_ID`. El apartado canónico, con todos los sitios que deben coincidir, la prueba de banco y el procedimiento de cambio, es [CONFIGURACION_OFFBOARD_RPI4.md §2bis](CONFIGURACION_OFFBOARD_RPI4.md#2bis-ros_domain_id-lo-fija-el-fc-es-0-y-así-se-cambia-sin-romper-nada). Si algún día se quiere
aislar del resto de la LAN con otro dominio, hay que cambiar **a la vez** el FC
(`UXRCE_DDS_DOM_ID`), la webui y este script, y pasar la prueba de banco del reporte.

CycloneDDS lista `eno2` en el desktop (`192.168.1.109`) y `eth0`, `wlan0` y `lo` en la Pi,
todas con `presence_required="false"`: usa las que existan. Sin eso, en el campo (sin
Ethernet) Cyclone se negaba a crear el dominio. El clavado del desktop evita que elija un
puente Docker.

En el desktop, lanzar solo RViz con:

```bash
./scripts/run_rviz_lidar_desktop.sh
```

El script carga `ros2/cyclonedds-desktop.xml` y `ros2/slam_test.rviz`. La configuración
muestra `/scan`, `/tf` y `/map`, con `map` como *Fixed Frame*. RViz no publica setpoints ni
arma el vehículo.

La Pi debe tener `config/cyclonedds-pi.xml` y la webui debe exportar las mismas tres variables
para cada `ros2 launch`, `ros2 bag record` y `sysmon`. Tras actualizar `app.py`, reiniciar solo
la webui en la Pi:

```bash
sudo systemctl restart px4-webui
```

Con un nodo de sensores activo en la Pi, comprobar desde el desktop antes de abrir RViz:

```bash
source /opt/ros/jazzy/setup.bash
export ROS_DOMAIN_ID=0
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
export CYCLONEDDS_URI="file://$PWD/ros2/cyclonedds-desktop.xml"
ros2 topic hz /scan
```

Debe mostrar aproximadamente 10 Hz. Si no descubre `/scan`, verificar que ambos equipos están
en la red `192.168.1.0/24`, que no hay nodos todavía activos con dominio 0 y que el firewall
no bloquea el multicast DDS.

## 7. Herramientas MAVLink en la Pi

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

## 8. Reglas de datos

- **Ningún log de más de 5 MB al repo** — `.ulg`, rosbags y cualquier dato crudo.
- Los comentarios de `.gitignore`, siempre en su propia línea.
