# Reporte: MTF-01 (flujo óptico + rango) no valida para hold de posición indoor

**Fecha:** 2026-07-23
**Autor / origen:** RPi companion
**Estado:** 🔄 en progreso (raíz: interferencia mag → mag-free, persiste tras recalibrar)

**Contexto:** PX4 v1.17.0 (main, commit `82e3322e0cf0afc9ad640f37a0a8b639077b3fa4`,
firmware custom HKUST_NXT_DUAL, recién reflasheado con mods de board que
reubicaron el sensor MTF-01 a TEL4/UART8). Companion: Raspberry Pi 4, ROS 2
Jazzy, comunicación FC↔RPi vía uXRCE-DDS ya verificada y funcionando
(ver `px4_drone/docs/offboard_control.md` §10 para esa parte, ya resuelta).

**Objetivo bloqueado:** primer test de despegue indoor (`takeoff_position_hold_indoor`)
— arma, sube a una altura objetivo, mantiene posición, aterriza solo. El nodo
exige `vehicle_local_position.{xy_valid, z_valid, v_xy_valid, dist_bottom_valid}`
todos en `true` antes de intentar despegar (chequeo de seguridad, por diseño).
Hasta ahora **nunca se llegó a completar ese chequeo de forma confiable**.

---

## 1. Síntoma observado

Monitoreando `/fmu/out/vehicle_local_position_v1` en vivo mientras se mueve el
dron a mano sobre un banco de pruebas:

| Momento | dead_reckoning | xy_valid | v_xy_valid | dist_bottom_valid | x / y (m) | Notas |
|---|---|---|---|---|---|---|
| Dron quieto, ~10cm de una mesa, cerca del borde | — | true | true | **false** | ~0 | Lidar viendo dos superficies (mesa+piso) por estar cerca del borde → lecturas saltando 1.15m↔0.17m |
| Recolocado lejos del borde, superficie única, 10-50cm | — | true | true | **false** | ~0, estable | Variancia de `dist_bottom` bajando (0.017→0.004) pero nunca cruza a `valid=true` |
| Tras reinicio del FC, pocos segundos después de bootear | **true** | true | true | false | **x=-41.5, y=-4.8** | Drift enorme en <30s con el dron quieto — el estimador estaba en dead-reckoning (solo IMU) pese a `xy_valid=true` |
| Con **mucha luz de laboratorio**, dron quieto | **false** | true | true | false | ~0, estable | Mejoró: el flujo óptico sí aporta datos con buena luz |
| Se levanta el dron rápido (movimiento) | **true** | **false** | **false** | false | salta a -2.97 / 1.17 | Pierde tracking óptico ante movimiento rápido |
| Mantenido quieto tras eso, esperando que recupere | **true** (no se recupera) | false | false | false | **x=160, y=85** (!) | No vuelve a enganchar el flujo óptico; el drift sigue creciendo sin control |

`heading_good_for_control` estuvo en **`false` en todos los casos observados**,
sin excepción.

## 2. Lectura directa del sensor (consola MAVLink, `listener sensor_optical_flow`, dron apoyado en el piso)

```
TOPIC: sensor_optical_flow
 sensor_optical_flow
    timestamp: 459349470 (0.007089 seconds ago)
    device_id: 11665678 (Type: 0xB2, MAVLINK:1 (0x01))
    pixel_flow: [0.00000, 0.00000]
    delta_angle: [0.00000, 0.00000, 0.00000]
    distance_m: 0.00000
    integration_timespan_us: 10000
    error_count: 0
    max_flow_rate: nan
    min_ground_distance: nan
    max_ground_distance: nan
    delta_angle_available: False
    distance_available: False
    quality: 60
    mode: 0
```

Puntos clave de esta lectura:
- **`distance_available: False`, `distance_m: 0.00000`** — el canal de
  distancia/rango del propio MTF-01 no está entregando dato, pese a que
  `vehicle_local_position.dist_bottom` (la salida ya fusionada por EKF2) SÍ
  mostraba valores no-cero variables (0.10 – 1.15 m) en otros momentos. Esto
  sugiere que el `dist_bottom` fusionado viene de **otra fuente de rango**
  distinta al canal de distancia integrado del MTF-01 (a confirmar: revisar
  qué rangefinder está realmente seleccionado/activo — parámetros
  `EKF2_RNG_*`, `SENS_EN_*` según corresponda al setup).
- **`quality: 60`** — calidad de flujo óptico moderada/baja. Sospecha
  principal: si el umbral mínimo configurado en el FC (parámetro típico
  `EKF2_OF_QMIN`, verificar nombre exacto en este firmware) es mayor a 60,
  el EKF2 puede estar **descartando intermitentemente** las muestras de
  flujo, lo que encajaría con las caídas a `dead_reckoning: true` apenas hay
  movimiento (el flujo deja de ser "suficientemente bueno" bajo movimiento
  más rápido, que es cuando más se necesita).
- `delta_angle_available: False` — sin compensación de giro propia del
  sensor (puede ser esperado si se usa el giro del FC en su lugar, pero
  vale confirmarlo).

## 3. Hipótesis a investigar

1. **Umbral de calidad de flujo óptico demasiado exigente para las
   condiciones reales.** Revisar `EKF2_OF_QMIN` (o el parámetro equivalente
   en esta versión/fork de PX4) contra la calidad real observada (~60-78,
   posiblemente más baja bajo movimiento). Considerar bajar el umbral con
   cautela, o mejorar las condiciones (más textura en la superficie, más luz,
   altura de operación dentro del rango óptimo del sensor).
2. **Canal de distancia del MTF-01 no configurado/no seleccionado.**
   `distance_available: False` constante en el sensor crudo — revisar cableado
   I2C/UART del rango dentro del módulo MTF-01, y los parámetros de PX4 que
   seleccionan qué rangefinder alimenta `dist_bottom` (puede que el sistema
   esté (mal) usando otro rangefinder o ninguno, y lo que se ve en
   `vehicle_local_position.dist_bottom` sea ruido/una fuente distinta).
3. **`heading_good_for_control` nunca en `true`.** Persiste incluso tras
   desactivar el magnetómetro (ver §3.5) — revisar requisitos exactos de este
   flag en la versión de PX4 usada, y confirmar que `EKF2_MAG_TYPE` realmente
   quedó en "None" (no solo desconectado físicamente).
4. **Sensibilidad a movimiento rápido.** El flujo óptico se pierde con
   movimientos de mano relativamente bruscos — esperable hasta cierto punto
   en estos sensores, pero la magnitud del drift resultante (decenas de
   metros en segundos) sugiere que, una vez perdido el tracking, el sistema
   no tiene una buena estrategia de recuperación/rechazo de esas muestras
   corruptas (revisar si hay un timeout/gate de reingreso a dead-reckoning
   configurado de forma muy permisiva).
5. **El offset de posición no se resetea al salir de dead-reckoning** (ver
   §3.5) — riesgo de seguridad real: el nodo de despegue solo mira los
   booleanos `*_valid`, no la magnitud del error acumulado. Investigar si
   existe un parámetro que fuerce un reset del EKF al recuperar el aiding
   (algo como reiniciar el origen local en vez de arrastrar el error), y/o
   agregar un chequeo adicional en `takeoff_position_hold_indoor` que
   rechace despegar si hubo un `xy_reset_counter`/drift reciente sospechoso.

**Recomendaciones prácticas para la próxima sesión de tuning:**
- Reiniciar el FC justo antes de cualquier intento nuevo, para partir de
  `x=y=0` sin arrastre.
- Si es posible, probar con el dron en un soporte/trípode fijo en vez de
  sostenido a mano, para eliminar el temblor como variable — ayuda a
  distinguir "el sensor no engancha con movimiento suave real" de "se pierde
  por vibración/temblor de mano".
- Revisar por qué `distance_available` del MTF-01 nunca es `True` — puede
  ser la pieza más fácil de arreglar y probablemente ayude a que
  `dist_bottom_valid` finalmente pase a `true`.

## 3.5 Segunda ronda (tras calibrar sensores y desactivar el magnetómetro para indoor)

Se recalibraron los sensores y se desactivó el magnetómetro para las pruebas
indoor. Se repitió el monitoreo en vivo de `vehicle_local_position_v1`:

| Momento | dead_reckoning | xy_valid | dist_bottom_valid | x / y (m) | Notas |
|---|---|---|---|---|---|
| Dron quieto, ~10cm, tras recalibrar | false | true | false | ~0.01, -0.007 | Buen arranque, estable |
| Subido con cuidado a altura normal | **true** | **false** | false | -0.48 / 0.44 | Pierde tracking al moverlo, igual que antes pero con menos drift que la primera ronda |
| Mantenido quieto, esperando recuperar | true (no se recupera aún) | true | false | **-10.5 / 4.8** | `xy_valid` vuelve a `true` pero **con `dead_reckoning` todavía en `true`** — es decir, el flag de validez no garantiza que el flujo óptico esté realmente aportando |
| Sigue quieto | true | false | false | **-34.2 / 11.3** | Empeora más |
| Chequeo de `sensor_optical_flow` crudo en esta posición | — | — | — | — | `quality: 78` (subió de 60), `distance_available: False` sigue igual, `pixel_flow: [0.017, 0.0]` (no cero, dron no perfectamente inmóvil en mano) |
| Momento posterior | **false** (recuperó) | true | false | **-55.1 / 16.4** (!) | Volvió a `dead_reckoning: false`, pero el offset acumulado **no se resetea solo** — sigue arrastrando el error de los ~30s en dead-reckoning |

**Hallazgo crítico nuevo:** cuando el estimador sale de `dead_reckoning`, el
offset de posición acumulado durante el episodio de dead-reckoning **no se
corrige/resetea automáticamente** (al menos no en la ventana observada) —
queda un error de decenas de metros en `x`/`y` mientras `xy_valid` puede
volver a marcar `true`. **El nodo `takeoff_position_hold_indoor` solo chequea
los booleanos de validez, no la magnitud del error acumulado** — con este
comportamiento, el nodo podría considerar "todo OK" y despegar usando un
origen de referencia completamente arruinado. Esto es un riesgo real
adicional a resolver (ya sea a nivel EKF2/parámetros para forzar un reset
limpio tras dead-reckoning, o agregando un chequeo adicional en el nodo antes
de despegar).

**Conclusión de esta ronda:** mejoró la calidad del flujo (60→78) pero el
comportamiento de fondo (pérdida de tracking al mover + drift no controlado +
no-reset del offset) sigue igual. **No se intentó el despegue real.**

## 4. Qué NO se tocó todavía

No se modificó ningún parámetro de EKF2/sensor en el FC durante esta sesión
de diagnóstico — todo lo de arriba son observaciones en vivo, sin cambios.
La recomendación fue **no intentar el despegue indoor** hasta resolver esto,
dado que el estimador de posición no es confiable de forma sostenida bajo
movimiento real (justo lo que se necesita durante un despegue/hold real).

## 5. Contexto ya resuelto (descartar)

La comunicación RPi↔FC (uXRCE-DDS) fue diagnosticada y arreglada en la misma
sesión — no es la causa de nada de lo de arriba, se menciona solo para
descartar que sea un problema de comunicación:
- `px4_msgs` debe alinearse al commit fuente del firmware (no a la fecha de
  build).
- `MicroXRCEAgent` debe compilarse v2.4.3 con Fast-DDS/Fast-CDR del sistema
  (evita mismatch de versión mayor con ROS 2 Jazzy).
- `ROS_DOMAIN_ID` debe coincidir con `UXRCE_DDS_DOM_ID` del FC (ambos en `0`
  en este setup).

Detalle completo en `/home/kevin/drone_ws/src/px4_drone/docs/offboard_control.md`
sección 10.
