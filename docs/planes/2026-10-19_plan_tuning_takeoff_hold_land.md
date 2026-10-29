# Plan de ajuste: vuelo suave y repetible con PX4 Offboard

**Objetivo acordado el 2026-10-19:** usar takeoff–hold–land para ajustar el dron
hacia un comportamiento de producto: despegue predecible, estacionario estable,
aterrizaje suave y repetibilidad. La comparación PID/MPC sirve a ese objetivo;
no se presupone que cambiar de algoritmo mejore el vuelo.

**Estado:** recomendaciones y pruebas pendientes. No se han cambiado parámetros
ni ejecutado vuelos. Base consultada: documentación PX4 v1.14 y fuente local del
tag `v1.14.3`; el firmware de fábrica puede tener diferencias que deben verificarse
antes de aplicar ajustes. Los volcados antiguos no describen necesariamente el FC actual.

## 1. Qué demuestra este ciclo

El ciclo permite medir transiciones, seguimiento vertical, deriva durante hold,
contacto y desarme. No identifica por sí solo los lazos de todos los ejes: un
estacionario casi nivelado excita poco roll, pitch, yaw y movimiento horizontal.
Tras estabilizarlo, hacen falta pruebas específicas de pequeños movimientos,
frenado y yaw, y validación con distintas baterías/cargas y condiciones.
Un vuelo correcto tampoco demuestra fiabilidad comercial ni certificación.

## 2. Orden de trabajo y puertas de avance

1. **Mecánica y propulsión:** revisar hélices/motores, rigidez, fijación del FC,
   masa y centro de gravedad, patas y cables. Medir vibraciones/clipping,
   desequilibrio entre motores y saturación. Corregir causas mecánicas antes
   de intentar ocultarlas mediante filtros o ganancias.
2. **Estimación:** verificar escalas, NED/FRD frente a ENU/FLU, offsets, tiempos,
   edad de la odometría, covarianzas, innovaciones, rechazos y resets del EKF.
   Calentar de forma reproducible y vigilar deriva térmica/barómetro. Contrastar
   posición/altura con una referencia independiente de la que utiliza el control.
3. **Tasas y actitud:** ajuste conservador inicial de tasas, análisis de ruido y
   latencia/filtros, refinamiento de tasas y después actitud. Evaluar consigna y
   respuesta por eje; D alto puede amplificar ruido. El ciclo vertical no sustituye
   una prueba específica de estos lazos. No iniciar un autotune sin verificar que
   el firmware lo incluya y disponer del espacio/procedimiento adecuado.
4. **Empuje:** verificar empuje de hover y su estimador, modelo de empuje,
   margen de actuación y efecto de batería/carga. Una mala conversión de
   aceleración a empuje también afecta al MPC exterior.
5. **Control exterior:** ajustar primero velocidad y después posición en la
   cascada P/PID. Con aceleración externa, esos lazos se omiten y se ajustan
   modelo, pesos, horizonte, restricciones y compensación de sesgo del MPC.
6. **Referencia y transiciones:** perfiles coherentes de posición/velocidad/
   aceleración con jerk limitado. Inicializar desde el estado actual y evitar
   saltos al entrar en Offboard, frenar, pasar a hold y entregar a NAV_LAND.
7. **Repetibilidad y robustez:** conservar una configuración de referencia,
   cambiar una familia de ajustes por iteración y validar regresiones.

No bajar ganancias solo para que un movimiento brusco parezca suave: se puede
perder rechazo a perturbaciones. Separar seguimiento de lazo y forma de referencia.
Un vuelo suave debe conservar autoridad de frenado y margen frente a obstáculos.

## 3. Prioridades de este dron

- Resolver el SLAM inestable y el retorno trasero del LiDAR antes de usar los
  ciclos para ajustar control: las guardas detuvieron las pruebas del 2026-10-16.
- Mantener el perfil inicial de 0.8 m y 30 s de hold, dentro del rango de altura
  documentado como fiable sobre el suelo ensayado. No elevar el techo para obtener
  una prueba más larga. La reflectividad y la geometría siguen importando.
- La guarda de sigma SLAM de 0.30 m es un umbral operativo, no una precisión
  suficiente para demostrar estacionario de pocos centímetros.
- Separar movimiento real de deriva del estimador: el error contra el EKF
  puede ser pequeño aunque el vehículo se desplace en el mundo.
- Evaluar proximidad al suelo y recirculación del aire; el comportamiento a
  0.8 m no se extrapola automáticamente a otras alturas o entornos.

## 4. Parámetros a revisar, sin valores propuestos para escribir

| Capa | Familias/puntos de revisión en PX4 1.14.3 |
|---|---|
| Tasas y actitud | `MC_ROLLRATE_*`, `MC_PITCHRATE_*`, `MC_YAWRATE_*`; `MC_ROLL_P`, `MC_PITCH_P`, `MC_YAW_P` |
| Ruido/latencia | `IMU_GYRO_CUTOFF`, `IMU_DGYRO_CUTOFF`, notch disponible, perfil de logging |
| Empuje | `MPC_THR_HOVER`, `MPC_USE_HTE`, `THR_MDL_FAC`, mínimos/máximos de empuje |
| Velocidad/posición | `MPC_Z_VEL_*_ACC`, `MPC_XY_VEL_*_ACC`, `MPC_Z_P`, `MPC_XY_P` |
| Despegue | `COM_SPOOLUP_TIME`, `MPC_TKO_RAMP_T`, `MPC_TKO_SPEED` y perfil externo realmente aplicado |
| Descenso/contacto | `MPC_LAND_SPEED`, `MPC_LAND_ALT1/2/3`, `MPC_LAND_CRWL`, `LNDMC_*`, `COM_DISARM_LAND` |
| MPC exterior | Modelo, periodo, horizonte, pesos, restricciones, estado inicial, sesgos, fallos del solver |

**No todos estos parámetros afectan de la misma forma a cada variante.**
`MPC_JERK_MAX` está documentado en el fuente para los modos suavizados de Position;
no debe suponerse que suaviza las consignas Offboard. `MPC_TKO_RAMP_T` actúa sobre
la lógica de rampa de despegue y no garantiza por sí solo una rampa de aceleración
para la variante MPC. Verificar las señales efectivas y `takeoff_status`.

En el tag v1.14.3, `MPC_TKO_SPEED` tiene mínimo declarado de 1 m/s y
`MPC_LAND_SPEED` de 0.6 m/s. No recomendar escribir valores inferiores tomados
de otra versión. El aterrizaje dispone de una fase `MPC_LAND_CRWL` condicionada
por rango válido y altura. Confirmar la implementación del firmware de fábrica.
Una rampa de despegue excesivamente lenta puede prolongar el contacto y favorecer
un vuelco; buscar una transición limpia, no minimizar toda velocidad indiscriminadamente.

## 5. Registro y evaluación por fase

| Fase | Medidas clave |
|---|---|
| Tierra/prearmado | Deriva en reposo, salud/edad de sensores, temperatura, origen y referencia inicial |
| Despegue | Tiempo hasta separarse del suelo, inclinación/desplazamiento, overshoot de altura y frenado |
| Hold | Error real RMS/p95/máximo, sesgo, dispersión, deriva, yaw y oscilaciones |
| Descenso | Seguimiento de velocidad, continuidad al entregar a LAND y cambio de empuje |
| Contacto/desarme | Velocidad real antes del contacto, rebote, inclinación y tiempo hasta desarme |
| Todo el ciclo | Consignas y medidas, saturación/integradores, resets, cambios de modo, guardas, retrasos y cómputo |

Registrar `.ulg`, rosbag, sysmon y vídeo/referencia externa sincronizados,
volcado de parámetros, commits, masa/carga, batería inicial/final, suelo,
posición del dron y condiciones. Confirmar disponibilidad y tasa de cada señal
antes de volar; no todo uORB se exporta automáticamente por DDS.
En jerk medido usar el mismo filtrado y método entre corridas: derivar ruido
puede producir picos que no representan la suavidad real.

El heartbeat Offboard (>2 Hz) comprueba presencia, no calidad ni frescura de
consignas/odometría. Medir periodo, jitter, antigüedad y plazos incumplidos;
a 20 Hz hay 50 ms para todo el ciclo. Verificar que el heartbeat no continúe
ocultando un controlador bloqueado con datos obsoletos.

## 6. Objetivos iniciales propuestos, sujetos a metrología

Estos números son objetivos de ingeniería para discutir, **no una norma comercial,
ni requisitos certificados, ni garantías del hardware actual**.

| Medida | Objetivo inicial candidato |
|---|---|
| Hold vertical | RMS real ≤0.05 m durante 30 s |
| Hold horizontal | RMS de distancia horizontal real ≤0.10 m durante 30 s |
| Overshoot vertical | ≤10 % de la subida relativa solicitada (0.08 m para 0.8 m) |
| Asentamiento | Entrar en ±0.05 m de altura en ≤3 s desde el fin de la referencia de ascenso y permanecer dentro durante el hold |
| Contacto | Sin rebote que vuelva a separar las patas, vuelco ni falso landed en el aire |
| Repetibilidad | Tres ciclos completos por configuración para explorar; al menos diez para una primera validación, informando fallos y dispersión |

La referencia independiente debe tener incertidumbre suficientemente menor que
la tolerancia evaluada; si no, registrar el resultado como no verificable.
Las ventanas y la definición de contacto deben fijarse antes de comparar.
Diez ciclos no bastan para afirmar fiabilidad comercial.

## 7. Campaña propuesta

- [ ] Cerrar sensores/mecánica/guardas y verificar registro completo.
- [ ] Obtener tres ciclos de referencia sin cambiar ajustes para medir dispersión.
- [ ] Ajustar la capa responsable según consigna frente a respuesta, una familia
  por iteración, guardando resultado y punto de retorno.
- [ ] Ejecutar A/B/C del [protocolo de comparación, §8](2026-10-16_protocolo_pid_vs_mpc.md#8-pendiente-acordado-separar-trayectoria-y-controlador-2026-10-19).
- [ ] Validar configuración elegida con más ciclos, baterías/cargas representativas
  y posteriormente movimientos horizontales/yaw y frenado.
- [ ] Ensayar pérdida/envejecimiento de odometría, bloqueo del solver y enlace en
  simulación primero; planificar por separado cualquier validación física.

El usuario ejecuta el armado. Se conservan guardas, escape RC y procedimientos
de la [metodología](../referencia/METODOLOGIA_TRABAJO.md); las pruebas abortadas cuentan al
evaluar disponibilidad aunque no formen una pareja válida para comparar seguimiento.

## Fuentes

- [PX4 v1.14: ajuste PID](https://docs.px4.io/v1.14/en/config_mc/pid_tuning_guide_multicopter).
- [PX4 v1.14: filtros y latencia](https://docs.px4.io/v1.14/en/config_mc/filter_tuning).
- [PX4 v1.14: generación de consignas](https://docs.px4.io/v1.14/en/config_mc/mc_trajectory_tuning).
- [PX4 v1.14: estimación externa](https://docs.px4.io/v1.14/en/ros/external_position_estimation).
- [PX4 v1.14: Offboard](https://docs.px4.io/v1.14/en/flight_modes/offboard).
- [PX4 v1.14: detector de aterrizaje](https://docs.px4.io/v1.14/en/advanced_config/land_detector).
- [Fuente v1.14.3: parámetros](https://github.com/PX4/PX4-Autopilot/blob/v1.14.3/src/modules/mc_pos_control/mc_pos_control_params.c).
- [Fuente v1.14.3: control de posición](https://github.com/PX4/PX4-Autopilot/blob/v1.14.3/src/modules/mc_pos_control/MulticopterPositionControl.cpp).
- [Fuente v1.14.3: aceleración y empuje](https://github.com/PX4/PX4-Autopilot/blob/v1.14.3/src/modules/mc_pos_control/PositionControl/PositionControl.cpp).
- [Pruebas locales del 2026-10-16](../../reports/2026-10-19_pid-mpc-pruebas-guardas-rpi.md).
