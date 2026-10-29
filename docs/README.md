# docs/ — índice

Documentación del proyecto, organizada por tipo. Los reportes de diagnóstico de cada sesión
siguen en [`reports/`](../reports/README.md); los respaldos de parámetros y firmware en `backups/`.

| Carpeta | Qué va aquí | Convención de nombre |
|---|---|---|
| [`referencia/`](referencia/) | Documentos **estables** que describen cómo es y cómo se usa la plataforma. Se actualizan en sitio cuando algo cambia. | `MAYUSCULAS_TEMA.md` |
| [`planes/`](planes/) | Planes de prueba, protocolos y análisis **fechados** que guían un bloque de trabajo. Se cierran con un reporte en `reports/`. | `YYYY-MM-DD_tema.md` |
| [`publicaciones/`](publicaciones/) | Revisión de literatura, huecos de investigación y propuestas de paper (markdown de trabajo + PDF/HTML para compartir). | `YYYY-MM-DD_tema.*` |
| [`historico/`](historico/) | Informes del bring-up inicial (jun-2026). Se conservan por las lecciones; ya no se editan. | `MAYUSCULAS_TEMA.md` |
| `images/` | Imágenes compartidas: `hardware/` (fotos del dron), `sensores/` (fotos de producto), gráficas de logs. | |

## Referencia

- [PLATAFORMA_HARDWARE.md](referencia/PLATAFORMA_HARDWARE.md) — ficha completa: airframe, motores, ESC, FC, sensores, GPS, batería, mapeo de motores, referencia SUPER.
- [SOFTWARE_ROS2_PX4_DRONE.md](referencia/SOFTWARE_ROS2_PX4_DRONE.md) — el paquete `px4_drone` en la Pi: nodos, launches, webui.
- [CONFIGURACION_OFFBOARD_RPI4.md](referencia/CONFIGURACION_OFFBOARD_RPI4.md) — enlace uXRCE-DDS Pi ⇄ FC, puertos, dominio, gotchas.
- [CONEXION_MAVLINK_SCRIPTS.md](referencia/CONEXION_MAVLINK_SCRIPTS.md) — hablar con el FC por USB o radio sin QGC (pymavlink).
- [INTEGRACION_MTF-01P_FLOW_LIDAR.md](referencia/INTEGRACION_MTF-01P_FLOW_LIDAR.md) — flujo óptico + LiDAR 1D: cableado, protocolo, EKF2.
- [PARAMETROS_INDOOR.md](referencia/PARAMETROS_INDOOR.md) — todos los parámetros del perfil indoor sin GPS, por importancia.
- [MPC_CICLO_COMPLETO.md](referencia/MPC_CICLO_COMPLETO.md) — el MPC de acados en la Pi: variantes, tiempos, deuda.
- [SIMULACION_GAZEBO_INDOOR.md](referencia/SIMULACION_GAZEBO_INDOOR.md) — modelo del RJX F450 en Gazebo y sus trampas.
- [PX4_1143_FUENTE_VERIFICADO.md](referencia/PX4_1143_FUENTE_VERIFICADO.md) — qué se verificó leyendo el fuente del tag 1.14.3.
- [METODOLOGIA_TRABAJO.md](referencia/METODOLOGIA_TRABAJO.md) — cómo se analiza, se documenta, se guarda en memoria y se toca el FC.
- [Key_parameters_MAVLINK.txt](referencia/Key_parameters_MAVLINK.txt) — nota corta sobre `EKF2_HGT_REF` indoor/outdoor.

## Planes y protocolos

- [2026-09-16 Test LiDAR 2D como visión externa + Offboard](planes/2026-09-16_test_lidar2d_ev_offboard.md)
- [2026-10-16 Protocolo de comparación PID vs MPC](planes/2026-10-16_protocolo_pid_vs_mpc.md)
- [2026-10-19 Plan de tuning: despegue, hold y aterrizaje suaves](planes/2026-10-19_plan_tuning_takeoff_hold_land.md)
- [2026-10-19 Companion para MID-360S y SLAM 3D](planes/2026-10-19_companion_mid360s_slam.md)
- [2026-10-20 Parámetros del FC para vuelo suave](planes/2026-10-20_parametros_vuelo_suave_produccion.md)
- [2026-10-21 Pruebas en banco sin hélices](planes/2026-10-21_pruebas_banco_sin_helices.md)
- [2026-10-21 GPS outdoor ZED-F9P: position hold, perfiles, RTK](planes/2026-10-21_outdoor_gps_zedf9p_position_hold.md)

## Publicaciones

- [2026-10-01 Huecos de investigación para publicar](publicaciones/2026-10-01_gaps_publicacion.md) — SLAM, incertidumbre de alineación, multi-LiDAR, mina.
- [2026-10-29 Paper de energía/batería con datos de campo](publicaciones/2026-10-29_paper_energia_bateria_campo.md) — revisión, decisiones y plan (documento de trabajo).
  - Propuesta para compartir: [PDF español](publicaciones/2026-10-29_propuesta_paper_energia_bateria.pdf) · [PDF inglés](publicaciones/2026-10-29_paper_proposal_battery_energy_EN.pdf). Fuente `.html` al lado; se regeneran con Chrome headless (`--headless=new --no-pdf-header-footer --print-to-pdf`).

## Histórico (bring-up, junio 2026)

- [INFORME_VUELO_DRONE.md](historico/INFORME_VUELO_DRONE.md) — los 4 problemas del primer vuelo y la configuración de referencia.
- [DIAGNOSTICO_RUIDO_MOTORES_YAW.md](historico/DIAGNOSTICO_RUIDO_MOTORES_YAW.md) — "ruido al armar" = saturación de yaw.

## Otros

- [README.es.md](README.es.md) — versión en español del README principal.
