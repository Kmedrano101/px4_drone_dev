# Outdoor con GPS ZED-F9P: Position/Altitude hold manual (FC#2, 1.14.3)

**Fecha:** 2026-10-21 · **Objetivo:** volar el FC#2 outdoor en modo manual (RC, sin la Pi),
validando Altitude hold y Position hold con GPS. **Estado:** preparación. No se ha cambiado
ningún parámetro del FC ni montado hardware. Respaldo del perfil indoor:
[`backups/backup_fc_2026-10-21_indoor-profile.params`](../backups/backup_fc_2026-10-21_indoor-profile.params).

## El GPS y lo que NO trae

**u-blox ZED-F9P** (RTK, una antena): da **posición** (con RTK, centímetros; autónomo ~1 m, de
sobra para Position hold). **No lleva brújula ni IMU.** RTK/NTRIP no hace falta para esta prueba.

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

## Cableado

- **GPS → GPS1** (`/dev/ttyS0`): RX, TX, 5V, GND. El puerto ya está en protocolo **auto**
  (`GPS_1_PROTOCOL=0`) y baud **auto** (`SER_GPS1_BAUD=0`): el F9P se autodetecta al enchufarlo.
- **Brújula → bus I2C** (si se hace Position hold). Montar lejos de cables de potencia/ESC.

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
