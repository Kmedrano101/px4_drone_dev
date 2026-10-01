# Gaps de investigación para publicar en los próximos meses

**Fecha:** 2026-10-01 · **Para:** Kevin Medrano (TIDOP, USAL)
**Qué es esto:** revisión de literatura reciente cruzada con lo que ya existe en el grupo, para
decidir en qué enfocar el próximo paper. Las referencias están al final, con enlace.

**Conclusión en una línea:** el gap más rentable **no está en el algoritmo, sino en cómo se mide**,
y está medio resuelto en los datos que ya hay en disco.

Activos de partida que condicionan toda la recomendación:
- Payload de **doble Livox MID-360** (22 cm de base, configuración delante-detrás) con LIO en dos
  modos, Navigation y Reconstruction, sobre Jetson Orin NX — borrador para RA-L.
- **12 celdas M3C2** indoor (D1/D2 × T1/T2 × repeticiones) + exterior, contra referencia **BLK2Go**
  survey-grade: P50 de 1.6–3.6 cm, completeness ≤10 cm del 88–98%
  (`xtract-paper/experimentos/M3C2_RESULTS.md`).
- Borrador del caso de estudio en la **mina de Björkdal** y protocolo de campo.
- Plataforma PX4 indoor (LiDAR 2D + flujo óptico) con **fallos de vuelo reales documentados**
  ([reporte del log 158](../reports/2026-09-18_takeoff-ev-log158-caida-stabilized.md)).
- **GPS RTK u-blox ZED-F9P-02B-01** disponible (ver [PLATAFORMA_HARDWARE.md](PLATAFORMA_HARDWARE.md) §3).

---

## Gap A — La evaluación de mapas SLAM ignora la incertidumbre de alineación

**La apuesta recomendada.**

En 2025 la robótica ha estandarizado la evaluación de mapas con **MapEval** (RA-L + IROS 2025):
AC, COM, Chamfer, MME y dos métricas nuevas (AWD, SCS). Revisada su documentación: **no usa normales
locales, no calcula level of detection (LoD) y no propaga la incertidumbre de la alineación** con la
verdad de terreno. La práctica habitual en los benchmarks es alinear el mapa estimado con la
referencia por ICP y tratar esa alineación como exacta ("proxy ground-truth alignment"), aunque se
sabe que la variante de ICP y los umbrales de correspondencia mueven los números.

La geomática lleva una década con esto resuelto: **M3C2** (Lague et al. 2013), **M3C2-EP** (propaga
la incertidumbre de medida **y de alineación** para dar un LoD sin sesgo), **M3C2 por parches** y
trabajo reciente de incertidumbre punto a punto en MLS. **Nadie ha hecho el puente entre las dos
comunidades para benchmarking de SLAM.**

**La evidencia empírica ya está medida en el grupo.** `M3C2_RESULTS.md` documenta que la alineación
automática por ICP (CloudCompare CLI) daba P50 de 15–22 cm y completeness del 28–41%, y que con
point-pairs manuales + ICP fino bajó a ~2.5 cm:

> **Un factor ~9 en la exactitud publicada del mismo mapa, decidido por el procedimiento de
> alineación y no por el algoritmo de SLAM.**

Eso cuestiona la comparabilidad de los números que publica el campo entero, y es un resultado
metodológico defendible.

**Qué falta (semanas, sin campaña nueva):**
1. Pasar **MapEval** sobre las 12 nubes ya alineadas → tabla directa "métricas de robótica vs
   M3C2/LoD" sobre los mismos datos.
2. **Experimento de sensibilidad a la alineación**: N procedimientos (ICP punto-punto, punto-plano,
   point-pairs manual + ICP fino, con y sin recorte al volumen de la trayectoria) × 12 nubes →
   distribución del error reportado. Es la figura central del paper.
3. Propagar la covarianza de la alineación al LoD, estilo M3C2-EP, y proponer un **mínimo de
   reporte**: LoD, covarianza de alineación, y sensibilidad del completeness al umbral.

**Venues:** ISPRS Journal / ISPRS Annals, *Remote Sensing* o *Drones* (rápidas). También RA-L si se
enmarca como benchmarking.
**Riesgo:** que un revisor diga "esto ya existe en geociencias". La novedad es la **transferencia
sistemática** y la cuantificación de sus consecuencias sobre las afirmaciones de exactitud en SLAM.

---

## Gap B — Geometría multi-LiDAR como mitigación de degeneración

**Sube el nivel del RA-L que ya está escrito.**

El lado algorítmico de la degeneración está saturado: DALI-SLAM, OR-LIM, DAMM-LOAM, D²-LIO, y
variantes que añaden UWB, odometría de rueda, radar o intensidad (DURAL, CM-LIUW, FIRE-LIVWO).
**No conviene escribir otro LIO degeneracy-aware.**

Lo que sigue abierto es el lado del **hardware**: las revisiones de SLAM en UAV (scoping review en
JFR 2024, survey GPS-denied 2025) señalan que el SLAM específico de UAV está poco estudiado por la
limitación de carga de pago, y que **el solapamiento y la colocación de varios LiDAR son decisivos
pero no están cuantificados**. Existe M-LOAM para la calibración extrínseca online, y como
alternativa para ampliar el campo de visión hay plataformas autorrotantes (2026). **No se encontró
ningún estudio de un payload de doble MID-360 en UAV.**

**Qué falta:** añadir a la ablación D1 (bundle) vs D2 (async) que ya existe una **métrica de
observabilidad por barrido** — número de condición de la matriz de información, desglosado por
dirección — para S1 vs D1 vs D2 en los tramos de pasillo y túnel, más el coste de cómputo asociado.
Todo offline, con los bags ya grabados.

Con eso el mensaje pasa de "montamos un payload doble" a **"cuánta robustez a degeneración compra la
geometría del sensor, comparada con arreglarlo en el filtro"**, que es la pregunta que nadie ha
contestado con datos.

---

## Gap C — Validación independiente de cartografía aérea en mina operativa (Björkdal)

Volar un dron en una mina ya no es novedad: hay cuadricóptero autónomo para mapeo rápido de minas
(RAPDASA 2025) y un UAV autónomo multi-modal validado en mina de caliza en operación (Robotics
2026), más todo el legado de DARPA SubT. Lo que sigue flojo es lo que un ingeniero de minas necesita:
los fabricantes anuncian 1–3 cm, o "menos de 10 cm", **sin validación independiente revisada por
pares**.

Aplicando el protocolo del Gap A dentro de la mina, con referencia TLS y declarando **LoD** en lugar
de un RMSE suelto, se responde la pregunta real: *¿me puedo creer el volumen de este hueco, y con qué
incertidumbre?* Añadir los eventos de degeneración detectados (Gap B) y el envolvente operativo
(polvo, falta de referencia, geometría) lo convierte en un field report sólido.

**Venues:** Journal of Field Robotics, ISPRS, o revistas de minería/túneles.
**Depende de:** que la campaña de campo esté medida.

---

## Gap D — El contrato de incertidumbre entre el SLAM y el autopiloto

**Real pero de menor impacto: mejor como sección de C que como paper propio.**

Existe **LOFF** (Drones 2024), que fusiona LiDAR y flujo óptico con un detector de fallo que
sustituye la dirección degenerada por flujo óptico — ⚠️ no se pudo leer el texto completo (la
editorial devolvió HTTP 403), hay que confirmarlo antes de citarlo. Y acaba de salir **UAV-SEAD**, un
dataset de anomalías de estimación de estado.

El hueco que queda es el **interfaz**: qué incertidumbre debe declarar un SLAM al EKF de un
autopiloto de producción, cómo se tratan la latencia y las poses repetidas, y qué taxonomía de fallos
aparece en vuelo real. El [log 158](../reports/2026-09-18_takeoff-ev-log158-caida-stabilized.md) es
un caso de libro: el EKF creyó una pose de hace 0.8 s con σ declarada de 0.1 m mientras el dron
recorría ~3 m, porque el puente mandaba la varianza como NaN. La corrección (varianza del SLAM +
antigüedad de la pose) y el arnés de reproducción están ya implementados y validados en
`px4_drone`.

---

## Dos avisos que ahorran trabajo

**1. El ZED-F9P no sirve como verdad de terreno para exactitud de mapa.** Los benchmarks en entornos
sin GNSS muestran que una referencia asistida por SLAM baja de 2 cm, "bastante mejor que las
soluciones GNSS/RTK". Con errores de mapa de ~2.3 cm, el RTK no tiene margen. Sí sirve, y mucho,
para **deriva de trayectoria en exterior** y para pruebas de transición interior↔exterior, que es
un hueco reconocido (dataset RTK-SLAM, 2026).

**2. El cómputo embarcado da para media sección, no para un paper.** El throttling térmico del Jetson
tras ~30 min ya está reportado en la literatura de edge. Pero la cifra de **"el SLAM procesa 1.2 de
9.9 barridos/s"** (medida en la Pi 4, ver `px4_drone/tools/sysmon/`) es el tipo de dato que casi nadie
publica y que refuerza B y C.

---

## Orden recomendado

| | Gap | Datos necesarios | Plazo | Venue |
|---|---|---|---|---|
| 1 | **A** — incertidumbre de alineación | **ya en disco** | semanas | ISPRS / Remote Sensing / Drones |
| 2 | **B** — geometría multi-LiDAR vs degeneración | bags ya grabados + análisis offline | 1–2 meses | RA-L (borrador actual) |
| 3 | **C** — mina Björkdal | campaña de campo | según campaña | JFR / ISPRS |
| 4 | **D** — contrato SLAM ↔ autopiloto | ya en disco | — | sección de C |

Los tres primeros **comparten el protocolo de evaluación**, así que cerrar A primero no es un desvío:
es la base metodológica de B y de C.

**Pendiente de decidir:** si la campaña de Björkdal está ya medida o por hacer, y si hay alguna fecha
de convocatoria que deba mandar en el orden.

---

## Referencias

**Evaluación de mapas e incertidumbre**
- MapEval — *Cloud_Map_Evaluation* (RA-L & IROS 2025): <https://github.com/JokerJohn/Cloud_Map_Evaluation>
- M3C2-EP, ISPRS J. Photogramm. Remote Sens. 2021: <https://www.sciencedirect.com/science/article/pii/S0924271621001696>
- Patch-based M3C2, ISPRS J. 2023: <https://www.sciencedirect.com/science/article/pii/S156984322300359X>
- Point-level uncertainty evaluation of MLS point clouds: <https://arxiv.org/html/2510.24773>
- Benchmark multi-modal LiDAR SLAM con GT en entornos sin GNSS: <https://arxiv.org/abs/2210.00812>
- RTK-SLAM dataset para exactitud absoluta (interior/exterior): <https://arxiv.org/html/2604.07151>

**SLAM en UAV y multi-LiDAR**
- UAV-based SLAM: systematic scoping review, JFR 2024: <https://onlinelibrary.wiley.com/doi/full/10.1002/rob.22325>
- GPS-Denied LiDAR-Based SLAM — A Survey, 2025: <https://ietresearch.onlinelibrary.wiley.com/doi/full/10.1049/csy2.70031>
- M-LOAM (multi-LiDAR con calibración extrínseca online): <https://arxiv.org/pdf/2010.14294>
- Self-rotating tri-rotor UAV para ampliar el campo de visión: <https://arxiv.org/pdf/2603.28581>

**Degeneración**
- DALI-SLAM, ISPRS J. 2025: <https://www.sciencedirect.com/science/article/abs/pii/S0924271625000413>
- OR-LIM, ISPRS J. 2024: <https://www.sciencedirect.com/science/article/abs/pii/S0924271624003745>
- DAMM-LOAM: <https://arxiv.org/pdf/2510.13287> · D²-LIO: <https://arxiv.org/html/2508.14355>

**Subterráneo**
- Present and Future of SLAM in Extreme Underground Environments: <https://arxiv.org/pdf/2208.01787>
- CompSLAM (autonomía en entornos subterráneos): <https://arxiv.org/pdf/2505.06483>
- Autonomous quadcopter for rapid underground mine mapping, RAPDASA 2025: <https://www.matec-conferences.org/articles/matecconf/pdf/2025/11/matecconf_rapdasa2025_04019.pdf>
- Autonomous UAV for multi-modal mapping of underground mines, Robotics 2026: <https://www.mdpi.com/2218-6581/15/3/63>

**Fallos de estimación de estado**
- LOFF: LiDAR and Optical Flow Fusion Odometry, Drones 2024 (⚠️ texto completo no accesible): <https://doi.org/10.3390/drones8080411>
- UAV-SEAD: State Estimation Anomaly Dataset for UAVs: <https://arxiv.org/pdf/2602.13900>

**Cómputo embarcado**
- Embodied Foundation Models at the Edge (restricciones de despliegue): <https://arxiv.org/pdf/2603.16952>
