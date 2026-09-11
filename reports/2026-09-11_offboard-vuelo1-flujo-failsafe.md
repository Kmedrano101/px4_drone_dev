# Reporte: primer vuelo offboard real — el flujo óptico cae en vuelo, failsafe y re-entrada automática en OFFBOARD

**Fecha del análisis:** 2026-09-11 · **Log:** `logs/log100.ulg` (163 s; la SD lo fecha en 2000-01-01 porque sin GPS el FC no tiene hora real)
**Autor / origen:** RPi companion (nodo offboard por uXRCE-DDS) + análisis del `.ulg`
**Estado:** 🔄 causa del fallo identificada · ⛔ la causa física de la pérdida de flujo **no está aislada** · ⚠️ riesgo grave detectado (re-entrada en OFFBOARD)

**Contexto:** FC#2 (NxtPX4v2, PX4 1.14.3 de fábrica `micoair743-v1.14.3`), MTF-01P en TEL4,
sin GPS ni brújula. `SDLOG_PROFILE=3` (estimator replay). Geometría ya corregida: `CA_ROTOR*_PX/PY = ±0.159` ✅.
Parámetros de escape por RC **sin cambiar** (`COM_RC_OVERRIDE=1`, `COM_RCL_EXCEPT=4`, `COM_OBL_RC_ACT=0`).

**Objetivo:** despegue en offboard por posición a 1.6 m, hold y pequeño desplazamiento en X, comandado desde la Pi.

---

## 1. Línea temporal

| t (s) | Evento | Evidencia |
|---|---|---|
| 107.31 | La Pi empieza a publicar setpoints | `offboard_control_signal_lost → False` |
| 112.29 | La Pi pide OFFBOARD | `DO_SET_MODE p1=1 p2=6` → ACCEPTED |
| 113.37-113.56 | Piloto mueve el switch 6 → 4 → **1 (Offboard)** | `mode_slot` |
| 115.34 | La Pi arma | `ARM_DISARM p1=1` → ACCEPTED |
| 116 | Setpoint `z=-1.6 m` (`x=0`) | `trajectory_setpoint` |
| 118.0 | En el aire | `cs_in_air` |
| **121.0** | **Calidad de flujo 28 < `EKF2_OF_QMIN=30`** a 0.62 m → flujo rechazado | `vehicle_optical_flow` |
| 121-126 | Dead-reckoning inercial; el dron sube a 1.6 m inclinado hasta **pitch −8.5°, roll −5.5°** | `vehicle_attitude` |
| **126.04** | **`local_position_invalid`** (= 121.0 + `EKF2_NOAID_TOUT` 5 s) | `failsafe_flags` |
| **126.05** | **Failsafe → ALTCTL** (el switch sigue en slot 1: no fue el piloto) | `nav_state`, `mode_slot` |
| 126-132 | ALTCTL mantiene 1.4-1.6 m. La XY estimada se escapa a 3 m/s con roll/pitch en ±0.6° | `vehicle_local_position` |
| 128 | La secuencia de la Pi avanza a `x_sp=+0.49` **estando en failsafe** | `trajectory_setpoint` |
| 131.5-132 | Piloto baja el gas (−0.91) → descenso | `manual_control_setpoint` |
| **132.67** | **Kill switch** → `manual_lockdown`, `actuator_outputs` a 0 al instante | `actuator_armed`, `actuator_outputs` |
| 133.0 | Impacto desde ~0.7 m: vz 1.52 m/s, pitch −10°, luego roll −8°, yaw 15° → 41° | |
| **133.86** | **Posición válida de nuevo en el suelo → PX4 vuelve solo a OFFBOARD** | `nav_state`, `failsafe_flags` |
| 133.9-137.5 | El controlador pide subir a 1.6 m e ir ~11 m hacia el setpoint: motores 3-4 a 0.9-1.0, motor 2 a 0. **El kill mantiene las salidas a 0** | `actuator_motors` vs `actuator_outputs` |
| 137.67 | Desarme automático (`COM_KILL_DISARM=5` s tras el kill) | |

## 2. Hallazgo principal: el flujo óptico deja de funcionar en vuelo por encima de ~0.5 m

| Altura | Muestras | Calidad media | Rechazadas (<30) | Gas |
|---|---|---|---|---|
| 0.00-0.15 m | 8 | 158 | 0% | 0.16 |
| 0.30-0.50 m | 1 | 114 | 0% | 0.30 |
| **0.50-0.80 m** | 2 | **14** | **100%** | 0.29 |
| 0.80-1.20 m | 5 | 12 | 100% | 0.29 |
| 1.20-1.80 m | 17 | 14 | 100% | 0.30 |

- Por encima de 0.6 m el sensor saca **`pixel_flow = 0.000` exacto** con calidad 1-20: no es flujo ruidoso, es **ausencia de dato**.
- Con el **mismo gas** (~0.30), la calidad pasa de 114 a 0.4 m a 14 a 0.7 m → depende de la altura.
- En el banco, a mano y sin motores (2026-09-07), a 1 m daba 45-100. **Algo del vuelo lo empeora**. Candidatos, sin aislar:
  - **vibración**: métrica de vibración del acelerómetro de 0.04 en suelo a **2.50 en vuelo** (máx 3.72), y giróscopo de 0.008 a 0.13, en las dos IMU;
  - **textura/iluminación del suelo** en la zona de vuelo;
  - montaje del sensor.
- ⚠️ **No bajar `EKF2_OF_QMIN`**: fusionaría esos ceros como "velocidad cero", y el EKF creería el dron quieto mientras deriva.

### Lo que NO fue el problema

- **La cadena flujo → terreno del EKF**: `cs_opt_flow` activo el 100% del vuelo, terreno estimado (innovación `hagl` rms 0.09 m). La conclusión del [reporte del SITL del 2026-09-08](2026-09-08_ekf2-no-converge-sitl.md) (`RNG_CTRL=2` rompe el flujo) **no se reproduce en el FC real**: el SITL corre `main`/1.17, con el terreno dentro del filtro principal; la 1.14.3 tiene un estimador de terreno separado que no mira `RNG_CTRL`.
- ~~**La altura**: el LiDAR sostuvo bien 1.6 m (innovación rms 0.09 m). El barómetro leyó ~1 m de más, perturbado por las hélices.~~
  ⚠️ **Corregido el 2026-09-11: razonamiento circular.** Con `HGT_REF=2` el rango *es* la referencia, así que su innovación es pequeña por construcción: eso no demuestra que acierte. El [vuelo 2](2026-09-11_offboard-vuelo2-runaway-rango.md) §6 muestra que el LiDAR lee un 30-40% de menos por encima de ~1.5 m. Lo más probable es que aquí fuera **el LiDAR el que leía bajo** (1.84 m ≈ 2.5 m reales según el barrido de banco) y que el dron volara a ~2.5 m, no a 1.6 m.

  > ⚠️ **Invalidado por el [vuelo 2](2026-09-11_offboard-vuelo2-runaway-rango.md)**: con `HGT_REF=2` y un setpoint por encima del rango del LiDAR, el dron se escapó a ~25 m. Se vuelve a `HGT_REF=0`.

  → ~~Esto revisa la recomendación anterior de `EKF2_HGT_REF=0`~~: dentro de la envolvente indoor (≤1.5 m) el rango es ~4× mejor que el barómetro. El riesgo del LiDAR está en subir por encima de ~2 m, no en el hover bajo.

## 3. Riesgo grave: re-entrada automática en OFFBOARD

Tras un failsafe, PX4 **vuelve al modo que el usuario pidió** en cuanto la condición desaparece. Aquí:

- la intención del usuario seguía siendo OFFBOARD (switch en slot 1, sin mover);
- la Pi **seguía publicando** `offboard_control_mode` + setpoints;
- al tocar el suelo el flujo recuperó calidad → posición "válida" → **OFFBOARD a 133.86 s**, con la posición estimada a (−10.4, +6.7) m y el setpoint en (+0.49, 0, −1.6).

El controlador pidió subir 1.6 m y desplazarse ~11 m con la inclinación máxima. **Sin el kill switch activo el dron habría despegado de lado.**

## 4. El nodo de la Pi

- Mandó `DO_SET_MODE` y `ARM`, **nunca LAND**.
- Su secuencia **siguió avanzando durante el failsafe** (`x_sp → +0.49` a 128 s): no vigila `nav_state`.
- ⚠️ La versión que corrió en la Pi **no es** `px4_drone/scripts/offboard_hardware.py` de este equipo (esa sube a −1.0 m y aterriza al llegar). Hay que sincronizar las dos copias.

## 5. Qué cambiar antes del próximo vuelo

**Nodo offboard (Pi)** — lo más urgente:
1. Si `nav_state != OFFBOARD` o `vehicle_status.failsafe`: **dejar de publicar** `offboard_control_mode` y detener la secuencia. Sin heartbeat offboard, PX4 no puede volver a OFFBOARD.
2. Terminar la secuencia con `NAV_LAND` explícito y un timeout.
3. Comprobar `xy_valid` antes de mandar setpoints de posición.

**Procedimiento del piloto:**
4. Al primer failsafe, **sacar el switch del slot 1** (a Altitude, slot 4). El switch solo actúa al cambiar, y así la intención del usuario deja de ser Offboard.

**Flujo óptico:**
5. Hasta aislar la causa, **pruebas offboard a ≤0.4 m**, donde la calidad fue >100.
6. Tests para aislarla: alfombrilla con textura bajo el dron; montaje del MTF-01P sobre goma; revisar el equilibrado de hélices (vibración 60× respecto al suelo); hover manual a 0.4 / 0.7 / 1.0 m con `SDLOG_PROFILE=3`, comparando calidad y vibración.

**Parámetros aún pendientes** (sin cambios en este vuelo): `COM_RC_OVERRIDE=3`, `COM_RCL_EXCEPT=0`, `COM_OBL_RC_ACT`. Sobre `EKF2_HGT_REF`, ver §2: se mantiene en rango mientras el vuelo quede por debajo de 1.5 m.

## Archivos

| Archivo | Qué es |
|---|---|
| `logs/log100.ulg` | log del vuelo (7.5 MB, bajo el umbral de 10 MB) |
