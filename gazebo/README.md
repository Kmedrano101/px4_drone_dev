# gazebo/ — copia de seguridad de los recursos de simulación

**Copia** de los modelos SDF y del airframe del dron de pruebas. Los ficheros que mandan
son los de `PX4-Autopilot`; esto es un respaldo versionado.

**El motivo:** `Tools/simulation/gz` es un submódulo upstream de PX4. Todo lo propio que
dejes dentro queda sin trackear y se pierde con un `git clean`, al cambiar de rama del
submódulo, al actualizarlo o al reclonar PX4. Con esta copia se recupera en un comando.

Documentación completa: [`docs/SIMULACION_GAZEBO_INDOOR.md`](../docs/SIMULACION_GAZEBO_INDOOR.md).

## Contenido

```
gazebo/
├── sync_px4.sh                backup / restore / diff
├── airframes/
│   └── 4023_gz_rjx_f450_indoor
├── models/
│   ├── rjx_f450_base/         frame, rotores, Pi4, protectores, patines, sensores base
│   │   ├── model.sdf
│   │   └── meshes/prop_guard.stl    <- malla real del protector impreso
│   ├── rjx_f450/              base + los 4 plugins de motor
│   ├── ldrobot_d500/          LiDAR 2D 360 grados, 12 m
│   └── rjx_f450_indoor/       rjx_f450 + MTF-01P + D500   <- el que se lanza
└── worlds/
    └── indoor_zone.sdf        copia; el original lo genera scan2bim
```

Del mundo se guarda copia **porque lleva el parche de los plugins de sensores** (ver la
doc, §"El mundo necesita declarar los sistemas de sensores"). Sus mallas no se duplican:
las genera `scan2bim` y `restore` las enlaza desde ahí.

## Uso

```bash
./sync_px4.sh backup     # PX4 -> este repo   (tras tocar los modelos)
./sync_px4.sh restore    # este repo -> PX4   (tras perderlos)
./sync_px4.sh diff       # ¿está la copia al día?

./sync_px4.sh restore /otra/ruta/PX4-Autopilot
SCAN2BIM_OUT=/otra/ruta ./sync_px4.sh restore
```

`restore` también registra el airframe en el `CMakeLists.txt` de la ROMFS, que es el único
paso que no consiste en copiar un fichero. Después hay que recompilar:

```bash
cd ~/PX4-Autopilot && make px4_sitl_default
```

## Regenerar el frame

La geometría de `rjx_f450_base/model.sdf` sale de
[`scripts/gazebo/gen_rjx_f450.py`](../scripts/gazebo/gen_rjx_f450.py), con las medidas de
[`docs/PLATAFORMA_HARDWARE.md`](../docs/PLATAFORMA_HARDWARE.md). El generador escribe
**directamente en PX4-Autopilot**; luego hay que hacer `./sync_px4.sh backup`.

⚠️ Sobrescribe el fichero entero: si editas el `model.sdf` a mano y relanzas el generador,
pierdes los cambios.
