# CLAUDE.md — px4_drone_dev

## Reglas de trabajo

### Memoria y registro de sesión
Durante todo el proceso de trabajo (diagnóstico, pruebas, tuning, desarrollo) se deben guardar en memoria las partes importantes:
- **Resultados de pruebas** — qué se probó, qué arrojó, qué confirmó o descartó.
- **Hallazgos y conclusiones** — causas raíz encontradas, hipótesis descartadas con su evidencia.
- **Cambios de parámetros o configuración** — qué se cambió, por qué, y qué efecto tuvo.
- **Próximos pasos acordados** — qué queda pendiente al cerrar una sesión.
- **Riesgos o advertencias identificados** — comportamientos peligrosos o estados inválidos detectados.

Usar el sistema de memoria persistente (`memory/`) para que la siguiente conversación pueda retomar sin perder contexto.

### Documentación
La documentación en `docs/` y `reports/` debe mantenerse actualizada conforme avanza el trabajo:
- **Reportes** (`reports/`) — crear o actualizar el reporte correspondiente al finalizar cada sesión de diagnóstico o tuning, reflejando los nuevos hallazgos y el estado actual.
- **Docs de integración/configuración** (`docs/`) — actualizar si un procedimiento cambia, un sensor se reconfigura, o un parámetro clave se modifica definitivamente.
- **Milestones del README** — actualizar el estado (✅ / 🔄 / ⏳) cuando un hito se completa o avanza.
- No dejar información importante solo en la conversación: si algo es un hallazgo real, debe quedar en el archivo correspondiente.
