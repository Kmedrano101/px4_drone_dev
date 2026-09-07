# Reporte: FC nuevo con firmware de fábrica 1.14.3 — MTF-01P integrado y params migrados desde el FC de 1.17

**Fecha:** 2026-09-04
**Autor / origen:** dev machine (QGC + consola MAVLink por USB)
**Estado:** ✅ Sensor publicando y params migrados · ✅ **EKF configurado para indoor flow-only y fusionando** (§9) · ⚠️ sin brújula: no hay hold absoluto de heading

**Contexto:** segundo drone, **otro FC NxtPX4v2** (`HKUST_NXT_DUAL`, board id 1013,
STM32H743, 1792 KiB). Trae el **firmware de fábrica PX4 1.14.3** (branch
`micoair743-v1.14.3`, git `4a0e65f2`, build Nov 19 2024) — **no** la 1.17.0 del primer
drone. Decisión de esta sesión: **conservar la 1.14.x**, no reflashear. Cableado idéntico
al del primer drone; el MTF-01P ya venía configurado en `Mavlink_PX4`.

**Objetivo bloqueado:** el mismo de siempre — hold de posición indoor sin GPS. El
transporte del sensor y la configuración ya están, pero falta la fuente de yaw
(ver [reporte 2026-07-23](2026-07-23_mtf01-ekf2-tuning.md), §3.6).

---

## 1. Estado de partida del FC

| Cosa | Valor | Nota |
|---|---|---|
| Firmware | PX4 1.14.3 `micoair743-v1.14.3` | de fábrica, **no** es V1 ni V2 del INDEX |
| Params | 909 | `CAL_MAG0_ID=0`, `CAL_BARO0_ID=0` → sin calibrar |
| Mapeo de motores | `PWM_MAIN_FUNC1..4 = 0,0,0,0` | **sin mapear** |
| Puertos serie declarados | solo **GPS1** y **TEL1** | la 1.17 declara 7 |
| Magnetómetro | **ninguno** | ver §4 |

## 2. Backup del firmware: NO se puede

El bootloader del NxtPX4v2 es **rev 5**. Se reinició el FC al bootloader (`reboot -b`,
USB pasa de `1b8c:0036` a `3162:004b`) y se le mandaron los comandos de lectura de flash:

```
bootloader rev : 5
board id       : 1013
flash size     : 1835008 bytes (1792 KiB)
chip desc      : STM32H7[4|5]x,V

CHIP_VERIFY (0x24) -> sin respuesta
READ_MULTI  (0x28) -> sin respuesta      (ambos son rev2-only)
```

**No existe ningún comando del protocolo PX4 rev3+ para volcar la flash.** El binario de
fábrica no es recuperable. Vías alternativas: DFU por BOOT0
(`dfu-util -a 0 -s 0x08000000:1835008 -U dump.bin`, solo con RDP nivel 0), sonda SWD, o
pedirlo al fabricante (el git-hash `4a0e65f2` no existe en upstream PX4).

➡️ Refuerza la regla 1 del `backups/firmware/INDEX.md`: **guardar el `.px4` ANTES de flashear.**

Sí quedó respaldado: identidad del firmware, info del bootloader y los 909 params
(`backups/firmware/v0-vendor_2026-09-04_stock-1.14.3/`).

## 3. MTF-01P en TEL4: funciona, pero por otra vía

`MAV_1_CONFIG=104` (la receta del primer drone) **no puede funcionar aquí**: la 1.14.3 del
fabricante solo declara GPS1 y TEL1, así que el código 104 no mapea a ningún dispositivo.
Se confirmó por la ausencia de `SER_TEL4_BAUD` (solo hay `SER_GPS1_BAUD` y `SER_TEL1_BAUD`).

**Solución:** `mavlink start -d <ruta>` toma la ruta cruda del dispositivo y se salta el
mapeo por parámetros. Se persiste en el hook de la SD que `rcS` ejecuta en cada arranque
(línea 486, `. $FEXTRAS`):

```
/fs/microsd/etc/extras.txt:
mavlink start -d /dev/ttyS7 -b 115200 -m minimal
```

⚠️ El `echo` de NuttX **conserva las comillas simples literalmente** — hay que escribir el
archivo sin comillas o queda inejecutable.

**Verificado tras reiniciar el FC:**

```
instance #1:
	rx: 7403.3 B/s      rx loss: 0.0%
	  msgid:  132, last 0.00s ago      (DISTANCE_SENSOR)
	  msgid:  106, last 0.01s ago      (OPTICAL_FLOW_RAD)
	mode: Minimal        MAVLink version: 1
	transport protocol: serial (/dev/ttyS7 @115200)
```

```
TOPIC: vehicle_optical_flow
    device_id: 11665678 (Type: 0xB2, MAVLINK:1)   <- mismo device_id que en julio
    pixel_flow: [0.00000, 0.00213]
    distance_m: 0.02000
    max_flow_rate: 8.00000   min_ground_distance: 0.08000   max_ground_distance: 100.00000
    quality: 90
```

`distance_sensor`: `max_distance 12.00`, `orientation 25` (downward). Cadena completa
`MAVLink → sensor_optical_flow → vehicle_optical_flow → EKF2` confirmada por inyección de
mensajes sintéticos antes de tener el sensor conectado.

⚠️ **`SENS_FLOW_ROT` no existe en este build** → rotación de flujo clavada en 0. El sensor
debe ir montado con su eje X hacia adelante; no hay corrección por software.

## 4. ⛔ No hay magnetómetro — y este firmware no puede tenerlo

```
i2cdetect -b 1  ->  solo 0x77   (barómetro SPL06 interno)
i2cdetect -b 4  ->  vacío
listener sensor_mag  ->  never published
```

Drivers de mag en la 1.14.3 de fábrica: `ak09916`, `bmm150`, `hmc5883`, `ist8308`,
`ist8310`, `lis3mdl`, `qmc5883l`, `rm3100`, `vcm1193l`. **No trae `qmc5883p`** — que es
justo el chip que el board config de main arranca (`qmc5883p -X start`). El QMC5883P y el
QMC5883L son chips distintos; el driver L no maneja el P.

**Consecuencia directa:** esto es exactamente el bloqueo del reporte de 2026-07-23
(`heading_good_for_control = false` siempre → el flow no fusiona sin yaw). Este FC está
**peor**: allí al menos había mag. Opciones:
1. Conectar un mag de los que **sí** soporta este firmware (p.ej. IST8310 o RM3100).
2. Fuente de yaw externa (Livox + FAST-LIO por EV), que era el plan del reporte de julio.
3. Pasar a la V2 de main, que sí trae `qmc5883p`.

## 5. Migración de params 1.17 → 1.14.3

Origen: `backups/backup_fc_2026-07-23.params` (967 params, PX4 1.17.0, git `82e3322e`).

```
comunes 1.17 <-> 1.14.3 : 834      (133 solo existen en 1.17)
  ya idénticos          : 669
  excluidos a propósito :  62
  MIGRADOS              :  97      escritos por MAVLink, verificados por lectura, 0 fallos
```

**Excluidos y por qué** — "el nombre existe en ambos" NO es compatibilidad:

| Excluido | Motivo |
|---|---|
| `CAL_*` (46) | Calibración **por unidad física**. Los device ID de PX4 codifican bus/dirección/tipo, **no** número de serie → en un board del mismo modelo el ID coincide y la calibración ajena se aplica en silencio |
| `SENS_BOARD_X/Y_OFF` | Nivelación de horizonte, también por unidad |
| `SER_*`, `MAV_0/1/2_*`, `GPS_*_CONFIG` | Esta 1.14.3 solo declara GPS1 y TEL1 |
| `RC_PORT_CONFIG` (→105) | Código de puerto inexistente aquí; **mataría la entrada RC** (se dejó en 300) |
| `UXRCE_DDS_CFG` (→102) | Apunta a TELEM2, que no existe |
| `MAV_PROTO_VER` (→2) | Forzaría MAVLink v2 en el enlace del MTF-01P |
| `SYS_HAS_MAG` (→1) | No hay mag (§4) → bloquearía el armado |

**Lo que sí entró:**

| Grupo | Valores |
|---|---|
| Mapeo de motores | `PWM_MAIN_FUNC1..4 = 101, 104, 102, 103` |
| DShot | `PWM_MAIN_TIM0 = -3` (600, antes 300) |
| Geometría | `CA_ROTOR0..3_PX/PY = ±0.17` (antes ±0.15) |
| PIDs | `MC_ROLLRATE_P` 0.0848, `MC_PITCHRATE_P` 0.084, `MC_YAWRATE_P` 0.1198, D/I/K |
| Límites indoor | `MPC_XY_VEL_MAX` 1.5, `MPC_MAN_TILT_MAX` 20, `MPC_THR_MIN` 0.05 |
| RC | `RC_MAP_*` completo, `RC_INPUT_PROTO=6`, `RC_CHAN_CNT=16`, trims |
| Batería | 6S |
| **Flujo óptico** | `EKF2_OF_CTRL=1`, `EKF2_HGT_REF=2`, `EKF2_GPS_CTRL=0`, `EKF2_OF_QMIN=30`, `EKF2_RNG_A_HMAX=12` |

Los EKF2 de flujo vinieron **gratis** en la migración: el FC de 1.17 ya estaba configurado
para indoor. `EKF2_RNG_A_HMAX=12` cuadra con el láser de 12 m.

Persistido con `param save` y confirmado tras reinicio (marca `+` en `param show`).

## 6. Qué NO se tocó

- **Calibración de acelerómetro y giróscopo** — pendiente, hay que hacerla en este FC.
- `EKF2_OF_POS_*` y `EKF2_RNG_POS_*` siguen en **0** (también lo estaban en el FC de 1.17).
  Si el MTF-01P no va cerca del centro de gravedad, hay que medirlos.
- `EKF2_RNG_CTRL` sigue en **1** (condicional). Para indoor puro conviene **2**.
- `RC_PORT_CONFIG`, `SYS_HAS_MAG`, `UXRCE_DDS_CFG`, `MAV_PROTO_VER`: intactos a propósito.
- No se reflasheó nada. El FC sigue con la 1.14.3 de fábrica.

## 7. Contexto ya resuelto (descartar)

- **El sensor y su protocolo no son el problema**: llega a 7.4 kB/s con 0% de pérdida,
  quality 90-97, y los tres tópicos publican. El MTF-01P ya venía en `Mavlink_PX4`.
- **El transporte por TEL4 no es el problema**: sobrevive al reinicio vía `extras.txt`.
- **El mapeo de motores ya no es el problema**: migrado y verificado.
- **No perder tiempo con `MAV_1_CONFIG=104`** en este firmware: no existe el puerto.
- **No intentar volcar el firmware del FC**: el bootloader rev 5 no lo permite (§2).

## 8. Próximos pasos

1. Calibrar acelerómetro + giróscopo en QGC (los `CAL_*` se excluyeron a propósito).
2. Test de banco: mover el dron a mano y ver `pixel_flow` responder y la posición local.
3. **Resolver el yaw** (§4) — es el bloqueo real, y es el mismo de julio.
4. Medir y poner los offsets `EKF2_OF_POS_*` / `EKF2_RNG_POS_*`.

## 9. Sesión 2 (2026-09-04, tarde) — configuración indoor flow-only

### 9.1 Hallazgo: la fusión de flujo NO depende del yaw

El §4 daba por bloqueado el hold sin magnetómetro. **Es más restrictivo de lo que hace el
código.** En la 1.14.3 la única alineación que exige el control de flujo es la de tilt
(`optical_flow_control.cpp`):

```cpp
const bool inhibit_flow_use = ((preflight_motion_not_ok || flight_condition_not_ok) && !is_flow_required)
            || !_control_status.flags.tilt_align;      // no hay yaw_align
```

Y la validez de posición local tampoco lo mira (`ekf.h:340`):

```cpp
bool local_position_is_valid() const
{ return (!_horizontal_deadreckon_time_exceeded && !_control_status.flags.fake_pos); }
```

`heading_good_for_control` (= `isYawFinalAlignComplete()`, `EKF2.cpp:1619`) sí queda en
`false` para siempre sin mag/GPS/EV, pero sus únicos consumidores son `mc_att_control`
(`_reset_yaw_sp`) y `FlightTask` (`generateYawSetpoint`): degradan el yaw a control por
velocidad, **no cierran `xy_valid` ni bloquean Position mode**.

**Confirmado en vivo** tras aplicar §9.2 — `listener estimator_status_flags`:

```
cs_tilt_align: True        cs_yaw_align: False        cs_opt_flow: True
cs_rng_hgt:    True        cs_rng_kin_consistent: True   cs_rng_fault: False
cs_fake_pos:   False       cs_inertial_dead_reckoning: False
```

→ **El flujo óptico fusiona sin brújula.** Lo que se pierde es el hold absoluto de
heading: el yaw pasa a control por velocidad y deriva con el sesgo del giróscopo. Aceptable
para un primer hover indoor; **no** para navegación con setpoints (fase offboard).

### 9.2 Params aplicados (por MAVLink, verificados por lectura y tras reboot)

| Param | Antes | Ahora | Motivo |
|---|---|---|---|
| `EKF2_RNG_CTRL` | 1 (condicional) | **2** (Enabled) | En modo condicional el rango solo entra bajo `RNG_A_VMAX`/`HMAX`. Con 2 el EKF pasó a `cs_rng_hgt: True` |
| `EKF2_MAG_TYPE` | 0 (Automatic) | **5** (None) | Explícito, sin mag que esperar. Requiere reboot |

Guardado con `MAV_CMD_PREFLIGHT_STORAGE` (ack 0) y reverificado tras
`MAV_CMD_PREFLIGHT_REBOOT_SHUTDOWN`.

### 9.3 `dist_bottom_valid=False` en banco es **por diseño**, no un fallo

Era el bloqueo aparente de julio. `isTerrainEstimateValid()` exige rango fusionado en los
últimos 5 s, y `controlHaglRngFusion()` (`terrain_estimator.cpp:114`) solo fusiona si:

```cpp
const bool continuing_conditions_passing = _control_status.flags.in_air
                                           && _rng_consistency_check.isKinematicallyConsistent();
```

**En tierra `in_air=false` → nunca se fusiona HAGL → `dist_bottom_valid` no puede ser
`true`.** Cualquier chequeo previo al despegue que lo exija es insatisfacible por
construcción — ojo con el nodo `takeoff_position_hold_indoor` del reporte de julio, que lo
pedía como precondición de seguridad.

### 9.4 Estado verificado en banco (dron quieto, ~10 cm del suelo)

```
vehicle_local_position:  xy_valid True · z_valid True · v_xy_valid True
                         dead_reckoning False · x 0.0005  y -0.00003  z -0.100
                         dist_bottom 0.100 · dist_bottom_valid False (esperado, §9.3)
                         heading_good_for_control False (esperado, §9.1)
vehicle_optical_flow:    quality 98 · device_id 11665678 · min_ground_distance 0.08
mavlink instance #1:     /dev/ttyS7 @115200 · rx 7421 B/s · 0% loss · msgid 106 @100 Hz
failsafe_flags:          local_position_invalid False · local_altitude_invalid False
                         attitude_invalid False · manual_control_signal_lost True (RC apagado)
```

`commander check` → FAILED, pero por **RC ausente** (banco), no por el estimador.

### 9.5 Calibración: lo que hay y lo que falta

`CAL_ACC0_ID`, `CAL_ACC1_ID`, `CAL_GYRO0_ID`, `CAL_GYRO1_ID` son **distintos de cero** ya en
el dump de fábrica → acelerómetro y giróscopo vienen calibrados por el fabricante. El §8.1
los daba por pendientes; no lo están.

⚠️ **Ojo con el device ID como prueba de nada:** `CAL_ACC0_ID=6946826` y
`CAL_GYRO0_ID=6684682` son **idénticos en FC#1 y FC#2** — codifican bus/dirección/tipo, no
la unidad. Es justo la trampa que documenta §5.

**Lo que sí falta:** `SENS_BOARD_X_OFF = SENS_BOARD_Y_OFF = 0` (en FC#1 eran 0.67 y -1.23)
→ **nivelación de horizonte sin hacer**. Con un horizonte torcido el dron acelera solo en
hover; es la calibración que más afecta a un hold indoor. Hacer *Level Horizon* en QGC.

### 9.6 Pendiente antes de volar

1. **Level Horizon** en QGC (§9.5).
2. Medir y poner `EKF2_OF_POS_X/Y/Z` y `EKF2_RNG_POS_X/Y/Z` — offset del MTF-01P respecto
   al FC en metros, marco FRD. Si está a menos de ~3 cm del centro, dejar en 0.
3. Alimentar el receptor RC (`manual_control_signal_lost: True`).
4. Primer test **sobre suelo plano y despejado**: con `EKF2_HGT_REF=2` la altura es el
   LiDAR, así que volar sobre una mesa o una caja salta la referencia.
5. Orden: Altitude primero, luego Position. Esperar deriva lenta de rumbo (§9.1).

## Archivos

| Archivo | Qué es |
|---|---|
| `backups/backup_fc_2026-09-04.params` (909) | estado de fábrica — **rollback a vendor** |
| `backups/backup_fc_2026-09-04_pre-indoor.params` (914) | previo a §9.2 — **rollback de esta sesión** |
| `backups/backup_fc_2026-09-04_post-migracion.params` (914) | estado actual |
| `backups/firmware/v0-vendor_2026-09-04_stock-1.14.3/` | identidad del FW + info del bootloader |
| `backups/firmware/INDEX.md` | tabla de versiones + detalle de la migración |
| `/fs/microsd/etc/extras.txt` (en el FC) | arranque del MAVLink del MTF-01P |
