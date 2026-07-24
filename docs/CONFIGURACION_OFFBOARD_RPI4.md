# Configuración Offboard — Enlace RPi 4 ⇄ FC (uXRCE-DDS / ROS2)

**Objetivo:** habilitar Offboard mode con una Raspberry Pi 4 como companion, comunicándose
con el FC vía **uXRCE-DDS** sobre UART, para navegación autónoma con ROS2.
**Estado:** ✅ **Loop bidireccional FC↔Pi confirmado** — el FC recibe setpoints Offboard a 10 Hz desde el nodo ROS2 (`Running, connected` + `timesync converged`). Falta test de enganche outdoor.
**Fecha:** 2026-07-08

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
UXRCE_DDS_DOM_ID = 0          (debe COINCIDIR con el agent)
```

**Verificación en MAVLink Console (NSH):**
```nsh
uxrce_dds_client status      # → "Running, disconnected" (normal sin agent)
param show UXRCE*            # confirma UXRCE_DDS_CFG=102, DOM_ID=0
param show SER_*             # confirma SER_TEL2_BAUD=921600
```
> ⚠️ Los params **sí existían**; el buscador de QGC no los mostraba. La **MAVLink Console es la fuente de verdad**.

---

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
