# Parámetros para navegación indoor sin GPS — NxtPX4v2 (FC#2)

Configuración completa para **hover y position hold en interior** con MTF-01P (flujo óptico +
LiDAR), **sin GPS y sin magnetómetro**.

**Firmware:** PX4 1.14.3 de fábrica (`micoair743-v1.14.3`) · **Valores leídos del FC el 2026-09-07**
Volcado de referencia: [`backups/backup_fc_2026-09-07.params`](../backups/backup_fc_2026-09-07.params)

> Ordenado **por importancia**: el grupo A decide si el dron puede navegar; el F solo afecta a
> lo que puedes diagnosticar después. Si tienes que revisar algo con prisa, empieza por arriba.

Leyenda: ✅ correcto · ⏳ pendiente de aplicar · ⚠️ atención

---

## A. Fuentes de navegación — sin esto no hay vuelo indoor

Definen **de dónde saca el EKF la posición, la altura y el rumbo**. Un error aquí no degrada el
vuelo: lo rompe.

| Param | Actual | Opciones | Qué hace y por qué importa |
|---|---|---|---|
| `EKF2_OF_CTRL` | **1** ✅ | 0 off · 1 on | Activa la fusión de flujo óptico. **Es la única fuente de posición horizontal que tienes.** Sin esto no hay Position mode |
| `EKF2_RNG_CTRL` | **1** ✅ | 0 off · 1 condicional · 2 siempre | Fusión del LiDAR como altura. En condicional solo entra por debajo de `EKF2_RNG_A_HMAX`. **A 1 porque el sensor solo es fiable hasta ~1.5 m** (§ medición). ⚠ **No subir a 2**: fusionaría el rango también por encima de la saturación, que es el mecanismo del escape vertical del vuelo 2 |
| `EKF2_HGT_REF` | **0** ✅ | 0 barómetro · 1 GPS · 2 rango · 3 visión | **Referencia de altura del EKF.** Fue la causa del accidente: con el LiDAR como referencia y el sensor saturando a 2.4 m, un despegue a 5 m no tiene punto de equilibrio y el dron sube sin parar. **Requiere reboot** |
| `EKF2_GPS_CTRL` | **0** ✅ | bitmask: b0 lat/lon · b1 alt · b2 vel 3D · b3 heading | GPS desactivado por completo. Coherente con volar solo en interior |
| `EKF2_MAG_TYPE` | **5** ✅ | 0 auto · 1 heading · 2 3-ejes · 3 VTOL · 4 MC · 5 ninguno | Sin brújula. **Requiere reboot.** Consecuencia: `heading_good_for_control=false` y el yaw pasa a control por velocidad — pero el flujo **sí** fusiona sin yaw |
| `SYS_HAS_GPS` | **0** ✅ | 0 no · 1 sí | Declara que no hay GPS. Si está en 1 con `EKF2_GPS_CTRL=0`, el preflight cuenta con un GPS que el EKF ignora. **Requiere reboot** |
| `SYS_HAS_MAG` | **0** ✅ | 0 no · 1 sí | Igual para la brújula. En 1 bloquearía el armado. **Requiere reboot** |
| `COM_ARM_WO_GPS` | **1** ✅ | 0 exige fix · 1 permite | Sin esto no armas nunca en interior |
| `EKF2_TERR_MASK` | **3** ✅ | bitmask: b0 rango · b1 flujo | Fuentes del estimador de terreno. **El flujo no fusiona sin terreno válido**, y el terreno sale del rango: por eso el techo del LiDAR limita también la posición horizontal |
| `EKF2_BARO_CTRL` | **1** ✅ | 0 off · 1 on | Barómetro como ayuda de altura. Es la red bajo el LiDAR |

---

## B. Calidad de la estimación — afinan, no habilitan

Con los valores por defecto vuela; estos deciden **cuánto se fía** el EKF de cada medida.

| Param | Actual | Rango | Qué hace y por qué importa |
|---|---|---|---|
| `EKF2_OF_QMIN` | **30** | 0–255 | Calidad mínima del flujo **en vuelo**. Por debajo, la muestra se descarta. El MTF-01P da 90-100 sobre suelo con textura y **cae a 6-10 en altura**: ahí el EKF se queda sin posición |
| `EKF2_OF_QMIN_GND` | **0** | 0–255 | Lo mismo **en tierra**. En 0 acepta cualquier calidad con el dron apoyado |
| `EKF2_MIN_RNG` | **0.17 m** ✅ | ≥0.01 | Lectura esperada del LiDAR con el dron **apoyado en las patas**. Medido 2026-09-17: 0.16–0.17 m, varianza 0. Es el suelo del HAGL (`terrain_estimator.cpp:78`) y de la medida de rango (`range_height_control.cpp:101`): con el 0.10 anterior el EKF creía estar 7 cm por debajo del suelo real al despegar |
| `EKF2_RNG_A_HMAX` | **1.5** ✅ | 1.0–10.0 | Altura máxima para el modo condicional del rango (el 12.0 anterior estaba fuera del rango documentado y era 5× el techo real). Ojo a la histéresis: **engancha por debajo de 0.7× = 1.05 m** y se mantiene hasta 1.5 m (`range_height_control.cpp:220`) |
| `EKF2_RNG_A_VMAX` | **1.0 m/s** | 0.1–2 | Velocidad horizontal máxima para el modo condicional |
| `EKF2_RNG_NOISE` | **0.10 m** | ≥0.01 | Ruido asumido del rango |
| `EKF2_RNG_SFE` | **0.05 m/m** | 0–0.2 | Ruido proporcional a la distancia. ⚠️ **Medido: 29% de error a 3 m**, muy por encima del 5% asumido |
| `EKF2_RNG_GATE` / `EKF2_OF_GATE` | 5.0 / 3.0 SD | ≥1 | Puertas de rechazo de outliers |
| `EKF2_OF_DELAY` / `EKF2_RNG_DELAY` | 20 / 5 ms | 0–300 | Retardo de cada medida respecto a la IMU. **Requieren reboot** |
| `EKF2_OF_N_MIN` / `N_MAX` | 0.15 / 0.5 rad/s | ≥0.05 | Ruido del flujo con calidad máxima / mínima |
| `EKF2_TERR_NOISE` / `TERR_GRAD` | 5.0 / 0.5 | — | Ruido de proceso y pendiente del terreno |
| `EKF2_OF_POS_X/Y/Z` | **0.055 / 0 / 0.018** ✅ | m | Posición del **flujo** respecto al centro de gravedad (X adelante, Y derecha, Z abajo). Medido 2026-09-17. Un offset no declarado mete velocidad falsa al girar |
| `EKF2_RNG_POS_X/Y/Z` | **0.055 / 0 / 0.020** ✅ | m | Igual para el **LiDAR** |

---

## C. Failsafe — qué pasa cuando algo falla

| Param | Actual | Opciones | Qué hace y por qué importa |
|---|---|---|---|
| `NAV_RCL_ACT` | **3** ✅ | 1 Hold · 2 Return · 3 Land · 5 Terminate · 6 Disarm | Pérdida de RC. **Return es imposible sin GPS** — dejarlo en 2 (el default) da comportamiento indefinido |
| `COM_POSCTL_NAVL` | **0** ✅ | 0 Altitude/Manual · 1 Land/Descend | Qué hacer si se pierde la posición en Position mode. En 0 cae a Altitude y sigues teniendo el mando |
| `COM_POS_FS_EPH` | **1.5 m** ✅ | m | Error horizontal a partir del cual la posición se declara inválida. El default de 5 m es tardísimo en una sala; con flujo el `eph` real es ~0.05 m |
| `COM_POS_FS_DELAY` | 1 s | 1–100 | Retardo antes de activar ese failsafe |
| `COM_LOW_BAT_ACT` | **2** ✅ | 0 aviso · 2 Land · 3 Return/Land | Batería baja. **Return no es opción sin GPS** |
| `COM_DISARM_LAND` | 2.0 s | s | Desarme automático tras aterrizar |
| `COM_DISARM_PRFLT` | 10.0 s | s | Desarme si armas y no despegas. Útil en banco |
| `COM_RC_LOSS_T` | 0.5 s | 0–35 | Tiempo para declarar RC perdido |

### ⚠️ Lo que NO funciona sin GPS

| Param | Actual | Por qué es inútil aquí |
|---|---|---|
| `GF_MAX_VER_DIST` | 0.0 | La geofence trabaja sobre **posición global** (`geofence.cpp:180`) y exige `home_global_position_valid()` |
| `GF_MAX_HOR_DIST` | 0.0 | Igual |
| `LNDMC_ALT_MAX` | −1.0 | `FlightModeManager::limitAltitude()` sale si `!home_position.valid_alt`, y `valid_alt` requiere `lpos.z_global`, que necesita GPS |

**No existe techo de altura por software en esta configuración.** El único límite es el techo de
la sala y el piloto. Por eso el grupo A importa tanto: si la referencia de altura miente, nada
detiene la subida.

---

## D. Límites de vuelo — que la sala no se quede pequeña

| Param | Actual | Default | Qué hace |
|---|---|---|---|
| `MPC_XY_VEL_MAX` | **1.0 m/s** ✅ | 12.0 | Velocidad horizontal máxima |
| `MPC_VEL_MANUAL` | **1.0 m/s** ✅ | 10.0 | Máxima en Position mode con sticks |
| `MPC_XY_CRUISE` | **1.0 m/s** ✅ | 5.0 | Velocidad de crucero |
| `MPC_Z_VEL_MAX_UP` | **1.06 m/s** ✅ | 3.0 | Ascenso máximo |
| `MPC_Z_VEL_MAX_DN` | **0.81 m/s** ✅ | 1.5 | Descenso máximo |
| `MPC_TKO_SPEED` | **1.0 m/s** ✅ | 1.5 | Velocidad de despegue |
| `MPC_LAND_SPEED` | **0.6 m/s** ✅ | 0.7 | Velocidad de aterrizaje |
| `MPC_TILTMAX_AIR` | **25°** ✅ | 45.0 | Inclinación máxima en vuelo. Por encima de ~30° el flujo falla `is_tilt_good` y deja de fusionar |
| `MPC_MAN_TILT_MAX` | **20°** ✅ | 35.0 | Inclinación máxima en manual/altitude |
| `MPC_THR_HOVER` | **0.30** ✅ | 0.5 | Empuje de hover. **Medido en vuelo real**: 0.284 de media, mediana 0.287. Con 0.5 el despegue sale disparado |
| `MPC_THR_MIN` | 0.05 | 0.12 | Empuje mínimo |
| `MPC_ALT_MODE` | **0** ✅ | 0 | 0 altitud · 1 sigue terreno · 2 mantiene terreno. Con `HGT_REF` ya relativo al suelo, el modo 2 duplicaba el conmutador |
| `MPC_POS_MODE` | 4 | 4 | 0 simple · 3 suave · 4 por aceleración |
| `MPC_USE_HTE` | 1 | 1 | Estimador de empuje de hover en vuelo. Corrige `MPC_THR_HOVER` solo |
| `MPC_HOLD_MAX_XY` | 0.8 m/s | 0.8 | Velocidad por debajo de la cual engancha el hold al soltar sticks |

> ⚠️ `MPC_XY_CRUISE` y `MPC_VEL_MANUAL` tienen `@min 3.0` en los metadatos y están en 1.0.
> PX4 los acepta; es QGC quien se queja. Es deliberado para interior.

---

## E. Control de actitud

| Param | Actual | Opciones | Qué hace y por qué importa |
|---|---|---|---|
| `MC_AIRMODE` | **0** ✅ | 0 off · 1 Roll/Pitch · 2 Roll/Pitch/Yaw | ⚠️ **Nunca poner 2 en este dron.** Con `MC_AIRMODE=2` y un error de rumbo, dos motores del mismo diagonal se van al 100% a gas cero — es el incidente documentado en `DIAGNOSTICO_RUIDO_MOTORES_YAW.md` |
| `MC_YAW_P` | **2.8** ✅ | 0–5 | Ganancia P de yaw. Sin referencia de rumbo, ganancia alta amplifica cualquier error |
| `MC_YAWRATE_MAX` | **120 °/s** ✅ | 0–1800 | Sin brújula no hace falta más autoridad de yaw |
| `MC_YAW_WEIGHT` | 0.4 | 0–1 | Peso del yaw frente a roll/pitch al saturar |
| `MC_ROLLRATE_P` / `MC_PITCHRATE_P` | 0.0849 / 0.0840 | 0.01–0.5 | Salida de autotune, volada el 2026-07-01 |
| `MC_YAWRATE_P` | 0.1198 | 0–0.6 | Igual |
| `MC_AT_EN` | **0** ✅ | 0 off · 1 on | Autotune desactivado. No pinta nada en un test indoor |
| `SENS_BOARD_X_OFF` / `Y_OFF` | **0.364 / 0.210°** ✅ | deg | Nivelación de horizonte. En 0 el dron acelera solo en hover — medido ~1° de error antes de calibrar |

---

## F. Diagnóstico — lo que puedes analizar después

| Param | Actual | Opciones | Por qué importa |
|---|---|---|---|
| `SDLOG_MODE` | **2** ✅ | −1 off · 0 al armar · 1 boot→desarme · 2 boot→apagado · 3 AUX1 · 4 1er armado→apagado | ⚠️ **El modo 1 para de grabar en el primer desarme.** Por eso el vuelo del accidente no tiene log. **Requiere reboot** |
| `SDLOG_PROFILE` | **3** ✅ | bitmask: b0 default · b1 **estimator replay** · b2 térmica · b3 sysid · b4 alta tasa… | El bit 1 registra innovaciones y entradas del EKF2 — sin él no se puede saber **por qué** el EKF rechazó una medida. **Requiere reboot** |

### Transporte del sensor (no son parámetros)

El MTF-01P va en **TEL4 / UART8 (`/dev/ttyS7`)** a 115200, protocolo `Mavlink_PX4`. En este
firmware `MAV_1_CONFIG=104` **no funciona** (solo declara GPS1 y TEL1): se arranca desde
`/fs/microsd/etc/extras.txt` con `mavlink start -d /dev/ttyS7 -b 115200 -m minimal`.
Detalle en [`INTEGRACION_MTF-01P_FLOW_LIDAR.md`](INTEGRACION_MTF-01P_FLOW_LIDAR.md).

Radio de telemetría: `MAV_0_CONFIG=101` (TEL1), `SER_TEL1_BAUD=57600`, `MAV_0_RATE=1200`.

---

## Pendientes

| Param | De | A | Motivo |
|---|---|---|---|
| `COM_FLTMODE1` | 7 (Offboard) | **2 (Position)** | Position no está en ningún slot; Offboard sin flujo de datos da failsafe |
| `EKF2_EV_DELAY` | 0 ms | medir | Latencia del SLAM 2D. Sin medir no se puede fusionar EV con garantías |

### Aplicado el 2026-09-17 (por USB, `set_params.py`, verificado y guardado)

`EKF2_HGT_REF` 2→**0** · `EKF2_RNG_CTRL` 2→**1** · `EKF2_RNG_A_HMAX` 12.0→**1.5** ·
`EKF2_MIN_RNG` 0.10→**0.17** · `EKF2_RNG_POS_X/Z` **0.055 / 0.020** · `EKF2_OF_POS_X/Z` **0.055 / 0.018** ·
`EKF2_EV_POS_Z` **−0.114** · `COM_RC_OVERRIDE` 1→**3** · `COM_RCL_EXCEPT` 4→**0**.

FC reiniciado después (`EKF2_HGT_REF` es `@reboot_required`) y valores releídos: persisten todos.
Estado del estimador en tierra tras el reinicio: `filter_fault_flags 0`, `innovation_check_flags 0`,
`dist_bottom 0.170` (antes quedaba clavado en 0.100 por el `MIN_RNG` viejo), `xy_valid true`,
`solution_status_flags 302` — el único bit en cero que importa es el **0 (`attitude`)**, por
`yaw_align=false`: es el bloqueo de yaw EV, no un problema de esta tabla.

## La limitación que no se arregla con parámetros

**El hover indoor con flujo óptico solo es viable por debajo de ~1.5 m.** El LiDAR satura en
torno a 2.4 m (medido: −5% de error a 1 m, **−29% a 3 m**, y nunca superó 2.44 m en ningún log
de vuelo). Sin rango fiable no hay estimado de terreno válido, y sin terreno **el flujo deja de
fusionar** — así que el techo del LiDAR limita también la posición horizontal, no solo la altura.

Para subir más hace falta el LiDAR 3D de la siguiente fase.

---

## Referencias

- [`CONEXION_MAVLINK_SCRIPTS.md`](CONEXION_MAVLINK_SCRIPTS.md) — cómo leer y escribir estos parámetros
- [`reports/2026-09-04_fc2-vendor-1143-mtf01p-migracion.md`](../reports/2026-09-04_fc2-vendor-1143-mtf01p-migracion.md) — de dónde salen
- [`DIAGNOSTICO_RUIDO_MOTORES_YAW.md`](DIAGNOSTICO_RUIDO_MOTORES_YAW.md) — el incidente de `MC_AIRMODE`
