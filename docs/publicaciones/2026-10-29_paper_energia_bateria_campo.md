# Paper de energía/batería con datos de campo reales — estado del arte y propuesta concreta

**Fecha:** 2026-10-29 · **Para:** Kevin Medrano + compañero de energía
**Resumen visual para compartir:** `docs/publicaciones/2026-10-29_propuesta_paper_energia_bateria.pdf` (7 páginas, generado desde el `.html` del mismo nombre con Chrome headless; fotos de sensores en `docs/images/sensores/`). **Versión en inglés:** `docs/publicaciones/2026-10-29_paper_proposal_battery_energy_EN.pdf` (+ `.html`).
**Qué es esto:** revisión de la literatura reciente (2021-2026) sobre consumo y baterías en
multirrotores, cruzada con lo que la plataforma RJX F450 / PX4 1.17 ya mide, para elegir **un**
paper concreto con datos de vuelo reales. Referencias con enlace al final.

**Conclusión en una línea:** el hueco más claro y barato de cerrar es **la batería vista desde el
vuelo**: identificar un modelo de circuito equivalente de una LiPo a régimen alto (10-20 C) *con
los propios logs de vuelo*, y validar el **tiempo de vuelo restante contra descargas reales hasta
el corte**, comparándolo con lo que hace el estimador de serie de PX4. Nadie publica eso con
verdad de terreno, y el dron ya ha vivido el fallo que lo motiva (0 % falso a 24.1 V).

---

## 1. Qué dice la literatura (y dónde está el hueco)

### 1.1 Modelos de consumo del multirrotor

- Los modelos físicos clásicos (D'Andrea, Kirschstein, Stolaroff, Liu, regresión de Tseng) están
  revisados y comparados en *An Overview of Drone Energy Consumption Factors and Models* y en
  *A Comparative Study on Energy Consumption Models for Drones* (2022). Conclusión común: en
  vuelo lento la **potencia inducida de hover** explica casi todo el consumo; velocidad y viento
  pesan poco dentro de la envolvente de un dron pequeño.
- La validación con vuelo real existe pero es escasa: *Range, Endurance and Optimal Speed
  Estimates for Multicopters* (2.5 % RMSE en potencia), un cuadrirrotor de 4.7 kg con 537 kJ
  medidos frente a 550 kJ simulados, y un marco "wind-resilient" (Drones 2026) con anemómetro.
- **Revisión 2025** (*State-of-the-art in energy optimization for quadcopter UAVs*): compara los
  cinco modelos más usados sobre el dataset de reparto del M100 y propone un LSTM. Señala que
  la mayoría de trabajos **siguen validando en simulación**.

### 1.2 Control y planificación "energy-aware"

- NMPC energy-aware vs PID/LQR (Mubdir & Prempain): **36-37 % de ahorro, solo simulación.**
- *Mission specific PID tuning for energy-efficient quadrotor flights* (Aerospace Science and
  Technology, 2025): hasta **70 % de ahorro, numérico**.
- *Battery-Aware Predictive Trajectory Planning and Control for Multirotors Under Disturbances*
  (arXiv 2609.12188, sept. 2026): modelo de batería de orden reducido, **7.46 % de ahorro**, validado
  contra una referencia Simscape, **sin vuelo real**. Reconoce que "la elección del controlador
  cambia el compromiso entre precisión, energía y uso de actuadores", pero no lo mide.
- *Aggressiveness-Aware Learning-based Control* (arXiv 2602.21936, 2026): las ganancias altas
  suben el consumo; de nuevo simulación.

> **Hueco 1:** no se ha encontrado **ningún estudio que mida en vuelo real cuánta energía cuesta
> el controlador** (PID vs trayectoria suave vs MPC) sobre la misma plataforma y la misma misión.
> Las cifras de ahorro que circulan (7-70 %) son todas simuladas.

### 1.3 Batería del dron: SoC, fin de descarga y salud

- **Dibbern et al. (JATE 2023, Flensburg):** ECM + EKF/UKF/conteo de culombios con perfiles de
  reparto e inspección. Hallazgo útil: la precisión del SoC depende sobre todo de la identificación
  de parámetros, y **el error de fin de descarga NO correlaciona con el error de SoC**; depende de
  la carga dinámica. Datos de banco.
- **Motion-Specific Battery Health Assessment for Quadrotors (ICRA 2026, arXiv 2603.12791):**
  S500 + Pixhawk 6C + 4S 2.2 Ah; miden corriente en vuelo (sensor ±100 A a 10 Hz, logger propio)
  para hover, vertical y horizontal, y **reproducen** esas corrientes en un modelo electroquímico
  calibrado. La degradación es **simulada, no medida en el pack**; no dicen cuántos vuelos; dejan
  como futuro "validación estadística" y la integración online.
- **SoH por ML (arXiv 2607.06791, 2026):** 342 + 289 vuelos con packs de 2200 y 1100 mAh,
  capacidad medida cada 10 vuelos, ResNet sobre V/I/throttle. **Sin temperatura.**
- **SoC/RUL en helicóptero Pixhawk (Drones 10(7):549, 2026):** 1310 muestras (≈262 s) de nueve
  señales. Muy poco dato.
- **Tesis sobre 162 logs públicos de PX4 Flight Review** (predicción de energía a 60 s): declara
  que **"no hay verdad de terreno de tiempo restante en los logs públicos de PX4"**, así que
  solo estima.
- **Modelos ECM de LiPo**: Thevenin de 3 RC identificado por relajación (2 C), mapas parámetro ×
  SoC × temperatura por HPPC (Energies 2019). Todo en banco y a C-rates bajos; el dataset eVTOL
  de Bills et al. (Scientific Data 2023, 21 392 ciclos) es celda 18650 con perfil de aeronave,
  no un pack LiPo de dron a 15 C. Una revisión de 2022 lo resumía: *"no se ha hecho un trabajo
  detallado de modelado de batería y verificación en condiciones reales en el campo de los
  drones"*.

> **Hueco 2 (el recomendado):** no hay un trabajo que (a) identifique el ECM de una LiPo de dron
> **a régimen alto (10-20 C) desde los logs de vuelo**, con temperatura, (b) lo valide contra el
> banco, y (c) mida el error del **tiempo de vuelo restante contra vuelos descargados hasta el
> corte real**, comparando con el estimador de serie del autopiloto (voltaje vs culombios). La
> única verdad de terreno de "tiempo restante" que existe hay que volarla.

### 1.4 Datasets abiertos

- Rotor: **solo** el del DJI Matrice 100 de Rodrigues/Samaras (Scientific Data 2021): 209 vuelos
  con V/I por sensor Hall, GPS, IMU y viento; autopiloto cerrado, sin RPM por motor, sin RTK.
- Ala fija: IDF-DS19 (Scientific Data 2026), 240 vuelos PX4/INAV con `battery_status`.
- Otros (Race Against the Machine, NanoBench, INSANE con RTK) no traen corriente o no son de
  energía.

> **Hueco 3 (subproducto):** no existe un dataset abierto de multirrotor sobre autopiloto
> abierto con **corriente calibrada + RTK + eRPM por motor + temperatura de pack + viento**.

---

## 2. Propuesta: paper principal, segundo paper y subproducto

### Paper 1 (principal, con el compañero de energía) — "La batería vista desde el vuelo"

**Título de trabajo:** *In-flight identification of a high-C-rate LiPo model on an open-source
quadrotor: remaining-flight-time error against discharge-to-cutoff ground truth.*

**Pregunta:** ¿cuánto se equivoca el tiempo de vuelo restante (y el SoC) cuando se estima con lo
que hace PX4 de serie, con conteo de culombios, y con un ECM identificado desde los logs, medido
contra vuelos reales llevados hasta el umbral de aterrizaje?

**Por qué es publicable:**
1. Régimen que la literatura de baterías no cubre: 1300 mAh a ~20 A de hover son **~15 C**, con
   picos de 40+ C; los datasets de celda van de 0.1 a 5 C.
2. Verdad de terreno que nadie tiene: el tiempo real hasta el corte, en N vuelos.
3. Impacto práctico: el estimador que se evalúa es el que llevan miles de drones PX4 (`BAT1_*`,
   `battery_status.time_remaining_s`). El dron ya mostró el fallo (0 % a 24.1 V, 27-oct).
4. Encaja con lo que Dibbern et al. dejaron abierto (fin de descarga ≠ SoC) y con lo que el
   paper de ICRA 2026 no hizo (validar en el pack real, varios vuelos).

**Qué se mide (campaña):**
- 2 packs: **6S 1300 mAh 100C** (actual) y **6S 4500 mAh 60C** (ya previsto). Dos tamaños =
  dos regímenes de C-rate con el mismo dron.
- Por vuelo: `battery_status` (V, I calibrada, T), `esc_status` (eRPM × 4, ya activo con
  `DSHOT_BIDIR_EN=1`), RTK (posición/velocidad cm), IMU, modo de vuelo, viento (anemómetro en
  tierra), temperatura de pack (termistor) y temperatura ambiente.
- Tres perfiles repetidos: hover puro, vertical (subir/bajar), horizontal (ida y vuelta RTK).
  Cada vuelo **hasta 3.5 V/celda bajo carga** (verdad de terreno de fin de descarga).
- Banco (laboratorio del compañero): OCV-SoC, HPPC a varias temperaturas, capacidad de referencia
  cada ~10 vuelos (misma receta que arXiv 2607.06791). Esto es lo que aporta el socio de energía.

**Análisis:**
- Identificar ECM (1-2 RC + R0(T, SoC)) desde los logs de vuelo; comparar con el identificado en
  banco (la figura central: *¿los parámetros de vuelo coinciden con los de laboratorio?*).
- Estimadores: (i) PX4 por voltaje, (ii) culombios, (iii) ECM + UKF. Métricas: error de SoC y
  **error del tiempo restante (s) en función del horizonte** (1, 2, 3 min antes del corte).
- Extra barato: potencia de hover vs masa de pack (1300 vs 4500) contra la predicción de teoría
  de cantidad de movimiento (el escalado ×2.37 que ya se usa en el reporte del 27-oct).

**Tamaño:** 30-40 vuelos hasta el corte (≈5 min con 1300, ≈11 min con 4500) → 4-6 sesiones de
campo. Análisis offline con pyulog (ya hay `analyze_flight.py`).

**Venues:** *Journal of Energy Storage* o *Energies* (ángulo batería), *Drones* o *Aerospace
Science and Technology* (ángulo UAV), IEEE *Trans. Transportation Electrification*.

### Paper 2 (misma instrumentación) — "¿Cuánta energía cuesta el controlador?"

Tira del plan A/B/C ya acordado el 2026-10-19 (`docs/planes/2026-10-16_protocolo_pid_vs_mpc.md`): PID,
trayectoria con jerk acotado y MPC sobre la misma misión. Añadir **energía por misión** (J y
J/m) y la **precisión de seguimiento** por RTK como par de ejes: la figura es el **frente de
Pareto precisión-energía medido en campo**, que la literatura solo tiene simulado. Diseño: ensayos
emparejados e intercalados (ABCCBA), misma ventana de SoC, viento registrado. El efecto esperado
es pequeño (unidades de %), así que sin corriente calibrada y sin repeticiones no sale.

### Subproducto — dataset abierto

Con la campaña de los papers 1 y 2 sale un dataset tipo IDF-DS19 pero de multirrotor: logs `.ulg`
+ Parquet (`flight-review-rs`), corriente calibrada, RTK, eRPM, temperaturas, viento, etiquetas de
maniobra. *Scientific Data* o *Data in Brief*. Hay que resolver dónde alojarlo (Zenodo), porque el
repo no admite logs de más de 5 MB.

---

## 3. Lo que hay que arreglar antes de medir nada (bloqueantes)

| # | Bloqueante | Estado | Qué hacer |
|---|---|---|---|
| 1 | **Corriente no fiable** (`BAT1_A_PER_V=17`, 13.6 A con el dron parado) | ❌ | El pad de corriente del ESC Bluejay no sirve. Montar un **sensor Hall/shunt externo** (módulo de potencia tipo Holybro PM02/PM07 o ACS758/INA238 hacia el ADC del FC) y calibrarlo con pinza amperimétrica a 3-4 puntos de gas en banco, hélices quitadas. Sin esto no hay paper. |
| 2 | **Temperatura del pack** | ❌ no se mide | Termistor/DS18B20 pegado al pack, logueado por la Pi o por ADC del FC. El baro a 79 °C ya avisa de que el dron trabaja caliente. |
| 3 | **Conteo de culombios desactivado** (`BAT1_CAPACITY=-1`) | ⚠️ deliberado | Re-habilitar a 1300/4500 **después** de calibrar la corriente, para poder evaluar el estimador por culombios. |
| 4 | Verdad de terreno de fin de descarga | ⏳ | Protocolo de vuelo hasta 3.5 V/celda bajo carga con piloto y `COM_LOW_BAT_ACT` en aviso, no en Land automático (la caída de voltaje bajo carga lo dispararía antes). |
| 5 | eRPM por motor en el log | ✅ `DSHOT_BIDIR_EN=1` | Confirmar que `esc_status` aparece en el `.ulg` con `SDLOG_PROFILE=3`. |
| 6 | Banco de batería (OCV, HPPC, capacidad) | ⏳ compañero | Carga programable o al menos descarga controlada con registro V/I/T. |
| 7 | Viento | ⏳ | Anemómetro de mano o estación barata en el punto de vuelo; se registra por vuelo. |

**Riesgos:**
- Un revisor puede decir "el ECM de LiPo ya está estudiado". La defensa es el régimen (15 C+),
  la identificación **desde vuelo** y la verdad de terreno de tiempo restante, no el modelo.
- La fade de capacidad en 30-40 vuelos puede ser pequeña; el paper no debe prometer SoH. Si
  sale, es un bonus.
- Vuelos hasta el corte: hay que respetar el 3.5 V/celda bajo carga (ver
  `reports/2026-10-27_vuelos-rtk-suaves-logs17-18.md`), y no bajar de 3.3 V en reposo.

---

## 4. Plan y plazos

| Semana | Hito |
|---|---|
| 1-2 | Sensor de corriente externo + termistor; calibración en banco; re-habilitar culombios. |
| 2-3 | Banco con el compañero: OCV-SoC y HPPC de los dos packs a 2-3 temperaturas. |
| 3-6 | Campaña: 4-6 sesiones, 30-40 vuelos hasta el corte, tres perfiles, viento registrado. |
| 6-9 | Identificación ECM en vuelo vs banco, estimadores, figuras. |
| 9-12 | Redacción del paper 1; el paper 2 reutiliza los vuelos del protocolo PID/MPC. |

---

## 5. Pulido (2026-10-29, 2ª iteración): comparar dos químicas

### 5.1 Qué se usa de verdad en multirrotores

| Química | Dónde se usa | Wh/kg a nivel de pack | Descarga continua | Comentario para este dron |
|---|---|---|---|---|
| **LiPo pouch alta descarga** (lo que lleva el dron) | FPV, racing, industrial pequeño | ~150-200 | 30-100 C | Poca resistencia interna, mucho sag solo a C muy altos. |
| **Li-ion cilíndrica 21700 alta descarga** (Molicel P45B/P50B, Samsung 40T/50S) | Long-range FPV, industrial de autonomía | ~200-230 (celda 230-250) | P45B 45 A, P50B 60 A por celda | Más energía, **más resistencia interna** → más sag y más calor a la misma corriente. |
| LiHV | Variante de LiPo a 4.35 V/celda | +5-8 % | igual que LiPo | No aporta química nueva; descartar. |
| Semi-sólido (Tattu/Grepow/Herewin, 280-350 Wh/kg) | Agrícola y heavy-lift, packs de 10-30 Ah | 250-300 | **1-3 C continuos** | Con un pack de 4.5 Ah el hover (~3 C medios) ya está en el límite; descartar en este dron. |
| LiFePO4 | Casi nunca en multirrotor | ~100-130 | media | Descartar. |

**Las dos a comparar: LiPo pouch vs Li-ion 21700 alta descarga.** Son las dos que de verdad
se montan, y no se ha encontrado ningún paper que las compare **en vuelo** sobre el mismo dron y la
misma misión: todo lo que hay son guías de fabricante con cifras de "30-50 % más autonomía" sin
ensayo controlado (y un supuesto estudio de ETH 2022 que ninguna fuente localiza).

### 5.2 Par emparejado propuesto (misma tensión, misma capacidad, misma masa ±10 %)

| | LiPo (ya previsto) | Li-ion |
|---|---|---|
| Pack | 6S1P 4500 mAh 60C | **6S1P Molicel P50B** (5000 mAh, 60 A continuos) |
| Energía nominal | ~100 Wh | ~108 Wh |
| Masa | ~510 g | 6 × 70 g + níquel/cables/XT60 ≈ **460 g** |
| Descarga continua | 270 A | 60 A |
| Corriente media del dron | ~13-16 A (log 18: 1300 mAh en 4.8 min) → **~3 C** | igual, ~3 C |

Con corriente media de ~3 C ambos packs van cómodos. El riesgo está en los **picos**: PX4 puede
pedir empuje máximo (4 × 45 A de los F90) y en una 1P de Li-ion eso es 3× su continuo → sag
brutal y posible brownout. Mitigación obligatoria: **limitar `MPC_THR_MAX` (~0.6)** y volar
perfiles suaves con el Li-ion; el F450 tiene empuje de sobra (9.4 kg) así que el cap no cuesta nada.
Alternativa más segura pero no emparejada en masa: 6S2P P45B (90 A continuos, ~880 g).

**Dos packs de cada química** (4 packs) para separar la variación pack-a-pack de la de química.
Montar el Li-ion en el laboratorio del compañero (soldadura por puntos, sin BMS, con balance lead)
o comprar un 6S1P P50B comercial de long-range FPV.

### 5.3 Qué pregunta se añade al paper

La hipótesis, formulada como tal: **el Li-ion da más Wh pero su mayor resistencia interna hace
que el estimador por voltaje de PX4 (el de serie) se equivoque más, y que el corte a 3.6 V/celda
bajo carga deje más energía sin usar.** Eso convierte la comparación de químicas en el caso de
uso del ECM: el mismo estimador que sirve para la LiPo falla en la Li-ion, y el modelo lo arregla.

Detalle útil: PX4 **ya tiene** un knob de compensación de caída IR (`BAT1_R_INTERNAL`, por
defecto -1 → usa `BAT1_V_LOAD_DROP`). Una contribución concreta y reproducible es: *identificar
R0 por química desde el vuelo, ponerlo en `BAT1_R_INTERNAL` y medir cuánto baja el error.*

Métricas por química: Wh utilizables en vuelo vs Wh de banco; R0 en vuelo vs HPPC; subida de
temperatura; error de SoC y de tiempo restante; autonomía en minutos y **minutos por gramo**.
Matriz: 2 químicas × 3 perfiles × ≥5 repeticiones = 30 vuelos hasta el corte, más banco por pack.

---

## 6. Sensor de corriente para datos de consumo en vuelo

### 6.1 Por qué no vale lo que hay

El FC#2 recibe la corriente por el **pad del ESC Bluejay** (`BAT1_SOURCE=0`, `BAT1_A_PER_V=17`):
marca 13.6 A con el dron parado. Es un canal sin sensor válido, y además PX4 **solo loguea
`battery_status` cada 200 ms (5 Hz)** en el perfil por defecto, y `esc_status` cada 100 ms.
Ambas cosas se arreglan.

### 6.2 Opciones compatibles con PX4

| Opción | Tecnología | Rango / precisión | Cómo entra en PX4 | Veredicto |
|---|---|---|---|---|
| **Mauch PL-050 / HS-050-LV** (~40 $) | **Hall** (sin shunt), sin deriva térmica, **hoja de calibración individual** (V_DIV y A/V) | 50 A continuos, picos de cientos de A | Analógico → pad de corriente del FC, `BAT1_A_PER_V` = valor de la hoja | **Recomendada.** La referencia que usa ArduPilot para medir bien. Va en serie en el XT60. |
| Holybro PM02 V3 (~25 $) | Analógico, 36.364 A/V | 60 A continuos, 120 A de medida | Igual que arriba | Correcto pero sin calibración individual; a 15 A da solo 0.4 V de 3.3 V al ADC. |
| Holybro PM02D / PM03D | Digital I2C (INA228/INA226), "mejor que 5 %" | 2-12S | `SENS_EN_INA228` | Para Pixhawk 5X/6X; en el NxtPX4 habría que colgarlo del I2C libre. |
| **INA228/INA238 + shunt externo** (breakout ~10 $ + shunt 0.5-1 mΩ 100 A) | Digital, 16-20 bit, mide también **energía integrada** (culombios en hardware) | según shunt | Driver `ina228`/`ina238` de PX4 por I2C, **o directamente en la Raspberry Pi** a 100 Hz | **Segunda medida independiente**, en la Pi, con marca de tiempo ROS 2. Sirve para validar lo que ve el FC. |
| ESC con telemetría de corriente (EDT) | Por motor | depende del ESC | `esc_status` | El Bluejay no la da; no hace falta para el paper 1. |
| CUAV CAN PMU | DroneCAN | 110 A | CAN | El FC#2 no tiene CAN; descartar. |

Lo que usó el paper de ICRA 2026: sensor Hall ±100 A + STM32 + SD a 10 Hz, aparte del autopiloto.
Nosotros podemos hacerlo mejor: **sensor Hall calibrado hacia el FC** (para que el estimador de PX4
que evaluamos vea la corriente real) **+ INA228 en la Pi** como referencia independiente a 100 Hz.

### 6.3 Lo que hay que configurar

1. Mauch en el XT60 → salida analógica al pad `CURR` del FC (comprobar que el pad del NxtPX4 es
   ADC de 3.3 V y qué divisor lleva; si el ESC ya alimenta ese pad, desconectarlo).
2. `BAT1_A_PER_V` = hoja de calibración; verificar con pinza a 3-4 puntos de gas en banco, hélices
   quitadas. Después `BAT1_CAPACITY` = 4500 / 5000 y `BAT1_R_INTERNAL` según química.
3. En la SD, `etc/logging/logger_topics.txt`:
   ```
   battery_status 0
   esc_status 10
   ```
   (`0` = sin límite de tasa; el ADC de batería publica a ~100 Hz). Se lee tras el perfil, así que
   sobrescribe los 200 ms por defecto sin tocar `SDLOG_PROFILE`.
4. Termistor en el pack (DS18B20 o NTC) leído por la Pi, mismo reloj que el INA228.
5. Antes de cada sesión: capacidad de referencia del pack en banco cada ~10 vuelos.

---

## 7. Decisión (29-oct): comprar ambas químicas y registrar en la Raspberry Pi

### 7.1 Compra

| Qué | Cantidad | Nota |
|---|---|---|
| LiPo 6S1P 4500 mAh 60C | 2 | La ya prevista. Dos unidades para separar pack-a-pack de química. |
| Li-ion 6S1P Molicel **P50B** (5000 mAh, 60 A) | 2 | Si no hay P50B montada, P45B (45 A). Con **balance lead JST-XH 7 pines** (banco y carga). Ideal: mismo lote. |
| INA228 (o INA238) en breakout | 1 | ⚠️ Los breakouts típicos llevan shunt de 15 mΩ para **≤10 A**: hay que usar **shunt externo** por las entradas IN+/IN-. |
| Shunt 1 mΩ ≥3 W (o 0.5 mΩ), 100 A | 1 | A 20 A disipa 0.4 W; a 100 A de pico 10 W un instante. En el positivo (el INA228 mide high-side hasta 85 V). |
| DS18B20 (×2) | 2 | Uno pegado al pack, otro ambiente. 1-Wire nativo del GPIO4 de la Pi. |
| Mauch PL-050 / HS-050-LV | 1 (opcional, fase 2) | Para que el estimador de PX4 reciba corriente real en vivo. Analógico → pad CURR del FC. |
| Pinza amperimétrica DC o vatímetro | 1 | Calibración en banco (hélices quitadas). |
| Anemómetro | 1 | Un dato por vuelo basta. |

Cuatro packs permiten además rotarlos y no calentar el mismo dos veces seguidas.

### 7.2 Registro en la Pi: sí, y por qué basta para el paper 1

**Todo lo que necesita el análisis se puede registrar en la Pi** sin tocar el cableado del FC:

```
XT60 batería ──[ shunt 1 mΩ ]── XT60 dron (ESC + FC)
                  │   │
              INA228 (I2C, 100 Hz) ──┐
     DS18B20 pack / ambiente (1 Hz) ─┤─── Raspberry Pi ── rosbag
     /fmu/out/battery_status (V FC)  ─┤      (ROS 2, reloj de la Pi)
     /fmu/out/vehicle_odometry, RTK  ─┘
                                        .ulg en la SD del FC (IMU, esc_status eRPM, modos)
```

- La Pi tiene I2C y 1-Wire nativos: **no necesita ADC**. Por eso el INA228 (digital) va a la Pi y
  el Mauch (analógico) iría al FC, no al revés.
- Carga de CPU: una lectura I2C a 100 Hz es despreciable (nada que ver con el SLAM).
- **Sincronización con el `.ulg`:** el `battery_status` del FC llega por DDS con el timestamp de
  PX4; se alinea la **tensión** del INA228 con la del FC por correlación cruzada (misma señal
  física, dos sensores) → error <10 ms. No hace falta hardware de sync.
- **El estimador de PX4 se evalúa offline por replay**: el código de `battery.cpp` (voltaje,
  culombios, `R_INTERNAL`, `time_remaining_s`) es simple y determinista; se reimplementa en
  Python y se alimenta con la tensión del FC y la corriente del INA228. Es incluso más limpio que
  en vivo: se pueden barrer parámetros (`BAT1_R_INTERNAL`, `V_LOAD_DROP`) sobre los mismos vuelos.

**Qué se pierde sin alimentar al FC (y por qué es fase 2, no bloqueante):** que el failsafe y
el `time_remaining_s` que ve el piloto sean los "de verdad" en vuelo. Vale para una figura de
demostración al final, no para la identificación ni la validación. Se añade cuando se compruebe
el pad CURR del NxtPX4 (ADC 3.3 V, divisor) y se desconecte el canal del ESC.

### 7.3 Nodo de registro (a implementar en `px4_drone`, en la Pi)

- `power_logger`: INA228 por `smbus2` a 100 Hz → topic `sensor_eval/power` (V, I, P, energía
  acumulada en hardware del propio chip), DS18B20 a 1 Hz → `sensor_eval/temp`.
- Se graba con `ros2 bag record` junto a `/fmu/out/battery_status`, `/fmu/out/vehicle_odometry`,
  `/fmu/out/vehicle_status` (modo) y `/fmu/out/vehicle_gps_position`.
- Cada vuelo: `flight_id`, pack (etiqueta física), química, masa pesada, T ambiente, viento,
  perfil, capacidad de referencia más reciente del pack. Un `manifest.yaml` por sesión.
- Los rosbags **no van al repo** (regla de 5 MB); se suben a Zenodo al cerrar la campaña.

### 7.4 Opcional: tensión por celda en vuelo

Para Li-ion merece la pena ver el desbalance bajo carga. Un ADS1115 (I2C, 16 bits) con divisores
sobre el balance lead da 6 celdas a ~10 Hz. No es necesario para el ECM del pack; es un extra
barato que a un revisor de baterías le gusta.

---

## 8. Repetibilidad de los perfiles: Offboard desde la Pi con RTK + NTRIP

**Sí, y es la forma correcta de hacerlo.** Con el piloto a mano cada vuelo es distinto; con
Offboard el perfil es el mismo setpoint, el mismo ramp-up de despegue de PX4 y el mismo criterio
de parada. El RTK es lo que hace que "el mismo setpoint" sea el mismo sitio físico (±2 mm en
estático, cm en vuelo) y lo que da velocidad sobre el suelo fiable para los J/m.

### 8.1 Qué está ya validado (no hay que inventar nada)

| Pieza | Estado | Evidencia |
|---|---|---|
| Enlace Offboard uXRCE-DDS en FC#2 1.17 | ✅ verificado 26-oct (sin armar) | memoria `offboard-dds-1.17-fc2-verificado` |
| RTK fixed con NTRIP IGN VRS3M | ✅ 27-oct, 91/91 fixed, 2 mm | `reports/2026-10-27_campo-rtk-validado-fixed.md` |
| Brújula calibrada, perfil outdoor (`EKF2_GPS_CTRL=7`) | ✅ 27-oct | mismo reporte |
| Vuelos reales con RTK en el aire, EKF sano | ✅ logs 17/18 (manuales) | `reports/2026-10-27_vuelos-rtk-suaves-logs17-18.md` |
| Nodo `takeoff_position_hold_outdoor` (gate fix 3D, despegue, hold, patrón, aterrizaje) | ✅ existe en `px4_drone`, **no volado aún** | pendiente #4 de `pendiente-rtk-ntrip-y-calibracion` |
| Puerta del switch RC, escape por ch6/ch8, modo banco | ✅ | `puerta-switch-rc-offboard`, `offboard-escape-rc-fc2` |
| NTRIP desde la **tablet con QGC** (datos móviles) → radio SiK → FC → F9P | ✅ es la vía de los logs 17/18 (92-97 % fixed) | **se mantiene**: en el campo no hay WiFi; la Pi no necesita internet |

**Las correcciones NTRIP no dependen de quién manda.** QGC en la tablet (con datos móviles) las
reenvía por la radio SiK y el FC las mete en el F9P; la Pi manda setpoints por TEL2/DDS. Son dos
enlaces distintos que no se pisan. **Decisión (29-oct): se mantiene la tablet**, porque en el campo
no hay WiFi; el cliente NTRIP de la Pi queda descartado para este trabajo.

Consecuencias prácticas:
- **El estado RTK queda igualmente en el rosbag**: `fix_type` viene en
  `/fmu/out/vehicle_gps_position` (6 = fixed, 5 = float). No hace falta que la Pi sepa nada del caster.
- **El nodo no debe abortar si el fix cae de 6 a 5 en vuelo** (un corte de datos en la tablet o
  una ráfaga RTCM perdida en la SiK): el gate de RTK es solo al despegue; en vuelo se sigue y se
  etiqueta el tramo. Para la energía da igual, para los J/m la velocidad del EKF sigue siendo buena.
- La radio SiK lleva telemetría + RTCM (~1-2 kB/s de VRS3M). A 57600 cabe, pero conviene no
  subir las tasas de stream de QGC; la Pi **no** usa la SiK (TEL2 para DDS, USB-C para la webui).
- ✅ **Confirmado por Kevin (29-oct):** la tablet tiene internet móvil y corre la última versión de
  QGC con el NTRIP del IGN ya configurado (la misma configuración de los vuelos 17/18). No hay
  nada que montar en ese lado. El operador lanza el nodo desde la webui de la Pi conectándose al
  AP de la propia Pi (`field-ap`), que no necesita internet.

### 8.2 Lo que falta: un nodo `energy_profile` (hereda de `TakeoffPositionHoldBase`)

Tres perfiles, parámetro `profile:=hover|vertical|horizontal`, todo relativo al punto de despegue
en NED local y con rumbo fijo:

| Perfil | Setpoint | Parámetros |
|---|---|---|
| `hover` | subir a `h` y mantener | `h=1.5 m` |
| `vertical` | ciclo `h_min ↔ h_max` a `vz` constante | `1 ↔ 5 m`, `vz=1 m/s`, pausa 3 s en cada extremo |
| `horizontal` | ida y vuelta de `d` m sobre un rumbo fijo a `v` constante, a `h` | `d=20 m`, `v=2 m/s`, `h=2 m` |

Cambios respecto al nodo actual:
1. **Gate de RTK:** exigir `fix_type == 6` (fixed) antes de despegar, no solo 3D (parámetro,
   para poder relajar a 5 si un día el caster falla).
2. **Fin por batería, no por tiempo:** suscribirse a `/fmu/out/battery_status`; cuando la tensión
   de celda filtrada (media 2 s) baje de `v_cell_land=3.5 V` **bajo carga**, volver al punto de
   despegue y aterrizar. Backstop: el piloto y, en PX4, `BAT_EMERGEN_THR` (hoy `COM_LOW_BAT_ACT=0`,
   solo aviso, que es lo que queremos para descargar hasta el corte).
3. **Etiqueta de fase:** publicar `energy/phase` (takeoff, hold, up, down, out, back, land) para
   segmentar el análisis sin adivinar.
4. **Repetibilidad geográfica (opcional):** si se quiere que la ida y vuelta sea literalmente el
   mismo tramo de suelo entre sesiones, convertir dos waypoints lat/lon fijos a NED con
   `vehicle_local_position.ref_lat/ref_lon` de cada vuelo. Para el paper basta con la marca de
   despegue (el RTK la hace reproducible) y el rumbo.

### 8.3 Lo que el RTK no resuelve: el checklist de igualdad entre vuelos

| Factor | Control |
|---|---|
| Viento | Anemómetro por vuelo; descartar vuelos con racha > umbral; **intercalar químicas ABBA** en la misma sesión. |
| Temperatura | Pack a temperatura ambiente antes de volar (no recién cargado ni recién volado); DS18B20. |
| Carga inicial | Siempre a 4.20 V/celda (Li-ion P50B también carga a 4.20) + 30 min de reposo. |
| Masa | Misma carga de pago (Pi, sensores, soportes); pesar el dron con cada pack y anotarlo. |
| Controlador | Mismos gains PID en todos los vuelos del paper 1; el MPC solo en el paper 2. |
| Altura | `EKF2_HGT_REF=0` (baro) con el baro a 79 °C; con RTK fixed probar `HGT_REF=1` (GPS) antes del perfil vertical. |
| Orden | Aleatorizar perfil y pack dentro de la sesión; anotar hora. |

### 8.4 Orden de pruebas

1. **Prueba 0 (ya debida):** hover Offboard outdoor con el nodo actual, 2 m, 10 s, RTK fixed,
   Kevin arma. Es el pendiente #4 y valida el gate GPS + aterrizaje con el perfil outdoor.
2. Nodo `energy_profile` en banco sin hélices (modo banco ya existe) y luego hover corto.
3. Primera descarga hasta el corte con la LiPo 1300 (la conocida) para afinar `v_cell_land` y el
   filtro.
4. Campaña con los cuatro packs nuevos.

---

## Referencias

**Modelos de consumo y validación en vuelo**
- An Overview of Drone Energy Consumption Factors and Models: <https://arxiv.org/abs/2206.10775>
- A Comparative Study on Energy Consumption Models for Drones: <https://arxiv.org/abs/2206.01609>
- Range, Endurance, and Optimal Speed Estimates for Multicopters: <https://arxiv.org/abs/2109.04741>
- Modelling Power Consumptions for Multi-rotor UAVs: <https://arxiv.org/abs/2209.04128>
- CVaR-based Flight Energy Risk Assessment using a Deep Energy Model: <https://arxiv.org/abs/2105.15189>
- State-of-the-art in energy optimization for quadcopter UAVs (2025): <https://www.researchgate.net/publication/396669414>
- Wind-Resilient Energy Estimation Framework for UAVs (Drones 2026): <https://doi.org/10.3390/drones10050337>

**Control y planificación energy-aware (todo simulación)**
- Energy-Efficient Trajectory Optimization with NMPC: <https://www.researchgate.net/publication/382534279>
- Mission specific PID tuning for energy-efficient quadrotor flights (AST 2025): <https://www.sciencedirect.com/science/article/abs/pii/S1270963825013367>
- Battery-Aware Predictive Trajectory Planning and Control (2026): <https://arxiv.org/abs/2609.12188>
- Aggressiveness-Aware Learning-based Control (2026): <https://arxiv.org/abs/2602.21936>

**Batería: SoC, fin de descarga, salud**
- Dibbern et al., load-dependent SoC and end of discharge of a multirotor battery (JATE 2023): <https://docs.lib.purdue.edu/jate/vol12/iss2/4/>
- Motion-Specific Battery Health Assessment for Quadrotors (ICRA 2026): <https://arxiv.org/abs/2603.12791>
- ML-based battery SoH prediction for UAV predictive maintenance (2026): <https://arxiv.org/abs/2607.06791>
- SoC and RUL estimation on a rotary-wing UAV battery (Drones 2026): <https://www.mdpi.com/2504-446X/10/7/549>
- Tesis: remaining flight time sobre 162 logs públicos de PX4: <https://github.com/arjjunck/uav-thesis>
- SoC EKF for UAV power-type packs (Energies 2019): <https://doi.org/10.3390/en12203960>
- LiPo modeling for dynamic WPT in UAV (Thevenin 3 RC): <https://ieeexplore.ieee.org/document/9922909/>
- Peng et al., splice-ECM for UAV Li-ion (2022, "no field verification in drones"): <https://scijournals.onlinelibrary.wiley.com/doi/10.1002/ese3.1268>
- Bills et al., battery dataset for eVTOL (Scientific Data 2023): <https://www.nature.com/articles/s41597-023-02180-5>
- NASA, Remaining Flying Time Prediction (ECM Edge-540T): <https://ntrs.nasa.gov/api/citations/20180004466/downloads/20180004466.pdf>

**Datasets**
- Rodrigues et al., DJI M100 in-flight energy dataset (Scientific Data 2021): <https://www.nature.com/articles/s41597-021-00930-x>
- Drone flight data reveal energy and GHG savings (Patterns 2022): <https://www.cell.com/patterns/fulltext/S2666-3899(22)00180-5>
- IDF-DS19, fixed-wing PX4 open benchmark (Scientific Data 2026): <https://www.nature.com/articles/s41597-026-06716-3>
- NanoBench (2026): <https://arxiv.org/abs/2603.09908> · Race Against the Machine: <https://arxiv.org/abs/2311.02667>
- PX4 flight-review-rs (ULog → Parquet): <https://github.com/PX4/flight-review-rs>

**Químicas y sensores de corriente**
- Molicel INR21700-P45B datasheet: <https://www.molicel.com/wp-content/uploads/INR21700P45B_1.2_Product-Data-Sheet-of-INR-21700-P45B-80109.pdf>
- Molicel P50B (5 Ah, 60 A): <https://www.aboutenergy.io/voltt-battery-library/molicel-p50b>
- Mauch power monitors (hall, hoja de calibración): <https://ardupilot.org/copter/docs/common-mauch-power-modules.html> · <https://www.mauch-electronic.com/>
- Holybro PM02 V3 en PX4: <https://docs.px4.io/main/en/power_module/holybro_pm02>
- Comparativa de módulos Holybro: <https://docs.holybro.com/power-module-and-pdb/power-module-comparison>
- Módulos de potencia soportados por PX4: <https://docs.px4.io/main/en/power_module/>
- Intervalos de log por defecto (`logged_topics.cpp`): <https://github.com/PX4/PX4-Autopilot/blob/main/src/modules/logger/logged_topics.cpp>
- Semi-sólido vs LiPo (fabricante, no independiente): <https://www.herewinpower.com/blog/semi-solid-battery-cell-vs-conventional-lipo-uav-integrators/>
- Li-ion vs LiPo FPV (guía, no independiente): <https://blog.uavmodel.com/6188-2/>

**Telemetría ESC**
- PX4 DShot / bidirectional DShot / EDT: <https://docs.px4.io/main/en/peripherals/dshot>
- Airspeed estimation from propeller feedback (potencia desde V/I/RPM del ESC): <https://arxiv.org/abs/2507.03456>
