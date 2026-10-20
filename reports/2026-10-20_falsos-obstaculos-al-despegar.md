# Por qué los ciclos PID y MPC no despegaron: retornos falsos del LiDAR 2D al despegar

**Fecha del análisis:** 2026-10-20
**Origen:** rosbags del 2026-10-16 en la Pi, analizados por SSH
**Estado:** ✅ causa identificada y corrección validada contra los bags. Sin volar.

El [reporte del 2026-10-19](2026-10-19_pid-mpc-pruebas-guardas-rpi.md) dejó abierto si el
retorno trasero a 0.95 m que abortó el MPC era un obstáculo real o un artefacto, y pedía
inspeccionar físicamente el sector trasero. Este análisis lo cierra con los datos del bag:
**no era un obstáculo, y tampoco es estructura del dron visible de forma permanente.**

Dato de campo aportado por el piloto: en la zona de pruebas los únicos obstáculos son
**4 pilares a unos 3 m**, con el dron en el centro. Cualquier retorno a menos distancia que
no sea el propio dron es un error de medida.

## 1. La prueba de control: con las hélices paradas el LiDAR no ve nada

La corrida `ev_takeoff_1792149648` fue **rechazada antes de armar** (pedía 1.2 m, por encima
del techo fiable del LiDAR 1D). Las hélices nunca giraron, pero el LD19 estuvo barriendo
66 s. Es el control perfecto:

| | Barridos | Con algún retorno < 2 m | Rayos pegados a `range_min` |
|---|---|---|---|
| `ev_takeoff_1792149648` (hélices paradas) | 655 | **0 (0.0 %)** | **0** |

**Nada del dron está dentro del plano de barrido en reposo.** Ni protectores, ni patas, ni
brazos, ni cables. Esto descarta que la causa sea un problema estático de montaje.

## 2. Con las hélices girando aparecen los retornos, y solo entonces

### MPC `mpc_cycle_1792149766` — despegó a 0.70 m

Armado en t+11.86 s; inicio de subida t+12.8; apogeo `z = −0.914 m`, `dist_bottom = 0.701 m`
en t+13.89. De los **398 barridos del vuelo, solo 7 tienen algún retorno por debajo de 2 m**,
y los 7 caen en una ventana de **0.6 s** durante la subida:

```
t+13.29  47 rayos   -169°:0.020 … -93°..-86°:0.124-0.144
t+13.39  32 rayos   -179°:0.020  -132°..-125°:0.020 …        (r_min util 0.157)
t+13.49   7 rayos   -57°..-55°:0.126-0.131   +178°:0.921  +178°:0.930  +179°:0.947  <-- dispara
t+13.59   7 rayos   -101°..-99°:0.020   +165°..+168°:1.016-1.038
t+13.69   5 rayos   +171°..+174°:0.980 0.985 0.984 0.982 0.981
t+13.79  11 rayos   -91°..-83°:1.074 1.075 1.081 1.091 1.105 1.124 1.139 1.149 1.163 1.177 1.182
t+13.89   4 rayos   -87°..-84°:1.141-1.174
```

A partir de t+13.99 y durante los **25 s restantes de vuelo: cero retornos por debajo de 2 m.**
El desplazamiento horizontal entre el armado y el disparo fue de **0.019 m**.

### PID `ev_takeoff_1792149542` — ni siquiera se separó del suelo

`dist_bottom` se queda en **0.188–0.198 m** todo el rato y `z` apenas pasa de −0.225 a −0.125:
el dron **nunca despegó**. Pero los motores sí subieron a empuje de despegue — la vibración
(desviación típica de |a|) salta de **0.02 en reposo a 0.41–1.38**. Y justo en esa ventana,
de t+14.50 a t+16.10, aparecen **hasta 96 rayos por barrido** repartidos en **7 sectores a la vez**.
Fuera de ella, nada.

**El dron con las hélices a empuje de despegue y pegado al suelo es el caso peor de todos.**

## 3. Por qué no puede ser un obstáculo ni estructura del dron

1. **No es permanente:** 391 de 398 barridos del MPC están limpios, y el control con hélices
   paradas da 0 de 655.
2. **No es un objeto:** aparece en muchos rumbos opuestos **a la vez** (−169°, −93°, −57°,
   +165°, +178°) y desaparece.
3. **No es estable en distancia:** la misma banda de rumbos da 0.921 → 1.027 → 0.982 en
   barridos consecutivos. Un pilar a 0.95 m se quedaría en 0.95 m.
4. **No se puede alcanzar:** el dron se movió 0.019 m en horizontal; los pilares están a 3 m.
5. **No es inclinación viendo el suelo:** con `dist_bottom = 0.70 m`, un retorno a 1.07 m
   exigiría unos 41° de inclinación. Roll y pitch estuvieron por debajo de 1°.

## 4. Hipótesis del mecanismo: polvo levantado por el chorro de las hélices

No está demostrada, pero es la que encaja con todo:

- **Correlaciona con los motores, no con la altura ni con la actitud.** Hélices paradas: 0.
  Hélices girando: ráfaga. Y es peor pegado al suelo (PID, 96 rayos) que subiendo (MPC, 47).
- **Crece y se disipa** a lo largo de ~1.5 s (3 → 18 → 36 → 27 → 66 → 47 → 96 → 27 → … → 0).
  Un efecto eléctrico sería instantáneo con la corriente, no una rampa.
- **Los grupos son espacialmente coherentes**, no ruido aleatorio: +171°..+174° da 0.980,
  0.985, 0.984, 0.982, 0.981 en rayos contiguos, y −91°..−83° una rampa monótona de 1.074 a
  1.182. Eso son retornos ópticos de algo que está ahí, no bytes corruptos en el UART.
- El suelo es **hormigón oscuro de un parking abandonado**, con polvo suelto.

**Cómo confirmarlo, sin volar:** subir motores a empuje de despegue con el dron sujeto, sobre
hormigón desnudo y luego sobre una lona o cartón de 2 m, grabando solo `/scan`. Si la ráfaga
desaparece sobre la lona, es polvo. Es una prueba de dos minutos.

## 5. La zona ciega de 0.70 m: necesaria, pero no suficiente

El piloto añadió una zona ciega circular de 0.70 m de diámetro (`obstacle_blind_radius_m=0.35`)
atribuyendo los retornos a los protectores del dron. Los datos la respaldan **a medias**:

- **A favor:** en la ventana de ráfaga sí hay retornos a 0.12–0.21 m, que es el radio correcto
  para estructura propia, y son los que dispararon el PID (0.16 m @ +165°). La zona ciega los
  elimina.
- **En contra:** los retornos que abortaron el MPC estaban a **0.92–0.95 m**, casi tres veces
  fuera del círculo ciego, y el código prohíbe (con razón) un radio ciego ≥ la distancia de
  parada de 1.00 m.

Pasando los bags reales por `obstacle_guard_replay`:

| Zona ciega | Debounce | MPC 16-oct (*debe NO*) | PID 16-oct (*debe NO*) | Accidente 18-sep (*debe SÍ*) |
|---|---|---|---|---|
| 0.00 m | 2 (el del 16-oct) | ⛔ PARA 0.95 m @ +175° | ⛔ PARA 0.16 m @ +165° | ✅ PARA 1.65 m @ +5° |
| **0.35 m** | **2 (lo desplegado hoy)** | ✅ libre | ⛔ **PARA 0.58 m @ −15°** | ✅ PARA 1.65 m @ +5° |
| 0.00 m | 3 | ✅ libre | ⛔ PARA 0.27 m @ +5° | ✅ PARA 1.51 m @ +5° |
| **0.35 m** | **3** | ✅ **libre** | ✅ **libre** | ✅ **PARA 1.51 m @ +5°** |

**Con la configuración desplegada esta mañana, el MPC habría volado pero el PID habría vuelto
a abortar.** Hace falta además subir el debounce.

## 6. Corrección aplicada: `obstacle_debounce_scans = 3`

Se expone el debounce como parámetro del nodo y de los dos launches, con **3** por defecto
(antes 2, fijo en el código). El valor por defecto de la clase C++ sigue siendo 2, así que
ningún otro usuario de `ObstacleGuard` cambia de comportamiento por esto.

Por qué 3 y no otra cosa:

- Es lo mínimo que limpia las dos corridas del 16-oct, y sigue parando en el bag del accidente
  a **1.51 m con 1.31 m/s de acercamiento** (umbral 1.89 m): la protección real se conserva.
- Cuesta **0.1 s** de latencia (un barrido a 10 Hz). En hover eso son 0 cm; a la velocidad de
  acercamiento máxima configurada son 25 cm, dentro del margen de 1.00 m de parada.
- No se tocó `min_points`. Subirlo de 3 a 5 también limpia los bags, pero exige 5 rayos en un
  sector de 10°: a 2 m un poste de 5 cm da unos 2 rayos, así que se perdería sensibilidad a
  obstáculos finos. El debounce no tiene ese efecto.

### Lo que se probó y se descartó

- **Detector de contaminación por rayos pegados a `range_min`.** Parecía limpio (0 en 655
  barridos con hélices paradas; 3–29 en las ráfagas), pero el bag del accidente tiene un
  **26 % de barridos** así, y ahí había un obstáculo real. Un filtro basado en eso habría
  cegado la guarda justo cuando hacía falta. **Descartado.**
- **Debounce por sector** (exigir que confirme el *mismo* rumbo en barridos seguidos).
  Implementado y probado: a debounce 3 da exactamente el mismo resultado que el global en los
  tres bags, y es menos sensible mientras el dron guiña, porque un obstáculo en el borde entre
  dos sectores deja de acumular. **Revertido**, no aporta en el punto de operación elegido.

## 7. ¿Hay que activar la guarda solo después del despegue?

**No, y conviene no hacerlo.** El razonamiento con los datos:

- Es cierto que **el 100 % de los disparos falsos** de ambas corridas cae dentro del transitorio
  de despegue, así que suprimir la guarda ahí los eliminaría todos. Pero la corrección del §6
  ya los elimina sin renunciar a nada.
- El chequeo **previo al armado** es el más fiable de todos y hay que conservarlo: se hace con
  las hélices paradas, que es justamente la condición en la que el barrido está limpio
  (0 de 655 barridos con retornos espurios).
- Durante la subida el riesgo real de colisión es bajo (0.019 m de desplazamiento horizontal),
  pero no es cero: alguien que entra andando en la zona es un escenario normal en campo de
  pruebas, y ahí la respuesta de la guarda —frenar y aterrizar desde 0.7 m— es la correcta.
- Apagar la guarda en el despegue la dejaría ciega en la fase en la que el dron está más cerca
  del suelo y de las personas, para arreglar un problema que ya está arreglado en su origen.

Si en una repetición futura una ráfaga peor volviera a batir el debounce de 3, el siguiente
paso **no** es cegar la guarda en el despegue, sino tratar el barrido contaminado como lo que
es: subir el debounce, o no permitir el despegue hasta que el barrido se estabilice.

## 8. Qué no se tocó

No se armó el dron, no se voló y no se escribió ningún parámetro en el FC. Los cambios son en
el repositorio `px4_drone`: el parámetro nuevo del nodo y de los dos launches, y dos argumentos
extra en `obstacle_guard_replay` (zona ciega y debounce) para poder repetir esta tabla.
`src/obstacle_guard.cpp` queda como estaba salvo la zona ciega del 2026-10-20.

Los rosbags y CSV se quedan en la Pi: superan el límite de 5 MB para datos crudos.

## 9. Consecuencia para el protocolo

Queda **cerrado** el punto que el reporte del 2026-10-19 dejaba abierto: no hay nada que
inspeccionar en el sector trasero, porque no había nada ahí. La condición de repetición
«solo en una ubicación con 1.5 m libres en 360°» sigue siendo buena práctica, pero **no era el
problema**: con 4 pilares a 3 m la ubicación ya era válida.

Sigue pendiente, y es independiente de esto, la causa del `sigma_xy = 0.311 m` que abortó el
PID por salud del SLAM. La guarda está desactivada por defecto en los launches desde hoy
([reporte](2026-10-20_zona-ciega-circular-ciclos.md)), así que ya no aborta — pero la estimación
sigue siendo la que se usa para medir el error de hover, y eso hay que registrarlo en cada
corrida.
