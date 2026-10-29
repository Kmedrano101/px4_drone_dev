# Reporte: Validación RTK en campo — fixed, dispersión 2 mm

**Fecha:** 2026-10-27
**Autor / origen:** campo (Ávila, zona plana) + RPi companion + QGC
**Estado:** ✅ resuelto (RTK validado); pendiente test EKF2 armado en tierra antes de volar

**Contexto:** FC#2 (HKUST NxtPX4v2, PX4 1.17, board `hkust/nxt-dual`), ZED-F9P por GPS1, perfil
**outdoor** ya aplicado (`EKF2_GPS_CTRL=7`, `HGT_REF=0`, failsafe Land). Correcciones RTCM del
caster IGN "tiempo real" (SPTR), mountpoint `VRS3M`, reenviadas por QGC vía MAVLink. Objetivo:
confirmar, **antes de volar**, que el RTK engancha y qué aporta frente al GPS autónomo, capturando
en el **mismo punto** una toma sin correcciones y otra con correcciones.

**Objetivo de la sesión:** cuantificar el beneficio real del RTK para decidir si merece la pena
para el vuelo, y dejar listo el chequeo EKF2+GPS armado en tierra.

---

## 1. Procedimiento

Dos tarjetas de la webui (`gps_rtk_validate.py`), dron quieto en el mismo punto:

1. **Toma 1 — SIN correcciones** (`--label sin_corr`): NTRIP desactivado en QGC → GPS autónomo.
2. **Toma 2 — CON correcciones** (`--label con_corr`): NTRIP activo (caster IGN `VRS3M`) → RTK.
3. **Comparar** (`gps_rtk_compare.py`): dispersión, eph, fix y offset entre centroides.

Ficheros (en la Pi, `~/drone_ws/src/px4_drone/tools/webui/logs/sensor_eval/`):
`2026-10-27_11-42-51_sin_corr_gps_rtk.csv` · `2026-10-27_11-43-43_con_corr_gps_rtk.csv` ·
`2026-10-27_12-48-29_gps_rtk_compare.txt`. (Hubo un arranque abortado previo a las 11:41:59 con 0
muestras; se ignora.)

## 2. Resultados (salida del comparador)

| Métrica                | Sin corr. (autónomo) | Con corr. (RTK) |
|------------------------|----------------------|-----------------|
| Muestras               | 22                   | 91              |
| Mejor fix / distrib.   | 3D (22/22)           | **RTK-fixed (91/91)** |
| Satélites (media/máx)  | 29 / 29              | 29 / 29         |
| Dispersión RMS         | 0.103 m              | **0.002 m**     |
| Dispersión máx         | 0.203 m              | 0.009 m         |
| eph media / mín        | 0.51 / 0.51 m        | 0.56 / 0.56 m   |
| Centroide              | 40.6504293, −4.6794206 | 40.6504393, −4.6794219 |
| **Offset A→B**         | —                    | **1.119 m**     |

Veredicto del comparador: **RTK MEJORA**. Mapa a escala (artifact, solo lectura):
`https://claude.ai/artifact/3kZet9oqaQ4vxh5hKALCbM`.

## 3. Conclusión del análisis — exactitud absoluta ≠ precisión

Hay que separar dos cosas que se confunden:

- **Exactitud absoluta (¿dónde estoy en el mundo?): prácticamente igual.** El autónomo ya acierta a
  ~1 m con 29 sats y cielo abierto; el RTK lo corrige esos **1.12 m**. A escala de un mapa (Google
  Maps) **ambos caen en el mismo sitio** — el RTK no cambia nada apreciable aquí. Además ese 1.12 m
  es una foto de 21 s; el autónomo puede derivar varios metros en minutos, así que es un **mínimo**,
  no el peor caso.
- **Precisión / estabilidad (¿cuánto baila la posición?): el RTK gana ×59, y es lo que importa para
  volar.** Con el dron **quieto**, el autónomo salta ±10 cm (hasta 20 cm); el RTK se queda en ±2 mm.

**Implicación práctica:** el RTK no sirve para "saber dónde estás en el mapa" (eso ya lo hacía el GPS
normal), sino para que la posición **no se mueva**: position hold firme, waypoints repetibles, y
sobre todo que el **EKF2 no tenga que pelear contra una medida ruidosa**. Esos ±10 cm de ruido del
autónomo son justo lo que hace derivar a un multirrotor en "mantener posición".

## 4. Matiz técnico — el `eph` no refleja el RTK

En RTK-fixed el `eph` de `GPS_RAW_INT` **no baja** (0.51 → 0.56 m) pese a que la dispersión real sea
2 mm. Es un artefacto del firmware: el campo `eph` no refleja la solución RTK. **La métrica fiable es
la dispersión real, no el eph.** Consecuencia para las herramientas: `ekf_rtk_armed_check.py` usa
`--eph-max` (default 1.0) — con RTK fixed el eph se queda en ~0.5, así que ese umbral **no sirve para
detectar RTK**; para eso mirar `fix_type` (5/6) y la deriva/dispersión. Con el default 1.0 el eph
pasa el veredicto (0.56 ≤ 1.0), así que no da falso REVISAR.

## 5. Estado y próximos pasos

- ✅ Brújula calibrada en QGC (prearm de interferencia magnética ya no bloquea).
- ⏳ **Test EKF2 + GPS RTK armado en tierra** (`ekf_rtk_armed_check.py`, tarjeta webui): hélices
  fuera, NTRIP on con RTK-fixed, Kevin arma por RC/QGC, monitoriza ~15 s y auto-desarma. Verifica
  `POS_HORIZ_ABS` sostenido, sin glitches, actitud/velocidad estables, `mag_ratio<1.0`, deriva local.
  Es el que confirma que la estabilidad RTK llega al estimador antes de volar.
- ⏳ Batería: corriente sin calibrar (`BAT1_A_PER_V`), fiarse del voltaje, no del %.
- ⏳ Vuelo outdoor real tras el chequeo armado.

## Referencias

- Doc de configuración: `docs/planes/2026-10-21_outdoor_gps_zedf9p_position_hold.md`.
- Caster/credenciales: memoria `ign-ntrip-caster-sptr`.
- Resultado y conclusión: memoria `rtk-campo-fixed-2mm-27oct`.
