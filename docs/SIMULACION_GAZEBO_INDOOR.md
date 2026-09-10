# Simulación Gazebo — RJX F450 en la zona indoor real

Recreación en Gazebo Sim del dron de pruebas y del local donde vuela, para poder
desarrollar navegación indoor sin arriesgar el hardware.

**Fecha:** 2026-09-08
**Simulador:** Gazebo Sim 8.10 (Harmonic) · PX4 `main` · SDF 1.9
**Airframe:** `4023_gz_rjx_f450_indoor` · **Modelo:** `rjx_f450_indoor` · **Mundo:** `indoor_zone`

---

## 1. Qué se ha modelado

| Elemento real | En la simulación |
|---|---|
| Frame RJX F450 carbono, 450 mm diagonal | Rotores a ±0.159 m, brazos de tubo, doble placa |
| T-Motor F90 2806.5 1300KV (4×) | Campana 33.4 × 34.7 mm, empuje calibrado (§3) |
| HQProp 7×4×3 tripala | 3 palas de 7" por rotor |
| Protectores de hélice impresos | **Malla STL real** (`jaula_sin_patas.stl`), arco de 100 mm |
| Tren de aterrizaje | **Dos patines en T invertida**: montante central + tubo horizontal de 280 mm |
| ESC MicoAir Bluejay-4IN1-60A | Placa 44 × 43.5 × 5.2 mm entre placas |
| FC NxtPX4v2 | Caja 27 × 32 × 8 mm |
| Batería Ovonic 6S 1300 mAh | Caja 74 × 44 × 34 mm + soporte naranja |
| Raspberry Pi 4 + ventilador | PCB verde 85 × 56 mm, ventilador, cubierta beige |
| MicoAir MTF-01P | Flujo óptico + láser 1D, bajo la placa inferior |
| LDROBOT D500 | LiDAR 2D 360°, 12 m, sobre la cubierta |
| Zona de pruebas escaneada | Mundo `indoor_zone` de `scan2bim` |

> ⚠️ **Los protectores son ROJOS**, no negros. La descripción inicial decía negros pero en
> las fotos del 2026-09-08 son claramente rojos, y se ha modelado lo que se ve. Si hiciera
> falta cambiarlos, es la constante `RED` del generador.

## 2. Dónde vive cada cosa

Los ficheros **viven en PX4-Autopilot**, que es donde los lee Gazebo:

```
PX4-Autopilot/
├── Tools/simulation/gz/models/
│   ├── rjx_f450_base/          frame, rotores, Pi4, protectores, patines, sensores base
│   │   ├── model.sdf
│   │   └── meshes/prop_guard.stl     <- malla real, recentrada en el eje del motor
│   ├── rjx_f450/               base + los 4 plugins de motor
│   ├── ldrobot_d500/           LiDAR 2D 360 grados
│   ├── rjx_f450_indoor/        rjx_f450 + MTF-01P + D500   <- el que se lanza
│   ├── indoor_clean_less_dense/ ┐
│   ├── puerta_entrada/          ├─ symlinks a scan2bim/output/gazebo/
│   └── puerta_salida/           ┘
├── Tools/simulation/gz/worlds/indoor_zone.sdf   -> symlink a scan2bim
└── ROMFS/px4fmu_common/init.d-posix/airframes/
    ├── 4023_gz_rjx_f450_indoor
    └── CMakeLists.txt          <- hay que añadir el airframe a la lista
```

Los del escaneo son symlinks a `~/src/3d_modeling/IndoorZone/scan2bim/output/gazebo/`, así
que **si regeneras el escaneo la simulación coge la versión nueva sola**.

### Copia de seguridad en este repo

`Tools/simulation/gz` es un **submódulo upstream de PX4**: nada de lo propio que dejes ahí
está trackeado, y se pierde con un `git clean`, al cambiar de rama del submódulo, al
actualizarlo o al reclonar PX4. Por eso hay una copia en [`gazebo/`](../gazebo/README.md):

```bash
cd ~/src/drone_tunning/gazebo
./sync_px4.sh backup      # PX4 -> repo, tras tocar los modelos
./sync_px4.sh restore     # repo -> PX4, para recuperarlos
./sync_px4.sh diff        # ¿está la copia al día?
```

Del mundo se guarda copia porque **lleva el parche de los plugins de sensores** (§5); sus
mallas no, que las genera `scan2bim`.

## 2b. Cómo añadirlo a PX4-Autopilot desde cero

`./sync_px4.sh restore` lo hace todo. Esto es lo que toca, por si hay que hacerlo a mano:

| # | Fichero / ruta en PX4 | Qué |
|---|---|---|
| 1-4 | `Tools/simulation/gz/models/{rjx_f450_base, rjx_f450, ldrobot_d500, rjx_f450_indoor}` | copiar los directorios |
| 5 | `Tools/simulation/gz/worlds/indoor_zone.sdf` | symlink a la salida de `scan2bim` |
| 6-8 | `Tools/simulation/gz/models/{indoor_clean_less_dense, puerta_entrada, puerta_salida}` | symlinks a `scan2bim` |
| 9 | `ROMFS/px4fmu_common/init.d-posix/airframes/4023_gz_rjx_f450_indoor` | copiar el airframe |
| 10 | `ROMFS/px4fmu_common/init.d-posix/airframes/CMakeLists.txt` | **añadir el airframe a `px4_add_romfs_files`** |

**El paso 10 es el único que no es copiar un fichero, y el más fácil de olvidar.** Sin él
el airframe no entra en la ROMFS y `SYS_AUTOSTART=4023` no existe:

```cmake
	4021_gz_x500_flow
	4022_gz_x500_lidar_360
	4023_gz_rjx_f450_indoor      # <- esta linea
```

Los targets `gz_<modelo>` y `gz_<modelo>_<mundo>` los genera CMake solo escaneando el
directorio de modelos — no hay que declararlos. Tras instalar hace falta **recompilar**
(`make px4_sitl_default`) para meter el airframe en la ROMFS; los `.sdf` se leen en
caliente y no necesitan build.

### Verificar que quedó bien

```bash
cd ~/PX4-Autopilot
ls build/px4_sitl_default/etc/init.d-posix/airframes/ | grep 4023   # airframe en la ROMFS
ninja -C build/px4_sitl_default -t targets | grep gz_rjx_f450       # targets generados
```

## 3. Empuje: calibrado contra el vuelo real

El dato que ancla toda la dinámica es el **hover medido en vuelo: 0.284 de media**
(p10-p90 0.270-0.295) → `MPC_THR_HOVER=0.30`.

En SITL, PX4 mapea la salida normalizada `u` a velocidad de rotor con
`SIM_GZ_EC_MIN=150` y `SIM_GZ_EC_MAX=1000`:

```
ω = 150 + u · 850
empuje_total = 4 · motorConstant · ω²
```

Imponiendo que el hover caiga en u = 0.30 con la AUW modelada de 1.2 kg:

```
ω_hover = 150 + 0.30 · 850 = 405 rad/s
4 · k · 405² = 1.2 · 9.81 = 11.77 N   →   k = 1.8e-05
```

Resultado: **72 N de empuje máximo (7.34 kg), 1835 g por motor**. La ficha de T-Motor da
2360 g de pico con hélice 7×4; el valor modelado queda por debajo, que es lo razonable
para empuje sostenido con caída de tensión.

## 4. Sensores — nombres obligatorios

`GZBridge.cpp` se suscribe a **topics fijos**. Los nombres de link y sensor no son
descriptivos: son los que PX4 exige, y si no coinciden el sensor no llega.

| Sensor real | Link | Sensor | Línea en GZBridge.cpp |
|---|---|---|---|
| MTF-01P flujo óptico | `flow_link` | `optical_flow` | 321 |
| MTF-01P láser 1D | `lidar_sensor_link` | `lidar` | 268 |
| LDROBOT D500 2D | `link` | `lidar_2d_v2` | 256 |

Se activan con `SIM_GZ_EN_FLOW=1` y `SIM_GZ_EN_LIDAR=1`, ya puestos en el airframe.

## 5. Cómo lanzarlo

```bash
cd ~/PX4-Autopilot
make px4_sitl gz_rjx_f450_indoor                       # mundo indoor_zone por defecto
PX4_GZ_NO_FOLLOW=1 make px4_sitl gz_rjx_f450_indoor    # con camara libre (ver abajo)
```

### El zoom no funciona → desactivar el seguimiento de cámara

`px4-rc.gzsim` (línea 161) pone la cámara en **modo FOLLOW** sobre el modelo. En ese modo
la cámara queda fijada al offset y **la rueda del ratón no hace zoom**. Dos salidas:

```bash
PX4_GZ_NO_FOLLOW=1 make px4_sitl gz_rjx_f450_indoor     # cámara libre desde el arranque
```
o, sin relanzar, botón derecho sobre el modelo en la vista 3D y quitar el seguimiento.
También se puede alejar la cámara con `PX4_GZ_FOLLOW_OFFSET_X/Y/Z` (por defecto -2,-2,2).

### El dron spawnea a z=0.17, no a 0

El origen del modelo está en la placa inferior y el tren baja hasta z≈−0.167. Spawneando
en z=0 **las patas quedan enterradas bajo el suelo y no se ven**. El airframe fija
`PX4_GZ_MODEL_POSE="0,0,0.17,0,0,0"` para que apoye sobre los patines.

✅ **`HEADLESS=1` funciona**, incluidos los sensores GPU. Medido el 2026-09-08:
4 de 4 corridas headless con el flujo óptico y los dos LiDAR publicando. Los
`libEGL warning: egl: failed to create dri2 screen` del log son ruido — el servidor
tira por otro camino que sí funciona. (Una versión anterior de este documento decía
lo contrario; salía de una comprobación temprana que no se repitió.)

⚠️ Si el entorno tiene un **virtualenv activo**, el build de PX4 falla al generar código.
Sacarlo del `PATH` antes (mismo problema que en `drone_ws`, ver su `sanitize.sh`).

### ⚠️ El mundo necesita declarar los sistemas de sensores

**Esto costó un rato de diagnóstico.** En cuanto un mundo declara `<plugin>` propios, gz
**deja de añadir el set por defecto**. `indoor_zone.sdf` declaraba Physics, UserCommands,
SceneBroadcaster, Contact y Sensors — con eso los LiDAR (que son GPU, van por `Sensors`)
funcionaban, pero **IMU, barómetro, magnetómetro y navsat no**, y PX4 arrancaba con:

```
Preflight Fail: Accel Sensor 0 missing
Preflight Fail: Gyro Sensor 0 missing
Preflight Fail: barometer 0 missing
Preflight Fail: ekf2 missing data
```

El mundo `default.sdf` de PX4 no lo sufre porque **no declara ningún plugin**.

Arreglado en origen, en `scan2bim/gazebo_envelope.py`, añadiendo `Imu`, `AirPressure`,
`Magnetometer`, `NavSat`, `Altimeter` y `ForceTorque`, más `<gravity>`, `<magnetic_field>`
y `<atmosphere>`. Así cualquier mundo que regeneres ya sale bien. Copia de seguridad del
original en `gazebo_envelope.py.bak`.

### El MTF-01P no puede ir sobre la batería

El sensor va en `x=0.055`, **delante** de la batería, no centrado. La batería ocupa
`x=-0.037..0.037` y `z=-0.047..-0.013`; con el sensor en `x=0.020, z=-0.016` queda
*dentro* de esa caja y el rayo del láser choca contra la propia batería:

```
DISTANCE_SENSOR: 0.020 m    <- el <min> del sensor, constante a cualquier altura
```

**No da ningún error**: PX4 recibe un valor válido y plausible, simplemente es basura.
Se detecta comparando con la geometría: en reposo, apoyado en los patines, tiene que leer
**0.14-0.15 m** (base_link a 0.161 m menos los 20 mm del sensor).

Comprobación rápida, sin pasar por PX4:

```bash
gz topic -e -n 3 -t /world/indoor_zone/model/rjx_f450_indoor_0/link/lidar_sensor_link/sensor/lidar/scan \
  | grep ranges:
# ranges: 0.150 / 0.146 / 0.149   <- correcto
```

⚠️ **No intentes verificarlo teletransportando el modelo con `set_pose`.** Con los motores
parados el dron cae libremente y para cuando lees ya está otra vez en el suelo: parece que
el sensor no sigue la altura cuando en realidad sí. Mídelo en reposo, o en vuelo.

Si se cambian los offsets físicos hay que actualizar también `EKF2_OF_POS_*` y
`EKF2_RNG_POS_*` en el airframe.

### ⚠️ NO copiar los EKF2 del dron real al simulador

Tres parámetros migrados del FC#1 **rompen la cadena del flujo óptico**:

| Param | FC real | Correcto aquí | Por qué |
|---|---|---|---|
| `EKF2_RNG_CTRL` | 2 | **1** | Con 2, el láser va a altura absoluta (`rng_hgt`) y **nunca alimenta el terreno** (`rng_terrain`) |
| `EKF2_HGT_REF` | 2 | **1** | Refuerza lo mismo |
| `EKF2_OF_QMIN` | 30 | **1** | Descarta casi todas las muestras de flujo |

El flujo óptico necesita terreno válido para escalar; el terreno se alimenta del
láser *como terreno*. Rota esa cadena, `cs_opt_flow` nunca se activa,
`dist_bottom_valid` se queda en 0 y **el dron no despega**. El airframe de
referencia de PX4 (`4021_gz_x500_flow`) no toca ninguno de los tres.

Ya están corregidos en `4023_gz_rjx_f450_indoor`. Detalle completo en
[`reports/2026-09-08_ekf2-no-converge-sitl.md`](../reports/2026-09-08_ekf2-no-converge-sitl.md).

### Validar vuelos contra groundtruth, no contra el EKF

`vehicle_local_position` es **la estimación** y puede mentir: en este trabajo llegó
a reportar 8 m con el dron parado en el suelo. Para comprobar si voló de verdad hay
que mirar `vehicle_local_position_groundtruth` en el `.ulg`.

### El suelo texturado no es decoración

El flujo óptico mide por correlación de imagen; sobre color plano no hay señal.
`scripts/gazebo/gen_floor_texture.py` genera la baldosa real del local. El detalle
debe dimensionarse contra lo que resuelve la cámara: **a 0.40 m ve 31 cm en 100 px
= 3.1 mm/px**, así que el veteado va a escala de centímetros, no de milímetros.

## 6. Diferencias deliberadas con el dron real

Son las que hacen que la simulación **no** reproduzca los problemas reales. Conviene
tenerlas presentes antes de sacar conclusiones de un vuelo simulado.

| | Real | Simulación | Cómo igualarlo |
|---|---|---|---|
| **Magnetómetro** | **No hay** | Sí, y perfecto | `param set SYS_HAS_MAG 0` + `EKF2_MAG_TYPE 5` |
| **Láser MTF-01P** | Satura por encima de ~1.5 m (a 3 m lee 2.14) y nunca avisa | Lineal hasta 12 m | Bajar `<max>` a ~2.5 en `rjx_f450_indoor/model.sdf` |
| Rotación del flujo | `SENS_FLOW_ROT` no existe en la 1.14.3 | Parámetro disponible | — |
| Autonomía | ~3-4 min (1300 mAh) | Sin límite | — |

**La primera es la importante.** El bloqueo real del hold de posición indoor es la falta de
yaw sin brújula (ver [`reports/2026-07-23_mtf01-ekf2-tuning.md`](../reports/2026-07-23_mtf01-ekf2-tuning.md)
y [`reports/2026-09-04_fc2-vendor-1143-mtf01p-migracion.md`](../reports/2026-09-04_fc2-vendor-1143-mtf01p-migracion.md)).
Con la brújula perfecta de la simulación el dron vuela sin problema, así que **un vuelo
simulado OK no demuestra nada** sobre ese fallo. Para reproducirlo hay que desactivar el mag.

## 7. Colisiones

El footprint de colisión llega a **0.325 m de radio** (motor a 0.225 + arco de 0.10), que es
la envolvente real con protectores. Los arcos se aproximan con una caja de 0.20 × 0.20 × 0.065
por protector en vez de usar la malla de 54k triángulos — suficiente para chocar con paredes
y marcos de puerta sin hundir el rendimiento.

## 8. La planta del entorno (paredes y suelo)

La geometría del edificio no se dibujó a mano: sale de la nube escaneada
`IndoorZone/Indoor_clean_less_dense.ply` con
[`scripts/gazebo/muros_cv.py`](../scripts/gazebo/muros_cv.py) (necesita
`/usr/bin/python3`, que es el intérprete que tiene cv2 + open3d + trimesh; el
python del venv NO los tiene).

### Por qué hubo que rehacerla

El modelo que había en Gazebo venía de una exportación **vieja y recortada**: le
faltaba entero el brazo inferior derecho del edificio, unos 63 m². Medido contra
la nube, el modelo anterior cubría X −20.66..3.14 e Y −22.44..8.51, mientras que
el pavimento real llega a X −20.91..6.54 e Y −27.99..8.76. Tres de las nueve
medidas tomadas sobre la nube real no encajaban con ninguna pared, precisamente
las del saliente inferior.

Enderezar la malla exportada, como se intentó primero, no arregla eso: una planta
incompleta no se completa alisándola. Hay que volver a la nube.

### Cómo funciona

1. Banda de puntos a cota de suelo (−0.15 / +0.25 m) → ráster en planta a 5 cm/px.
2. Cierre morfológico de radio 0.60 m, que tapa las sombras del escáner sobre el
   pavimento, y `cv2.findContours` → contorno **cerrado por construcción**.
3. `cv2.approxPolyDP` (ε = 0.30 m) reduce el contorno a segmentos.
4. Cada segmento se reajusta por **mínimos cuadrados totales** sobre los puntos
   de contorno que le tocan, recortando el 15% de cada extremo: las esquinas están
   redondeadas por el cierre morfológico y arrastrarían la recta.
5. Los ángulos se agrupan en **familias** con tolerancia de 8°, y cada segmento
   adopta la media circular de su familia ponderada por longitud. No se fuerza una
   retícula global a propósito: este edificio tiene dos alas giradas ~30° entre sí
   (familias dominantes medidas: 132.5°, 29.2°, 62.1°, 151.4°), y forzar dos
   direcciones ortogonales destruiría una de las dos.
6. Las rectas consecutivas se cortan entre sí → esquinas limpias. Los lados de
   menos de 0.90 m se absorben en sus vecinos.

El **suelo se rehace con esa misma planta**, desbordada medio espesor de muro
hacia fuera para que la pared apoye encima. Así suelo y muros comparten contorno
por construcción: no puede quedar suelo asomando fuera de la pared ni al revés.

### Marco de coordenadas

El script **no recentra** por el centroide del nuevo polígono, que es lo que hace
`gazebo_envelope.py`. En su lugar registra la malla vieja contra la planta nueva
con `cv2.matchTemplate` y aplica ese desplazamiento (7.806, 5.897 m, correlación
0.95). Motivo: las columnas, el mundo `indoor_zone.sdf` y el punto donde aparece
el dron (0, 0) ya están en ese marco. Recentrar lo movería todo varios metros y
dejaría las 6 columnas fuera de sitio. Comprobado tras regenerar: las 6 siguen
dentro del recinto.

### Validación

El script comprueba solo las 9 medidas que se tomaron sobre la nube real. Peor
desviación **0.45 m**, y las nueve por debajo de 3° de error angular:

| medida | real | modelo | error |
|---|---|---|---|
| 08-26-35 | 13.52 m @ 151.4° | 13.60 m @ 151.4° | +0.08 m |
| 08-26-53 |  8.06 m @  46.3° |  8.40 m @  44.3° | +0.34 m |
| 08-27-09 | 20.84 m @ 133.5° | 20.71 m @ 132.5° | −0.13 m |
| 08-39-13 | 18.10 m @  61.5° | 18.16 m @  62.1° | +0.06 m |
| 08-57-06 | 13.42 m @  29.7° | 13.68 m @  29.2° | +0.26 m |
| 08-57-55 |  7.29 m @  31.9° |  6.98 m @  29.2° | −0.31 m |
| 08-58-07 | 11.40 m @ 137.7° | 11.39 m @ 140.2° | −0.01 m |
| 09-20-28 |  2.27 m @  44.3° |  2.42 m @  44.3° | +0.16 m |
| 09-20-37 |  8.88 m @ 127.0° |  9.33 m @ 127.9° | +0.45 m |

Ojo: **no todas son paredes**. 08-58-07, 08-57-06 y 09-20-37 cruzan en diagonal,
no recorren un muro; el script lo etiqueta en su salida.

Contra el contorno denso de la nube, la planta recta se desvía **4.7 cm de media**,
12 cm en el p95 y 33 cm como máximo, y encierra 388.8 m² frente a los 389.2 m²
del pavimento escaneado (0.1% de diferencia).

### Las normales del OBJ no son opcionales

Un OBJ sin `vn` se carga en Gazebo, con su geometria correcta, pero se pinta
**BLANCO**: se pierde la textura del `<albedo_map>` del SDF. Diagnosticado
comparando las mallas del modelo: las que se texturaban (`muros.obj.bak` con 3144
`vn`, `suelo.obj.pre_cv` con 496) las llevaban; las que salian blancas, ninguna.
Los muros llevaban sin ladrillo desde el enderezado a mano, no solo desde la
regeneracion.

Asi que `muros_cv.py` escribe normal por vertice e indices en la forma
`v/vt/vn`. En el suelo los triangulos se **desueldan** para que cada uno lleve su
normal plana: soldados, la normal del canto de la losa se promediaria con la de
la cara vista. Verificado renderizando en Gazebo: baldosa y ladrillo se ven.

Las mallas anteriores quedan como `*.pre_cv` (lo enderezado a mano) y `*.bak` (la
exportación original curvada) junto a las nuevas.

## Documentos relacionados

- [`PLATAFORMA_HARDWARE.md`](PLATAFORMA_HARDWARE.md) — de donde salen todas las medidas
- [`INTEGRACION_MTF-01P_FLOW_LIDAR.md`](INTEGRACION_MTF-01P_FLOW_LIDAR.md) — el sensor en el dron real
- [`PARAMETROS_INDOOR.md`](PARAMETROS_INDOOR.md) — configuración sin GPS
