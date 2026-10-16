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

## 9. Estado y deuda abierta

- ✅ Compilado e instalado en la Pi (2026-10-14; **recompilado el 2026-10-16**
  con los arreglos de acados ya en el repo, `FIN_RC=0`). Solver verificado con
  cuatro casos numéricos (status 0), `ldd` resuelto, ROS 2 enumera el ejecutable.
- ✅ Comunicación FC → Pi recuperada tras arrancar el cliente DDS desde QGC.
- ⛔ **Sin prueba de vuelo.** El dron no se ha armado con el MPC.
- ✅ **Deuda de código cerrada** (2026-10-16): los dos arreglos de acados v0.6.0
  ya están commiteados en la Pi (`9f1b9a3`); un clon en limpio vuelve a compilar
  el MPC. Pendiente de `git push` desde la Pi.
- ⚠️ El cliente DDS del FC se arrancó a mano desde QGC; **no se ha comprobado que
  persista tras reiniciar el FC**.

Detalle de la compilación y de los dos intentos de lanzamiento:
[`reports/2026-10-14_mpc-compilado-rpi.md`](../reports/2026-10-14_mpc-compilado-rpi.md).
Protocolo de la comparación contra el PID:
[`2026-10-16_protocolo_pid_vs_mpc.md`](2026-10-16_protocolo_pid_vs_mpc.md).
