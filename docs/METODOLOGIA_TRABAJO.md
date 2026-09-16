# Metodología de trabajo

Cómo se trabaja en este proyecto: diagnóstico con evidencia, dónde queda registrado cada
hallazgo y qué reglas se siguen al tocar el dron. Escrito a partir de lo que ha funcionado
—y de lo que ha fallado— en las sesiones de tuning y análisis de vuelos.

---

## 1. Nada se afirma sin comprobarlo

- **Leer el fuente de la versión exacta que corre el FC**, no la de `main`. El repo está en
  `/home/kmedrano/PX4-Autopilot`; se consulta con `git show v1.14.3:<ruta>`. Varias
  conclusiones válidas en `main` **no se cumplen en la 1.14.3** y al revés: la cadena
  flujo→terreno del EKF2 es el ejemplo claro.
- **Verificar los bits de una máscara** en su `.msg` antes de interpretarlos
  (`msg/EstimatorStatus.msg`), en vez de tirar de memoria.
- **Comprobar los enlaces y las rutas** antes de publicarlos: una URL inventada se detecta
  con un `curl` de 5 segundos.
- Si un dato viene del usuario ("estaba a 3 metros"), se anota **como estimación**, no como
  medida.

## 2. Corregirse en cuanto los datos lo pidan

Cuando una medida nueva invalida una conclusión anterior, se corrige **en los tres sitios**:
el reporte donde se afirmó, la memoria, y el mensaje al usuario, diciendo claramente qué
estaba mal. Ejemplos reales de esta sesión:

- "El barómetro lee 1 m de más" → era **razonamiento circular**: con `HGT_REF=2` el rango es
  la referencia, así que su innovación es pequeña por construcción.
- "Los saltos de altura son resets del EKF" → eran **cambios de instancia primaria** del
  selector, coincidentes al décimo de segundo.
- "El cliente uXRCE-DDS satura la CPU" → medido: **0.004%**. Hipótesis descartada.

Una hipótesis descartada con datos vale tanto como una confirmada, y se registra igual.

## 3. Dónde queda cada cosa

| Tipo | Sitio | Cuándo |
|---|---|---|
| Análisis de una sesión | `reports/AAAA-MM-DD_tema.md` + fila en `reports/README.md` | al cerrar cada diagnóstico o vuelo |
| Procedimientos y configuración | `docs/` | cuando cambia un procedimiento o un parámetro de forma definitiva |
| Contexto entre conversaciones | memoria (`memory/`) | hallazgos, riesgos, decisiones y pendientes |
| Estado de hitos | `README.md` y `docs/README.es.md` | al completar o avanzar un hito |

Regla de fondo: **si es un hallazgo real, no puede quedarse solo en la conversación.**

## 4. Logs

- Los `.ulg` se analizan con `pyulog` (venv en `/home/kmedrano/src/Asistente/.venv`).
- **No se commitean logs de más de ~10 MB.** Se quedan en el `.gitignore` con una línea
  explicando por qué; lo que se conserva es el **análisis**, no el fichero crudo.
  Comprobación: `find logs -name '*.ulg' -size +10M`.
- Al comparar dos volcados de parámetros, **el conteo distinto no significa pérdida**: PX4
  solo enumera los parámetros en uso, así que apagar un módulo hace desaparecer los suyos.

## 5. Tocar el FC

- Herramientas en `scripts/mavlink/`, procedimiento en
  [`CONEXION_MAVLINK_SCRIPTS.md`](CONEXION_MAVLINK_SCRIPTS.md). Funcionan por cable y por radio.
- **Volcado de parámetros antes de cambiar nada**, como punto de retorno.
- Toda escritura va **verificada por lectura**; si alguna falla, no se guarda ninguna.
- Los parámetros marcados `@reboot_required` no aplican hasta reiniciar, aunque se lean bien.
- **Nunca armar el dron.** Los comandos de armado los da el usuario. Antes de un reinicio se
  comprueba que está desarmado y se aborta si no lo está.
- Antes de proponer un cambio, comprobar que **ese firmware lo soporta**: `param show` para
  los parámetros en uso, `ls /bin` para los drivers.

## 6. Git

- Trabajo directo sobre `main` en el repo del diario, que es personal; la Pi hace `git pull`.
- Para tocar otro repo sin alterar su rama activa, **worktree temporal** en vez de cambiar de
  rama en el checkout del usuario.
- Los logs pesados y los binarios regenerables no entran.

## 7. Seguridad en las pruebas

Reglas que vienen de accidentes reales, no de teoría:

- **Gas centrado durante todo el vuelo offboard.** Al pasar a Stabilized el stick manda
  directamente: arriba dispara el dron, abajo lo deja caer.
- **El switch de modo solo actúa al cambiar de posición**: debe reposar en una posición
  distinta de la de escape.
- **Reiniciar el FC entre vuelos** mientras el EKF no sea estable: un estado roto sobrevive
  al desarme.
- **No probar ciclos de despegue sin hélices**: el integrador lleva los motores al 100%
  indefinidamente.
- Un nodo offboard **deja de publicar** en cuanto el dron no está en OFFBOARD, y no manda
  `LAND` si el piloto ha tomado el control.
