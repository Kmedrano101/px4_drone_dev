# MPC del ciclo completo (arm → takeoff → hold → descenso → land → disarm)

Diseño, justificación y estado del controlador MPC que corre en la Raspberry Pi
y manda aceleraciones al FC. Código en el repo
[`px4_drone`](https://github.com/Kmedrano101/px4_drone):
`scripts/mpc/generate_cycle_mpc.py`, `src/mpc_cycle.cpp`,
`src/takeoff_hold_land_mpc.cpp`, `launch/takeoff_hold_land_mpc.launch.py`.

---

## 1. Primero, una aclaración de nombres

**Los parámetros `MPC_*` de PX4 NO son un MPC.** `MPC` ahí significa
*Multicopter Position Control*. Verificado en el fuente de v1.14.3, lo que hay
dentro del FC es una cascada clásica:

```
P de posición        (PositionControl::_positionControl)
  → PID de velocidad (_velocityControl)
  → aceleración → empuje/actitud (_accelerationControl, usa MPC_THR_HOVER)
    → P de actitud por cuaternión
      → PID + feed-forward de tasas (rate_control.cpp)
```

No había ningún control predictivo a bordo. El MPC es nuestro, va en la Pi, y es
el lazo exterior.

## 2. Por qué hacía falta

Dos hechos del firmware 1.14.3, comprobados en el fuente:

- **En Offboard no hay suavizado.** No existe un FlightTask de offboard en esa
  versión, así que un escalón en el setpoint de posición pide **aceleración
  máxima** desde el primer ciclo. El perfil del vuelo lo dibuja el error, no una
  trayectoria.
- **PX4 no satura el setpoint de aceleración** (issues 18033 y 18855). Si se le
  manda una aceleración absurda, la obedece. El recorte tiene que estar de
  nuestro lado — y lo está, además de ser restricción del propio MPC.

El límite de **jerk** del MPC es lo que da la rampa que el setpoint de posición
no tiene.

## 3. El modelo

Triple integrador por eje en NED, con el **jerk como variable de control**:

```
x = [p(3), v(3), a(3)]     u = jerk(3)
ṗ = v     v̇ = a     ȧ = j
```

- Horizonte: **N = 30 pasos × 0.05 s = 1.5 s**.
- Coste: diagonal sobre posición, velocidad, aceleración y jerk
  (`q_pos_z = 60` pesa más que `q_pos_xy = 30`: la altura es lo crítico).
  El coste terminal es 3× el de etapa, como margen de estabilidad.
- **Restricciones suaves** (con penalización L1+L2): el suelo `pz ≤ z_floor` y
  las tres velocidades. Suaves a propósito: si el estado medido ya viola el
  límite (una ráfaga, un salto del EKF) un problema con restricciones duras sería
  **infactible** y el solver no devolvería nada justo cuando más falta hace.
- **Restricción dura**: solo el jerk. Es la que garantiza la suavidad y nunca
  puede volverse infactible, porque es sobre el control.
- El suelo se fija en cada ciclo a la z de armado (`originZNed()`): el MPC no
  puede planificar por debajo del punto donde arrancó.

El tercer estado es la **última aceleración comandada**, no una medida: el dron
no mide su aceleración deseada, y esto hace que la trayectoria arranque desde
donde la dejó el ciclo anterior en vez de dar un salto.

## 4. Cómo se integra con PX4

| | PID (`takeoff_position_hold_ev`) | MPC (`takeoff_hold_land_mpc`) |
|---|---|---|
| Qué publica | setpoint de **posición** | setpoint de **aceleración**, posición y velocidad en `NaN` |
| Quién controla | la cascada P/PID de PX4 | el MPC de la Pi; PX4 solo cierra actitud y tasas |

La clave está en `control_mode.cpp`: **si el heartbeat de Offboard pide
`acceleration`, PX4 apaga sus lazos de posición y velocidad.** Por eso el nodo
MPC sobreescribe `publishOffboardControlMode()` con
`(position=false, velocity=false, acceleration=true)`. La aceleración va en
**m/s² en NED**, no normalizada.

`takeoff_hold_land_mpc` **hereda** de `TakeoffPositionHoldEv`. Misión, espera del
switch del RC, salud del SLAM, parada por obstáculo con el LiDAR 2D,
HOLD/ATERRIZAR desde la webui y registro son **exactamente los mismos**. Eso es
la condición para que comparar los dos controladores signifique algo: misma
misión, mismas guardas, mismos logs, distinto controlador.

Para que encajara, la clase base expone tres puntos de extensión
(`emitTrackingSetpoint`, `publishBrakeSetpoint`, `publishOffboardControlMode`) y
un estado nuevo, **`kControlledDescent`**: el MPC baja con su propio perfil hasta
`mpc_descent_agl_m` (0.25 m) y ahí **entrega a `NAV_LAND`**, que es quien detecta
el contacto y desarma. El toque de suelo se lo deja a PX4 a propósito: su
detector de aterrizaje usa información que el MPC no tiene.

Frenar no es cortar en seco: `publishBrakeSetpoint` pide quedarse en el sitio con
velocidad cero y el MPC resuelve la parada con su límite de jerk.

## 5. Qué hace cuando algo va mal

- **Solver sin solución:** se desvanece la última aceleración (×0.8 por ciclo) en
  lugar de cortar a cero, que sería un escalón.
- **10 ciclos seguidos sin solución** (0.5 s a 20 Hz) → `abortToLand()`.
- **Sin posición válida** → aceleración nula, se mantiene vivo el flujo.
- Status 2 del solver (`maxiter`) **es normal**: en SQP_RTI se hace una iteración
  por ciclo y la solución sigue siendo utilizable. Solo status distinto de 0 y 2
  cuenta como fallo.

## 6. Coste de cómputo — cabe en la Pi 4

| Máquina | acados | Tiempo de solver |
|---|---|---|
| Desktop | v0.5.3 | 1.4–3.3 ms (1.88 ms medio / 4.08 ms pico en lazo real) |
| **Raspberry Pi 4** | **v0.6.0** | **4.4–9.3 ms** |

A 20 Hz el ciclo es de 50 ms: el peor caso en la Pi es el **18 %**. Cabe de
sobra. El nodo registra media y máximo cada 5 s en el log de la prueba, así que
el número se vuelve a medir en cada vuelo en vez de darse por bueno.

## 7. Diagnóstico para el análisis posterior

El nodo publica `mpc_status` (`Float32MultiArray`, etiquetado) y va al rosbag:

```
solve_ms, status, ok, frenando, acc_x, acc_y, acc_z,
err_x, err_y, err_z, vel_pred_z, dist_bottom, z_floor
```

Con eso se afina el MPC después del vuelo y se compara contra el PID sin tener
que reconstruir nada desde el `.ulg`.

## 8. Compilación: el solver se genera en cada máquina

El C generado por acados **no se versiona** (`.gitignore`): el desktop tiene
acados v0.5.3 y la Pi v0.6.0, y el código generado no es compatible entre
versiones. Cada máquina genera el suyo:

```bash
cd ~/drone_ws/src/px4_drone
./scripts/mpc/build_on_this_machine.sh      # genera el solver y compila
```

Dos trampas ya pisadas, documentadas para no repetirlas:

1. **`--cmake-force-configure` es obligatorio.** Sin él, si ya había una
   compilación previa, CMake no detecta que acaba de aparecer el solver generado
   y **deja el nodo MPC fuera en silencio**: la webui falla con
   *"takeoff_hold_land_mpc.launch.py was not found in the share directory"*.
   Corregido en `px4_drone@1303427`. La webui, además, ya no ofrece una tarjeta
   cuyo launch o ejecutable no esté instalado (`px4_drone@7bd4f1f`).
2. **Los nombres que genera acados v0.6.0 no son los que espera CMake.** El
   desktop tiene v0.5.3 y la Pi v0.6.0, y no dejan el solver en el mismo sitio:
   v0.6.0 deriva el nombre del OCP de un hash y exporta a su propia carpeta, así
   que CMake buscaba `acados_solver_px4_cycle_mpc.h` donde no se había escrito
   nada y **dejaba el nodo fuera de la compilación en silencio**. Se fija
   `ocp.name = "px4_cycle_mpc"` y la exportación a `c_generated_code`, que es lo
   que incluye el wrapper C++ y lo que CMake comprueba (en v0.6 el atributo se
   movió a `code_gen_options`, así que se escribe el que exista).
   Y se instala `env-hooks/acados.dsv.in`, registrado con
   `ament_environment_hooks`: acados enlaza sus propias bibliotecas transitivas y
   solo se encuentran si `ACADOS_DIR/lib` está en `LD_LIBRARY_PATH` al cargar el
   workspace. Sin el hook el nodo compila y luego **no carga**.
   Commiteado en `px4_drone@9f1b9a3` (2026-10-16), después de dos días viviendo
   solo en la copia de trabajo de la Pi.

Tarda ~6 min con `-j1` en la Pi.

## 9. Las tres variantes de MPC (2026-10-20)

A raíz de la revisión del estado del arte, el ciclo tiene ahora **tres** controladores
predictivos además del PID, y es importante entender que no son tres versiones de lo mismo:

| Tarjeta de la webui | Ejecutable | Modelo | Salida al FC | Qué cierra PX4 |
|---|---|---|---|---|
| **MPC** | `takeoff_hold_land_mpc` | triple integrador, `v'=a` | aceleración | actitud + tasas |
| **MPC+** | **el mismo** `takeoff_hold_land_mpc` | triple integrador **con perturbación**, `v'=a+d` | aceleración | actitud + tasas |
| **MPC moderno (CTBR)** | `takeoff_hold_land_ctbr` | **dinámica con actitud** (cuaternión), `[p,v,q]` | **tasas + empuje** | **solo tasas** |

### 9.1 MPC+: el estado de perturbación que faltaba

Un triple integrador **no tiene dónde meter un error constante**: ante un sesgo de empuje
(`THR_MDL_FAC=0` deja el mapeo lineal y una hélice es cuadrática), una masa o batería
distintas, o la deriva del barómetro, el lazo se asienta en un equilibrio vecino al de la
referencia. Eso es sesgo permanente en el hold — una de las métricas del protocolo.

Es la construcción estándar de MPC *offset-free* ([revisión de MPC para
MAV](https://arxiv.org/pdf/2011.11104)): el modelo pasa a `v' = a + d`, con `d` como
**parámetro** de acados (no como estado), así que el QP no crece y el solver no se encarece.
Un observador en el nodo integra la diferencia entre la aceleración que el dron consiguió
(`vehicle_local_position.ax/ay/az`) y la que el modelo predecía (`a_prev + d`).

Dos detalles que no son de adorno:

- **Solo adapta por encima de `mpc_dist_min_agl_m`** (0.35 m). En tierra, con la máquina de
  despegue de PX4 por debajo de `rampup`, el FC **descarta nuestro setpoint** y mete 100 m/s²
  hacia abajo ([parámetros](../planes/2026-10-20_parametros_vuelo_suave_produccion.md) §2): el residuo
  medido ahí no es nuestra perturbación, y el observador se iría a su tope.
- **Con `d = 0` el modelo es idéntico al anterior**, y el banco de pruebas lo demuestra: los
  cuatro casos de siempre devuelven exactamente los mismos números. Un solo solver y una sola
  compilación sirven para las dos variantes; la tarjeta MPC+ es el mismo binario con
  `mpc_dist_gain = 0.5`.

Con 0.8 m/s² de perturbación hacia abajo en la referencia, el solver manda −0.20 m/s² con jerk
−4.0: compensa, limitado por el jerk, que es lo correcto.

También lleva **compensación de retardo** (`mpc_delay_comp_s`): propaga el estado medido hacia
delante con el mismo modelo antes de usarlo como condición inicial. Sale **apagada** a propósito:
compensar un retardo equivocado es peor que no compensar. El nodo registra la edad del estado
que usa (`edad_lp_ms` en `mpc_status`) para elegir el valor con datos.

### 9.2 MPC moderno: empuje + velocidades angulares (CTBR)

Es lo que publica la literatura ágil ([HPA-MPC](https://arxiv.org/pdf/2411.11982),
[Dual-Channel Adaptive NMPC](https://arxiv.org/pdf/2507.15261)): el modelo incluye la
actitud y la salida es lo que PX4 necesita para su lazo de tasas.

```
x = [p(3), v(3), q(4)]     u = [T, wx, wy, wz]
p' = v
v' = R(q)·[0,0,−T] + [0,0,g]     (NED; el empuje va por −z del cuerpo)
q' = ½ q ⊗ [0, w]
```

`T` es empuje **específico** (m/s²), así que no hace falta la masa. Restricciones duras sobre
el control: `T ∈ [0.5g, 1.6g]` (un multirrotor no tira hacia abajo) y tasas acotadas para
interior. Coste lineal sobre el cuaternión, con el signo canónico `qw ≥ 0`: vale cerca de
nivelado, que es el vuelo interior; para vuelo agresivo haría falta error de cuaternión.

**Cabe en la Pi 4, y es más rápido que el cinemático.** Medido con N=20 × 0.05 s (horizonte
1 s), 250 resoluciones sin carga de SLAM:

| | |
|---|---|
| Solver | media **2.67 ms**, p95 3.32 ms, máx **5.87 ms** |
| A 50 Hz (20 ms) | **cabe**: 29 % en el peor caso |
| A 100 Hz (10 ms) | justo: 59 % |
| A 150 Hz (6.7 ms) | no: 88 % |

Las soluciones son físicamente correctas: en la referencia `T = 9.81 = g` con tasas nulas; 20 cm
por debajo, 11.84; desde el suelo satura en 15.69 = 1.6 g; con 30 cm de error horizontal mete
ωy = +1.34 rad/s para inclinarse. ⚠️ Sin carga de SLAM, DDS ni grabación: el lazo real hay que
medirlo en vuelo.

**Tu firmware de fábrica ya lo soporta**, verificado en el fuente del tag:
`OffboardControlMode.body_rate` existe, `control_mode.cpp:144` deja **solo**
`flag_control_rates_enabled`, y `/fmu/in/vehicle_rates_setpoint` está como suscripción en
`dds_topics.yaml`. No hay que recompilar PX4.

#### Lo que cambia de verdad, y por qué solo controla el hold

`control_mode.cpp:169-175`: con solo `body_rate`, `flag_multicopter_position_control_enabled`
es **falso** → **`mc_pos_control` no se ejecuta**. Desaparecen de golpe:

- la máquina de despegue (spoolup, rampa, la sustitución del setpoint en tierra),
- el límite de inclinación `MPC_TILTMAX_*`,
- el estimador de empuje de hover,
- cualquier interacción del controlador de posición con el detector de aterrizaje.

**El empuje que publicamos va del mezclador a los motores sin nada en medio.** Despegar así en
la primera prueba sería temerario, y además no hace falta: lo que se mide es el hold. Por eso
`takeoff_hold_land_ctbr`:

1. deja que PX4 despegue con setpoints de posición, igual que el ciclo PID;
2. **se engancha** `ctbr_engage_delay_s` (3 s) después de entrar en el hold, si la actitud es
   fresca (< 200 ms) y la inclinación está bajo `ctbr_max_tilt_deg`;
3. arranca desde el empuje de hover y mueve el publicado con una rampa (`ctbr_thr_slew_per_s`)
   para que el cambio de controlador no meta un escalón;
4. **se suelta** y devuelve el mando a PX4 si la actitud se queda obsoleta, si el solver falla
   5 ciclos seguidos, si la inclinación pasa del límite, al frenar por obstáculo, o al salir del
   hold. Al soltar publica un setpoint de posición en el acto: el controlador de tasas de PX4
   obedece el **último** setpoint recibido indefinidamente, así que dejar de publicar sin
   soltar no es una opción;
5. el descenso y el contacto los hace PX4 (`NAV_LAND`), como en el PID.

Lazo propio a `ctbr_rate_hz` (50 Hz): el de la misión va a 20 Hz y no basta para cerrar actitud
desde la Pi.

#### El mapeo de empuje hay que calibrarlo

`thrust_body` va normalizado en [0, 1]. El nodo usa un mapeo **lineal** con el hover como ancla:
`T = g → ctbr_thr_hover` (0.30, el `MPC_THR_HOVER` del FC). Es aproximado por la misma razón que
afecta a todo lo demás: `THR_MDL_FAC = 0`. **Hay que medirlo en banco** antes de fiarse; está
como parámetro por eso. Un hover a 0.8 m con el CTBR enganchado y `thrust_norm` en el bag
contra `dist_bottom` es la medida.

#### Lo que encontró la segunda lectura (2026-10-20)

Revisar el nodo como revisor y no como autor sacó **cuatro fallos**, todos en el mismo sitio:
la frontera entre "publicamos" y "ya no deberíamos publicar". Corregidos antes de ningún vuelo:

1. **El lazo rápido no comprobaba la fase.** Cuando el hold termina la base manda `NAV_LAND`, y
   cuando el piloto toma el mando `controlLostDuringFlight()` deja el estado en `kFinished` y
   la base calla — pero el temporizador de 50 Hz **seguía inyectando `vehicle_rates_setpoint`
   en uORB**, que el controlador de tasas obedece en cualquier modo (#26712). Es la clase de
   accidente del vuelo 2 del 11-09. Ahora `lazoRapido()` comprueba `inHoldPhase()` antes que
   cualquier dato.
2. **`soltar()` publicaba posición y heartbeat aunque el control ya no fuera nuestro.** Ahora,
   si `offboardArmed()` es falso, no publica nada: la entrega es dejar de hablar.
3. **Al enganchar, el heartbeat `body_rate` tardaba hasta un ciclo de 20 Hz**, y durante esos
   50 ms el controlador de actitud de PX4 y el nodo publicaban a la vez en el mismo topic. Ahora
   sale en el acto, como hace `enterObstacleStop` con el frenado.
4. **Un desenganche por causa se re-enganchaba al ciclo siguiente** en cuanto la condición se
   relajaba: a tirones sobre una inclinación marginal. Ahora es definitivo para ese ciclo
   (`no_reenganchar_`); el resto del hold lo vuela PX4.

La regla que sale de esto, y que vale para cualquier nodo futuro: **todo lazo que publique algo
que PX4 obedece fuera de Offboard tiene que comprobar la fase y `offboardArmed()` en cada
tick, no solo al arrancar.** La base expone ambos como lecturas puras, sin efectos.

#### Dos avisos de seguridad que no son negociables

- [Los setpoints por uXRCE-DDS no están filtrados por el modo de
  vuelo](https://github.com/PX4/PX4-Autopilot/issues/26712): van directos a uORB. Publicar
  tasas afecta al vehículo **en cualquier modo**. El diseño de la base (dejar de publicar si el
  control ya no es nuestro) pasa de buena práctica a imprescindible.
- `vehicle_angular_velocity` está **comentado** en el `dds_topics.yaml` de 1.14.3: no llegan
  las tasas medidas por ese topic. El giróscopo viene en `sensor_combined`.

## 10. Estado y deuda abierta

- ✅ Compilado e instalado en la Pi (2026-10-14; **recompilado el 2026-10-16**
  con los arreglos de acados ya en el repo, `FIN_RC=0`). Solver verificado con
  cuatro casos numéricos (status 0), `ldd` resuelto, ROS 2 enumera el ejecutable.
- ✅ Comunicación FC → Pi recuperada tras arrancar el cliente DDS desde QGC.
- ⛔ **Sin prueba de vuelo.** El dron no se ha armado con ninguno de los tres MPC.
- ✅ **MPC+ y CTBR compilados e instalados en la Pi** (2026-10-20): `takeoff_hold_land_mpc`
  con el parámetro de perturbación, `takeoff_hold_land_ctbr` con 0 bibliotecas sin resolver,
  los tres launches resueltos y las tres tarjetas en la webui.
- ⚠️ **El mapeo de empuje del CTBR no está calibrado** (`ctbr_thr_hover`). No volar el CTBR
  hasta medirlo.
- ⚠️ El tiempo de solver del CTBR se midió **sin** carga de SLAM/DDS/grabación.
- ✅ **Deuda de código cerrada** (2026-10-16): los dos arreglos de acados v0.6.0
  ya están commiteados en la Pi (`9f1b9a3`); un clon en limpio vuelve a compilar
  el MPC. Pendiente de `git push` desde la Pi.
- ✅ El cliente DDS del FC **arranca solo** desde `/fs/microsd/etc/extras.txt`
  (`uxrce_dds_client start -t serial -d /dev/ttyS3 -b 921600`): verificado el 2026-10-21 tras
  un reinicio, `Running, connected` con el agente de la Pi. Pendiente del 14-oct cerrado.
- ⚠️ **El dominio DDS lo fija el FC (`UXRCE_DDS_DOM_ID=0`)**; la Pi entera va en 0. No cambiar
  uno sin el otro: [cómo y por qué](CONFIGURACION_OFFBOARD_RPI4.md#2bis-ros_domain_id-lo-fija-el-fc-es-0-y-así-se-cambia-sin-romper-nada).

Detalle de la compilación y de los dos intentos de lanzamiento:
[`reports/2026-10-14_mpc-compilado-rpi.md`](../../reports/2026-10-14_mpc-compilado-rpi.md).
Protocolo de la comparación contra el PID:
[`2026-10-16_protocolo_pid_vs_mpc.md`](../planes/2026-10-16_protocolo_pid_vs_mpc.md).
