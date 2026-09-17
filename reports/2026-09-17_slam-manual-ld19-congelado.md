# Reporte: Validación SLAM 2D manual (LD19 + slam_toolbox) y resolución de mapa/pose congelados

**Fecha:** 2026-09-17  
**Autor / origen:** RPi 4 (`kevin@192.168.1.221`) + Dev Machine (Ubuntu 24.04, ROS 2 Jazzy)  
**Estado:** ✅ Resuelto — escaneos procesados en continuo, mapa expandiéndose en vivo y pose estimada por scan matching.

**Contexto:**  
Fase 1 del [plan de test LiDAR 2D](../docs/2026-09-16_test_lidar2d_ev_offboard.md): validar la calidad del mapa y estimación de movimiento llevando el dron a mano con el LiDAR 2D LD19/D500 conectado a la RPi 4 en `/dev/ttyUSB0`, sin odometría de ruedas (TF `odom -> base_link` estática en identidad) y visualizando en RViz 2 localmente.

**Objetivo evaluado:**  
Mover el dron a mano por la estancia y comprobar que `slam_toolbox` (modo online async) genera el grid de ocupación (`/map`), estima la pose del dron (`/pose`) y mantiene la coherencia geométrica de la habitación.

---

## 1. Síntoma observado

Al arrancar `slam_test.launch.py` en la Raspberry Pi 4 y mover el dron manualmente por la sala:
- El sensor `/scan` publicaba a ~10 Hz con normalidad (502 puntos, ~440 válidos).
- **El mapa (`/map`) y el marco del robot (`base_link`) no se actualizaban**, quedando congelados en el estado del primer segundo tras el encendido.
- El tópico `/pose` no recibía mensajes periódicos.

---

## 2. Diagnóstico y Causa Raíz

En [`slam_toolbox_params.yaml`](../docs/2026-09-16_test_lidar2d_ev_offboard.md), la configuración inicial definía:
```yaml
minimum_travel_distance: 0.01  # 1 cm
minimum_travel_heading: 0.01   # 0.01 rad
```

Al inspeccionar la implementación de `slam_toolbox` (`src/slam_toolbox_common.cpp` y `src/slam_toolbox_async.cpp`):
1. Cada escaneo entrante llama a `laserCallback`:
   ```cpp
   if (!pose_helper_->getOdomPose(pose, scan->header.stamp)) return;
   if (shouldProcessScan(scan, pose)) {
       addScan(laser, scan, pose);
   }
   ```
2. La pose odométrica `pose` se obtiene del árbol TF entre `odom_frame` y `base_frame`. Al ser `odom -> base_link` una transformada estática fija en `(0, 0, 0)`:
   $$\Delta x = 0.0\text{ m}, \quad \Delta y = 0.0\text{ m} \implies \text{dist}^2 = 0.0$$
3. En `shouldProcessScan`:
   ```cpp
   const double dist2 = last_pose.SquaredDistance(pose);
   // Con dist2 = 0.0 y min_dist2 = 0.01^2 = 0.0001:
   else if (dist2 < 0.8 * min_dist2) {
       return false; // Descarte sistemático
   }
   ```
4. **Consecuencia:** Como `0.0 < 0.00008` es siempre verdadero, `shouldProcessScan` descartó el **100% de los escaneos** tras el primer ciclo. El scan matching de Karto nunca llegaba a ejecutarse (`addScan` no se llamaba jamás).
5. Además, las variables `min_dist2` y `min_rotation` están declaradas como `static` dentro de la función en C++, por lo que un cambio dinámico de parámetros vía `ros2 param set` en caliente no las recalcula; requería corregir el YAML y reiniciar el nodo.

---

## 3. Corrección aplicada

En la Raspberry Pi (`/home/kevin/drone_ws/src/px4_drone_slam/config/slam_toolbox_params.yaml` y en su ruta instalada `install/`):

```yaml
# Configuración corregida para SLAM sin odometría previa:
use_scan_matching: true
use_scan_barycenter: true
minimum_travel_distance: 0.0
minimum_travel_heading: 0.0
minimum_time_interval: 0.2
```

Al fijar ambos umbrales en `0.0`:
- La comprobación de distancia odométrica no bloquea ningún escaneo ($0.0 < 0.0$ es falso).
- El paso de escaneos queda regulado por `minimum_time_interval: 0.2` (5 Hz de procesamiento, seguro para la CPU).
- Karto procesa cada escaneo con `m_pSequentialScanMatcher->MatchScan`, estimando el movimiento real por correlación de barridos y actualizando la transformada `map -> odom`.

---

## 4. Resultados y verificación empírica

Tras reiniciar `slam_test.launch.py` con los nuevos parámetros:

| Métrica | Antes del fix | Después del fix |
|---|---|---|
| Ingesta de scans en Karto | 0 scans procesados | Scans procesados continuamente (~5 Hz) |
| Celdas libres en `/map` | 1.798 celdas (6.0%) | **10.395 celdas (33.5%)** |
| Celdas de obstáculos (`>50`) | 115 celdas | **496 celdas (1.6%)** |
| Tamaño de la cuadrícula | Estático 127×237 | Creció a **131×237** dinámicamente |
| Tópico `/pose` | Inactivo (timeout) | Publicando a **~1–2 Hz** con covarianza válida |
| Carga de CPU en la RPi 4 | ~15% | **~23% total** (92% CPU idle, 464 MB RAM, 0 swap) |
| Visualización RViz 2 local | Congelada | Actualización en vivo de mapa y posición de `base_link` |

---

## 5. Conclusión y siguientes pasos

- **Conclusión:** La Fase 1 (SLAM 2D puro a mano) queda **funcional y validada**. El LiDAR LD19 tiene alcance y densidad suficientes indoor (~440 puntos útiles/barrido a 10 Hz) y el algoritmo de correlación de `slam_toolbox` es capaz de estimar el desplazamiento del dron sin requerir odometría previa.
- **Siguiente paso (Fase 2):** Levantar el puente de odometría externa (`ev_odometry_bridge` publicando `/fmu/in/vehicle_visual_odometry` en `POSE_FRAME_NED`) y verificar que el EKF2 del FC valide posición horizontal (`xy_valid=true`) y alinee rumbo (`heading_good_for_control=true`).
