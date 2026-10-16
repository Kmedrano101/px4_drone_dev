# MPC compilado en Raspberry Pi

Verificado por SSH en `kevin@192.168.1.221` (Raspberry Pi 4), el 2026-10-14.

## Problema y corrección

La compilación de las 10:39 omitía `takeoff_hold_land_mpc`; el intento de la web
de las 10:41 fallaba porque el ejecutable no existía. Acados
`v0.6.0-56-g988136c9e` generaba nombres de OCP con hash y una carpeta distinta
de la esperada por CMake y el wrapper C++.

En `/home/kevin/drone_ws/src/px4_drone` se modificó el generador para fijar
`ocp.name = "px4_cycle_mpc"` y la exportación a `c_generated_code`.
Se añadió `env-hooks/acados.dsv.in`, registrado en CMake, para incluir
las bibliotecas transitivas de acados en `LD_LIBRARY_PATH` al cargar el workspace.
Cambios en la Pi, sin commit ni push.

## Validación

- Generación y cuatro casos numéricos del solver: estado 0 en todos,
  tiempos entre 4.27 y 9.21 ms (pruebas aisladas, no rendimiento en vuelo).
- Compilación Release e instalación completadas.
- ROS 2 enumera `px4_drone takeoff_hold_land_mpc`.
- `ldd` resuelve las bibliotecas después de cargar `install/setup.bash`.
- Arranque aislado en dominio ROS 231 con `confirm_takeoff:=false`:
  salida 1 esperada, con rechazo explícito a despegar.
- La web carga el setup del workspace en sus comandos de lanzamiento.

No se armó el dron ni se ejecutó una misión. La validación en vuelo queda pendiente.
Logs de compilación en la Pi: `/tmp/mpc_build_20261014.log` y
`/tmp/mpc_build_env_20261014.log`.

## Intento posterior de las 10:50:37

Log remoto: `tools/webui/logs/mpc_cycle_1791967832.log` y su bag asociado.
El nodo arranca (PID 4979) e inicializa el MPC: 30 pasos de 0.05 s.
Aborta a las 10:50:49 por fuente de posición no disponible tras 10 s,
antes de solicitar OFFBOARD o armado.

El agente XRCE abre `/dev/ttyAMA0` a 921600, pero no registra creación de
cliente/sesión. El bag de 65.9 s no contiene ningún topic `/fmu/out/`;
sí contiene 1259 mensajes de EV, 83 poses y 614 scans. La evidencia apunta
a falta de comunicación FC → ROS, sin determinar aún si es alimentación,
cableado, cliente DDS del FC o configuración de conexión.

El SLAM baja de sigma 1 m a 0.049 m. Además, el LiDAR detecta un obstáculo
a 0.50–0.53 m, por debajo del mínimo de 1 m: es una segunda condición que
impediría el despegue aunque se recuperase la posición del FC.
Los topics de comandos, setpoints, heartbeat Offboard y `/mpc_status`
tienen cero mensajes. Los errores con código -2 ocurren al SIGINT final,
después de que el MPC haya salido, y no explican el aborto inicial.

## Comunicación recuperada, aproximadamente 11:01

Tras iniciar el cliente DDS desde QGC, se ejecutó únicamente el agente de la
Pi durante 40 s, sin lanzar el ciclo de vuelo. Se crearon los participantes
y topics DDS; ROS recibió `/fmu/out/vehicle_local_position` y otros nueve
topics del FC. Comunicación FC → Pi confirmada.

Una muestra mostró `xy_valid=true`, `z_valid=true`, `dead_reckoning=false`,
`eph=0.0488 m`, pero `heading_good_for_control=false` y
`dist_bottom_valid=false`. No estaban activos SLAM ni el puente EV durante
esta comprobación. Por tanto, recuperar DDS no demuestra aún que estén
cumplidas las condiciones de inicio del MPC. No se verificó persistencia
del cliente tras reiniciar el FC.
