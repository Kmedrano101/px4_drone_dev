# Integración MicoAir MTF-01P (Optical Flow + LiDAR) en PX4

**Objetivo:** dar al drone posición/altura **indoor sin GPS** (Altitude/Position hold, offboard) con el
sensor MTF-01P (optical flow + LiDAR láser). Sensor económico como paso previo al VOXL2.
**Estado:** ✅ **Sensor integrado y publicando en PX4** (`sensor_optical_flow` + `distance_sensor`).
**Fecha:** 2026-07-20
**Puerto final:** **TEL4 / UART8** (`/dev/ttyS7`, código 104).

> **Nota (2026-09-04):** todo lo de §1–§9 es del **FC#1 (PX4 1.17.0)**. El **FC#2 del
> segundo drone** corre el firmware de fábrica **PX4 1.14.3** y ahí la configuración de
> puerto **es distinta** — ver **§10**.

---

## 0. El sensor

- **MTF-01P** (variante de 12m; el MTF-01 base es 8m — única diferencia el rango del LiDAR).
- Combina **optical flow** (PMW3901, velocidad horizontal) + **LiDAR** (distancia/altura AGL).
- **Alimentación 5V**, señal **LVTTL 3.3V**, salida **UART 115200**.
- Conector **SH1.0-4P**, serigrafía de pines: **`GVRT`** = GND, VCC, RX, TX.
- Protocolos (configurables por **MicoAssistant**, Windows): Micolink, MSP, Mavlink_APM, **Mavlink_PX4**.
- En PX4 emite **`OPTICAL_FLOW_RAD` (msgid 106)** y **`DISTANCE_SENSOR` (msgid 132)** por MAVLink.

---

## 1. La odisea de diagnóstico (resumen)

La integración pasó por **4 problemas encadenados**, cada uno enmascarando al siguiente:

| # | Síntoma | Causa raíz | Solución |
|---|---|---|---|
| 1 | ¿Dónde conectarlo? Todos los UART ocupados | Placa compacta: GPS1, TEL1, TEL2 en uso | Investigar UARTs libres del board |
| 2 | `rx=0.0` en el puerto "debug" (ttyS5/USART6) | **El conector debug es SWD-only, sin UART** | Descartar debug; usar UART real |
| 3 | Params reseteados tras flashear firmware | Flasheo borró parámetros | Recuperados desde `.ulog` |
| 4 | `rx>0` pero `rx loss: nan%`, cero topics | **Sensor en modo MSP, no MAVLink** | MicoAssistant → `Mavlink_PX4` |

---

## 2. Hallazgo clave: el puerto "debug" NO tiene UART

Se asumió que el conector "debug" era **USART6** (la consola NuttX). Se llegó a **modificar y
recompilar el firmware** para liberar USART6 de la consola y mapearlo como GPS3 (código 203).
**Pero el sensor seguía dando `rx=0.0` en ttyS5.**

**Conclusión (confirmada por eliminación):** el conector "debug" del NxtPX4v2 es **SWD-only**
(`VCC, SWDIO, SWCLK, GND`) — **no lleva ninguna UART**. Por eso nunca llegó un byte.

> ⚠️ El diagrama de MicoAir que sugería conectar el sensor "ahí" es para **ArduPilot**, donde la
> consola va por USB y el mapeo de puertos difiere. **En PX4 no aplica.**

### Cambio de firmware realizado (queda inútil pero inofensivo)
En `boards/hkust/nxt-dual/`:
- `nuttx-config/nsh/defconfig`: `# CONFIG_DEV_CONSOLE is not set`, quitado `CONFIG_USART6_SERIAL_CONSOLE=y`, USART6 buffers 600/1500 @115200.
- `default.px4board`: `CONFIG_BOARD_SERIAL_GPS3="/dev/ttyS5"`.
- Receta copiada del **CubeOrange** (placa PX4 sin consola serie, config probada).
- Consola preservada por **USB** (`ttyACM0`, CDCACM).

**Se puede revertir** (recuperar consola serie en USART6) ya que UART8 no lo necesita.
FLASH quedó al **98.54%** — muy justo.

---

## 3. Mapeo real de UARTs del NxtPX4v2 (nxt-dual, PX4)

Confirmado desde `board.h` + `default.px4board` + lógica NuttX (`DISABLE_REORDERING=y`):

| ttyS | UART | Pines | PX4 | Código | Uso |
|---|---|---|---|---|---|
| ttyS0 | USART1 | PB10/PA9 | GPS1 | 201 | M100-5883 (GPS+brújula) |
| ttyS1 | USART2 | PD6/PD5 | TEL1 | 101 | Radio MAVLink/QGC |
| ttyS2 | USART3 | PD9/PD8 | GPS2 | 202 | Reservado RTK |
| ttyS3 | UART4 | PB8/PB9 | TEL2 | 102 | RPi 4 (offboard uXRCE-DDS) |
| ttyS4 | UART5 | PB12/PB13 | RC | 300 | Receptor |
| ttyS5 | USART6 | PC7/PC6 | (consola/debug) | — | **SWD-only, sin UART útil** |
| ttyS6 | UART7 | PE7/PE8(NC) | TEL3 | 103 | ESC telem (RX-only) |
| **ttyS7** | **UART8** | **PE0/PE1** | **TEL4** | **104** | **MTF-01P** ✅ |

---

## 4. Problema del protocolo: MSP → Mavlink_PX4

El sensor venía de fábrica en **MSP** (no MAVLink). Síntoma en el FC: bytes llegando pero
`rx loss: nan%` y **cero "Received Messages"** (PX4 esperaba MAVLink, recibía MSP).

**Confirmado por sniffing** con USB-TTL (FTDI) en Linux (`python3` + `termios`, sin pyserial):
```
Bytes crudos:  24 58 3c 00 ...   =  "$X<"  =  MSP V2   ← el problema
Funciones:     0x1f01, 0x1f02    =  sensor MSP (rangefinder + flow)
```

**Solución:** MicoAssistant (Windows) → protocolo **`Mavlink_PX4`** → Write. Tras el cambio, el
mismo sniff mostró:
```
OPTICAL_FLOW_RAD (msgid 106)  x199/3s  → ~66 Hz  ✅
DISTANCE_SENSOR  (msgid 132)  x87/3s   → ~29 Hz  ✅
```

> 💡 **Truco de diagnóstico reutilizable:** sniff de protocolo con USB-TTL + Python stdlib:
> ```python
> import os, termios, select, time
> fd = os.open('/dev/ttyUSB0', os.O_RDWR | os.O_NOCTTY)
> a = termios.tcgetattr(fd); a[0]=a[1]=a[3]=0
> a[2]=termios.CS8|termios.CREAD|termios.CLOCAL; a[4]=a[5]=termios.B115200
> termios.tcsetattr(fd, termios.TCSANOW, a); termios.tcflush(fd, termios.TCIOFLUSH)
> # leer y clasificar: fd=MAVLink v2, fe=MAVLink v1, 24 58=MSP, aa=Micolink
> ```
> El sensor **necesita 5V** (a 3.3V no arranca bien → 0 bytes).

---

## 5. Configuración final que funciona

### Puerto (una vez el sensor está en Mavlink_PX4 y cableado a TEL4)
```
MAV_1_CONFIG   = 104        (TEL4 / UART8)
MAV_1_MODE     = 0          (Normal)
MAV_1_FLOW_CTRL= 0          (el sensor no tiene CTS/RTS)
SER_TEL4_BAUD  = 115200
```

### Fusión en el EKF2
```
EKF2_OF_CTRL   = 1          (fusionar optical flow)
EKF2_RNG_CTRL  = 1          (usar rangefinder LiDAR)
EKF2_HGT_REF   = 2          (Range como referencia de altura, indoor sobre suelo plano)
SENS_FLOW_ROT  = 0          (ajustar según montaje real del sensor)
EKF2_RNG_A_HMAX= 12         (altura máx para range aid = rango del MTF-01P)
EKF2_MIN_RNG   = 0.1
```

### Cableado (serigrafía `GVRT`)
```
Sensor TX (pin4) → UART8 RX (PE0)     [CRUZADO]
Sensor RX (pin3) → UART8 TX (PE1)
Sensor GND (pin1)→ GND
Sensor VCC (pin2)→ 5V
```

---

## 6. Verificación (estado sano)

```nsh
mavlink status
```
Instancia de `/dev/ttyS7 @115200`:
- `rx loss: 0.0%` ✅ (no `nan%`)
- `msgid 132 DISTANCE_SENSOR → ~109 Hz`, `msgid 106 OPTICAL_FLOW_RAD → ~100 Hz`

```nsh
listener distance_sensor
```
```
current_distance: 0.29 m     ← LiDAR midiendo real
max_distance: 12.0 m         ← confirma MTF-01P (12m)
variance: 0.0000             ← limpio
orientation: 25              ← downward-facing (correcto)
```

```nsh
listener sensor_optical_flow
```
```
quality: 137                 ← bueno (>50 usable); depende de luz+textura
pixel_flow: [0,0]            ← 0 si está QUIETO (normal); cambia al mover sobre textura
distance_available: False    ← OK: el rango va por distance_sensor aparte, el EKF fusiona ambos
```

---

## 7. Lecciones clave

1. **Un conector "debug" en PX4 puede ser SWD-only (sin UART).** No asumir que lleva serie —
   verificar con `mavlink status` (rx) o multímetro (¿el TX del FC baila?). El diagrama del
   fabricante puede ser para ArduPilot, no PX4.
2. **`rx` cuenta bytes crudos; `rx loss: nan%` + cero "Received Messages" = protocolo equivocado**
   (no MAVLink), no un problema de cableado/baud.
3. **El MTF-01/01P viene en MSP de fábrica** — hay que cambiarlo a **Mavlink_PX4** con MicoAssistant
   (Windows). Sin eso, PX4 no lo entiende aunque lleguen bytes.
4. **El sensor necesita 5V** — a 3.3V no transmite.
5. **Sniff de protocolo con USB-TTL + Python stdlib** (termios) identifica el protocolo en segundos
   sin pyserial ni internet. Mismo espíritu que el `cat|xxd` del enlace Pi↔FC.
6. 🔴 **BACKUP DE PARÁMETROS ANTES DE FLASHEAR.** El flasheo reseteó todos los params. Se
   recuperaron desde `.ulog` (guarda `initial_parameters`), pero es un susto evitable:
   QGC → *Tools → Save to file* antes de tocar firmware.

---

## 8. Recuperación de params tras reset de flasheo

Los `.ulog` guardan **todos** los parámetros iniciales. Script de recuperación:
```python
from pyulog import ULog
u = ULog('<log>.ulg'); p = u.initial_parameters
with open('restore.params','w') as f:
    f.write('# Onboard parameters for Vehicle 1\n# Vehicle-Id Component-Id Name Value Type\n')
    for k in sorted(p):
        v=p[k]; t,vs=(9,repr(float(v))) if isinstance(v,float) else (6,str(int(v)))
        f.write(f'1\t1\t{k}\t{vs}\t{t}\n')
```
Cargar en QGC: *Parameters → Tools → Load from file* → reboot.
Archivo generado: `~/Documents/restore_nxt_2026-07-01.params` (945 params del log 2026-07-01).

> **Corrección de dato:** el mapeo real de motores es `PWM_MAIN_FUNC1..4 = 101,104,102,103`
> (según el log que voló), no `101,104,103,102` como decía `INFORME_VUELO_DRONE.md`.

---

## 9. Próximos pasos

1. **Ajustar `SENS_FLOW_ROT`** al montaje real (mover el dron y verificar signo del flow).
2. **Offsets de posición** `EKF2_OF_POS_*` / `EKF2_RNG_POS_*` si el sensor no está en el CG.
3. **Test de banco:** mover el dron a mano → verificar que la **posición local** responde al flow (sin GPS).
4. **Vuelo indoor Altitude mode** — objetivo original: mantener altura X sin pelear el throttle.
5. **Position hold indoor** con flow (hands-off, sin GPS).
6. (Opcional) **Revertir el cambio de firmware** de USART6 → recuperar consola serie.
7. Integrar con **offboard** (Pi) para navegación autónoma indoor.

---

## 10. FC#2 — mismo sensor sobre PX4 1.14.3 de fábrica (2026-09-04)

El segundo drone usa otro NxtPX4v2 pero con el **firmware de fábrica PX4 1.14.3**
(branch `micoair743-v1.14.3`, git `4a0e65f2`), no la 1.17.0. El sensor, el cableado y el
protocolo son **idénticos** a §4/§5; lo único que cambia es **cómo se levanta el puerto**.

### 10.1 Por qué `MAV_1_CONFIG=104` no sirve aquí

Esa 1.14.3 **solo declara dos puertos serie: GPS1 y TEL1**. Se comprueba en un segundo:

```
nsh> param show SER_*
x   SER_GPS1_BAUD : 0
x   SER_TEL1_BAUD : 57600      <- no hay SER_TEL4_BAUD
```

Sin `TEL4` declarado, el código de puerto **104 no mapea a ningún dispositivo**. No da
error: simplemente no arranca nada. (La 1.17 declara 7 puertos: GPS1, GPS2, TEL1–TEL4, RC.)

### 10.2 La vía que sí funciona: `extras.txt` en la SD

`mavlink start -d <ruta>` toma la **ruta cruda del dispositivo** y se salta el mapeo por
parámetros. `/dev/ttyS7` existe aunque el puerto no esté declarado. Se persiste en el hook
que `rcS` ejecuta en cada arranque (línea 486, `. $FEXTRAS`):

**`/fs/microsd/etc/extras.txt`:**
```
mavlink start -d /dev/ttyS7 -b 115200 -m minimal
```

⚠️ Escribirlo con `echo` **sin comillas** — el `echo` de NuttX conserva las comillas
simples literalmente y el archivo queda inejecutable:

```sh
mkdir /fs/microsd/etc
echo mavlink start -d /dev/ttyS7 -b 115200 -m minimal > /fs/microsd/etc/extras.txt
cat /fs/microsd/etc/extras.txt      # verificar que NO salen comillas
```

### 10.3 Verificación (tras reiniciar el FC)

```
instance #1:
	rx: 7403.3 B/s      rx loss: 0.0%
	  msgid:  132, last 0.00s ago      (DISTANCE_SENSOR)
	  msgid:  106, last 0.01s ago      (OPTICAL_FLOW_RAD)
	mode: Minimal        MAVLink version: 1
	transport protocol: serial (/dev/ttyS7 @115200)
```

`vehicle_optical_flow` → quality 90-97, `device_id 11665678` (el mismo sensor de julio).
`distance_sensor` → `max_distance 12.00`, `orientation 25` (downward).

### 10.4 Diferencias de esta 1.14.3 a tener en cuenta

| | FC#1 (1.17.0) | FC#2 (1.14.3 de fábrica) |
|---|---|---|
| Puerto del MTF-01P | `MAV_1_CONFIG=104` + `SER_TEL4_BAUD` | `extras.txt` en la SD |
| Puertos serie declarados | 7 | 2 (GPS1, TEL1) |
| `SENS_FLOW_ROT` | existe | **no existe** → rotación fija en 0 |
| Driver `qmc5883p` | sí | **no** (solo `qmc5883l`, que es otro chip) |

Como `SENS_FLOW_ROT` no es ajustable, en FC#2 el sensor **debe ir montado con su eje X
hacia adelante**; no hay corrección por software.

### 10.5 ⛔ Sin magnetómetro

En FC#2 no hay brújula conectada (`i2cdetect -b 1` solo muestra `0x77`, el barómetro
SPL06; `listener sensor_mag` → "never published") y este firmware **no puede** manejar un
QMC5883P. Esto reproduce el bloqueo del reporte
[`2026-07-23_mtf01-ekf2-tuning.md`](../reports/2026-07-23_mtf01-ekf2-tuning.md):
sin yaw, el flujo óptico no fusiona. Opciones: un mag de los soportados (IST8310, RM3100…),
yaw externo por EV (Livox + FAST-LIO), o pasar a la V2 de main.

Detalle completo de la sesión, incluida la migración de 97 params desde el FC#1:
[`reports/2026-09-04_fc2-vendor-1143-mtf01p-migracion.md`](../reports/2026-09-04_fc2-vendor-1143-mtf01p-migracion.md).
