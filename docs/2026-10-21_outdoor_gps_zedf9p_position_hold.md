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
