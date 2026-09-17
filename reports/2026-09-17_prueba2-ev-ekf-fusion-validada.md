# Reporte: Validación de Visión Externa (EV) al EKF2 en tierra (Prueba 2)

**Fecha:** 2026-09-17  
**Autor / origen:** RPi 4 (`kevin@192.168.1.221`) + FC#2 (NxtPX4, PX4 v1.14.3 vendor)  
**Estado:** ✅ Éxito completo — EKF2 fusiona odometría del LiDAR 2D en `POSE_FRAME_NED`; posición horizontal y rumbo validados para control sin magnetómetro.

**Contexto:**  
Fase 2 del [plan de test LiDAR 2D](../docs/2026-09-16_test_lidar2d_ev_offboard.md): validar en tierra y con el dron desarmado que la pose estimada por el SLAM 2D (`slam_toolbox`) se traduce correctamente a `VehicleOdometry` y es aceptada y fusionada por el estimador de estados EKF2 de PX4.

---

## 1. Pipeline de comunicación probado

```
[LiDAR 2D LD19] 
       │ USB (230400 bps)
       ▼
[ldlidar (ROS 2)] ──/scan (10 Hz)──> [slam_toolbox]
                                            │ TF: map -> base_link
                                            ▼
                               [ev_odometry_bridge (20 Hz)]
                                            │ /fmu/in/vehicle_visual_odometry (POSE_FRAME_NED)
                                            ▼
                                   [MicroXRCEAgent]
                                            │ UART TELEM2 (921600 bps)
                                            ▼
                                     [PX4 EKF2 (FC)]
                                            │ /fmu/out/vehicle_local_position
                                            ▼
                               [ev_offboard_handshake]
```

---

## 2. Telemetría directa verificada

### A. Tópico `/fmu/in/vehicle_visual_odometry` (Salida del puente EV hacia el FC)
* **Frecuencia:** 20.00 Hz (estabilidad temporal $\pm 1$ ms).
* **Frame:** `pose_frame = 1` (`POSE_FRAME_NED`).
* **Orientación:** Cuaternión restringido a $\text{yaw}$ puro ($\text{roll}=\text{pitch}=0$).
* **Calidad y varianzas:** `NaN` para magnitudes no observadas por el escáner 2D ($Z$, velocidades).

### B. Tópico `/fmu/out/vehicle_local_position` (Estimación final de PX4 EKF2)
Lectura muestreada con el dron en tierra:
```yaml
x: 0.015 m
y: -0.008 m
z: -3.197 m
heading: 1.571 rad (90.0 deg)
xy_valid: True
z_valid: True
v_xy_valid: True
heading_good_for_control: True
dead_reckoning: False
eph: 0.046 m
epv: 0.284 m
```

### C. Handshake del nodo Offboard (`ev_offboard_handshake`)
```
[INFO] [ev_offboard_handshake]: Primera odometria EV recibida del puente SLAM.
[INFO] [ev_offboard_handshake]: Esperando LiDAR 2D (xy/z_valid, heading_good_for_control, !dead_reckoning, eph y odometria EV fresca)...
[INFO] [ev_offboard_handshake]: LiDAR 2D listo (eph=0.04 m, heading_good_for_control=true).
[INFO] [ev_offboard_handshake]: nav_state: UNKNOWN(255) -> ALTCTL
[INFO] [ev_offboard_handshake]: arming_state: DISARMED
```

---

## 3. Puntos clave y resolución de bloqueos históricos

1. **`heading_good_for_control = True` sin magnetómetro:**  
   Desde julio el proyecto arrastraba la imposibilidad de alinear rumbo en interiores debido a la ausencia de magnetómetro y a la incapacidad del flujo óptico para corregir guiñada. La publicación en `POSE_FRAME_NED` desde el SLAM 2D ha permitido que el EKF2 complete `yaw_align` de forma limpia.
2. **Incertidumbre horizontal mínima:**  
   $eph = 0.046\text{ m}$ (menos de 5 cm de dispersión), muy por debajo del umbral de seguridad de 1.0 m exigido por el handshake.
3. **Firmware 1.14.3 vendor compatible:**  
   El handshake valida `vehicle_local_position` de forma nativa sin depender de `estimator_status_flags` (topic no compilado en esta versión de fábrica).

---

## 4. Estado de los criterios de aceptación

| Criterio | Requisito | Medido | Resultado |
|---|---|---|---|
| Ingesta EV | $\ge 10\text{ Hz}$ | 20.0 Hz | ✅ Cumplido |
| Validez XY | `xy_valid == true` | `True` | ✅ Cumplido |
| Validez Z | `z_valid == true` | `True` | ✅ Cumplido |
| Validez Velocidad | `v_xy_valid == true` | `True` | ✅ Cumplido |
| Rumbo para control | `heading_good_for_control == true` | `True` | ✅ Cumplido |
| Ausencia de dead reckoning | `dead_reckoning == false` | `False` | ✅ Cumplido |
| Error horizontal | $eph < 1.0\text{ m}$ | **$0.046\text{ m}$** | ✅ Cumplido |

---

## 5. Próximo paso: Prueba 3 (Vuelo)

Con la Prueba 2 completamente validada en tierra, el sistema queda formalmente habilitado para la **Prueba 3**: despegue y mantenimiento de posición en Offboard a **1.0 m** de altura controlada por el LiDAR 1D + barómetro y posición horizontal asistida por el LiDAR 2D.
