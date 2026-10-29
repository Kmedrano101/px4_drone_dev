# Diagnóstico: "Ruido fuerte intermitente al armar" → Saturación de YAW

**Drone:** NxtPX4v2 (PX4) · Motores T-Motor F90 2806.5 1300KV · Quad-X
**Fecha:** 2026-06-19
**Estado:** ✅ RESUELTO Y VERIFICADO

---

## 1. Síntoma reportado

Al armar el dron, **a veces** los motores hacían **mucho ruido** (zumbido/chirrido agudo) y
otras veces armaban suaves y normales. Comportamiento **intermitente entre arranques** —
apagar y volver a armar cambiaba el resultado de forma aparentemente aleatoria.

Primera hipótesis (descartada): desincronización/cogging de los ESC con DShot.

---

## 2. Método de análisis

Se analizaron **11 logs `.ulg`** de ciclos armar/desarmar
(`/home/kmedrano/Documents/QGroundControl/Logs/`) con un script Python sobre `pyulog`:

```bash
source /home/kmedrano/src/Asistente/.venv/bin/activate
python3 /home/kmedrano/src/drone_tunning/analyze_motor_noise.py
```

El script clasifica cada log como **"idle limpio"** vs **"SATURADO"**, y en los saturados
identifica el eje (roll/pitch/yaw) cruzando: salidas de motor, `vehicle_torque_setpoint`,
`vehicle_rates_setpoint`, sticks RC (`manual_control_setpoint`) y modo de vuelo.

---

## 3. Evidencia (datos de los logs)

| Log | Clase | Motores al 100% | Eje |
|---|---|---|---|
| 11_52_39, 12_07_06/33, 12_08_13, 12_13_38/44 | idle limpio | — | — |
| 11_55_18 | SATURADO | 0,1 (FR+RL, CCW) | YAW + |
| 11_57_52 / 11_58_25 / 12_08_45 / 12_09_27 | SATURADO | 2,3 (FL+RR, CW) | YAW − |

En los logs ruidosos:
- **Dos motores de un mismo diagonal (mismo sentido de giro) al 100%** → firma de saturación de YAW.
- **Yaw rate setpoint al máximo** (+6.28 rad/s = 360°/s, o −4.35 rad/s) …
- … con el **stick de yaw centrado (≈0)** → no era input del piloto.
- **Yaw rate medido ≈ 0** (dron en banco, no podía girar) → error de yaw enorme y permanente.
- **Throttle = −1.0 (cero)** y aun así motores al 100%.

Error de heading implícito = yaw_rate_sp ÷ MC_YAW_P (2.8) ≈ **90° a 130°** de desviación.

---

## 4. Causa raíz

**Dos factores combinados:**

### a) Error de heading enorme (la enfermedad)
La brújula había quedado **desactivada** para el tuning en banco:
- `EKF2_MAG_TYPE = None`, `SYS_HAS_MAG = 0`, `CAL_MAG0_PRIO = 0`.

Sin brújula, el **yaw queda sin referencia absoluta** → el estimado de heading deriva /
inicializa mal en cada arranque. En unos arranques el error era ~0 (limpio) y en otros
90–130° (ruidoso). De ahí la **intermitencia**.

El controlador, al ver ese error, ordenaba **girar a tope** para corregir el heading.

### b) `MC_AIRMODE = 2` (el amplificador peligroso)
Con airmode en Roll/Pitch/**Yaw**, el controlador mantiene autoridad de actitud
**incluso a throttle cero** → convierte el error de yaw en **dos motores al 100%** en el suelo.
Sin airmode se habrían quedado en idle.

> El "ruido" eran literalmente **dos motores al 100%** intentando guiñar. Con hélices y
> throttle, el dron habría **girado/volcado violentamente**. Era una alarma real, no un capricho del ESC.

---

## 5. Solución aplicada

| Parámetro | Valor | Motivo |
|---|---|---|
| `CAL_MAG0_PRIO` | **50** | Reactivar la brújula (la calibración seguía intacta: `CAL_MAG0_ID=994337`) |
| `SYS_HAS_MAG` | **1** | Exigir/usar brújula |
| `EKF2_MAG_TYPE` | **0** (Automatic) | EKF vuelve a fusionar el mag → heading con referencia |
| `EKF2_MAG_CHECK` | **1** | Check de calidad de mag activo |
| `MC_AIRMODE` | **0** (Disabled) | Quita la amplificación a 100% en el suelo; no necesario para hover/primeros vuelos |

Reboot tras los cambios.

**Pistas falsas descartadas:** `DSHOT_MIN=0.055` (default, correcto) y `DSHOT_BIDIR_EN=0`
(solo explicaba la ausencia de RPM en los logs; no era la causa).

---

## 6. Verificación

Tras los cambios: **10+ ciclos de armado consecutivos limpios**, incluso **inclinando el dron
y cambiando de posición** — todo suave, sin motores disparándose. Confirmado por el usuario
y reproducible con el script (todos los logs → "idle limpio").

---

## 7. Lecciones

1. **Un ruido intermitente al armar puede ser saturación de control, no un ESC.** Verificar
   con logs antes de tocar los ESC.
2. **Desactivar la brújula tiene efectos colaterales:** sin heading, el yaw deriva y, con
   airmode, eso se traduce en motores al 100% en el suelo.
3. **Airmode en el suelo es peligroso si hay error de actitud.** Mantener `MC_AIRMODE=0`
   hasta tener estimación sólida y estar tuneando de verdad.
4. **El análisis de `.ulg` con pyulog** (salidas de motor + torque/rate setpoint + sticks)
   localiza el eje y la causa de forma objetiva.

---

## 8. Cómo re-analizar

```bash
source /home/kmedrano/src/Asistente/.venv/bin/activate
python3 /home/kmedrano/src/drone_tunning/analyze_motor_noise.py [carpeta_logs]
```
Salida esperada en estado sano: **todos los logs "idle limpio"**.
Cualquier log "SATURADO" indica que el problema reaparece (revisar heading/airmode).
