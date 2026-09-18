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
| 2026-09-11 | [Vuelo offboard 1 — flujo cae en vuelo, failsafe, re-entrada en OFFBOARD](2026-09-11_offboard-vuelo1-flujo-failsafe.md) | 🔄 Flujo inútil >0.5 m en vuelo → failsafe a ALTCTL · ⚠️ PX4 volvió solo a OFFBOARD; lo paró el kill |
| 2026-09-11 | [Vuelo offboard 2 — escape vertical a ~25 m por el LiDAR](2026-09-11_offboard-vuelo2-runaway-rango.md) | ⛔ Casi accidente: `HGT_REF=2` + setpoint +2 m → el LiDAR baja al perder el suelo, el EKF cree descender y sube a ~25 m. Cambios obligatorios |
| 2026-09-11 | [Estimador y sensores en los vuelos offboard](2026-09-11_estimador-sensores-offboard.md) | ⚠️ Saltos de altura = cambios de instancia EKF (acelerómetro vertical malo en EKF0 el 43%); LiDAR sin retorno el 58% en el aire; sin magnetómetro |
| 2026-09-17 | [Validación SLAM 2D manual y mapa congelado](2026-09-17_slam-manual-ld19-congelado.md) | ✅ **Resuelto** — `minimum_travel_distance: 0.0` permite a `slam_toolbox` procesar scans sin odometría de ruedas; mapa y pose en vivo validados |
| 2026-09-17 | [Validación EV al EKF2 en tierra (Prueba 2)](2026-09-17_prueba2-ev-ekf-fusion-validada.md) | ✅ **Éxito** — EKF2 fusiona EV en `POSE_FRAME_NED`; `heading_good_for_control=True` sin mag, `eph=0.046 m`, handshake listo para vuelo |
| 2026-09-17 | [Armado en tierra en Offboard (Prueba 2b)](2026-09-17_prueba2b-armado-tierra-offboard-validado.md) | ✅ Offboard + armado + 5 s en ralentí + auto-desarme |
| 2026-09-18 | [Log 158 — takeoff EV y escape en el patrón en cruz](2026-09-18_takeoff-ev-log158-caida-stabilized.md) | ⛔ Altura y LiDAR 1D bien. En la cruz el **SLAM 2D perdió el tracking** (1.2 Hz, ventana ±0.25 m) y el puente **ocultó su covarianza** → ~3 m de escape; la caída final fue Stabilized con gas a cero |
