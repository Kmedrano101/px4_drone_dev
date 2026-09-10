# reports/ — Reportes de diagnóstico (companion / RPi)

Canal compartido para **reportes generados desde la Raspberry Pi** (companion)
o durante pruebas de campo, para analizarlos y resolverlos.

Cada reporte describe **un problema concreto**: contexto, síntomas observados,
lecturas directas (consola MAVLink / topics ROS 2), e hipótesis a investigar.
Así el diagnóstico se hace con datos, no de memoria.

## Convención de nombres

```
YYYY-MM-DD_tema-corto.md
```
Ejemplos:
- `2026-07-23_mtf01-flow-no-valida-indoor.md`
- `2026-07-25_offboard-rx-cero.md`

## Cómo añadir un reporte desde la RPi

**Opción A — generar en la RPi y traer al repo (dev machine):**
```bash
# en la RPi: genera el reporte (ej. reporte.md)
scp reporte.md kmedrano@<dev-ip>:/home/kmedrano/src/drone_tunning/reports/
# en la dev machine:
cd /home/kmedrano/src/drone_tunning
git add reports/ && git commit -m "report: <tema>" && git push
```

**Opción B — clonar el repo en la RPi y commitear directo:**
```bash
# en la RPi (una vez):
git clone git@github.com:Kmedrano101/px4_drone_dev.git
# luego, por cada reporte:
cp reporte.md px4_drone_dev/reports/
cd px4_drone_dev && git pull --rebase && git add reports/ && git commit -m "report: <tema>" && git push
```

## Plantilla

Usa [`TEMPLATE.md`](TEMPLATE.md) como base para cada reporte nuevo — mantiene la
estructura consistente (contexto, síntoma, lecturas, hipótesis, qué no se tocó).

## Índice de reportes

| Fecha | Reporte | Estado |
|---|---|---|
| 2026-07-23 | [MTF-01 EKF2 tuning (flow no valida indoor)](2026-07-23_mtf01-ekf2-tuning.md) | ✅ Caso B confirmado en vuelo (2026-08-12): flow no fusiona sin yaw → necesita Livox+FAST-LIO |
| 2026-08-24 | [Motor M4 — tornillo haciendo contacto con bobina](2026-08-24_motor4-tornillo-bobina.md) | ✅ Resuelto — tornillo alejado, todos los motores OK |
| 2026-09-04 | [FC#2 vendor 1.14.3 — MTF-01P integrado + migración de params](2026-09-04_fc2-vendor-1143-mtf01p-migracion.md) | ✅ Sensor OK y 97 params migrados · ⛔ **sin magnetómetro** → mismo bloqueo de yaw que 2026-07-23 |
| 2026-09-08 | [EKF2 y flujo óptico en el SITL](2026-09-08_ekf2-no-converge-sitl.md) | ✅ **Resuelto** — 3 params EKF2 mal migrados rompían la fusión de flujo; ciclo completo verificado. Queda arranque intermitente ~2/7 |
