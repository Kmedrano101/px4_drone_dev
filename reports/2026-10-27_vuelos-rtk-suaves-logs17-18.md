# Reporte: dos vuelos RTK suaves (logs 17 y 18) — calidad de vuelo y autonomía real

**Fecha:** 2026-10-27
**Autor / origen:** campo + RPi companion (descarga de .ulg por MAVLink)
**Estado:** ✅ vuelos sanos y documentados

**Contexto:** FC#2 (HKUST NxtPX4v2, STM32H743, PX4 1.17), RJX F450, pack LiPo 6S
1300 mAh 100C (222 g). GPS ZED-F9P con correcciones NTRIP del IGN (caster
`ergnss-tr.ign.es:2101`, mountpoint `VRS3M`), RPi4 conectada. Perfil outdoor
aplicado (ver [[perfiles-indoor-outdoor-fc2]]). Kevin reportó *"un vuelo muy
suave"* y pidió revisar los logs para documentar.

**Objetivo:** confirmar objetivamente la calidad de vuelo (suavidad, salud del
estimador, RTK en el aire) y fijar la autonomía real para escalar al pack de
4500 mAh.

---

## 1. Qué se voló

Dos registros de la tarde del 2026-10-27, descargados del FC por MAVLink
(`logs.py`, ~10 KB/s, ~3 h las dos):

| Log | Hora | Tamaño | Armado | Modos (durante armado) | Altura máx | Recorrido XY |
|---|---|---|---|---|---|---|
| **flight_17** | 13:42 | 53 MB | **201.5 s** (3.4 min) | POSCTL 136 s · STAB 65 s | 1.03 m | 5.5 × 2.8 m |
| **flight_18** | 13:51 | 63 MB | **289.8 s** (4.8 min) | STAB 171 s · POSCTL 119 s | 9.44 m | 5.3 × 7.5 m |

flight_17 fue un hover bajo (~1 m) y flight_18 subió hasta ~9.4 m con más
maniobra manual (STAB). Los `.ulg` **no** se suben al repo (regla de >5 MB,
ver [[limite-logs-5mb]]); los resúmenes de texto quedan en el reporte.

## 2. Lecturas directas (analyze_flight.py, pyulog, en la Pi)

```
=== flight_17 ===
GPS en vuelo:   fix: DGPS 3% · RTK-fixed 97%   sats ~28   eph medio 0.02 m
Actitud:        roll -2.7° (sd 2.6)  pitch -0.3° (sd 2.4)
                ERROR seguimiento actitud: RMS 2.02°  p95 3.02°  max 8.54°
                vel. angular sd: roll 4.8  pitch 5.1  yaw 3.1 °/s
Bateria:        V 24.98 → 22.98 (fin)  min 22.17  (celda min 3.70 V)
EKF test ratios: vel 0.15 · pos 0.04 · hgt 0.07  (umbral 1.0)
STATUSTEXT:     49 mensajes, 0 de nivel <=WARNING

=== flight_18 ===
GPS en vuelo:   fix: DGPS 7% · RTK-float 1% · RTK-fixed 92%   sats ~28   eph medio 0.03 m
Actitud:        roll -0.7° (sd 2.9)  pitch -0.8° (sd 2.3)
                ERROR seguimiento actitud: RMS 2.33°  p95 5.96°  max 16.39°
                vel. angular sd: roll 10.9  pitch 7.7  yaw 4.7 °/s
Bateria:        V 24.98 → 22.60 (fin)  min 21.62  (celda min 3.60 V)
EKF test ratios: vel 0.23 · pos 0.05 · hgt 0.06  (umbral 1.0)
STATUSTEXT:     56 mensajes, 0 de nivel <=WARNING
```

Puntos clave:
- **RTK mantenido en el aire:** fixed el 97 % (log 17) y 92 % (log 18) del tiempo
  armado. El resto es DGPS (reconexiones puntuales de la VRS), nunca cayó a 3D.
- **Estimador sin estrés:** los cuatro *test ratios* del EKF2 por debajo de 0.25
  en todo momento (el umbral de rechazo es 1.0). GPS RTK + baro consistentes,
  sin saltos de instancia.
- **Suavidad confirmada:** error de seguimiento de actitud **~2° RMS** en ambos,
  sin un solo STATUSTEXT de nivel WARNING en 105 mensajes combinados. flight_17
  (hover bajo) fue el más tranquilo (vel. angular sd ~5°/s); flight_18 fue más
  activo (roll sd 10.9°/s) por la subida a 9.4 m y la maniobra manual en STAB,
  pero igual de bien controlado.

## 3. Autonomía real y escalado al pack de 4500 mAh

flight_18 es la mejor referencia porque descargó el pack hasta el voltaje de
aterrizaje seguro:

- **4.83 min armado**, de 24.98 V a un mínimo bajo carga de **21.62 V = 3.60 V/celda**
  (justo el umbral de aterrizaje que fijamos, ver [[bateria-cal-voltaje-ok-corriente-no]]).
- Es decir, el pack de **1300 mAh da ≈ 5 min de vuelo real** con este perfil mixto
  (hover + STAB + subida a 9 m), hasta aterrizar con margen.

Escalado al pack de **4500 mAh 60C 6S (510 g)** por teoría de cantidad de movimiento
(hover `P ∝ AUW^1.5`):

```
AUW actual ≈ 1.00 kg;  pack nuevo +288 g → AUW ≈ 1.29 kg
factor = (Cap2/Cap1) × (AUW1/AUW2)^1.5
       = (4500/1300) × (1.00/1.29)^1.5 = 3.46 × 0.684 = 2.37×
autonomía ≈ 4.8 min × 2.37 ≈ 11 min  (perfil mixto, hasta 3.6 V/celda)
```

- **Estimación fijada: ~10-12 min** con el pack de 4500 mAh para este mismo perfil
  (más si el vuelo es un hover suave y menos agresivo que flight_18).
- ⬆️ **Revisión al alza** de la estimación previa de ~7-9 min: aquella usaba una
  base de ~3 min; ahora tenemos un tiempo armado real de **4.8 min hasta voltaje
  de aterrizaje**, que sube la referencia.
- 60C del pack = 270 A continuos, muy por encima de lo que piden los 4× T-Motor
  F90 (pico ~45 A c/u). **60C sobra** (confirmado en sesión anterior).

## 4. Qué NO se tocó / advertencias de lectura

- **La dispersión de "HOLD" del analizador NO es precisión de position hold aquí.**
  El filtro (vel < 0.3 m/s) marca 0.48 m (log 17) y 1.60 m RMS (log 18), pero gran
  parte del armado fue **STAB (manual)** y los tramos POSCTL incluyeron traslación
  y subida deliberadas → esos números son estadística del sobre de vuelo, no deriva
  en estático. La precisión real del RTK quieto son los **2 mm** del test de
  dispersión aparte (ver [[rtk-campo-fixed-2mm-27oct]]).
- **La corriente del log sigue sin calibrar** (`BAT1_A_PER_V=17`, marca ~14 A que
  no son reales). La autonomía de arriba se deriva del **voltaje**, no de amperios.
  Pendiente: calibrar `A_PER_V` en banco (hélices fuera, pinza/vatímetro, Kevin
  arma) y re-habilitar `BAT1_CAPACITY=1300`.
- **Matiz del `eph`:** en estos logs `vehicle_gps_position` sí reporta `eph` bajo
  (0.02-0.03 m) coherente con el RTK-fixed. El artefacto de *"el eph no baja"*
  (~0.5 m) era específico del campo `GPS_RAW_INT` por MAVLink que usa la
  herramienta de comparación, no del topic del driver/EKF.

## 5. Estado y próximos pasos

- ✅ Vuelos sanos y suaves confirmados con datos (RTK, EKF, actitud, batería).
- ✅ Autonomía real fijada (~5 min con 1300 mAh → ~10-12 min proyectados con 4500 mAh).
- ⏳ Calibrar `BAT1_A_PER_V` en banco y re-habilitar el conteo de culombios.
- ⏳ Test EKF2 + GPS RTK armado en tierra (brújula ya calibrada).

**Relacionado:** [[rtk-campo-fixed-2mm-27oct]] · [[bateria-cal-voltaje-ok-corriente-no]] ·
[[perfiles-indoor-outdoor-fc2]] · reporte `2026-10-27_campo-rtk-validado-fixed.md`.
