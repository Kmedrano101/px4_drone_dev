#!/usr/bin/env bash
#
# Copia de seguridad de los recursos de Gazebo propios.
#
# Los ficheros que manda son los de PX4-Autopilot; este directorio es solo una COPIA
# versionada, para que no se pierdan si se limpia o se reclona el submodulo
# Tools/simulation/gz (que es upstream de PX4 y no traquea nada de esto).
#
#   ./sync_px4.sh backup    PX4  -> este repo   (refrescar la copia)
#   ./sync_px4.sh restore   este repo -> PX4    (recuperar tras perderlos)
#   ./sync_px4.sh diff      ver que ha cambiado
#
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODE="${1:-}"
PX4="${2:-$HOME/PX4-Autopilot}"
SCAN="${SCAN2BIM_OUT:-$HOME/src/3d_modeling/IndoorZone/scan2bim/output/gazebo}"

GZ="$PX4/Tools/simulation/gz"
AF="$PX4/ROMFS/px4fmu_common/init.d-posix/airframes"
AIRFRAME="4023_gz_rjx_f450_indoor"
# indoor_clean_less_dense es el edificio escaneado: en PX4 es un enlace al directorio
# de scan2bim, y cp -r lo sigue, asi que aqui queda la copia real de sus mallas.
MODELS=(rjx_f450_base rjx_f450 ldrobot_d500 rjx_f450_indoor indoor_clean_less_dense)

[ -d "$GZ/models" ] || { echo "ERROR: no encuentro $GZ/models — ¿es un clon de PX4-Autopilot?"; exit 1; }

case "$MODE" in
  backup)
    echo "PX4 -> repo"
    mkdir -p "$HERE/models" "$HERE/airframes" "$HERE/worlds"
    for m in "${MODELS[@]}"; do
      rm -rf "$HERE/models/$m"
      # -L a proposito: indoor_clean_less_dense es un ENLACE a scan2bim, y sin
      # dereferenciar aqui quedaria guardado el enlace en vez de las mallas, que
      # es justo lo que hay que respaldar.
      cp -rL "$GZ/models/$m" "$HERE/models/$m"
      rm -f "$HERE/models/$m"/meshes/*.bak "$HERE/models/$m"/meshes/*.pre_cv
      echo "  models/$m"
    done
    cp "$AF/$AIRFRAME" "$HERE/airframes/$AIRFRAME"
    echo "  airframes/$AIRFRAME"
    # el mundo lo genera scan2bim; se guarda copia porque lleva el parche de plugins
    if [ -f "$SCAN/indoor_zone.sdf" ]; then
      cp "$SCAN/indoor_zone.sdf" "$HERE/worlds/indoor_zone.sdf"
      echo "  worlds/indoor_zone.sdf  (copia; el original lo genera scan2bim)"
    fi
    echo "Copia actualizada."
    ;;

  restore)
    echo "repo -> PX4"
    for m in "${MODELS[@]}"; do
      # si en PX4 es un enlace a scan2bim, se restaura en el destino real del
      # enlace; borrarlo dejaria a scan2bim y a PX4 apuntando a cosas distintas.
      dst="$GZ/models/$m"
      [ -L "$dst" ] && dst="$(readlink -f "$dst")"
      rm -rf "$dst"
      cp -r "$HERE/models/$m" "$dst"
      echo "  models/$m -> $dst"
    done
    cp "$HERE/airframes/$AIRFRAME" "$AF/$AIRFRAME"
    echo "  airframes/$AIRFRAME"

    # el mundo y los modelos del escaneo se enlazan a scan2bim, no se copian
    if [ -d "$SCAN" ]; then
      ln -sfn "$SCAN/indoor_zone.sdf" "$GZ/worlds/indoor_zone.sdf"
      for m in indoor_clean_less_dense puerta_entrada puerta_salida; do
        [ -d "$SCAN/$m" ] && ln -sfn "$SCAN/$m" "$GZ/models/$m"
      done
      echo "  mundo indoor_zone -> enlazado a scan2bim"
      if ! grep -q "gz-sim-imu-system" "$SCAN/indoor_zone.sdf" 2>/dev/null; then
        echo "  AVISO: el mundo de scan2bim no declara gz-sim-imu-system."
        echo "         Sin el, PX4 arranca con 'Accel/Gyro Sensor 0 missing'."
        echo "         Hay una copia buena en $HERE/worlds/indoor_zone.sdf"
      fi
    else
      echo "  scan2bim no encontrado; usando la copia del repo"
      cp "$HERE/worlds/indoor_zone.sdf" "$GZ/worlds/indoor_zone.sdf"
    fi

    # registrar el airframe en la ROMFS (unico paso que no es copiar un fichero)
    CML="$AF/CMakeLists.txt"
    if grep -q "$AIRFRAME" "$CML"; then
      echo "  CMakeLists.txt: ya registrado"
    else
      cp "$CML" "$CML.bak"
      last=$(grep -oE '^\s+40[0-9]{2}_gz_[a-z0-9_]+' "$CML" | tail -1 | tr -d '[:space:]')
      [ -n "$last" ] || { echo "ERROR: no encuentro donde anclar el airframe en $CML"; exit 1; }
      python3 - "$CML" "$last" "$AIRFRAME" <<'PY'
import sys
cml, last, new = sys.argv[1:4]
s = open(cml).read()
s = s.replace(f"\t{last}\n", f"\t{last}\n\t{new}\n", 1)
open(cml, "w").write(s)
PY
      echo "  CMakeLists.txt: insertado detras de $last (copia en .bak)"
    fi
    echo
    echo "Ahora recompila para que el airframe entre en la ROMFS:"
    echo "    cd $PX4 && make px4_sitl_default"
    ;;

  diff)
    for m in "${MODELS[@]}"; do
      diff -rq "$HERE/models/$m" "$GZ/models/$m" 2>&1 | sed "s|^|  |" || true
    done
    diff -q "$HERE/airframes/$AIRFRAME" "$AF/$AIRFRAME" 2>&1 | sed "s|^|  |" || true
    echo "(sin salida = la copia esta al dia)"
    ;;

  *)
    sed -n '2,12p' "$0" | sed 's/^# \?//'
    exit 1
    ;;
esac
