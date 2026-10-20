# Parámetros del FC para vuelo suave: estado real y qué tocar

**Fecha:** 2026-10-20 · **Fuente:** volcado completo del FC#2 por USB (903/903 parámetros)
**Copia de seguridad:** [`backups/backup_fc_2026-10-20_pre-optimizacion.params`](../backups/backup_fc_2026-10-20_pre-optimizacion.params)
**Estado:** análisis. **No se ha escrito ningún parámetro.**

Complementa al [plan de ajuste por capas](2026-10-19_plan_tuning_takeoff_hold_land.md), que
dice *qué* revisar en cada capa; esto dice *qué hay ahora* en este FC y *qué cambiaría*, con
el valor actual delante y el motivo verificado en el fuente del tag `v1.14.3`.

---

## 1. Dos cambios de seguridad desde septiembre que no estaban documentados

El volcado comparado con `backup_fc_2026-09-07.params` da **29 parámetros cambiados**. Dos de
ellos cambian cómo se comporta el dron en las pruebas, y van en **sentido contrario** a lo que
estaba escrito:

| Parámetro | 2026-09-07 | **Hoy** | Qué significa ahora |
|---|---|---|---|
| `COM_RC_OVERRIDE` | 1 | **3** | El bit 1 es *override durante Offboard*. **Mover los sticks más del 30 % (`COM_RC_STICK_OV`) saca de Offboard.** Antes solo valía en modos auto |
| `COM_RCL_EXCEPT` | 4 | **0** | El bit 2 es *excepción en Offboard*. **Perder el RC ya dispara failsafe en Offboard**, y `NAV_RCL_ACT=3` = LAND. Antes se ignoraba |

Verificado en `commander_params.c` del tag. Consecuencias prácticas:

- **Bueno:** ya hay escape por sticks, que es más directo que el switch ch6/ch8. La
  [memoria de escape por RC](../README.md) estaba obsoleta y queda corregida.
- **A vigilar en las pruebas:** un roce accidental del stick durante los 30 s de hold **aborta
  la corrida**, y un microcorte del enlace RC provoca un LAND automático. Las dos cosas hay que
  anotarlas como causas de aborto válidas en el protocolo, para no atribuirlas al controlador.

Otros cambios del mismo diff, ya conocidos o inocuos: la familia `EKF2_*` de la configuración
indoor (`HGT_REF 2→0`, `RNG_CTRL 2→1`, `RNG_A_HMAX 12→1`, `EV_CTRL 0→9`, offsets de montaje),
`CA_ROTOR*_P*` 0.17→0.159 (brazo real), los `CAL_ACC*_*OFF` (**recalibración de acelerómetros**,
relevante para el reporte de deriva de z), los `UXRCE_DDS_*` nuevos y los `SENS_FLOW_*` que
desaparecieron.

---

## 2. Lo que PX4 le hace a nuestros setpoints durante el despegue

Esto no estaba en ningún documento y afecta directamente al MPC. En
`MulticopterPositionControl.cpp` y `Takeoff/Takeoff.cpp` del tag:

La máquina de despegue **sí actúa en Offboard, también con setpoints de aceleración**: el
`want_takeoff` se activa con el dron armado y `acceleration[2]` finito (líneas 442-461).
Los estados son:

```
disarmed → spoolup → ready_for_takeoff → rampup → flight
           (COM_SPOOLUP_TIME = 1.0 s)     (MPC_TKO_RAMP_T = 3.0 s)
```

Y entonces:

- **Mientras el estado sea menor que `rampup`** (es decir, durante el segundo que dura
  `spoolup`), nuestro setpoint se **descarta entero** y se sustituye por
  `acceleration = (0, 0, 100)` m/s² hacia abajo, y se resetean los integradores. Es correcto
  —no debe haber empuje antes de pedir despegue— pero significa que **las primeras
  aceleraciones que calcula el MPC no se aplican**, mientras su tercer estado (la última
  aceleración comandada) sí las registra. Es un desajuste de inicialización a documentar.
- **Durante `rampup`** (3 s con el valor actual): el límite de inclinación es
  `MPC_TILTMAX_LND` = **12°**, no `MPC_TILTMAX_AIR` = 25°; y como `flying` es falso,
  `setHoverThrust(MPC_THR_HOVER)` fuerza 0.30 y **el estimador de empuje de hover
  (`MPC_USE_HTE=1`) no entra**.
- El ciclo completo a 0.8 m sube en ~1 s. Con `MPC_TKO_RAMP_T = 3.0`, **todo el despegue y el
  principio del hold ocurren en `rampup`**: con 12° de inclinación máxima y el empuje de hover
  clavado en el parámetro en vez de estimado.

La rampa en sí (`updateRamp`) limita la **velocidad vertical**, así que con velocidad en `NaN`
no recorta nuestra aceleración. El efecto real de `MPC_TKO_RAMP_T` en nuestro caso es el
**tiempo que PX4 tarda en considerarse en vuelo**, con lo que eso arrastra.

---

## 3. Parámetros a cambiar, por efecto esperado

Ninguno está escrito. El orden es el de relación beneficio/riesgo.

### 3.1 `THR_MDL_FAC`: 0.0 → medir, probablemente 0.3

El empuje de una hélice va con el cuadrado del acelerador, no lineal. Con `THR_MDL_FAC = 0`
PX4 usa el mapeo lineal, así que **la ganancia efectiva de todo el lazo exterior cambia con el
acelerador**: la misma petición de aceleración da distinta respuesta a 0.25 que a 0.40 de
empuje. Afecta igual al PID y al MPC, y es justo lo que estropea un seguimiento suave de
aceleración.

Es el cambio de mayor efecto y el único que mejora las dos variantes a la vez. **Requiere
medida**, no un valor copiado: se obtiene del banco de empuje o del log comparando empuje
comandado contra aceleración medida.

### 3.2 `MPC_TKO_RAMP_T`: 3.0 → ~0.8 s

Por el §2: saca a PX4 de `rampup` justo después de separarse, con lo que se recupera el límite
de inclinación de 25° y entra el estimador de empuje de hover durante el hold, que es donde se
miden las métricas. ⚠️ No bajarlo mucho más: el plan advierte que una rampa demasiado rápida o
demasiado lenta prolonga el contacto con el suelo y favorece un vuelco. 0.8 s deja margen sobre
el segundo de `spoolup`.

### 3.3 `MC_ROLLRATE_D` y `MC_PITCHRATE_D`: ≈0 → subir con cuidado

| | Actual | Nota |
|---|---|---|
| `MC_ROLLRATE_D` | 0.0000158 | prácticamente cero |
| `MC_PITCHRATE_D` | **0.0** | exactamente cero |
| `MC_ROLLRATE_P` / `_I` | 0.0849 / 0.0931 | plausibles para 7" 6S |
| `MC_PITCHRATE_P` / `_I` | 0.0840 / 0.1023 | ídem |

**Sin término D no hay amortiguamiento de la oscilación de tasa**, y eso se ve como sobrepaso
en la respuesta a cualquier escalón de actitud. Es el lazo más interno, así que su efecto llega
a todo lo de arriba.

⚠️ El D amplifica ruido. Hay que subirlo **en pasos**, mirando en el log la señal de salida de
los motores, y sin tocarlo el mismo día que otra familia. `IMU_DGYRO_CUTOFF` ya está en 20 Hz,
que ayuda. Y conviene verificar antes si el firmware de fábrica trae autotune disponible, en
vez de ir a mano.

### 3.4 `EKF2_EV_DELAY`: 0.0 → medir (probablemente 50-150 ms)

No es un parámetro de control, pero se disfraza de mal ajuste. La pose del SLAM 2D viene de un
LiDAR a ~10 Hz, pasa por `slam_toolbox` y por el puente a 20 Hz: su latencia real no es cero.
Con `EKF2_EV_DELAY = 0` el EKF la fusiona como si fuera del instante actual, lo que mete
**desfase** en la posición estimada — y un controlador que persigue una posición desfasada
oscila aunque esté bien ajustado.

El nodo ya publica la edad de la odometría, así que el número se puede medir en vez de
adivinar. **Hasta medirlo, no escribirlo.**

### 3.5 `EKF2_BARO_NOISE`: 3.5 → probar 6-8

Hipótesis, no hecho. Con `EKF2_HGT_REF = 0` el barómetro es la referencia de altura, y está a
79 °C con una deriva medida de 3 mm/s en tierra
([reporte](../reports/2026-10-16_baro-temperatura-deriva-z.md)). Subir su ruido declarado hace
que el EKF se apoye más en el LiDAR 1D, que a 0.8 m está dentro de su zona honesta y además
engancha por `EKF2_RNG_A_HMAX = 1.0`. Hay que comprobarlo contra el log, no darlo por bueno.

### 3.6 `IMU_GYRO_NF0_FRQ`: 0 (desactivado) → solo si el FFT muestra un pico

`IMU_GYRO_FFT_EN` ya está en 1, así que el pico de vibración se puede leer del log. Sin pico
claro, un notch solo añade retardo de fase. Y el plan es tajante: **primero la mecánica**, no
esconder vibración con filtros.

---

## 4. Lo que NO hay que tocar, y por qué

| Parámetro | Valor | Motivo |
|---|---|---|
| `MPC_JERK_MAX` 8.0 · `MPC_JERK_AUTO` 4.0 · `MPC_POS_MODE` 4 | — | Solo actúan en los FlightTask suavizados de Position/Auto. **En Offboard 1.14.3 no hay suavizado**; el setpoint entra crudo. No suavizan nada de lo nuestro |
| `MPC_ACC_*`, `MPC_*_VEL_MAX` | 3-5 m/s², 1.0 m/s | Ya están en valores de interior. Y con setpoint de aceleración PX4 **no satura** (issues 18033/18855): el recorte es nuestro |
| `MPC_Z_VEL_*_ACC`, `MPC_XY_VEL_*_ACC`, `MPC_Z_P`, `MPC_XY_P` | valores por defecto de PX4 | **Son el controlador de la variante A.** Cambiarlos antes de medir su línea base invalida la comparación A/B/C. Se tocan después, y de uno en uno |
| `CAL_*` | recién recalibrados | No volver a tocarlos sin motivo |
| `MPC_THR_HOVER` 0.30 | — | Con `MPC_USE_HTE = 1` el estimador lo corrige en vuelo. Solo importa mientras PX4 está en `rampup` (§2), que es lo que arregla 3.2 |

---

## 5. Orden de aplicación y cómo verificar cada uno

Una familia por iteración, con un volcado de parámetros y tres ciclos de referencia antes y
después, según el [plan](2026-10-19_plan_tuning_takeoff_hold_land.md) §2 y §7.

1. **Tres ciclos de referencia sin tocar nada**, para medir la dispersión. Sin esto no se puede
   afirmar que ningún cambio mejore algo.
2. `MPC_TKO_RAMP_T` → se verifica en el log con `takeoff_status`: el estado debe llegar a
   `flight` justo después de separarse, y la inclinación máxima permitida pasar de 12° a 25°.
3. `EKF2_EV_DELAY`, una vez medido → se verifica en innovaciones y rechazos del EKF, no en la
   sensación de vuelo.
4. `THR_MDL_FAC`, una vez medido → se verifica con empuje comandado frente a aceleración medida
   a dos niveles de empuje distintos.
5. `MC_*RATE_D` en pasos → se verifica en la respuesta de tasa a un escalón y en la salida de
   los motores, que es donde aparece el ruido amplificado.
6. `EKF2_BARO_NOISE` → se verifica en la deriva de z durante los 30 s de hold.

**Antes de cada escritura: volcado nuevo.** La copia de hoy es el punto de retorno
(`backup_fc_2026-10-20_pre-optimizacion.params`, 903 parámetros); se restaura con
`~/mavlink_tools/set_params.py` desde la Pi.

---

## 6. Qué queda fuera de este ciclo

El ciclo takeoff-hold-land a 0.8 m **no excita** roll, pitch, yaw ni movimiento horizontal, así
que no sirve para cerrar 3.3 por sí solo: hace falta una prueba específica de pequeños
movimientos, frenado y yaw. Está en el plan §1 y sigue pendiente.

Y el objetivo de **hold horizontal RMS ≤0.10 m** del plan §6 **no es verificable** con la
referencia actual: se mediría contra el propio SLAM, cuyo umbral de guarda es σ = 0.30 m. Se
registra como no verificable hasta tener una referencia independiente.
