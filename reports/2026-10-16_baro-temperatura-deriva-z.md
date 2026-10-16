# Reporte: el barómetro a 79 °C y la deriva de z en tierra

**Fecha:** 2026-10-16
**Autor / origen:** consola nsh por USB + topics ROS 2, dron en el suelo
**Estado:** ⚠️ caracterizado, sin acción correctiva todavía

**Contexto:** FC#2 NxtPX4v2, PX4 1.14.3 de fábrica. La altura del EKF2 sale del
**barómetro** (`EKF2_HGT_REF = 0`) con el LiDAR 1D como ayuda condicional. El
barómetro es un **SPL06 en I2C1, dirección 0x77**.

**Por qué importa:** si el barómetro es la referencia de altura, su deriva es la
deriva del hover. Y la del LiDAR 1D ya sabemos que satura, así que estas dos
medidas son todo lo que hay en el eje z.

---

## 1. El sensor está sano, pero caliente

`spl06 status` → **0 errores, 31 Hz**. El camino de datos funciona.

La temperatura es otra cosa: **79 °C con los motores parados**, frente a los
**64–66 °C de las IMUs**. El barómetro es el sensor más caliente del FC, y está
midiendo presión.

## 2. La deriva: 3 mm/s con el barómetro plano

Con el dron **quieto en el suelo** y la presión del barómetro **plana** (±10 cm,
sin tendencia), la **z del EKF2 derivó 11 cm en 32 s de forma monótona**, unos
**3 mm/s**. En vuelos anteriores esa deriva llegó a arrastrar ~1 m de error.

Eso *es* la fusión IMU + barómetro derivando: con la presión sin tendencia, lo
que mueve la estimación es el sesgo del acelerómetro vertical, que el EKF estima
pero no cancela del todo. Es también la respuesta a *"¿y si saco la altura de la
IMU?"*: **no se puede** — la doble integración es justamente lo que está
derivando aquí.

Relacionado y ya documentado: el bit 16 del estado del filtro (acelerómetro
vertical malo) aparecía en EKF0 el 43 % del tiempo, y el selector conmutaba de
instancia, con saltos de z de hasta 21.6 m
([reporte](2026-09-11_estimador-sensores-offboard.md)).

## 3. Hipótesis, sin resolver

1. **Deriva térmica del SPL06 a 79 °C.** Es la sospecha principal, pero *no está
   demostrada*: la presión salía plana durante la medición, así que si la
   temperatura mete error, en esos 32 s no se vio en la presión.
2. **Autocalentamiento por falta de aislamiento.** El SPL06 comparte placa con un
   STM32H743 en TFBGA100 que ya lleva disipador. Un barómetro **necesita ver la
   presión ambiente** pero no la convección del micro: lo habitual es taparlo con
   espuma de celda abierta, que deja pasar presión y frena el aire caliente.
   **No se ha probado.**
3. **Sesgo del acelerómetro vertical mal estimado**, que sería independiente del
   barómetro y encaja con el bit 16.

## 4. Comandos que sirven (y uno que no existe)

```
spl06 status                  # salud del driver: errores y frecuencia
listener sensor_baro          # presión y temperatura crudas
listener vehicle_air_data     # altitud derivada
uorb top -1 sensor_baro       # frecuencia real de publicación
```

⚠️ **`sensor_baro status` NO existe** en este firmware. El driver se interroga
por su nombre, `spl06`.

## 5. Qué NO se tocó

- Ningún parámetro del barómetro.
- No se ha aislado térmicamente el sensor.
- No se ha repetido la medición de deriva con el FC frío, que es la comparación
  que haría falta para culpar a la temperatura.

## 6. Consecuencia práctica, mientras no se resuelva

**La ayuda del LiDAR 1D no es un lujo, es lo que ancla la z.** Por debajo de
0.70 m engancha (histéresis 0.7 × `EKF2_RNG_A_HMAX = 1.0`) y se mantiene hasta
1.0 m. Volar dentro de esa banda es lo que impide que la deriva del barómetro se
acumule — y es otro motivo, independiente de la saturación, para que el techo de
altura esté en 1.0 m.
