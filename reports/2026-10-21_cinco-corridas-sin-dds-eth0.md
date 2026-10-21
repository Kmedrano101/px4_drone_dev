# Las cinco corridas del 20-oct no volaron: CycloneDDS clavado a `eth0` sin Ethernet en el campo

**Fecha del análisis:** 2026-10-21
**Origen:** `tools/webui/logs/` de la Pi por SSH, corridas del 2026-10-20 de 14:07 a 14:10
**Estado:** ✅ dos causas cerradas (interfaz `eth0` y dominio DDS), corrección verificada en banco. Sin volar.

## Qué pasó

Cinco corridas en tres minutos — tres PID, una MPC, una MPC+ — y **ninguna llegó a crear un
solo nodo ROS**. No es un problema de vuelo, de guardas ni de controlador: es que el
*middleware* no arrancó.

| Corrida | Hora | Resultado |
|---|---|---|
| `ev_takeoff_1792498027` (PID) | 14:07 | Sin cabecera de launch en el log; el `_bag.log` y el `_sysmon.log` tienen el mismo error que las demás |
| `ev_takeoff_1792498077` (PID) | 14:08 | `rmw_create_node: failed to create domain` → `error creating node` |
| `ev_takeoff_1792498115` (PID) | 14:08 | ídem |
| `mpc_cycle_1792498171` (MPC) | 14:09 | ídem |
| `mpc_plus_cycle_1792498224` (MPC+) | 14:10 | ídem |

La línea que lo explica está en la **tercera línea** de cada log, antes del error:

```
1792498083.194705 [10]       ros2: eth0: does not match an available interface.
[ERROR] [1792498083.194931159] [rmw_cyclonedds_cpp]: rmw_create_node: failed to create domain, error Error
```

`config/cyclonedds-pi.xml` clavaba CycloneDDS a **`eth0`**. En el parking no hay Ethernet: la Pi
va con su propio punto de acceso por `wlan0` (192.168.4.1). CycloneDDS 0.10.5, si una
interfaz listada no existe, **se niega a crear el dominio**, y sin dominio no hay nodo: ni el
launch, ni `ros2 bag record`, ni el monitor de carga (que también crea un nodo — de ahí que
el "`nodo_vuelo` al 91 % de CPU" de la primera corrida fuera el launch muriendo, no el dron).

No hay bags de ese día: el grabador murió igual.

## Por qué no se vio antes

- Entró con **`px4_drone@a3d2506` (2026-10-19 10:22, "config: add desktop RViz LiDAR support")**,
  un día antes de la salida. El motivo del clavado era legítimo: que el RViz del escritorio
  viera los topics de la Pi por Ethernet, y en el laboratorio eth0 siempre está arriba.
- En el laboratorio no se reproduce. Y las comprobaciones que había no lo detectan:
  `ros2 launch --show-args` no crea participante, y `ros2 topic list` a secas habla con el
  *daemon* de ROS, que arranca con su propia configuración (dominio 0, RMW por defecto) y
  contesta `/rosout` aunque el entorno de las pruebas esté roto. Las primeras pruebas de
  candidatos de este análisis cayeron en esa trampa; hay que usar `--no-daemon`.

## Reproducción y corrección, verificadas

Con el entorno exacto de la webui (`RMW_IMPLEMENTATION=rmw_cyclonedds_cpp`,
`ROS_DOMAIN_ID=10`) y `ros2 topic list --no-daemon --spin-time 1`:

| Caso | `CYCLONEDDS_URI` | Resultado |
|---|---|---|
| Campo simulado | interfaz inexistente | ⛔ `does not match an available interface` → `failed to create domain` — **idéntico al del 20-oct** |
| Corrección, campo | `eth0`*(ausente)*, `wlan0`, `lo`, todas `presence_required="false"` | ✅ |
| Corrección, laboratorio | las tres presentes | ✅ |
| Corrección, **sin red** | solo `lo` presente | ✅ |
| Límite | todas ausentes | ⛔ hace falta al menos una — por eso va `lo` |

`presence_required="false"` es el atributo de CycloneDDS ≥ 0.10 que dice "si no existe,
sigue con las demás". Con `eth0` y `wlan0` arriba Cyclone usa las dos: el escritorio ve los
topics por Ethernet y el móvil por el AP. Sin ninguna, `lo` basta para volar, porque **todos
los participantes DDS viven en la propia Pi** — el FC entra por el agente XRCE en serie — y el
vuelo no necesita red.

El XML del escritorio (`eno2`) recibe la misma tolerancia. Ahí el clavado se mantiene a
propósito: sin él, Cyclone podría elegir uno de la docena de puentes de docker.

## El segundo bloqueo, tapado por el primero: el dominio DDS

Con `eth0` arreglado, la prueba de banco del 21-oct (dron en el suelo, `confirm_takeoff:=false`,
que arranca LiDAR, SLAM, agente XRCE y puente pero el nodo de vuelo se niega) dio:

| | |
|---|---|
| LD19 | ✅ `/scan`, 1 publicador, datos |
| SLAM | ✅ `/pose` en `map` (el aviso "contains 50x readings, expected 515" es benigno) |
| Enlace XRCE | ✅ "session established"; el FC pasa a `Running, connected` |
| Cliente DDS del FC | ✅ **arranca solo** desde `extras.txt` (pendiente del 14-oct, cerrado) |
| `/fmu/out/*` en el **dominio 10** de la Pi | ⛔ **solo `estimator_status_flags`** |
| `/fmu/out/*` en el **dominio 0** | ✅ **los 9**, `vehicle_status` responde |

El FC publica en `UXRCE_DDS_DOM_ID = 0`. El mismo commit `a3d2506` cambió la webui de
`ROS_DOMAIN_ID=0` a `10` en sus tres puntos de lanzamiento (el 16-oct estaba en 0, y por eso
los bags de ese día sí tienen `/fmu/out`). Con la Pi en 10 el nodo de vuelo **nunca ve
posición ni estado y sus setpoints no llegan al FC**: aunque `eth0` hubiera estado bien, el
20-oct no habría despegado nada.

Corrección: la Pi vuelve al dominio 0, como una **sola constante** en `app.py`, y el script
del RViz de escritorio también. No se toca el FC. Si se quiere aislamiento en la LAN del
laboratorio, lo correcto es `UXRCE_DDS_DOM_ID=10` en el FC **y** todo lo demás a la vez,
validado con esta misma prueba de banco.

## Para que no vuelva a pasar en silencio

La webui ahora hace una **comprobación previa** en `/api/launch`: crea un participante DDS
real con el entorno real de la prueba (`ros2 topic list --no-daemon`, 1–3 s, una vez por
lanzamiento) y, si falla, devuelve el motivo en una línea en vez de arrancar:

> *No se puede lanzar: DDS no puede crear el dominio: eth0: does not match an available
> interface (revisar config/cyclonedds-pi.xml y las interfaces de red con `ip -br addr`)*

Las pruebas por MAVLink (`sensor_eval`) no pasan por ahí: no usan ROS.

## Qué no se tocó

No se armó el dron, no se voló y no se escribió ningún parámetro en el FC. Los cambios son
los dos XML de `config/`, el `ros2/cyclonedds-desktop.xml` de este repo y la comprobación
previa en `tools/webui/app.py`. **El protocolo de pruebas no cambia:** las cinco corridas no
cuentan ni como abortos — no hubo intento.

## Lección para el procedimiento de campo

Antes de la primera corrida del día, con el dron en el suelo y sin armar: lanzar cualquier
tarjeta ROS desde la webui y comprobar que **arranca** (la comprobación previa ya lo hace
sola). Un cambio en la configuración de red o de DDS la víspera de una salida es un cambio que
hay que probar **con la red del campo**, no con la del laboratorio.
