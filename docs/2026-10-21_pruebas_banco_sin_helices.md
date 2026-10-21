# Pruebas en banco sin hélices: hasta el TAKEOFF, con parada automática

**Fecha:** 2026-10-21 · **Motivo:** varias salidas al campo sin un solo vuelo (16-oct: guardas;
20-oct: DDS). Antes de volver a desplazarse, toda la secuencia se demuestra en el banco.
**Estado:** modo banco implementado y compilado en la Pi; pendiente de ejecutarlo (el armado lo
hace el piloto).

## El peligro que manda

Sin hélices no hay empuje: el dron no sube, el error de altura crece y **el integrador de PX4
deja los cuatro motores al 100 % (~29 000 rpm en vacío) hasta que alguien pulse el kill**. Hasta
hoy la regla era *"no probar arm→takeoff→land sin hélices"*. Ahora hay una forma segura.

## Modo banco: `bench_disarm_after_s`

Parámetro del nodo (clase base, así vale para PID, MPC y MPC+). **0 = apagado**, que es lo que
usan todas las tarjetas de campo. Si es > 0 (2–30 s):

- N segundos después de entrar en `TAKEOFF`, el nodo manda **`VEHICLE_CMD_COMPONENT_ARM_DISARM`
  con `param2 = 21196`** — el código que PX4 reconoce para forzar el desarme en vuelo
  (`Commander.cpp:863` del tag v1.14.3). Sin él PX4 contesta *"Disarming denied! Not landed"*,
  que es exactamente lo que diría en el banco. Se envía dos ciclos seguidos por si el primero
  se pierde.
- El ciclo queda en `kFinished` **sin pedir LAND**: el detector de aterrizaje no dispararía con
  el integrador cargado y los motores seguirían girando.
- Al arrancar, el nodo escribe en rojo que está en modo banco y que **en vuelo real desarmaría
  el dron en el aire**. Por eso tiene sus propias tarjetas en la webui, con el prefijo
  **"BANCO sin hélices"** — una por controlador: PID, MPC, MPC+ y CTBR — y las de campo no
  llevan el parámetro.

El kill del RC (**canal 8**, `COM_KILL_DISARM=5` s) sigue siendo la red de seguridad; el modo
banco es para no depender del reflejo.

## Antes de pulsar nada

- Dron **sin hélices**, sobre espuma o sujeto por el frame (a 29 000 rpm vibra).
- Batería o fuente de banco (6S). `CBRK_USB_CHK` y `CBRK_SUPPLY_CHK` están desactivados: se
  puede armar con el USB puesto y con fuente.
- RC encendido, una persona con el dedo en el kill. **Sticks quietos y gas centrado**: con
  `COM_RC_OVERRIDE=3`, un stick a más del 30 % saca de Offboard.
- `~/drone_ws/src/px4_drone/tools/check_dds_domain.sh` → *"OK: todos en el dominio 0"*.
- **Parada por obstáculo a 0** en las tarjetas de banco: en el laboratorio hay paredes a menos
  de 1 m y el nodo se negaría a armar. En campo, 1.0.

## Orden

### 1. Handshake: arma, ralentí, desarma (sin despegue)

Tarjeta *"EV handshake (LiDAR 2D, sin despegue)"*, 10 s. Switch ch6 a OFFBOARD cuando el log lo
pida (10 s de margen). Valida la puerta del switch, el ARM desde el nodo y la fusión EV con los
motores girando (en septiembre: `eph = 0.045 m`).

**Negativa, aquí mismo:** repetir y mover el switch fuera de OFFBOARD durante la espera → debe
abortar **sin armar** (puerta `f5e1ab2`, nunca ejercida).

### 2. "BANCO sin hélices: ciclo PID", 5 s

| Log | Qué valida |
|---|---|
| `Fuente de posicion (...) lista` | EV + baro llegan por DDS. Si a los 5 s sale *"NO HA LLEGADO NINGUN MENSAJE DEL FC"*: dominio o agente |
| OFFBOARD confirmado | heartbeat aceptado |
| `Solicitando ARM` → ralentí | spoolup de PX4 (1 s) |
| `ARMADO. Despegando` | **empieza la cuenta** |
| `MODO BANCO: 5.0 s desde el TAKEOFF. DESARME FORZADO` | la parada automática |
| motores parados, `arming_state` vuelve a standby | PX4 aceptó el 21196 |

Si los motores **no** paran: kill. Si tampoco: batería fuera. (No debería pasar ninguna de las
dos.)

### 3. "BANCO sin hélices: ciclo MPC", 5 s

Igual, y además: `MPC: solver X ms de media` cada 5 s con datos reales (lejos de los 50 ms del
ciclo), y PX4 en modo `acceleration` (`vehicle_control_mode` en el bag con posición y velocidad
apagadas).

### 3b. "BANCO sin hélices: ciclo MPC+", 5 s

Mismo binario con el observador activo. Lo único que añade, y es importante: la línea
`perturbacion [x y z]` del log **tiene que seguir en cero** — en el suelo `dist_bottom < 0.35 m`
y el observador no debe adaptar (PX4 descarta nuestro setpoint antes del despegue, el residuo
no vale). Si crece, la puerta de altura falla: parar y avisar.

### 3c. "BANCO sin hélices: ciclo CTBR", 5 s

El CTBR **no engancha en banco** (solo toma el lazo de actitud en el hold): hasta el `TAKEOFF`
se comporta como el PID. Lo que se prueba es lo que nunca se ha probado con un FC real: que el
nodo arranca, carga el solver CTBR, recibe la actitud y no se cae. En el log: `CTBR: NMPC con
actitud` al arrancar y **ningún** `CTBR ENGANCHADO`.

### 4. Leer los logs antes de recoger

Cada corrida deja `.log`, bag y sysmon en la webui. Las tres cosas que tienen que estar:
el ARM aceptado, el `TAKEOFF` y el `DESARME FORZADO` con el `arming_state` de vuelta. Con eso
la secuencia completa hasta el despegue está demostrada y el campo solo añade la física.

## Lo que el banco no demuestra

Control de altura, hover, descenso y contacto. Eso es del campo, y ahí vuelve a valer el
[protocolo](2026-10-16_protocolo_pid_vs_mpc.md): A → C0 → C1 → calibrar empuje → C2.
