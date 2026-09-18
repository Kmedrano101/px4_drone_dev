# Log 158 — dos despegues EV a 1 m: la altura se alcanza; la caída fue por pasar a Stabilized con gas a cero

**Fecha del análisis:** 2026-09-18 · **Log:** SD `sess182/log100.ulg` (id MAVLink 158, bajado por USB con
`scripts/mavlink/logs.py`; `SDLOG_MODE=2`, graba desde el arranque) · **FC#2** PX4 1.14.3 vendor
**Estado:** ✅ causa de la caída identificada · ⚠️ mapa de modos del RC peligroso · ⚠️ pose EV repetida

El log 159, el último de la SD, es el de la sesión en curso por USB: con `SDLOG_MODE=2` crecía
durante la descarga (de 24.7 a 78.8 MB). **Las dos últimas pruebas de vuelo son los dos intentos de este log.**

## 1. Qué pasó

| | Intento A (166–189 s) | Intento B (277–301 s) |
|---|---|---|
| Armado | por comando externo (Pi) | por comando externo (Pi) |
| Setpoint | `z_armado − 1.0` = −1.73 | `z_armado − 1.0` = −1.46 |
| Subida según EKF | 0.98 m (z −0.73 → −1.71) | 0.99 m (z −0.46 → −1.45) |
| LiDAR 1D en hover | 1.34–1.37 m (patas a ~1.18 m) | 1.38–1.42 m (patas a ~1.24 m) |
| Tiempo hasta la altura | ~9 s (vz máx 0.24 m/s) | ~10 s (vz máx 0.28 m/s) |
| Final | LAND de la Pi a 181.5 s, aterrizaje suave, desarme | **cambio de modo a 294.0 s → caída y vuelco** |

**La altura de 1 m se alcanzó las dos veces.** Si acaso se pasó un poco: el EKF (referencia baro,
rango como ayuda condicional) mide ~1.0 m de subida y el LiDAR ~1.2 m. La subida es lenta
(~10 s), lo que en campo puede parecer que "no llega".

## 2. El LiDAR 1D funcionó bien

- 32 016 muestras en 320 s = **100 Hz continuos**, sin huecos.
- 0.17–0.18 m en tierra antes y después de cada vuelo (= `EKF2_MIN_RNG`).
- Durante la subida la lectura crece de forma monótona y sigue al EKF con un desfase casi constante.
- `cs_rng_hgt` entra al despegar y se mantiene en todo el vuelo, sin `rng_fault`.
- Ni valores clavados, ni caídas a 0.02 m (la firma de obstrucción), ni saltos.

## 3. Causa de la caída (intento B)

Secuencia medida:
1. Hover estable en OFFBOARD a ~1 m. Gas del mando **al mínimo (−1.00) todo el vuelo**: en Offboard se ignora.
2. **293.99 s** — el canal 6 (`RC_MAP_FLTMODE=6`) pasa de 999 a 2000: slot 1 → 4 → **6** en 60 ms.
3. `COM_FLTMODE4=1` (Altitude) solo dura 50 ms; **`COM_FLTMODE6=8` = Stabilized** a 294.06 s.
4. En Stabilized el gas va directo al empuje: con el stick abajo, el empuje cae de 0.33 a 0.05 → vz +3.6 m/s.
5. **295.0 s** — golpe y vuelco (roll 173°) → *Attitude failure (roll)* → failsafe. El piloto sube el gas a
   +0.93 en ese mismo instante, ya tarde. Kill switch a 296.2 s.

Horizontalmente iba derivando ±0.3–0.4 m (y +0.40 al final), lo que puede explicar por qué el piloto intervino.

## 4. Pose EV: 20 Hz de mensajes, 1.2–1.6 Hz de información

`vehicle_visual_odometry` llega a 20 Hz, pero la posición solo cambia 1.6 veces/s (A) y 1.2 veces/s (B):
**~93% de los mensajes repiten una pose vieja con sello de tiempo actual**, con `EKF2_EV_DELAY=0`.
Confirma en vuelo la sección 1 de la revisión del 18-sep: el puente republica la TF a 20 Hz aunque el
SLAM solo la actualice a 1–2 Hz. Es candidato directo a la deriva horizontal de ±0.4 m.

## 5. Cambios recomendados (no aplicados)

| Param / código | Ahora | Propuesto | Por qué |
|---|---|---|---|
| `COM_FLTMODE6` | 8 (Stabilized) | **2 (Position)** o 1 (Altitude) | Con gas abajo, Position/Altitude bajan a `MPC_Z_VEL_MAX_DN` (0.8 m/s) controlado; Stabilized corta el empuje |
| Procedimiento | — | **gas al centro antes de salir de Offboard** | En Offboard el stick no hace nada, y se queda donde lo dejaste |
| `ev_odometry_bridge` | republica la TF a 20 Hz | publicar solo cuando el SLAM actualiza, con su sello | Evitar alimentar el EKF con poses viejas como si fueran nuevas |
| `EKF2_EV_DELAY` | 0 | medir | Latencia real del SLAM |
