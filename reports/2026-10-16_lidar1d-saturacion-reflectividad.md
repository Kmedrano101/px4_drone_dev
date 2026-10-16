# Reporte: el LiDAR 1D del MTF-01P se satura sobre suelo oscuro

**Fecha:** 2026-10-16
**Autor / origen:** campo (parking indoor) + RPi — `flow_range_eval.py` por USB-C
**Estado:** 🔄 causa identificada (potencia óptica / reflectividad), decisión de hardware abierta

**Contexto:** FC#2 NxtPX4v2 con PX4 1.14.3 de fábrica, MTF-01P en TEL4 hablando
MAVLink directo al FC. La altura del EKF2 sale de barómetro (`EKF2_HGT_REF=0`)
con el rango como ayuda **condicional** (`EKF2_RNG_CTRL=1`). Zona de pruebas:
parking abandonado, hormigón oscuro, sin luz.

**Objetivo bloqueado:** saber a qué altura está realmente el dron. Mientras la
lectura no sea fiable, ni el hold de altura ni la comparación PID/MPC tienen
una referencia con la que medirse.

---

## 1. Síntoma observado

La lectura del LiDAR 1D se queda corta y la diferencia **crece con la altura**:
no es un offset ni un factor de escala, es una curva que se aplana.

## 2. Lecturas directas

Sensor sujeto a mano sobre el suelo del parking, altura real medida con
distanciómetro láser (±2 cm), lectura tomada con `monitor_sensors.py`:

| Altura real | Lectura | Error | Pendiente local |
|---|---|---|---|
| 1.00 m | 0.961 m | −3.9 % | 0.94 (desde 0.17 m) |
| 1.50 m | 1.251 m | −16.6 % | 0.58 |
| 1.75 m | 1.405 m | −19.7 % | 0.62 |
| 2.00 m | 1.513 m | −24.3 % | 0.44 |

Ruido en la zona buena (≤1 m): **9 mm**. El flujo óptico, en cambio, va
**excelente** entre 1 y 1.5 m: calidad 108–120 y deriva de 1 mm/s.

Ajuste de la curva (`scripts/` → ver §6):

```
lectura = 2.53 · (1 − e^(−real / 2.21))        residuo 2.1 cm
```

Puntos clave de la lectura:
- La pendiente cae de 0.94 a 0.44: el sensor pierde sensibilidad progresivamente.
- La asíntota es **2.53 m**. Por mucho que suba el dron, la lectura no pasa de ahí.
- Por debajo de 1 m el sensor es honesto: error ≤4 cm, dentro de su ruido.

## 3. Causa

**No está descalibrado: se queda sin señal.** El techo de 2.53 m coincide con la
especificación del TF-Luna (el telémetro que lleva dentro el MTF-01P) **para un
blanco del 10 % de reflectividad: 2.5 m**. El hormigón oscuro del parking es
exactamente ese caso. El sensor está cumpliendo su hoja de datos; lo que falta
es potencia óptica para ese suelo.

Hipótesis descartadas:
- *Calibración o escala mal puesta* — un error de escala daría una recta, no una
  exponencial saturante.
- *Problema del driver o del transporte MAVLink* — el ruido en la zona buena es
  de 9 mm y la lectura es estable; el camino de datos está sano.

## 4. Consecuencias (importan más que el hallazgo)

1. **La zona útil del sensor es ≤1 m**, idealmente 0.8 m. Ahí el error es de
   2–4 cm y sirve como referencia de altura.
2. **`EKF2_RNG_A_HMAX=1.5` está mal.** Deja al EKF fusionar lecturas con hasta
   17 % de error. Debe bajar a **1.0**. Con la histéresis de
   `range_height_control.cpp:220` la ayuda engancha por debajo de 0.7 × 1.0 =
   **0.70 m** y se mantiene hasta 1.0 m: un despegue a 0.8 m pasa por la zona de
   engache durante la subida, así que la ayuda entra y se queda.
3. **Corrige un dato del log 158.** Aquel hover, que se dio por "a 1 m", estaba
   en realidad a **1.66–1.82 m reales** (invirtiendo la curva sobre la lectura
   registrada). El reporte `2026-09-18_takeoff-ev-log158-caida-stabilized.md`
   decía "altura y LiDAR 1D bien"; lo correcto es que el LiDAR estaba
   saturando y el dron volaba más alto de lo que se creía.
4. **Invertir la curva amplifica el ruido**: factor 1.1× a 0.5 m, pero 1.7× a una
   lectura de 1.2 m. Compensar solo tiene sentido hasta ~1.2 m.

## 5. Opciones, con su coste real

| Opción | Alcance | Coste | Pega |
|---|---|---|---|
| **Volar a ≤1 m** (elegida para las primeras pruebas) | 0.8 m | 0 € | Limita la envolvente de vuelo |
| Compensar la curva en software | ~1.2 m | trabajo | El MTF-01P habla MAVLink **directo al FC**: habría que moverlo a la Pi y reemitir un `DISTANCE_SENSOR` corregido. Más latencia y una pieza más que falla |
| **LightWare SF11/C** | 120 m, afirma independencia de color/textura | ~300 € | — |
| **Garmin LIDAR-Lite v3HP** | 40 m | ~150 € | — |
| **Benewake TF02-Pro** | 40 m, UART | ~100 € | Único fabricante que publica cifras a 10 % de reflectividad |
| **Radar uLanding** | — | — | La reflectividad óptica deja de importar; útil si además hay polvo |

El conector **GPS1 del FC#2 expone I2C** (SDA/SCL/5V/GND), y el firmware de
fábrica ya trae los drivers `lightware_laser_i2c`, `ll40ls`, `tfmini`,
`tf02pro`, `vl53l1x`, `mb12xx` y `ulanding_radar` (comprobado con `help` en la
consola). **Un sensor nuevo entra sin recompilar**, arrancándolo desde el
`extras.txt` de la SD. Al añadirlo habría **dos fuentes de rango**: hay que
comprobar cuál elige el EKF2.

## 6. Qué NO se tocó todavía

- `EKF2_RNG_A_HMAX` sigue en **1.5**. Debe pasar a 1.0 antes del próximo vuelo.
- El techo de altura de los nodos sigue en `kMaxHeightM = 1.2`; debe bajar a 1.0.
- No se ha comprado ningún sensor.
- **Prueba de la pared, pendiente:** sensor horizontal apuntando a una pared
  clara, a 1.00 y 2.00 m con el láser como verdad
  (`monitor_sensors.py 30 pared_1m.csv`). Si contra la pared sí mide bien, queda
  demostrado que el límite es la reflectividad del suelo y no el sensor. Son
  2 minutos y cierra el diagnóstico.

Script de ajuste de la curva: `fit_lidar.py` (scratchpad de la sesión, pendiente
de mover al repo).
