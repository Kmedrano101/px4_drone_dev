# Reporte: vuelo offboard 2 — escape vertical a ~25 m por el LiDAR como referencia de altura

**Fecha del análisis:** 2026-09-11 · **Log:** `logs/log100v2.ulg` (519 s, 23.7 MB, 4 ciclos de armado)
**Autor / origen:** RPi companion (nodo offboard v2) + análisis del `.ulg`
**Estado:** ⛔ **casi accidente**. Mecanismo del escape vertical confirmado en vivo · cambios obligatorios antes del próximo vuelo

**Contexto:** FC#2, PX4 1.14.3 de fábrica, MTF-01P. Mismos parámetros que en el [vuelo 1](2026-09-11_offboard-vuelo1-flujo-failsafe.md):
`EKF2_HGT_REF=2`, `EKF2_RNG_CTRL=2`, `COM_RC_OVERRIDE=1`, `COM_RCL_EXCEPT=4`.
Nodo v2 de la Pi: despegue **relativo de +2.0 m** sobre la z estimada, hold y `NAV_LAND` al final.

---

## 1. Resumen por sesión

| Sesión | Ventana | Qué pasó |
|---|---|---|
| 1 | 92-106 s | La Pi arma en OFFBOARD con **`z_sp = 0.00`** (en el suelo) → no despega → desarme automático a los 10 s (`COM_DISARM_PRFLT`) |
| **2** | 238-304 s | **Escape vertical a ~25 m**, toma de control, LAND de la Pi que pisa al piloto, 20 s de oscilaciones de ±23° en POSCTL, descenso casi en caída libre, kill |
| 3 | 372-374 s | Armado manual en ALTCTL con el switch, desarmado al segundo |
| 4 | 410-437 s | Sin reboot desde la sesión 2: el canal de rango sigue roto → vuela con baro a ~2.3 m; salto de altura de +3.8 m al tocar suelo, kill, cabeceo de −21° |

## 2. Sesión 2 — el escape vertical, paso a paso

| t (s) | Modo | z estimada | LiDAR | Baro (rel.) | Salida máx. | Qué pasa |
|---|---|---|---|---|---|---|
| 243 | OFFB | −0.10 | 0.02 | 0.0 | 112 | setpoint z=−2.10 (+2.0 m) |
| 249 | OFFB | −1.24 | 1.16 | 1.64 | 756 | subida normal |
| 251 | OFFB | −1.68 | **1.57** | 3.47 | 778 | pico del LiDAR |
| 252 | OFFB | −1.64 | **1.44** | 4.44 | 833 | **el LiDAR baja mientras el dron sube** |
| 253 | OFFB | −1.51 | **1.25** | 5.77 | 863 | el EKF cree que desciende → más empuje |
| 254 | OFFB | −1.19 | **0.54** | 8.27 | 911 | lazo positivo |
| 254.5 | **STAB** | | 0.07 | ~10 | | el piloto toma el control por switch |
| 255 | STAB | −2.27 | 0.07 | **12.0** | **1806** | **gas a +0.77** → ~85% de empuje |
| 256 | STAB | | 0.02 | **22.1** | 720 | gas a −1.00 |
| 257 | STAB | | 0.02 | **25.0** | 451 | techo del escape |
| 258.0 | **LAND** | | | 24.2 | | **la Pi manda `NAV_LAND` y pisa el STAB del piloto** |
| 258.03 | **POSCTL** | ~−0.1 | 0.02 | 22 | | override de sticks en modo auto (bit 0 de `COM_RC_OVERRIDE`) |
| 269.28 | POSCTL | **−0.04 → −21.62** | 0.02 | 19.8 | | **cambio de instancia EKF0→EKF1** (ver [reporte del estimador](2026-09-11_estimador-sensores-offboard.md) §1): EKF0 creía estar en el suelo |
| 270-290 | POSCTL | −21 → −11 | 0.02 | 26 → 18 | | **roll/pitch oscilando ±23°** (límite `MPC_TILTMAX_AIR=25`) |
| 292.4 | STAB | | | 13.3 | | el piloto pasa a STAB |
| 293-294 | STAB | | 0.47→1.37 | **10.6 → 3.9** | 273 | gas a −1: **caída casi libre de 6.7 m en 1 s** |
| 294 | STAB | | 1.37 | 3.9 | 804 | gas a +0.82: recogido a ~4 m |
| 298 | STAB | | 0.05 | −0.3 | | en el suelo |
| 299.1 | STAB | | | | 0 | kill · aviso de batería de 255 a 304 s |

### El mecanismo

Con `EKF2_HGT_REF=2` el LiDAR es la referencia de altura. Pasado ~1.6 m el sensor pierde el
suelo, pero **no se queda saturado: su lectura baja** (1.57 → 1.44 → 1.25 → 0.54 → 0.02).
El EKF la sigue y cree que el dron **desciende** mientras sube. El controlador offboard
compensa metiendo más empuje, el dron se aleja todavía más del rango del sensor, y se cierra un **lazo de realimentación positiva**: de 1.6 m a 8 m en 3 s.

Dos agravantes:
- Las lecturas erróneas **parecen válidas**: 1.44 m, 1.25 m, todas por debajo de `EKF2_RNG_A_HMAX`. Ningún filtro de altura máxima las descarta.
- Con el rango como referencia, el chequeo de consistencia cinemática no tiene una velocidad vertical independiente con la que contrastar la lectura. `cs_rng_fault` no se activó hasta 268 s, 17 s tarde.

Es **exactamente el mecanismo que se infirió para el [accidente del árbol](2026-09-04_fc2-vendor-1143-mtf01p-migracion.md)**, que no quedó grabado. Aquí sí está en el log.

### Tres fallos que convirtieron un escape en un casi accidente

1. **El gas estaba arriba durante el offboard** (+0.98, y +0.77 al cambiar de modo). Al pasar a STAB el stick manda directamente: ~85% de empuje y 10 m más en un segundo. Es la trampa del gas documentada en memoria.
2. **La Pi mandó `NAV_LAND` sin mirar quién tenía el control.** Sacó al piloto de STAB y, al detectar movimiento de sticks, PX4 lo dejó en POSCTL: justo el modo que depende de la estimación rota.
3. **POSCTL con altura y terreno rotos**: el EKF creyó estar en el suelo a 22 m y luego saltó a −21.6 m. Con una HAGL errónea, el flujo óptico da velocidades erróneas y el controlador de posición oscila en el límite de inclinación.

## 3. Sesión 4 — el estado roto sobrevive entre vuelos

No hubo reboot entre las sesiones 2 y 4 (`SDLOG_MODE=2`: log continuo). En el suelo, antes de despegar:
`cs_rng_hgt=0`, **innovación del rango de 21.7 m** con el LiDAR leyendo 0.02 m. El dron voló con la altura
del barómetro, subió a ~2.3 m (el objetivo relativo de +2.0 m) y, tras el `NAV_LAND` de la Pi, al tocar
suelo la z saltó **+3.8 m**: fue un **cambio de instancia EKF1→EKF0** a 430.6 s, no un reset (ver [reporte del estimador](2026-09-11_estimador-sensores-offboard.md) §1). Kill a 431.45 s, cabeceo de −21°, y quedó apoyado con roll de 8.5°.

## 4. Lo que el vuelo 2 enseña sobre el vuelo 1

- **La calidad del flujo fue buena a todas las alturas**: 84-110 hasta 2 m, 0% de muestras rechazadas. En el vuelo 1 era 12-14 por encima de 0.5 m. **El problema del vuelo 1 era del entorno** (suelo, luz), no de la altura.
- La vibración fue incluso mayor (acelerómetro 3.1 de media, 6.5 de pico) y el flujo funcionó, así que **la vibración no era la causa** en el vuelo 1.
- ⚠️ **Queda invalidada la recomendación del vuelo 1 de mantener `HGT_REF=2`.** El rango es más preciso que el barómetro *dentro* de su rango, pero como referencia provoca el escape en cuanto el setpoint o una perturbación saca al dron de ese rango.

## 5. Cambios obligatorios antes del próximo vuelo

**Parámetros:**

| Param | Ahora | Poner | Motivo |
|---|---|---|---|
| `EKF2_HGT_REF` | 2 | **0** (baro) | El barómetro no se "cae" fuera de rango; el chequeo cinemático del rango tiene una vz independiente |
| `EKF2_RNG_CTRL` | 2 | **1** (condicional) | Rango como ayuda cerca del suelo |
| `EKF2_RNG_A_HMAX` | 12 | **1.2** | Techo fiable del sensor con margen |
| `COM_RC_OVERRIDE` | 1 | **3** | Que los sticks saquen también del offboard |
| `COM_RCL_EXCEPT` | 4 | **0** | Failsafe por pérdida de RC también en offboard |

**Nodo de la Pi:**
1. **Limitar el setpoint de altura (≤1.2 m) y hacerlo absoluto**, no relativo a una z estimada que puede estar desplazada. La sesión 1 armó con z=0 y la 4 salió de una z de partida de −0.46 m con el dron en el suelo.
2. **No mandar `NAV_LAND` si `nav_state != OFFBOARD`**: si el piloto ha tomado el control, el nodo no toca nada.
3. Dejar de publicar el heartbeat offboard ante failsafe o toma de control (ver vuelo 1 §3).

**Procedimiento:**
4. **Gas centrado durante todo el offboard.** En la sesión 2 estaba a +0.98, y en la 4 a −0.55 (en esa sesión, un paso a STAB lo habría dejado caer).
5. **Reboot del FC entre vuelos** hasta tener el EKF estable. Un estado de rango roto sobrevive al desarme.
6. **Techo físico**: probar solo en un espacio con techo o en exterior con margen. Sin GPS no hay geofence ni `LNDMC_ALT_MAX` (ver `docs/PARAMETROS_INDOOR.md` §C).

## 6. Por qué hay tanta deriva a ≤2 m en campo

### El LiDAR mide de menos desde ~1 m, no solo al pasar de 1.6 m

Relación entre la lectura del LiDAR y la altura real (baro), en las dos subidas:

| Altura real (baro) | S4 LiDAR / real | S2 LiDAR / real |
|---|---|---|
| ~0.55 m | 0.94 | — |
| ~0.85 m | — | 0.77 |
| ~1.3 m | 0.74 | — |
| ~1.7-1.8 m | 0.67 | 0.68 |
| ~2.2 m | 0.57 | — |
| ~2.5 m | 0.49 | 0.57 |
| >3 m | — | 0.44 → 0.06 (pierde el suelo) |

A **2 m el LiDAR lee ~1.2 m: un 40% de menos**. En exterior el techo útil es más bajo que en el
barrido de interior (allí, a 3 m, leía 2.14 m).

### Cómo se convierte ese error en deriva horizontal

El flujo óptico mide una **velocidad angular**. El EKF la pasa a velocidad multiplicándola por la
altura sobre el suelo (HAGL), y el estimador de terreno de la 1.14.3 saca esa HAGL del LiDAR
(`EKF2_TERR_MASK=3`). Si la HAGL es un 40% baja, **la velocidad estimada también lo es**: el EKF
ve menos movimiento del que hay, el controlador de posición corrige de menos, y la deriva real
es ~1.7× la estimada.

⚠️ Por eso **`EKF2_HGT_REF=0` evita el escape vertical, pero no la deriva horizontal a 2 m**: la HAGL
del flujo sigue saliendo del LiDAR. Con este sensor, el hold por flujo solo es preciso por debajo
de **~1.0-1.2 m**, donde el error del LiDAR está en torno al 5%.

### Otras fuentes, medidas

| Fuente | Medida | Peso |
|---|---|---|
| Sesgo del acelerómetro estimado | **+0.35 m/s² en X** (S4) | Alto. Cuando el flujo se rechaza (dead-reckoning el **34.5%** del tiempo armado), el error crece como ½·b·t²: 0.7 m en 2 s, 4.4 m en 5 s. Probables causas: temperatura (IMU a 74 °C en banco) y vibración (3.1 m/s² de media, 6.5 de pico) |
| Rumbo sin brújula | **−0.05 °/s** (0.4° en 8 s) | **Despreciable.** Descartado |
| Estado roto sin reboot | innovación del rango de 21.7 m en el suelo (S4) | Alto si no se reinicia entre vuelos |

## 7. Por qué el ciclo de la sesión 4 no terminó en desarme

`NAV_LAND` bajó a 0.6 m/s y tocó suelo a 430.5 s. En ese momento **el EKF creía estar a 1.03 m** (la
altura venía del baro, con el rango roto desde la sesión 2) y a 431.0 s la z saltó +3.8 m. El
detector de aterrizaje necesita pasar por `ground_contact` → `maybe_landed` → `landed`, cada fase
con empuje bajo y 1 s de confirmación. El empuje se quedó en ~0.30 hasta 432.5 s y no bajó a 0.05
hasta 434.5 s:

| t | ground_contact | maybe_landed | landed |
|---|---|---|---|
| 430.5 (contacto real) | 0 | 0 | 0 |
| 434.5 | 1 | 0 | 0 |
| 435.5 | 1 | 1 | 0 |
| (~436.5 previsto) | | | 1 → desarme a ~438.5 (`COM_DISARM_LAND=2`) |

El kill de 431.45 s desarmó antes, a 436.47 s (`COM_KILL_DISARM=5`). **No es un fallo del
detector: la altura errónea al tocar suelo lo retrasó ~6 s.** Con una altura correcta habría
desarmado solo.

## 8. `logs/sess168/log100.ulg` (2026-09-10, 1053 s): el offboard nunca llegó al FC

- Nunca se armó en offboard. El único armado fue de 0.8 s en ALTCTL, con el switch.
- **No hay `offboard_control_mode` ni `vehicle_command` en todo el log**: `offboard_control_signal_lost` estuvo a 1 los 17.5 minutos. El nodo de la Pi no llegó a entregar nada.
- El enlace uXRCE-DDS solo existió de **826.8 s a 915.7 s** (`No ping response, disconnecting`). En esos 89 s el FC creó sus publicadores `/fmu/out/*`, pero no recibió nada por `/fmu/in/*`.
- `614.78 s  Arming denied: high throttle`: otro intento de armar **con el gas arriba**. Es el mismo hábito de la sesión 2 del vuelo 2.

## Archivos

| Archivo | Qué es |
|---|---|
| `logs/log100v2.ulg` | log completo (23.7 MB, **por encima del umbral de 10 MB**: no commitear; queda resumido aquí) |
| `logs/sess168/log100.ulg` | sesión sin vuelo del 2026-09-10 (43.8 MB, no commitear) |
