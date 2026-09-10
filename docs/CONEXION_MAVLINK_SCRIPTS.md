# Conexión directa al FC por MAVLink con scripts

Cómo hablar con el NxtPX4v2 sin QGroundControl, por **cable USB** o por **radio**, para leer
y escribir parámetros, abrir la consola NuttX y muestrear sensores.

**Probado el 2026-09-07** contra el FC#2 (PX4 1.14.3 de fábrica, `micoair743-v1.14.3`).

Herramientas: [`scripts/mavlink/`](../scripts/mavlink/)

---

## 0. Preparar el entorno (una vez)

`pymavlink` **no** viene en el sistema. Hace falta un venv:

```bash
python3 -m venv ~/.venvs/mav
~/.venvs/mav/bin/pip install pymavlink pyserial
```

⚠️ **`pyserial` es obligatorio y no lo arrastra `pymavlink`.** Sin él, `mavutil` falla con
`ModuleNotFoundError: No module named 'serial'` al abrir el puerto, no al importar.

El usuario debe estar en el grupo `dialout` para abrir los puertos serie.

---

## 1. Identificar el puerto

```bash
ls -l /dev/serial/by-id/
```

| Enlace | Dispositivo | Puerto | Velocidad |
|---|---|---|---|
| **Cable USB** | `usb-Matek_HKUST_UAV_NxtPX4_0-if00` | `/dev/ttyACM0` | irrelevante (CDC) |
| **Radio** | `usb-Silicon_Labs_CP2102_...` | `/dev/ttyUSB0` | **57600** (= `SER_TEL1_BAUD`) |

Confirmar que hay tráfico antes de nada:

```bash
FC_DEV=/dev/ttyUSB0 FC_BAUD=57600 ~/.venvs/mav/bin/python scripts/mavlink/shell.py "ver all"
```

Diferencias observadas: el cable habla **MAVLink v1** y la radio **MAVLink v2**. `pymavlink`
lo resuelve solo, pero explica que los volcados de bytes empiecen por `fe` (v1) o `fd` (v2).

---

## 2. El truco del USB: hay que hablarle primero

**El USB del PX4 no transmite nada hasta que recibe MAVLink.** Abrir `/dev/ttyACM0` y
escuchar devuelve **0 bytes indefinidamente**, con o sin DTR/RTS, aunque el FC esté
perfectamente arrancado. `mavutil.wait_heartbeat()` a secas se cuelga para siempre porque
no envía nada.

La solución es mandar heartbeats **mientras** se espera el suyo — es lo que hace
`fc.connect()`:

```python
m = mavutil.mavlink_connection(dev, baud=baud, source_system=250, source_component=190)
while ...:
    m.mav.heartbeat_send(mavutil.mavlink.MAV_TYPE_GCS,
                         mavutil.mavlink.MAV_AUTOPILOT_INVALID, 0, 0, 0)
    hb = m.recv_match(type='HEARTBEAT', blocking=True, timeout=0.5)
    if hb and hb.get_srcSystem() != 250:      # ignorar el eco del propio
        break
```

Por radio no hace falta (el enlace ya emite), pero el mismo código sirve para los dos.

---

## 3. Consola NuttX sin QGC

PX4 expone su shell por `SERIAL_CONTROL` con `device = 10` (SHELL) y flags
`RESPOND | EXCLUSIVE | MULTI`. Se envía en trozos de 70 bytes y se "bombea" la salida
mandando paquetes vacíos ([`shell.py`](../scripts/mavlink/shell.py)):

```bash
FC_DEV=/dev/ttyACM0 ~/.venvs/mav/bin/python scripts/mavlink/shell.py \
    "ver all" "mavlink status" "listener vehicle_local_position"
```

Sintaxis del listener (verificada en el fuente de la 1.14.3, `listener_main.cpp`):

```
listener <topic> [-i instancia] [-r Hz] [-n num_mensajes]
```

Topics útiles en este proyecto:

| Topic | Para qué |
|---|---|
| `vehicle_local_position` | `xy_valid`, `z_valid`, `dist_bottom_valid`, `heading_good_for_control` |
| `estimator_status_flags` | `cs_opt_flow`, `cs_rng_hgt`, `cs_yaw_align`, `cs_rng_fault` |
| `distance_sensor` | LiDAR: `current_distance`, `variance`, `max_distance`, `orientation` |
| `vehicle_optical_flow` | flujo: `quality`, `distance_m`, `pixel_flow` |
| `failsafe_flags` | qué bloquea el armado (`commander check` solo dice "FAILED") |

⚠️ **`commander check` no imprime el motivo** por consola: en la 1.14 los fallos de armado
van por la interfaz de *eventos*, no por `STATUSTEXT`. Para saber qué falla hay que mirar
`listener failsafe_flags`.

---

## 4. Leer y escribir parámetros

```bash
# volcar los 914 parametros a formato QGC (punto de rollback)
FC_DEV=/dev/ttyACM0 ~/.venvs/mav/bin/python scripts/mavlink/dump_params.py \
    backups/backup_fc_$(date +%F).params

# escribir con verificacion por lectura + param save
FC_DEV=/dev/ttyACM0 ~/.venvs/mav/bin/python scripts/mavlink/set_params.py \
    EKF2_HGT_REF=0 EKF2_RNG_CTRL=1
```

⚠️ **PX4 mete los int32 bit a bit dentro del campo float** de `PARAM_VALUE`/`PARAM_SET`.
Leerlo como float da basura (`EKF2_RNG_CTRL=2` sale como `2.8e-45`). Hay que reinterpretar
los bits:

```python
valor = struct.unpack('<i', struct.pack('<f', msg.param_value))[0]   # leer int32
campo = struct.unpack('<f', struct.pack('<i', int(valor)))[0]        # escribir int32
```

`set_params.py` **no guarda nada si alguna escritura falla**: o entran todos o ninguno.
Persistir a la NVM es `MAV_CMD_PREFLIGHT_STORAGE` con `param1=1` (ack `0` = aceptado).

Los parámetros marcados `@reboot_required` (p.ej. `EKF2_MAG_TYPE`) **no aplican hasta
reiniciar**, aunque la lectura de vuelta ya devuelva el valor nuevo.

---

## 5. Reiniciar el FC

```bash
FC_DEV=/dev/ttyACM0 ~/.venvs/mav/bin/python scripts/mavlink/reboot_fc.py
```

`MAV_CMD_PREFLIGHT_REBOOT_SHUTDOWN` con `param1=1`. El script **aborta si el vehículo está
armado** — comprobación obligatoria, no quitarla. Tras el reboot tarda ~15 s en volver.

---

## 6. Monitorizar sensores en vivo

```bash
FC_DEV=/dev/ttyUSB0 FC_BAUD=57600 FC_WAIT=1.4 \
  ~/.venvs/mav/bin/python scripts/mavlink/monitor_sensors.py 900 barrido.csv
```

Muestrea `distance_sensor` + `vehicle_optical_flow` y escribe CSV con marca de tiempo, para
correlacionar después con las alturas reales. **Espera a que aparezca el puerto**, así que se
puede lanzar antes de enchufar el FC.

Tasa real: **~1 muestra cada 2 s por cable, ~3 s por radio**. Es la consola por MAVLink, no un
stream: cada muestra son dos `listener -n 1` de ida y vuelta. Para medir algo hay que mantener
cada condición **25-30 s**; los tránsitos rápidos no dejan puntos utilizables.

⚠️ Los dos topics se leen con ~1.4 s de diferencia. Si el dron se mueve en ese intervalo,
`rng_m` y `flow_dist_m` **parecerán discrepar aunque salgan del mismo láser**. Es artefacto
del muestreo, no un fallo del sensor.

---

## 7. Problemas comunes

| Síntoma | Causa | Solución |
|---|---|---|
| `Errno 16: Device or resource busy` | **QGroundControl tiene el puerto** | Cerrar QGC. Solo un proceso a la vez |
| `Errno 2: No such file or directory` | FC desenchufado o sin alimentación | Comprobar `ls /dev/serial/by-id/` |
| `ModuleNotFoundError: 'serial'` | falta `pyserial` | `pip install pyserial` |
| 0 bytes leyendo `ttyACM0` | el USB no transmite hasta recibir | mandar heartbeats (§2) |
| `sin heartbeat` por radio | dron apagado o radio sin emparejar | sniffar el puerto a 57600 primero |
| `pgrep -f script.py` encuentra procesos fantasma | casa con la **propia línea de comando** de bash | `ps -eo pid,cmd \| grep "[s]cript.py" \| grep -v "bash -c"` |

---

## 7bis. El número de parámetros NO es fijo

Un volcado del mismo FC puede dar **914 parámetros un día y 906 otro sin que se haya perdido
nada**. PX4 solo enumera por MAVLink los parámetros **en uso**: los de un módulo que no
arranca no se registran y no salen en el volcado.

Caso real medido el 2026-09-07 al apagar GPS y autotune (`SYS_HAS_GPS=0`, `MC_AT_EN=0`):

| Desaparecieron | Módulo que dejó de arrancar |
|---|---|
| `SENS_GPS_MASK`, `SENS_GPS_PRIME`, `SENS_GPS_TAU` | driver de GPS |
| `MC_AT_APPLY`, `MC_AT_RISE_TIME`, `MC_AT_START`, `MC_AT_SYSID_AMP` | autotune |
| `SENS_MAG_RATE` | sin magnetómetro conectado |

Al comparar dos backups, **diferencia de conteo ≠ pérdida de configuración**. Verificar
siempre qué nombres faltan antes de alarmarse:

```bash
comm -23 <(awk -F'\t' '/^1/{print $3}' viejo.params | sort) \
         <(awk -F'\t' '/^1/{print $3}' nuevo.params | sort)
```

---

## 8. Ejemplo completo: sesión de diagnóstico

```bash
V=~/.venvs/mav/bin/python
export FC_DEV=/dev/ttyUSB0 FC_BAUD=57600     # o /dev/ttyACM0 115200 por cable

# 1. respaldo antes de tocar nada
$V scripts/mavlink/dump_params.py backups/backup_fc_$(date +%F)_pre.params

# 2. estado del estimador y del enlace del sensor
$V scripts/mavlink/shell.py "mavlink status" \
    "listener estimator_status_flags -n 1" \
    "listener vehicle_local_position -n 1"

# 3. cambiar lo que toque
$V scripts/mavlink/set_params.py EKF2_HGT_REF=0 EKF2_RNG_CTRL=1

# 4. reiniciar y confirmar
$V scripts/mavlink/reboot_fc.py
$V scripts/mavlink/dump_params.py backups/backup_fc_$(date +%F)_post.params
```

---

## Referencias del proyecto

- [`scripts/mavlink/`](../scripts/mavlink/) — las herramientas
- [`reports/2026-09-04_fc2-vendor-1143-mtf01p-migracion.md`](../reports/2026-09-04_fc2-vendor-1143-mtf01p-migracion.md) — migración de parámetros por MAVLink
- [`INTEGRACION_MTF-01P_FLOW_LIDAR.md`](INTEGRACION_MTF-01P_FLOW_LIDAR.md) — el sensor y su puerto
