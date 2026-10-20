# PID y MPC — pruebas de 0.8 m detenidas por las guardas

**Fecha del análisis:** 2026-10-19  
**Origen:** RPi `tools/webui/logs/` por SSH, pruebas del 2026-10-16  
**Estado:** ⚠️ las guardas funcionaron; la comparación PID vs MPC todavía no es válida  
**Actualización 2026-10-20:** los dos abortos por obstáculo eran falsos positivos del LiDAR 2D con las hélices girando — [análisis y corrección](2026-10-20_falsos-obstaculos-al-despegar.md)

## Artefactos revisados

| Corrida | Perfil | Resultado |
|---|---|---|
| `ev_takeoff_1792149542` | PID, 0.8 m | Armó, no llegó a despegar y aterrizó por salud del SLAM |
| `mpc_cycle_1792149766` | MPC, 0.8 m | Armó, subió parcialmente y aterrizó por parada de obstáculo |
| `ev_takeoff_1792149648` | PID, 1.2 m | Rechazada antes de armar: supera el techo fiable del LiDAR 1D |
| `mpc_cycle_1792149845` | MPC, 1.2 m | Rechazada antes de armar: supera el techo fiable del LiDAR 1D |

Los rosbag, MCAP y CSV de sistema quedaron en la Pi. No se copiaron al repositorio porque
superan el límite de 5 MB para datos crudos.

## PID: no hubo despegue

La corrida PID entró en OFFBOARD, armó a los 14.14 s del rosbag y recibió el comando de
despegue. A los 17.50 s el nodo pasó a `AUTO_LAND`: el SLAM declaró `sigma_xy = 0.311 m`,
por encima del límite de 0.30 m. El FC se desarmó a los 20.97 s.

La posición local osciló entre `z = -0.235` y `0.064 m`, y el rango crudo entre 0.130 y
0.198 m. No hay evidencia de que dejara el suelo. La guarda de salud del SLAM evitó que el
nodo mantuviera o continuara el despegue con una estimación no fiable.

## MPC: despegue parcial, parada segura

La corrida MPC entró en OFFBOARD, armó a los 14.36 s y pidió despegue a 0.8 m. Alcanzó
`z = -0.915 m` y `dist_bottom = 0.706 m` antes de que la guarda detectara un obstáculo a
0.95 m, por debajo del margen activo de 1.00 m. El nodo frenó durante 2 s, pidió
`NAV_LAND` a los 18.08 s y el FC se desarmó a los 25.54 s.

Esto confirma que la secuencia MPC, el armado, el control de ascenso y la parada por
obstáculo se ejecutaron sin escape. No hubo hold de 30 s ni trayectoria comparable con PID,
por lo que no permite evaluar seguimiento, jerk, deriva ni ventaja del MPC.

### El retorno que disparó la guarda

> **Resuelto el 2026-10-20:** no era un obstáculo ni estructura permanente del dron, sino una
> ráfaga de retornos espurios que aparece solo mientras giran las hélices. No hay nada que
> inspeccionar en el sector trasero. Ver
> [retornos falsos al despegar](2026-10-20_falsos-obstaculos-al-despegar.md); lo que sigue es el
> análisis original, que se conserva por trazabilidad.

Durante el prearmado, el sector trasero de 170–180 grados veía ~7.6 m. Al iniciar la subida
aparecieron tres rayos a 0.921, 0.930 y 0.947 m; poco después volvió un grupo a
0.980–0.982 m. La guarda descarta los retornos de 0.02 m por estar por debajo de su mínimo
de 0.15 m y exige tres rayos por sector, por lo que el disparo no fue un único punto de ruido.

La actitud estaba casi nivelada (roll y pitch menores de 1 grado), así que esos rayos no eran
suelo y el filtro de suelo no debía descartarlos. Todavía no se puede distinguir solo con el
bag si fueron un obstáculo real que entró al plano de barrido al elevarse o una reflexión del
montaje trasero: los retornos cercanos son transitorios. Antes de repetir, inspeccionar el
sector trasero del LiDAR con el dron sin hélices a 0.7–0.8 m de altura y comprobar patas,
brazos, cables y cualquier pared u objeto en ese rumbo.

El desplazamiento horizontal entre el armado y el disparo fue solo 0.019 m. Por tanto, si el
dron estaba centrado entre pilares a 2–3 m, no se acercó a ninguno lo suficiente como para
explicar un retorno a 0.95 m: el origen está en el propio sector de barrido o en un objeto que
el plano del láser solo encontró al subir.

## Carga de la Pi

En la prueba MPC, CPU total: media 54.3 %, p95 91.2 %, máximo 95.9 %; temperatura máxima
55.0 C; sin throttling y con 3.14 GB de RAM disponibles como mínimo. `slam_toolbox` usó
117.2 % de un núcleo en p95, pero no hubo evidencia de saturación térmica, memoria agotada o
throttling que explique el aborto. El factor que detuvo MPC fue la distancia al obstáculo.

## Conclusión y siguiente condición de prueba

Las cuatro ejecuciones son coherentes con las guardas previstas. Repetir PID y MPC solo en
una ubicación con al menos 1.5 m libres en 360 grados, con `takeoff_height_m = 0.8`, la
parada por obstáculo activa y un SLAM estable por debajo de `sigma_xy = 0.30 m`. Hacen falta
tres corridas completas y comparables por controlador antes de concluir nada sobre PID frente
a MPC.
