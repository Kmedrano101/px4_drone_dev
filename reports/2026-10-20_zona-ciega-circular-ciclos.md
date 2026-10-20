# Zona ciega circular y guarda SLAM en ciclos PID/MPC

Revisión por SSH del código de `~/drone_ws/src/px4_drone` en la Raspberry Pi,
2026-10-20. Cambios locales, sin commit ni ejecución de vuelos.

## Configuración solicitada

- Zona ciega de **70 cm de diámetro**, centrada en el LiDAR y válida en los
  **360 grados**: `obstacle_blind_radius_m=0.35`. Descarta retornos con
  `r <= 0.35 m`. Sustituye la máscara angular inicial de `175 +/- 15 grados`.
- La distancia de parada sigue midiéndose desde el LiDAR, no desde el borde
  del círculo ciego. Fuera de ese círculo se conserva la detección por sectores,
  velocidad de acercamiento y debounce.
- `slam_health_enabled=false` por defecto en los launches
  `takeoff_position_hold_ev.launch.py` y `takeoff_hold_land_mpc.launch.py`.
  La ausencia, antigüedad o sigma de `/pose` no bloquean ni abortan estos ciclos.
  El SLAM y el puente EV siguen proporcionando la estimación; se conservan las
  comprobaciones de posición del FC. El valor por defecto de la clase C++ es
  `true`, por lo que otros nodos que la utilicen directamente no pierden esta
  guarda por este cambio.

## Activación desde el despegue (actualización de la misma sesión)

El diff inicial eliminaba `obstacleClearForTakeoff()` y condicionaba
`obstacleTooClose()` a haber entrado en HOLD. Tras definir el círculo ciego,
el usuario solicitó restaurar la detección desde TAKEOFF por seguridad.

Se restauró el chequeo previo al armado: exige un barrido reciente y utilizable,
y ausencia de obstáculos dentro de la distancia de parada, después del filtro
circular. En vuelo, `flightChecksFailed()` comprueba obstáculos desde TAKEOFF,
sin esperar a HOLD. Si dispara, frena y entrega a LAND. El cambio está en la
base compartida y se aplica tanto a PID como a MPC. Se mantiene
`slam_health_enabled=false` en los launches de ambos ciclos.

## Ampliación del mismo día: la zona ciega no bastaba

Al analizar los rosbags del 2026-10-16 se comprobó que la zona ciega de 0.35 m salva la
corrida MPC pero **no la PID**, que habría vuelto a abortar con un retorno espurio a 0.58 m,
fuera del círculo. Se añadió `obstacle_debounce_scans`, con **3** por defecto en el nodo y en
los dos launches. Con zona ciega 0.35 m y debounce 3 las dos corridas quedan libres y el bag
del accidente sigue parando a 1.51 m. Causa, evidencia y alternativas descartadas en
[retornos falsos al despegar](2026-10-20_falsos-obstaculos-al-despegar.md).

## Verificación

- 288 casos sintéticos C++ contra `ObstacleGuard` en la Pi: retornos dentro,
  sobre y fuera del radio, obstáculos en 36 rumbos, offset del LiDAR y máscara
  desactivada. Todos pasaron.
- Sintaxis de ambos launches y `ros2 launch ... --show-args`: radio `0.35`,
  guarda SLAM `false`, confirmación de despegue `false` por defecto.
- Evaluación de los parámetros efectivos de ambos nodos sin ejecutarlos:
  radio `0.35` y guarda SLAM `false`; la opción explícita `true` también se
  propaga correctamente. `confirm_takeoff` sigue siendo `false`.
- Compilación e instalación del paquete completas sin errores. La primera
  compilación tardó 2 min 54 s; la comprobación incremental final, con las
  fuentes definitivas, terminó en 4.31 s. Logs en la Pi:
  `/tmp/pid-mpc-review-build.log` y `/tmp/pid-mpc-review-final-build.log`.
- Tras restaurar la guarda desde TAKEOFF, recompilación completa e instalación
  correctas en 14 min 22 s (`/tmp/obstacle-takeoff-build.log`).
- El FC simulado de `tools/obstacle_guard/mock_fc.py` usaba
  `ARMING_STATE_DISARMED`, inexistente en los mensajes instalados de PX4 1.14.
  Se corrigió a `ARMING_STATE_STANDBY` para poder ejecutar las pruebas de
  integración aisladas.

Las pruebas sintéticas verifican el filtro, no la geometría del montaje ni la
ausencia de obstáculos reales dentro de la zona ignorada. No se armó el dron
ni se cambiaron parámetros del FC.
