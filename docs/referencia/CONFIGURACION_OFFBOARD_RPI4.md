# Configuración Offboard — Enlace RPi 4 ⇄ FC (uXRCE-DDS / ROS2)

**Objetivo:** habilitar Offboard mode con una Raspberry Pi 4 como companion, comunicándose
con el FC vía **uXRCE-DDS** sobre UART, para navegación autónoma con ROS2.
**Estado:** ✅ **Loop bidireccional FC↔Pi confirmado** — el FC recibe setpoints Offboard a 10 Hz desde el nodo ROS2 (`Running, connected` + `timesync converged`). Falta test de enganche outdoor.
**Fecha:** 2026-07-08

---

## Actualización 2026-10-26 — también verificado en el **FC#2** (V3/1.17)

El FC#2 (antes vendor 1.14.3) se pasó a **firmware propio V3** (1.17.0, fork
`Kmedrano101/PX4-Autopilot` rama `nxt-dual-custom`, commit `e1ca111b`, base `82e3322e`).
`px4_msgs` del companion actualizado a **v1.17.0** (`86d8239`). **Enlace offboard bidireccional
re-verificado** sobre esta config. Claves que costaron tiempo hoy (confirmadas de nuevo):

1. **Los topics llevan `_v1`** en este firmware: `/fmu/out/vehicle_status_v1`,
   `/fmu/out/vehicle_local_position_v1`, etc. (otros NO: `vehicle_control_mode`, `vehicle_odometry`,
   `sensor_combined`…; los de offboard `offboard_control_mode`/`trajectory_setpoint`/`vehicle_command`
   van **sin** `_v1`). Hacer `echo` del nombre **sin** `_v1` da "does not appear to be published" aunque
   el FC publique (`Payload tx` > 0). **Confirmar siempre el nombre con `ros2 topic list`.**
2. **`ros2 topic list` necesita `--no-daemon --spin-time 4`** o la discovery sale intermitente
   (a veces ve los topics, a veces 0).
3. **QoS `best_effort`** para suscribirse a `/fmu/out/*` (`--qos-reliability best_effort`); con el
   `reliable` por defecto no casan y no llega dato.
4. **El agente `MicroXRCEAgent` necesita el entorno ROS sourceado** o falla con
   `libfastrtps.so.2.14: cannot open shared object` → lanzarlo tras `source /opt/ros/jazzy/setup.bash`.
5. Verificado en vivo: `vehicle_local_position_v1` → `xy_valid/z_valid/heading` válidos (brújula
   QMC5883P ya en el EKF); FC suscrito a `offboard_control_mode`/`vehicle_command`
   (`Subscription count: 1`). **No hace falta armar para esta verificación.**

**Prearm (QGC) tras flashear:** "Crash dumps present on SD" = hay `fault_*.log` en la SD → borrar
`/fs/microsd/fault_*.log` (check controlado por `COM_ARM_HFLT_CHK`, dejarlo en 1). "Strong magnetic
interference" = brújula nueva sin calibrar + cerca de la potencia → calibrar en QGC con el compás en
su posición final, lejos de ESC/cables.

---

## 0. Arquitectura

```
  Raspberry Pi 4 (companion)                     FC NxtPX4v2 (HKUST_NXT_DUAL)
  ┌──────────────────────────┐                  ┌──────────────────────────┐
  │ ROS2 Jazzy               │                  │ PX4 1.17.0 (main)        │
  │ Micro-XRCE-DDS Agent  ◄──┼──── UART ────────┼─►  uxrce_dds_client       │
  │ px4_msgs + nodo offboard │   /dev/ttyAMA0   │    TELEM2 @ 921600        │
  └──────────────────────────┘   921600 baud    └──────────────────────────┘
```

**Firmware exacto (de `ver all`):**
| Campo | Valor |
|---|---|
| HW arch | HKUST_NXT_DUAL |
| PX4 version | **1.17.0** (main) |
| PX4 git-hash | `82e3322e0cf0afc9ad640f37a0a8b639077b3fa4` (commit fuente **2026-02-03**) |
| Build datetime | ~~Jun 12 2026~~ → **REFLASHEADO 2026-07-17** |

> ⚠️ **Firmware reflasheado (2026-07-17)** con mods de board **sin commitear** en `boards/hkust/nxt-dual/`.
> El `ver all` sigue reportando git-hash `82e3322e` (las mods no están commiteadas), pero el binario **ya no es
> el de "Jun 12"**. Mods incluidas:
> - **USART6 sin consola + GPS3→ttyS5** (intento fallido para el sensor en el debug; **inútil**, el debug es SWD-only → el MTF-01 acabó en **TEL4/UART8**). Reversible para recuperar consola serie.
> - **Drivers mag específicos** (QMC5883P/L, IST8310, HMC5883) + `qmc5883p -X start` (config de brújula, útil).
> - Consola del sistema disponible por **USB** (`ttyACM0`), no por USART6.
> - ⚠️ **El flasheo RESETEÓ los params** — restaurados desde `.ulog` (ver INTEGRACION_MTF-01P_FLOW_LIDAR.md §8).

**Companion:** Raspberry Pi 4 · Ubuntu 24.04 · **ROS2 Jazzy**

---

## 1. Cableado físico (FC TELEM2 ↔ Pi GPIO UART)

| FC (TELEM2) | → | Pi 4 (GPIO) |
|---|---|---|
| TX | → | **RX** = GPIO15, pin 10 |
| RX | → | **TX** = GPIO14, pin 8 |
| GND | → | GND, pin 6 |
| **5V** | ✗ | **NO conectar** (la Pi se alimenta aparte con buck 6S→5V) |

🔴 **Críticos:**
- **TX cruza con RX** (no TX→TX).
- **GND común obligatorio** — sin él no hay comunicación.
- **NO llevar el 5V del TELEM a la Pi.**
- Ambos son **lógica 3.3V** → compatibles, sin level shifter.

---

## 2. Config del FC (QGC → Parameters)

Ya venían correctos (verificado por **MAVLink Console**, no por el buscador de QGC que los ocultaba):

```
UXRCE_DDS_CFG    = 102        (= TELEM2)
SER_TEL2_BAUD    = 921600     (baud del DDS)
UXRCE_DDS_DOM_ID = 0          (debe COINCIDIR con ROS_DOMAIN_ID en la Pi: ver §2bis)
```

**Verificación en MAVLink Console (NSH):**
```nsh
uxrce_dds_client status      # → "Running, disconnected" (normal sin agent)
param show UXRCE*            # confirma UXRCE_DDS_CFG=102, DOM_ID=0
param show SER_*             # confirma SER_TEL2_BAUD=921600
```
> ⚠️ Los params **sí existían**; el buscador de QGC no los mostraba. La **MAVLink Console es la fuente de verdad**.

---

## 2bis. `ROS_DOMAIN_ID`: lo fija el FC, es **0**, y así se cambia sin romper nada

> **Regla:** el dominio DDS no es una elección de la Pi ni del escritorio. **Lo fija el FC**
> con `UXRCE_DDS_DOM_ID`, y todo lo demás se adapta a él. Hoy es **0**.

### Por qué

El cliente uXRCE-DDS del FC crea sus topics (`/fmu/out/*`) y sus suscripciones (`/fmu/in/*`)
en el dominio `UXRCE_DDS_DOM_ID`. Un proceso ROS 2 en otro dominio **no ve nada** del FC y el
FC **no recibe nada** de él. No hay error: solo silencio. El nodo de vuelo se queda en
"Esperando fuente de posicion" hasta el timeout y aborta sin tocar nada.

Así se perdió entera la salida del **2026-10-20**: el commit `px4_drone@a3d2506` (la víspera)
cambió la webui de `ROS_DOMAIN_ID=0` a `10` en sus tres puntos de lanzamiento para que el RViz
del escritorio viera la Pi, sin tocar el FC. En el banco, con ese dominio, solo se veía
`/fmu/out/estimator_status_flags`; en el 0, los nueve topics. Detalle en el
[reporte](../../reports/2026-10-21_cinco-corridas-sin-dds-eth0.md).

### Dónde tiene que coincidir (todos, a la vez)

| Sitio | Dónde | Hoy |
|---|---|---|
| **FC** | parámetro `UXRCE_DDS_DOM_ID` (NSH: `param show UXRCE_DDS_DOM_ID`) | **0** |
| Webui de la Pi | `tools/webui/app.py`, **una sola constante** `ROS_DOMAIN_ID` (la usan los tres lanzamientos y la comprobación previa) | 0 |
| Shell de la Pi | `~/.bashrc` (`export ROS_DOMAIN_ID`) — solo afecta a quien depura a mano, pero si difiere no ve nada y pierde una hora | 0 |
| RViz escritorio | `px4_drone/scripts/rviz_lidar_desktop.sh` y `px4_drone_dev/scripts/run_rviz_lidar_desktop.sh` | 0 |

`tools/check_dds_domain.sh` (en `px4_drone`) los compara todos y, si el FC está por USB
(`/dev/ttyACM0`), lee también el parámetro. Sale con error si alguno difiere.

### Cómo se comprueba que el FC se ve (la prueba que faltó el 20-oct)

Con el dron en el suelo, **sin armar**, y el entorno exacto de la webui:

```bash
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp ROS_DOMAIN_ID=0
export CYCLONEDDS_URI=file:///home/kevin/drone_ws/src/px4_drone/config/cyclonedds-pi.xml
source /opt/ros/jazzy/setup.bash && source ~/evarobot_ws/install/setup.bash && source ~/drone_ws/install/setup.bash
ros2 launch px4_drone takeoff_position_hold_ev.launch.py confirm_takeoff:=false &   # el nodo de vuelo se niega; el resto arranca
sleep 45
ros2 topic list --no-daemon --spin-time 4 | grep -c fmu/out        # esperado: ~10
ros2 topic echo --once --qos-reliability best_effort /fmu/out/vehicle_status | grep -E "nav_state|arming_state"
ros2 topic info -v --no-daemon /fmu/in/vehicle_visual_odometry | grep count   # Subscription count: 1 = el FC escucha
```

⚠️ **`--no-daemon` es obligatorio.** `ros2 topic list` a secas pregunta al *daemon* de ROS,
que arranca con su propia configuración y contesta `/rosout` aunque el entorno esté roto.
⚠️ Para parar: `pkill -x` trunca los nombres a **15 caracteres** (`async_slam_tool`,
`ev_odometry_bri`, `static_transfor`); con el nombre completo no mata nada y los huérfanos
dejan los puertos serie ocupados.

El nodo de vuelo, además, si pasan 5 s sin recibir **ni un** `vehicle_status`, lo dice en el
log con el dominio que está usando y las dos causas conocidas (dominio distinto, agente sin
sesión), para que el log del campo baste.

### Cómo cambiarlo, si algún día hace falta (p. ej. aislar la LAN del laboratorio)

1. Volcado de parámetros del FC (copia de seguridad).
2. `UXRCE_DDS_DOM_ID` en el FC al nuevo valor y **reiniciar el FC** (el cliente lee el
   parámetro al arrancar).
3. La constante de `app.py`, el `~/.bashrc` de la Pi y los dos scripts de RViz al mismo valor.
4. `tools/check_dds_domain.sh` con el FC por USB → `OK: todos en el dominio N`.
5. La prueba de banco de arriba → ~10 `/fmu/out` y `vehicle_status` responde.
6. Reiniciar el servicio `px4-webui` (lee `app.py` solo al arrancar).

Nunca uno solo de esos pasos. Y nunca la víspera de una salida sin pasar la prueba de banco.

## 3. Config del UART en la Pi (Ubuntu, sin raspi-config)

Queremos el **PL011 (`/dev/ttyAMA0`)** — estable a 921600 — **no** el mini-UART (`/dev/ttyS0`).
Por defecto el PL011 lo ocupa el Bluetooth → hay que liberarlo.

**`/boot/firmware/config.txt`** (Ubuntu; en Pi OS sería `/boot/config.txt`):
```
enable_uart=1
dtoverlay=disable-bt
```

**Consola serie:** en Ubuntu **no hay `raspi-config`** → se hace a mano:
- `/boot/firmware/cmdline.txt` → debe tener solo `console=tty1` (consola local). **Sin** `console=serial0/ttyAMA0`. En este equipo ya estaba limpio.
- Desactivar el getty:
  ```bash
  sudo systemctl disable --now serial-getty@ttyAMA0.service
  sudo reboot
  ```

> Nota: `/dev/serial0` **no existe en Ubuntu** (ese symlink es de Raspberry Pi OS). Se usa `/dev/ttyAMA0` directamente.

---

## 4. Test de bytes crudos (validar capa física antes de nada)

```bash
sudo stty -F /dev/ttyAMA0 921600
sudo timeout 3 cat /dev/ttyAMA0 | xxd | head
```
**Éxito observado:** tramas empezando en `7e` (framing del protocolo XRCE-DDS):
```
7e01 0010 0080 0000 0002 0108 0000 0aff fd02 ...
```
→ Confirma **cableado + baud + mapeo de ttyAMA0** de una sola vez. (Los `7e` = el FC transmitiendo su cliente DDS.)

---

## 5. Micro-XRCE-DDS Agent en la Pi

**Instalar (build desde fuente):**
```bash
cd ~
git clone https://github.com/eProsima/Micro-XRCE-DDS-Agent.git
cd Micro-XRCE-DDS-Agent && mkdir build && cd build
cmake .. && make
sudo make install
sudo ldconfig /usr/local/lib/
```

**Levantar contra el FC:**
```bash
sudo MicroXRCEAgent serial --dev /dev/ttyAMA0 -b 921600
```
**Éxito:** ráfaga de `create_client / session established / create_topic / create_publisher / create_datawriter`, una por cada topic uORB → **FC y Pi conectados**.

---

## 6. px4_msgs — DEBE coincidir con el firmware 🔴

Los topics traen sufijo **`_v1`** (`vehicle_local_position_v1`, `vehicle_status_v1`) → **message versioning** de PX4 1.16+/main. Si `px4_msgs` no coincide, sale `message type ... is invalid` o lee datos corruptos.

> 🔴 **CORRECCIÓN IMPORTANTE (2026-07-22):** hay que alinear `px4_msgs` al **COMMIT** del firmware
> (`82e3322e` = **2026-02-03**), **NO a la fecha de build** (jun 12). Se usó la fecha de build por error →
> gap de 4 meses → `VehicleStatus` (cambió tras feb) NO se publicaba por DDS (`Publisher count: 0`),
> aunque `VehicleLocalPosition` (sin cambios) sí. Fix correcto:
> `git checkout "$(git rev-list -n 1 --first-parent --before='2026-02-06 00:00:00' main)"` + `colcon build`.

Como el firmware es **main @ commit 2026-02-03** (build jun 12), se alinea `px4_msgs` al commit:
```bash
source /opt/ros/jazzy/setup.bash
mkdir -p ~/drone_ws/src && cd ~/drone_ws/src
git clone https://github.com/PX4/px4_msgs.git
cd px4_msgs
git checkout "$(git rev-list -n 1 --first-parent --before='2026-06-12 09:12:38' main)"
# → quedó en dca9fab (2026-06-09), sincroniza con PX4 7f77f108 (~3 días de deriva, OK)
cd ~/drone_ws
colcon build --packages-select px4_msgs
```

**Verificación final:**
```bash
source /opt/ros/jazzy/setup.bash
source ~/drone_ws/install/setup.bash
ros2 topic echo /fmu/out/vehicle_local_position_v1     # → datos fluyendo, sin "invalid" ✅
```

---

## 7. Nodo Offboard mínimo + confirmación del loop bidireccional

Nodo standalone en la Pi (`~/drone_ws/offboard_streamer.py`) que **solo transmite setpoints**
(sin auto-armar) — para validar el stream antes de meter armado/vuelo. Publica a **10 Hz**
(> 2 Hz requerido) en `/fmu/in/offboard_control_mode` (`position=True`) y `/fmu/in/trajectory_setpoint`
(`z = -1 m` NED), con QoS **BEST_EFFORT / TRANSIENT_LOCAL / KEEP_LAST depth=1** (obligatorio para uXRCE-DDS).

**Ejecutar:**
```bash
source /opt/ros/jazzy/setup.bash && source ~/drone_ws/install/setup.bash
python3 ~/drone_ws/offboard_streamer.py
```

**Verificación 1 — la Pi emite (otra terminal):**
```bash
ros2 topic hz /fmu/in/trajectory_setpoint     # → 10.00 Hz constante ✅
```

**Verificación 2 — el FC RECIBE (MAVLink Console / NSH):**
```nsh
uxrce_dds_client status        # → "Running, connected", timesync converged: true, RX ~1590 B/s ✅
listener offboard_control_mode # → position: True llegando a ~10 Hz ✅
```
→ **Loop Pi→FC confirmado.** El pipeline uXRCE-DDS está 100% operativo.

> ⚠️ **El nodo por sí solo NO mueve nada.** PX4 ignora los setpoints hasta que el dron esté
> **ARMADO** *y* en modo **OFFBOARD** (ambos, acciones manuales del piloto). Correr el script = motores quietos.

---

## 8. Lecciones clave

1. **La MAVLink Console (NSH) es la fuente de verdad** para params/puertos — el buscador de QGC puede ocultar params que sí existen (`UXRCE_DDS_DOM_ID`, `SER_TEL2_BAUD`).
2. **En Pi 4 usar `ttyAMA0` (PL011), no `ttyS0` (mini-UART)** — el mini-UART es inestable a alto baud. Requiere `dtoverlay=disable-bt`.
3. **Ubuntu ≠ Raspberry Pi OS:** no hay `raspi-config` ni `/dev/serial0`; la consola serie se quita a mano en `cmdline.txt` + `serial-getty`.
4. **El test de bytes crudos (`cat | xxd`)** valida cableado+baud+mapeo antes de instalar nada — las tramas `7e` son la firma XRCE-DDS.
5. **`px4_msgs` debe clavar la versión del firmware.** Con builds de `main`, alinear por **fecha de build** al commit de px4_msgs más cercano. El `_v1` de los topics = message versioning.
6. **GND común FC↔Pi** es tan importante como TX/RX; sin él, silencio total.

---

## 9. Estado y próximos pasos

**✅ Completado (Fases 1–5):**
- Capa física (cableado + test de bytes `7e`).
- Cliente uXRCE-DDS en el FC (TELEM2 @ 921600).
- UART de la Pi (ttyAMA0, disable-bt, sin consola serie).
- Micro-XRCE-DDS Agent compilado y conectado.
- `px4_msgs` alineado al firmware → topics `/fmu/out/*` leídos en ROS2.
- **Nodo offboard mínimo** publicando a 10 Hz → **FC recibe** (`connected`, `listener` confirma).
- **Params de failsafe Offboard aplicados** (`COM_OF_LOSS_T=1.0`, `COM_RCL_EXCEPT=4`, `COM_OBL_ACT`→Hold/Position).

**⏳ Pendiente:**
1. 🔴 **Test de enganche + failsafe — OUTDOOR con GPS** (indoor lo rechaza por falta de posición):
   props fuera → nodo a 10 Hz → armar (RC) → flipar a **Offboard** → confirmar engancha →
   **cortar el nodo (Ctrl+C)** → verificar failsafe (Hold/Land) → RC a Stabilized para abortar.
2. **Ampliar el nodo** con armado + cambio de modo por `VehicleCommand` (opcional; de momento manual por RC).
3. **Primer vuelo Offboard** — outdoor con GPS (setpoints de posición).
4. **Indoor:** requiere fuente de posición (**MTF-01** optical-flow+LiDAR o **VOXL2**) para setpoints de
   posición/velocidad. Sin ella, PX4 rechaza Offboard de posición (comportamiento correcto de seguridad).

> **Nota de seguridad clave:** Offboard de **posición** necesita `xy_valid=1`. Indoor sin GPS/flow → rechazado.
> El pipeline de comunicación ya está validado; lo que falta es puramente la **fuente de posición** + el test outdoor.

**Comandos para retomar el enlace (cada arranque):**
```bash
# Terminal 1 — Agent
sudo MicroXRCEAgent serial --dev /dev/ttyAMA0 -b 921600
# Terminal 2 — ROS2
source /opt/ros/jazzy/setup.bash && source ~/drone_ws/install/setup.bash
ros2 topic list        # deben aparecer los /fmu/out/*
```
