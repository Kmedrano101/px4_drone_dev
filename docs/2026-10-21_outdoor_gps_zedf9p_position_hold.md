# Outdoor con GPS ZED-F9P: Position/Altitude hold manual (FC#2, 1.14.3)

**Fecha:** 2026-10-21 · **Objetivo:** volar el FC#2 outdoor en modo manual (RC, sin la Pi),
validando Altitude hold y Position hold con GPS. **Estado:** preparación. No se ha cambiado
ningún parámetro del FC ni montado hardware. Respaldo del perfil indoor:
[`backups/backup_fc_2026-10-21_indoor-profile.params`](../backups/backup_fc_2026-10-21_indoor-profile.params).

## El GPS y lo que NO trae

**SparkFun GPS-RTK-SMA (ZED-F9P)** (RTK, una antena): da **posición** (con RTK, centímetros; autónomo ~1 m, de
sobra para Position hold). **No lleva brújula ni IMU.** RTK/NTRIP no hace falta para esta prueba. **Confirmado (ficha SparkFun): la placa no lleva brújula ni IMU**; se conecta por UART, y su Qwiic es I2C de 3.3V para configurar el F9P, no para un compás.

## La decisión que manda: el rumbo

| Modo | Necesita rumbo | ¿Hoy? |
|---|---|---|
| **Altitude hold** | No (baro + acelerómetro) | ✅ Sí, incluso sin GPS |
| **Position hold** | **Sí** | ⛔ **Solo con brújula montada** |

Con GPS pero **sin brújula**, un multirrotor quieto no puede fijar el heading → *toilet-bowling*
y fuga. El F9P de una antena no da rumbo (eso sería GPS dual-antena, otro hardware). Hoy el FC
está en `SYS_HAS_MAG=0`, `EKF2_MAG_TYPE=5` (sin mag). **Para Position hold hay que añadir un
magnetómetro I2C.** Los drivers (`qmc5883l`, `hmc5883`, `ist8310`, `lis3mdl`, `rm3100`) **están
en el firmware** (responden "Not running", no "command not found"), así que un compás externo es
arrancable y calibrable.

## Cableado — topología elegida (2026-10-21): todo en GPS1, cable en Y

El conector `GPS1` (`/dev/ttyS0`) lleva **UART e I2C a la vez** (SDA, SCL, Rx1, Tx1, 5V, GND).
Un cable en Y reparte:

```
GPS1  ├─ SparkFun F9P (RTK) ─→ Rx1, Tx1, 5V, GND      (UART, cruzado TX↔RX)
      └─ Brújula M100 (QMC5883L) ─→ SDA, SCL, 5V, GND  (I2C)
```

- El F9P va en GPS1 porque **es el que alimenta el EKF** (necesario para volar en RTK), y el
  puerto está en protocolo auto (`GPS_1_PROTOCOL=0`) y baud auto (`SER_GPS1_BAUD=0`): se
  autodetecta al enchufarlo.
- La brújula va en el I2C de GPS1 porque **es el único bus I2C del FC**. Montarla elevada y
  **lejos de cables de potencia/ESC** (si no, el campo magnético la corrompe → fuga).
- La parte GPS del M100 queda sin usar; el compás es lo único que se aprovecha de él.

**Pines del F9P SparkFun (verificado en el hookup guide):** usar el **UART1**, rotulado
`RX/MOSI` y `TX/MISO` (esos pines comparten UART1/SPI/I2C; en el modo por defecto, jumper
**DSEL abierto**, son UART1). **NO** usar `TX2/RX2` (UART2, que PX4 no lee por defecto).
Cruzado: `TX/MISO`→`Rx1`, `RX/MOSI`→`Tx1`. ⚠️ Dejar el **DSEL abierto**; si se cierra, los
pines pasan a SPI y el UART deja de funcionar.

**Niveles (verificado en la ficha SparkFun):** la placa F9P **acepta 5V** en su entrada (regula
a 3.3V a bordo) y **todo su UART es 3.3V TTL** → se alimenta del 5V de GPS1 y su UART conecta
**directo** al UART de GPS1 (3.3V), **sin conversor de nivel**. Cruzar TX↔RX. La brújula del
M100 es compass-only: solo sus 4 pines **V/G/C/D** (VCC, GND, SCL, SDA); sus pines R/T (GPS) se
dejan sin conectar. ⚠️ Confirmar en la serigrafía del M100 cuál es **SDA** (en algunos la "D" se
lee como "O").

**Comparación GPS normal vs RTK:** con el **mismo F9P**, activando/desactivando las correcciones
RTCM (FIX ≈ cm vs standalone ≈ 1–2 m). No con dos receptores: así la comparación aísla el RTK y
no mezcla dos antenas/posiciones.

### GPS2 descartado — y para qué se compró el MP1584EN

No se usa el conector `GPS2`: su pin de alimentación es **12V** (freiría un GPS de 5V) y, sobre
todo, **este firmware de fábrica no trae los parámetros de redundancia** (`SENS_GPS_MASK` ni
`SENS_GPS_PRIME` existen — verificado por NSH), así que un segundo GPS en GPS2 no alimentaría el
EKF ni tendría failover configurable. Se ha **comprado un módulo DC-DC `MP1584EN`** (buck
12V→5V, a ajustar a **5,0 V** con el pot antes de conectar) para alimentar un receptor en GPS2
desde ese 12V **cuando** se actualice a un firmware que sí soporte blending/primario. Hasta
entonces queda en reserva; la doble-GPS redundante no es viable con el 1.14.3 de fábrica.

## Parámetros — perfil OUTDOOR (propuesto; aplicar tras respaldo y con hardware montado)

> No aplicar nada sin: (1) respaldo hecho, (2) GPS —y brújula si Position— montados. Kevin
> ejecuta el armado.

| Parámetro | Indoor (hoy) | Outdoor | Por qué |
|---|---|---|---|
| `EKF2_GPS_CTRL` | 0 | **7** | Fusiona posición + altura + velocidad 3D del GPS |
| `EKF2_EV_CTRL` | 9 | **0** | No hay visión externa outdoor (la Pi/SLAM no vuela) |
| `EKF2_OF_CTRL` | 1 | **0** | El flujo es inútil a altura de exterior |
| `EKF2_RNG_CTRL` | 1 | **0** | El LiDAR 1D no sirve en exterior (y satura) |
| `EKF2_HGT_REF` | 0 (baro) | **0** (baro) o 2 (GPS) | Primera prueba: dejar baro. GPS como mejora |
| **Position hold (brújula):** | | | |
| `SYS_HAS_MAG` | 0 | **1** | Declara que hay compás |
| `EKF2_MAG_TYPE` | 5 (none) | **0** (auto) | Habilita la fusión del compás |
| `EKF2_MAG_CHECK` | 1 | 1 | Chequeo de consistencia del compás |
| **RC — modos de vuelo:** | | | |
| `COM_FLTMODE4` | 1 (Altitude) | **2 (Position)** ✅ aplicado 2026-10-21 | Slot 4 pasa a Position; Altitude se retira del switch (fallback restante: Stabilized, slot 6) |

Dejar igual: `COM_RC_OVERRIDE=3`, `NAV_RCL_ACT=3` (Land) — o 2 (RTL) ahora que hay GPS/home.

## Antes de armar (outdoor)

1. **Calibrar la brújula** (si Position): QGC → Sensors → Compass, girar el dron en todos los
   ejes. Sin esto no habrá yaw fiable.
2. GPS con **fix 3D** y **≥6 satélites** (`EKF2_REQ_NSATS=6`), `eph < COM_POS_FS_EPH` (1.5 m).
   Esperar a "Ready to fly" / EKF con posición global válida.
3. Primer vuelo: **Altitude** (slot 4) para validar propulsión y actitud con espacio. Luego
   **Position** solo con la brújula calibrada y el GPS sano.
4. Failsafe: con GPS, RTL (`NAV_RCL_ACT=2`) es una opción real; decidir antes de volar.

## Volver a indoor

Restaurar el perfil: `~/mavlink_tools/set_params.py backup_fc_2026-10-21_indoor-profile.params`
(reactiva EV/flujo/rango y desactiva GPS/mag). Los dos perfiles son **mutuamente excluyentes**:
no se vuela indoor con GPS activo ni outdoor con EV activo.

## Qué NO cambia

La Pi, la webui, el stack offboard/SLAM y los cuatro controladores no intervienen: esto es FC +
RC puro. Pendiente prioritario aparcado: capturar el motivo de denegación de armado en banco.

## Verificación por USB del Y cableado — 2026-10-22 (interior, sin cielo)

Prueba de **enumeración de hardware** (no de posición: en interior no hay fix 3D ni RTK, es
esperado). Por `~/mavlink_tools/shell.py` sobre `/dev/ttyACM0`:

**Brújula del M100 → incompatible con el firmware actual.** El I2C externo (bus 4 del NSH)
tiene **un dispositivo en `0x2c`** = **QMC5883P**. El cableado está bien (el chip responde:
5V, GND, SCL, SDA correctos), pero `qmc5883p` da **`command not found`**: el 1.14.3 de fábrica
**no incluye ese driver**. El firmware sí trae `qmc5883l` (dir. 0x0D), `hmc5883`, `lis3mdl`,
`rm3100`, `ist8308`, `ak09916`, `bmm150`, `lis2mdl`. **Salida:** una brújula con chip soportado
(un GY-271/QMC5883L en 0x0D, o un módulo GPS+IST8310), o flashear un firmware con el driver del P
(descartado por ahora). Con esta brújula tal cual, `SYS_HAS_MAG=1` **no serviría**: no hay quien
la lea.

**F9P → RESUELTO (2026-10-22, era Rx/Tx cruzados):** tras intercambiarlos, `gps status` da `UBX, OK, 115200, ~1550 B/s` y `sensor_gps` publica (fix_type 0 en interior). Diagnóstico original abajo.

**F9P → alimentado pero sin datos (0 B/s) [histórico].** `gps status`: `NOT OK, /dev/ttyS0, baudrate 0,
0 B/s`; `sensor_gps` nunca publicó. Como la brújula del **mismo conector GPS1** sí recibe
alimentación, el **5V/GND del Y está vivo** → el fallo es de las **líneas UART del F9P**, no de
la alimentación común. Revisar físicamente: (1) **jumper DSEL abierto** (cerrado = SPI, mata
UART1); (2) **TX/MISO→Rx1 y RX/MOSI→Tx1** bien crimpados y sin cruzar. La config del FC es
correcta: `GPS_1_CONFIG=201`, `GPS_1_PROTOCOL=0` (auto), `SER_GPS1_BAUD=0` (auto).

## Brújula adoptada: GY-273 (QMC5883L) — 2026-10-22

El compás del M100 (QMC5883P `0x2c`) no tiene driver en 1.14.3 y solo lo soporta PX4 `main`/≥1.17.
En vez de reflashear FC#2, se **compró un GY-273 (QMC5883L, `0x0D`)**, chip cuyo driver sí está
en el firmware (`qmc5883l`, verificado "Not running" en la prueba del 22-oct). Compatibilidad:
- **Dirección `0x0D`**, libre en el bus del GPS1 (solo está ocupado `0x2c`) → sin conflicto.
- **5V OK:** el GY-273 lleva LDO 3.3V + pull-ups a bordo; se alimenta de los 5V del GPS1. El chip
  es 2.16–3.6V y el bus ya va a 3.3V. (Si los pull-ups del módulo fueran a 5V habría que mirarlo,
  pero lo normal es que vayan al rail regulado de 3.3V.)
- **Seguro aunque venga HMC5883L:** el GY-273 a veces trae HMC5883L (`0x1E`) en vez de QMC5883L;
  los dos drivers están en 1.14.3, así que funciona igual.

**Puesta en marcha (cuando esté montado, por USB):**
1. `qmc5883l -X start` → debe detectarlo en `0x0D` (`listener sensor_mag 1` con datos). Si el
   chip fuese HMC5883L: `hmc5883 -X start`. Confirmar que arranca **solo en el boot**; si no, se
   añade al `extras.txt` (§6 de PLATAFORMA_HARDWARE.md).
2. Respaldo de params (ya existe el indoor), luego perfil outdoor: `SYS_HAS_MAG=1`,
   `EKF2_MAG_TYPE=0`, `EKF2_GPS_CTRL=7`, `EKF2_EV_CTRL=0`, `EKF2_OF_CTRL=0`, `EKF2_RNG_CTRL=0`.
3. Calibrar el compás en QGC. Luego Position hold en el parking.

## F9P validado con posición real — 2026-10-22 (junto a ventana, cielo parcial)

Captura por `gps_watch.py` (MAVLink `GPS_RAW_INT`, solo lectura) acercando el dron a una ventana:
- Arranque en frío: ~0–218 s sin satélites (interior), primeros satélites a **t≈219 s**.
- **Fix 3D a t≈247 s** con 6 satélites; pico **8 satélites, `eph`=6.24 m** (3D).
- Al alejar de la ventana, degradó (sats↓, vuelta a sin-fix) — coherente con el cielo tapado.
- Posición coherente con la ubicación (Ávila, ~40.6513 N, −4.6788 O).

**Conclusión:** el F9P funciona de punta a punta (hardware → UART → driver UBX → `sensor_gps` →
`GPS_RAW_INT`). El `eph` ~6 m es el autónomo normal con cielo parcial; en exterior abierto mejora
y con RTK baja a cm. **GPS cerrado.** Pendientes para el vuelo outdoor: montar la brújula GY-273
(QMC5883L) y aplicar el perfil outdoor.
