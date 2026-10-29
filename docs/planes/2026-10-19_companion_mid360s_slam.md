# Companion compacto para Livox MID-360S y navegación interior

**Consulta:** 2026-10-19. Objetivo: sustituir la Raspberry Pi 4 del dron para
odometría LiDAR-inercial 3D, SLAM, planificación y PX4 Offboard.
**Estado:** investigación y propuesta, sin compra ni validación en este dron.

## Recomendación y alcance de la evidencia

**Ampliación tras consulta específica sobre VOXL 2:** se localizó un benchmark
publicado el 2026-10-16 que sí mide FAST-LIO2 en VOXL 2. Véase la sección de
evidencia VOXL al final. Esto refuerza VOXL como candidato por masa; la propuesta
NX 16 GB de abajo es una elección de margen, no un mínimo necesario para LIO.

Priorizar **Jetson Orin NX 16 GB + carrier con Ethernet nativo + NVMe +
refrigeración**, conservando inicialmente el FC actual. Los 16 GB y ocho núcleos
son una elección de margen para ejecutar percepción, mapas, planificación,
registro y MPC juntos; no un requisito demostrado del sensor ni una garantía
de latencia. Comparar 15 W y 25 W bajo carga real antes de elegir perfil.

Hay evidencia pública de un dron con Orin NX **8 GB**, MID-360, Pixhawk/PX4,
FAST-LIO2/DLIO, EGO-Planner y FUEL, con vídeos y código. Es una implementación
publicada por su autor, basada en ROS 1/catkin, no un benchmark independiente
del MID-360S con ROS 2 Jazzy ni una validación de seguridad comercial.
[Proyecto](https://github.com/GaryLee1210/UAV-Navigation-System).

GLIM declara pruebas en Jetson Orin y soporte de MID360; utiliza GPU cuando se
elige esa implementación. FAST-LIO2 tiene soporte ARM, incluso Pi 4B de 8 GB:
no hay base para afirmar que una Pi sea incapaz de ejecutar LIO. El problema
a validar es el margen del sistema completo y su latencia, no solo arrancar el nodo.
[GLIM](https://github.com/koide3/glim), [FAST-LIO](https://github.com/hku-mars/FAST_LIO).
Los TOPS de IA no son una medida del rendimiento de FAST-LIO2, cuyo trabajo
principal se ejecuta en CPU.

## MID-360S: especificaciones comprobadas

Según [Livox](https://www.livoxtech.com/mid-360s/specs): 265 g,
65 × 65 × 60 mm, 6.5 W nominales, alimentación 9–27 V, Ethernet 100BASE-TX,
200 000 puntos/s de primer retorno, 10 Hz típicos, IMU ICM40609 y sincronización
PTPv2/GPS. FOV horizontal 360°, vertical −7° a +52°; no cubre una esfera.
El arranque con autocalentamiento entre −20 y 0 °C puede alcanzar 14 W.
No asumir PoE por disponer de Ethernet. En montaje horizontal no observa el
nadir: conservar una medida de altura hacia abajo fiable para proximidad/contacto.

El [driver oficial](https://github.com/Livox-SDK/livox_ros_driver2) ya documenta
Ubuntu 24.04/Jazzy y launches específicos `MID360s`. Eso demuestra soporte de
adquisición, no compatibilidad automática con cualquier port de LIO. Verificar
formato CustomMsg/PointCloud2, tiempo por punto, IMU, timestamps, unidades y
extrínsecos. El propio README presenta el driver como herramienta de pruebas
que debe adaptarse para producción.

## Alternativas de cómputo

| Plataforma | Ventaja | Límite de la recomendación |
|---|---|---|
| Orin NX 16 GB | Ocho Cortex-A78AE, margen de RAM y CUDA para mapas/percepción | Consumo, calor y coste; perfil de módulo no equivale a consumo del conjunto |
| Orin NX 8 GB | Existe implementación pública cercana de vuelo autónomo | Menos margen de RAM; seis núcleos frente a ocho del NX 16 GB |
| Orin Nano 8 GB | Plataforma de entrada al mismo ecosistema | Seis núcleos y menos margen; probar carga completa antes de dimensionarlo |
| Compute Module 5 8/16 GB | Cuatro Cortex-A76; continuidad con el ecosistema Pi y carrier muy pequeño | Sin evidencia localizada del conjunto MID-360S + LIO + planificador + MPC a los plazos requeridos |
| VOXL 2 | 70 × 36 mm, 16 g de placa, ocho núcleos y 8 GB; orientado a drones | Ecosistema/imagen propios y expansión Ethernet; no es una sustitución directa del Ubuntu/Jazzy actual |

NVIDIA publica modos de potencia de Orin NX entre 10 y 40 W; la disponibilidad
depende de BSP, configuración y alimentación. Seleccionar por rendimiento
sostenido medido. No comparar el peso de una placa desnuda con un ordenador
completo con disipador y carcasa.
[NVIDIA](https://www.nvidia.com/en-gb/autonomous-machines/embedded-systems/jetson-orin/),
[modos de potencia](https://docs.nvidia.com/jetson/archives/r36.5/DeveloperGuide/SD/PlatformPowerAndPerformance/JetsonOrinNanoSeriesJetsonOrinNxSeriesAndJetsonAgxOrinSeries.html),
[CM5](https://www.raspberrypi.com/products/compute-module-5/),
[VOXL 2](https://docs.modalai.com/voxl2-feature-matrix/).

## Integraciones físicas concretas

| Carrier/equipo | Datos del fabricante | Implicación |
|---|---|---|
| ARK Just A Jetson | Carrier 100 × 72 × 23 mm, 75 g sin Jetson ni M.2, GbE, NVMe, UART y entrada batería 5.5–75 V | Candidato para mantener FC externo; falta sumar módulo, SSD, disipación, cables y soportes |
| ARK Jetson PAB Carrier original | 116 × 72 × 23 mm sin módulos; 160 g con Jetson y disipador, sin FC | Referencia de integración ligera; esas dimensiones no incluyen toda la altura ensamblada |
| ARK PAB V3 | Carrier 132 × 61 × 19 mm, 66 g sin módulos; switch 10/100 y arnés específico | Nueva revisión distinta; no trasladar los 160 g del original a V3 |
| Seeed reComputer Mini J4012 | 63 × 95 × 42 mm, 345 g sin expansión; con expansión Ethernet 63 × 95 × 66.7 mm y 462 g | Fácil para prototipo; presupuestar la expansión para el Ethernet RJ45 documentado |
| CM5 + Waveshare CM5-NANO-B | Carrier del tamaño de CM5 y Ethernet GbE | Opción compacta; falta pesar el conjunto y medir rendimiento/térmica |

Fuentes: [ARK JAJ](https://arkelectron.com/product/ark-just-a-jetson/),
[ARK original](https://arkelectron.com/product/ark-jetson-pab-carrier/),
[ARK V3](https://arkelectron.com/product/ark-jetson-pab-v3/),
[Seeed Mini](https://wiki.seeedstudio.com/recomputer_mini_j401_getting_started/),
[Waveshare](https://www.waveshare.com/product/cm5-nano-b.htm).

Ejemplo de suma, **no peso de instalación**: 265 g de LiDAR + 160 g del conjunto
ARK original con Jetson/disipador = 425 g, antes de SSD, WiFi, alimentación,
cables y soportes. Con Seeed más expansión serían 727 g antes de esos extras.
Restar lo que se retire de la Pi/sensores para conocer el incremento neto;
comprobar centro de gravedad, empuje de hover y autonomía tras el cambio.

VOXL 2 exige comprobar versión de SDK/imagen y conectividad: la matriz consultada
publica Ubuntu 18.04/kernel 4.19. Soporte ModalAI describe expansión USB/Ethernet;
esto no acredita un stack MID-360S/Jazzy listo para usar.
[Integración Ethernet discutida con soporte](https://forum.modalai.com/topic/4660/integrating-lidar-sensor/12).

### Conexión concreta VOXL 2 ↔ MID-360/MID-360S

Ampliación comprobada en la misma sesión: la expansión **ModalAI M0062** aporta
Ethernet RJ45 y se conecta a VOXL 2 por sus conectores board-to-board: J1 del
M0062 corresponde a J3 del VOXL 2 y J2 a J5. La guía indica que el Ethernet
aparece como `eth0`. Enlazar el RJ45 al cable Ethernet del Livox; alimentar el
LiDAR por su rama de alimentación con una fuente dentro de 9–27 V, por ejemplo
12 V regulados. El Ethernet no sustituye esa alimentación. Usar el arnés de la
variante exacta del sensor, sin asumir que los conectores del S y original coinciden.

Alternativa: expansión USB host compatible con VOXL 2 y adaptador USB/Ethernet
soportado por su kernel. La M0062 evita ese adaptador externo. Su ficha excluye
VOXL 2 Mini; no extrapolar compatibilidad. Configurar IP estática del VOXL en la
misma subred del sensor y dirección de recepción del driver; verificar paquetes
LiDAR/IMU antes de iniciar LIO. Adquisición y LIO requieren portar/validar el
software en la imagen concreta del VOXL, no basta disponer de Ethernet.

Fuentes: [M0062 y compatibilidad](https://www.modalai.com/products/m0062-2),
[pinout](https://docs.modalai.com/m0062-datasheet/),
[guía Ethernet](https://docs.modalai.com/m0062-user-guide/).

## Software y arquitectura de navegación

- Mantener inicialmente PX4 1.14.3, mensajes compatibles y el FC independiente.
  El cambio de companion no obliga a cambiar el autopiloto.
- NVIDIA ya publica JetPack 7 con Ubuntu 24.04 y soporte Orin: no es correcto
  afirmar que todo Orin esté limitado a Ubuntu 22.04. Sin embargo, verificar
  soporte del BSP de **cada carrier**; las imágenes ARK documentadas consultadas
  usan JetPack 6/Jammy. No dar por validado Jazzy por soporte del módulo solamente.
  [JetPack](https://developer.nvidia.com/embedded/jetpack),
  [ARK-OS](https://github.com/ARK-Electronics/ARK-OS).
- Distinguir odometría local continua, SLAM global con cierre de bucle y
  planificación/evitación. FAST-LIO2 por sí solo no es una navegación completa.
  Evitar que una corrección global del mapa produzca saltos en la referencia de control.
- Un trabajo aceptado en IMAV 2026 identifica límites prácticos de LIO para
  vuelo: salida ligada a 10 Hz del LiDAR, ausencia de velocidades y bloqueo de
  IMU. Propone propagación a 200 Hz y validación en UAV. No basta con publicar
  repetidamente la última pose: deben existir predicción, tiempos y covarianzas
  coherentes. [Gaona et al.](https://arxiv.org/abs/2607.22145).

## Prueba de aceptación antes de decidir compra/integración final

- [ ] Fijar presupuesto, masa y volumen máximos, potencia disponible y autonomía mínima.
- [ ] Validar MID-360S real con driver/firmware elegidos y grabar recorridos a mano.
- [ ] Reproducir mismos datos a tiempo real con LIO, mapa/planificación, DDS,
  MPC y grabación activos. Probar modos de potencia sin extrapolar TOPS.
- [ ] Medir latencia sensor→odometría→PX4 p50/p95/p99, edad de datos, jitter,
  pérdidas UDP, plazos del control, CPU por núcleo, RAM y crecimiento del mapa.
- [ ] Ensayar duración suficiente para temperatura estable y mapa creciente;
  registrar consumo real en batería, picos, throttling y caídas de alimentación.
- [ ] Medir deriva y recuperación en pasillos repetitivos, paredes planas,
  cambios de altura, giros y transiciones interior/exterior. Separar pérdida
  geométrica de falta de cómputo: más CPU no resuelve falta de observabilidad.
- [ ] Verificar calidad/continuidad de posición, velocidad y covarianzas para
  EKF2, además de calibración IMU-LiDAR-FC y sincronización.
- [ ] Pasar después a simulación y al protocolo takeoff–hold–land con guardas.

Recomendación condicionada: **NX 16 GB para margen y evolución; NX 8 GB si las
medidas permiten ahorrar; CM5 si manda masa/coste y supera la prueba completa**.
No se ha encontrado una prueba comparativa controlada que establezca una placa
ganadora con MID-360S, vuestro software y vuestro chasis.

## Evidencia adicional: FAST-LIO2 medido en VOXL 2

En la consulta de seguimiento se localizó Matos et al., *Benchmarking LiDAR and
LiDAR-Inertial Odometry Algorithms for Embedded UAV Deployment in Warehouse
Environments*, Sensors 2026, 26(20), 6568, publicado el 2026-10-16.
[Artículo](https://www.mdpi.com/1424-8220/26/20/6568),
[DOI](https://doi.org/10.3390/s26206568).

Mide VOXL 2/QRB5165 con RoboSense Airy a 10 Hz, ROS Noetic en contenedor,
algoritmos fijados a los cuatro Cortex-A77 y servicios de vuelo activos
(1.9 núcleos medidos). FAST-LIO2 modificado/configurado: 23.4–26.8 ms por nube
en laboratorio y 25.1–35.0 ms en almacén, consumiendo la totalidad de las nubes.
En almacén: pico RSS 212–239 MB; temperaturas máximas 74.7–77.0 °C. Se usó
rango 0.45–15 m, filtrado y tres iteraciones; no es procesamiento ilimitado
de todos los puntos brutos. El ensayo de vuelo en lazo cerrado fue de Faster-LIO,
no FAST-LIO2. Resultados obtenidos del texto/tablas indexados por búsqueda;
la apertura directa del HTML del editor falló durante esta sesión.

Conclusión actualizada: hay evidencia experimental de CPU suficiente para
FAST-LIO2 configurado en VOXL 2. Sigue sin haber aquí un benchmark equivalente
con MID-360/S + ROS 2 Jazzy + vuestro planificador y MPC. No extrapolar un
tiempo por nube a latencia extremo a extremo ni prometer integración fácil.

## Ampliación: Orange Pi 5 y 6

**Recomendación condicionada:** incluir Orange Pi 5 Plus 16 GB en la evaluación
antes de pagar por una plataforma más costosa; si prima volumen/masa, estudiar
una variante 5 más pequeña comprobando Ethernet, almacenamiento y su imagen
exacta. No hay aquí un benchmark controlado MID-360S/Jazzy/planner/MPC en Orange Pi.

La ficha oficial de 5 Plus publica RK3588, cuatro A76 hasta 2.4 GHz y cuatro A55,
Ethernet doble 2.5G, NVMe PCIe 3.0 x4, 100×75 mm y 86.5 g de placa. Sumar
refrigeración, almacenamiento, regulación y montaje. No interpretar su fuente
5 V/4 A como consumo constante.
[Ficha/wiki](https://www.orangepi.org/orangepiwiki/index.php/Orange_Pi_5_Plus).

La familia RK3588 tiene evidencia primaria en Zhou et al.,
*FAST-LIVO2 on Resource-Constrained Platforms* (arXiv:2501.13876): su variante
LIVO optimizada funciona en CPU RK3588, con 37 ms/frame en una prueba propia
y media de 57.82 ms en Hilti; FAST-LIVO2 de referencia, 75.87 ms en Hilti.
No son tiempos de FAST-LIO2 en Orange Pi ni mediciones del sistema de vuelo completo.
[Texto del trabajo](https://arxiv.org/html/2501.13876v1).

Armbian documenta imágenes y ensayos Noble/Ubuntu 24.04 para Orange Pi 5;
verificar por separado soporte del modelo Pro/Plus/Max concreto. El nombre de
la familia no garantiza el mismo kernel ni conectividad. FAST-LIO2 usa CPU:
RKNN/NPU no aporta aceleración automática y Mali no ofrece CUDA de NVIDIA.
[Armbian Orange Pi 5](https://oldwww.armbian.com/orangepi-5/).

En las mediciones directas de Bret (agosto 2026), Orange Pi 6 y 6 Plus usan
CIX P1 con ocho A720 y cuatro A520. La 6 mide 90×90 mm y la Plus 115×100 mm.
En su ensayo, la 6 consumió 13.7 W en reposo, 26.7 W en carga y 41.4 W con
Linpack. No son consumos de SLAM ni límites absolutos de la placa.
[Ensayo primario](https://bret.dk/orange-pi-6-initial-thoughts/).

Conclusión: Orange Pi 5/RK3588 es un candidato razonable para LIO a coste
contenido, pendiente de medidas de carga completa. Orange Pi 6 es candidata
si se necesita más CPU y se acepta el presupuesto térmico/eléctrico; no
seleccionarla solo por núcleos/TOPS. VOXL conserva ventaja de masa de placa y
Orin el ecosistema CUDA cuando los algoritmos elegidos lo aprovechan.

### Comparación concreta: Raspberry Pi 5 frente a Orange Pi 5 Pro

Raspberry Pi 5 incorpora cuatro A76 a 2.4 GHz; Orange Pi 5 Pro/RK3588S,
cuatro A76 y cuatro A55, con RAM LPDDR5 frente a LPDDR4X de la Raspberry.
Ambas tienen Ethernet Gigabit. La Pro integra M.2 PCIe 2.0 x1; la Raspberry
expone PCIe 2.0 x1 por FPC y requiere adaptador para NVMe. No trasladar a la
Pro el NVMe PCIe 3.0 x4 ni los dos Ethernet 2.5G de la Plus.
Los A55 adicionales permiten distribuir servicios, pero no equivalen a duplicar
el rendimiento de FAST-LIO2. No hay aquí medición comparable del algoritmo en ambas.

Fuentes primarias: [Raspberry Pi 5](https://datasheets.raspberrypi.com/rpi5/raspberry-pi-5-product-brief.pdf),
[manual Orange Pi 5 Pro indexado](https://orangepi.net/wp-content/uploads/2024/05/OrangePi_5_Pro_RK3588S_User-Manual_v1.1.pdf).
El manual pudo consultarse en resultados indexados; su descarga directa falló.

Canonical soporta Raspberry Pi 5 con Ubuntu 24.04; Armbian clasifica la Pro
como Community y las descargas actuales consultadas son rolling Ubuntu 26.04
o Debian 13. Eso no demuestra que no pueda usarse 24.04, pero obliga a localizar,
fijar y validar imagen/kernel del modelo Pro para continuar con Jazzy.
[Canonical](https://ubuntu.com/hardware/docs/boards/how-to/ubuntu_supported/raspberry-pi/),
[Armbian Pro](https://armbian.com/boards/orangepi5pro).

Propuesta para este proyecto: Raspberry Pi 5 para minimizar cambios de plataforma
durante el tuning actual; Orange Pi 5 Pro si se acepta validar BSP y se busca
margen multitarea/NVMe integrado. Medir ambas con datos y configuración idénticos,
sin overclock y con temperatura estabilizada. No inferir consumo real a partir
de la potencia nominal del adaptador ni rendimiento de LIO a partir de TOPS.
