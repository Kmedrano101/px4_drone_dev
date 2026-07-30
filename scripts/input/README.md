# scripts/input/

Suelta aquí los archivos **`.ulg`** que quieras analizar.

Los scripts de `scripts/` leen de esta carpeta **por defecto** (sin argumentos):

```bash
cd scripts
cp /home/kmedrano/Documents/QGroundControl/Logs/2026-07-22/*.ulg input/
python3 analyze_temperature.py      # procesa TODOS los .ulg de input/
```

También puedes pasar una ruta o carpeta explícita:
```bash
python3 analyze_temperature.py /ruta/al/log.ulg
python3 analyze_temperature.py 09_41_55.ulg     # nombre suelto -> se busca en input/
```

Los `.ulg` de esta carpeta **no se versionan** (`.gitignore`); solo este README.
Los plots resultantes van a `scripts/output/<log>/`.
