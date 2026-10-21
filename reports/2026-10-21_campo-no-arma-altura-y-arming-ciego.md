# Campo 2026-10-21 (tarde): ni un ciclo armó — dos causas, una cerrada y una por capturar

**Origen:** 4 corridas de campo (10:55–10:59) en la Pi + consola NSH del FC por USB en banco.
**Estado:** ✅ 3 de 4 eran un fallo de configuración de la webui, ya corregido · 🔄 la 4ª es una
denegación real de armado de PX4 cuyo motivo **no viaja por DDS**; se captura con `arm_watch.py`.

## Qué pasó, corrida por corrida

| Corrida | Dónde murió | Causa |
|---|---|---|
| `ev_takeoff` 10:55 | FATAL del nodo, antes de OFFBOARD | `takeoff_height_m > 1.0 m` |
| `mpc_cycle` 10:57 | ídem | `takeoff_height_m > 1.0 m` |
| `ctbr_cycle` 10:59 | ídem | `takeoff_height_m > 1.0 m` |
| `mpc_plus` 10:58 | pidió ARM, **PX4 lo denegó** | `pre_flight_checks_pass=False` (motivo no visible) |

## Causa 1 (3 de 4): la webui dejaba pasar una altura por encima del techo — CERRADA

El nodo tiene un techo duro de **1.0 m** (`kMaxHeightM`, por la saturación del LiDAR 1D) y
aborta con FATAL si `takeoff_height_m > 1.0`. El input de la webui tiene `max="1.0"`, pero eso
**no impide teclear** un valor mayor, y ni el `parseFloat` del cliente ni el `float()` del
servidor lo recortaban en el path de `ros2 launch` (el de `sensor_eval` sí validaba rango). Así
que una altura > 1.0 llegaba al nodo, que la rechazaba, y el ciclo moría en el campo sin armar y
sin causa aparente en el dron.

**Corregido** (`px4_drone@8db02a3`): el path de launch valida el rango y devuelve el motivo
exacto (*"takeoff_height_m fuera de rango [0.3, 1.0] (recibido 1.5)"*), y el cliente recorta al
`min/max` del propio input. Verificado: un POST con 1.5 se rechaza y no lanza nada.

## Causa 2 (la 4ª): PX4 deniega el armado y estamos ciegos al motivo

`mpc_plus` llegó a OFFBOARD, SLAM σ=0.119 m (bien), switch confirmado, pidió ARM, y a los 5 s:
*"El FC no confirmó ARMED. Abortando."* En el bag, `pre_flight_checks_pass=False` todo el rato.
El motivo del rechazo lo emite PX4 por **STATUSTEXT** y por el nuevo sistema de eventos
(`events::send`), y **nada de eso está en el `dds_topics.yaml` de 1.14.3**: por DDS solo llega
`vehicle_status` (con el booleano, no el porqué). Por eso cada salida ha sido a ciegas.

Dato importante: **esa misma mañana, en banco, el dron SÍ armó** (`bench_pid`, arming 1→2). Así
que la pila arma; algo cambió entre el banco de la mañana y el campo de la tarde. Las candidatas
—todas por confirmar con el motivo real— son el estado de la batería, el chequeo de estimador de
PX4 (`EKF2_REQ_*`, más estricto que nuestra guarda de σ), o el RC. No se arranca a cambiar
parámetros sin el motivo: eso es lo que ha fallado tres salidas seguidas.

### La herramienta que cierra esto: `arm_watch.py`

Monitor **pasivo** (no arma, solo escucha) en `~/mavlink_tools/`: captura cada STATUSTEXT del
FC, el resultado de cada ARM/DISARM y el estado del armado, por USB en banco o por la radio
TEL1 en campo. Cuando el piloto arma (o lo pide un ciclo) y PX4 deniega, imprime
*"Arming denied: <motivo>"*. Probado en banco en modo escucha. Es lo que convierte la próxima
denegación en un dato en vez de otro viaje perdido.

## Qué falta (y no se puede resolver sin el dron alimentado)

Reproducir el armado en **banco, con batería y RC, hélices fuera**, con `arm_watch.py`
escuchando por USB y el piloto lanzando un ciclo desde la webui, para leer el motivo exacto de
la denegación. Con ese motivo, la corrección es dirigida; sin él, es adivinar.

## Qué no se tocó

No se armó, no se voló, no se escribió ningún parámetro en el FC. El cambio es la validación de
rango en la webui. El monitor solo lee.
