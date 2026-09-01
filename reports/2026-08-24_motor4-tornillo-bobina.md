# Reporte: Motor M4 (output[3]) — tornillo de fijación haciendo contacto con bobina

**Fecha:** 2026-08-24
**Estado:** ✅ Resuelto — tornillo alejado, todos los motores funcionan correctamente

---

## Síntoma observado

- Olor a electrónico quemado durante las sesiones de prueba indoor (2026-08-11 / 2026-08-12).
- En prueba de arme manual, M4 no giraba correctamente — comportamiento errático / sin respuesta normal.

## Diagnóstico por log (2026-08-12, `10_39_34.ulg`)

Análisis de `actuator_outputs` durante el vuelo real (~5.2s, `cs_in_air=true`):

| Motor | Mean (vuelo) | Max | Δ vs media |
|---|---|---|---|
| output[0] M1 | 483 | **972** ⚠️ | +53 |
| output[1] M2 | 450 | 739 | +20 |
| output[2] M3 | 454 | 812 | +24 |
| **output[3] M4** | **332** | 721 | **−98** ⚠️ |

M4 trabajaba ~30% por debajo del resto. El FC compensaba subiendo M1 hasta casi saturación (972). Esto apuntaba a un fallo mecánico/eléctrico en M4 o su ESC.

## Causa raíz

**Un tornillo metálico de fijación del motor al frame estaba haciendo contacto con la bobina (estátor) del motor M4.**

- El tornillo actuaba como cortocircuito parcial en el devanado → drenaba corriente, frenaba el rotor, generaba calor localizado.
- El olor a quemado era el esmalte aislante del devanado calentándose por la corriente extra.
- El FC detectaba el bajo empuje de M4 y compensaba con los otros motores, particularmente M1.

## Solución

Alejar / reajustar el tornillo metálico para eliminar el contacto con la bobina. Sin modificaciones de firmware ni parámetros.

## Verificación post-fix

- Prueba de arme: los 4 motores responden correctamente.
- **Log de verificación:** `logs/16_28_38.ulg` (2026-08-25, arme idle ~5s con ESC 60A nuevo):

| Motor | Mean | Δ vs media |
|---|---|---|
| output[0] M1 | 109 | −2 ✅ |
| output[1] M2 | 111 | ±0 ✅ |
| output[2] M3 | 110 | −1 ✅ |
| output[3] M4 | 113 | +2 ✅ |

Balance dentro de ±2 unidades (antes M4 tenía Δ=−98). **Verificación completa — listo para test indoor.**

## Lección

Antes de cada sesión de vuelo revisar que los tornillos de fijación de motores al frame **no sobresalgan** hacia el interior del motor. En motores con stator expuesto (outrunner), un tornillo demasiado largo o mal asentado puede tocar las bobinas sin ser visible desde el exterior.
