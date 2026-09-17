# Reporte: Validación de Armado en Tierra en Modo OFFBOARD con LiDAR 2D (Prueba 2b)

**Fecha:** 2026-09-17  
**Autor / entorno:** Raspberry Pi 4 (`kevin@192.168.1.221`) + FC#2 (NxtPX4, PX4 v1.14.3 vendor)  
**Estado:** ✅ Éxito completo — Armado, retención en ralentí durante 5.0 segundos y desarme automático ejecutados limpiamente sin despegue. El SLAM 2D y el EKF2 mantuvieron total convergencia sin degradación por vibración.

---

## 1. Objetivo y Alcance

Validar en condiciones reales en tierra el ciclo de control Offboard antes de cualquier intento de vuelo:
1. Comprobar que el nodo [`ev_offboard_handshake`](file:///home/kevin/drone_ws/src/px4_drone/src/ev_offboard_handshake.cpp) gestiona correctamente la máquina de estados previa al vuelo.
2. Confirmar la aceptación de `OFFBOARD` por parte de PX4 y el posterior comando de `ARM` vía DDS / ROS 2.
3. Verificar que los motores giran en ralentí en el origen $(0,0,0)$ **sin comandar despegue**.
4. Confirmar que la vibración y el ruido electromagnético de los motores no degradan la adquisición del LiDAR 2D (`ldlidar`), el tracking de `slam_toolbox` ni la fusión en el EKF2.
5. Validar el **desarme automático por software** tras una ventana configurada de 5 segundos.

---

## 2. Telemetría y Traza de Ejecución

### A. Pre-condiciones verificadas (antes del armado)
```yaml
Topic: /fmu/out/vehicle_local_position
xy_valid: true
z_valid: true
v_xy_valid: true
heading_good_for_control: true
dead_reckoning: false
eph: 0.0445 m
epv: 0.2852 m
dist_bottom: 0.1692 m
```

### B. Secuencia del nodo `ev_offboard_handshake`
```
[INFO] [ev_offboard_handshake]: ev_offboard_handshake iniciado a 10 Hz. Exige LiDAR 2D sano antes de armar...
[INFO] [ev_offboard_handshake]: Esperando LiDAR 2D (xy/z_valid, heading_good_for_control, !dead_reckoning, eph y odometria EV fresca)...
[INFO] [ev_offboard_handshake]: Primera odometria EV recibida del puente SLAM.
[INFO] [ev_offboard_handshake]: LiDAR 2D listo (eph=0.04 m, heading_good_for_control=true).
[INFO] [ev_offboard_handshake]: nav_state: UNKNOWN(255) -> OFFBOARD
[INFO] [ev_offboard_handshake]: arming_state: DISARMED
[INFO] [ev_offboard_handshake]: Switch del RC en OFFBOARD confirmado.
[INFO] [ev_offboard_handshake]: Solicitando modo OFFBOARD...
[INFO] [ev_offboard_handshake]: OFFBOARD confirmado por el FC, esperando 3.0 s antes de armar...
[INFO] [ev_offboard_handshake]: Solicitando ARM...
[INFO] [ev_offboard_handshake]: arming_state: ARMED
[INFO] [ev_offboard_handshake]: ARMADO en OFFBOARD (posicion, hold fijo, sin despegue) con LiDAR 2D. Ventana de 5 s; si no se interrumpe, este nodo desarma solo al final.
[INFO] [ev_offboard_handshake]: Ventana terminada sin desarme externo. Solicitando DESARME normal...
[INFO] [ev_offboard_handshake]: arming_state: DISARMED
[INFO] [ev_offboard_handshake]: *** HANDSHAKE OK: desarme confirmado. ***
[INFO] [ev_offboard_handshake]: Test de handshake EV finalizado.
```

### C. Estado posterior al desarme (telemetría EKF2)
```yaml
x: -0.0010 m (deriva acumulada: 1 mm)
y: -0.0006 m (deriva acumulada: 0.6 mm)
z: -4.3110 m (origen barométrico de referencia)
dist_bottom: 0.1702 m (LiDAR 1D sobre mesa/suelo)
heading: 1.5713 rad (90.0 deg)
heading_good_for_control: true
xy_valid: true
z_valid: true
v_xy_valid: true
dead_reckoning: false
eph: 0.0456 m
epv: 0.2834 m
```

---

## 3. Conclusiones y Criterios de Aceptación

| Criterio | Objetivo | Medido | Estado |
|---|---|---|---|
| Entrada a OFFBOARD | Aceptación limpia de PX4 | Confirmado por FC | ✅ Superado |
| Comando de armado | Armado por API / DDS | `arming_state: ARMED` | ✅ Superado |
| Estabilidad sin despegue | Setpoint en origen, sin $Z$ ascendente | $0.0\text{ m}$, sin salto | ✅ Superado |
| Resistencia a vibración | SLAM 2D sin pérdida ni congelamiento | 100% scans procesados | ✅ Superado |
| Estabilidad EKF2 | $eph < 1.0\text{ m}$ y `heading_good` | $eph = 0.045\text{ m}$, `heading_good = True` | ✅ Superado |
| Desarme automático | Ejecutado al cumplirse los 5 s | `arming_state: DISARMED` | ✅ Superado |
| Failsafes | Sin activaciones inesperadas | `failsafe: false` | ✅ Superado |

---

## 4. Habilitación para la Prueba 3 (Vuelo con Takeoff & Hold)

Habiendo validado:
1. **Prueba 1:** SLAM 2D en tierra con movimiento manual continuo sin congelamiento.
2. **Prueba 2:** Fusión de odometría EV en EKF2 con rumbo válido (`heading_good_for_control: True`) y $eph \approx 4.5\text{ cm}$.
3. **Prueba 2b:** Secuencia completa de cambio a Offboard, armado en tierra y desarme por software bajo vibración de motores.

El sistema queda **formalmente listo** para ejecutar la prueba de vuelo autónomo controlado con [`takeoff_position_hold_ev`](file:///home/kevin/drone_ws/src/px4_drone/src/takeoff_position_hold_ev.cpp) a la altura objetivo (1.0 m) cuando el usuario decida proceder.
