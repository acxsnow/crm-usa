# [CON-003] Dos personas editando lo mismo

## 1. Información general

- **ID:** CON-003
- **Módulo:** Concurrencia
- **Prioridad:** P2
- **Tipo de prueba:** Concurrencia
- **Estado:** APROBADO
- **Fecha de ejecución:** 2026-10-25 (parte por API)
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 15 min de ejecución
- **Tiempo real:** lote 3 por API
- **Versión o commit probado:** devjj 67141f2 + D-013, D-015 a D-018 (base QA reiniciada con seed_qa)

## 2. Objetivo

Saber qué pasa cuando dos editan la misma obra o expediente.

## 3. Precondiciones

- Dos sesiones de administración en la misma obra.

## 4. Datos de prueba

- Cambiar las notas en las dos y guardar una después de la otra.

## 5. Procedimiento paso a paso

1. [ ] Guardar en la ventana A y luego en la B sin recargar.

## 6. Resultado esperado

- Anotar si B pisa a A sin aviso (último gana) o si avisa del conflicto.

## 7. Resultado obtenido

- Qué pasó: Lote 3 por API (25 oct, base QA reiniciada): 1 de 1 comprobaciones bien. Dos sesiones de Administración guardan las notas de la misma obra una tras otra: último gana sin aviso.
- Diferencias con lo esperado: Ninguna (el escenario pedía anotar el comportamiento).
- Comprobaciones por API (1 de 1):
  - ✔ Dos sesiones guardan las notas una tras otra (A 200, B 200): queda «QA nota de la ventana B»

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`): ver las comprobaciones de la sección 7 (script `lote3` por API).
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] Si pisa sin aviso en datos de dinero, registrar defecto.

## 10. Resultado final

- [x] APROBADO
- [ ] FALLIDO
- [ ] BLOQUEADO
- [ ] PENDIENTE DE CORRECCIÓN
- [ ] PENDIENTE DE REEJECUCIÓN

## 11. Defectos encontrados

| ID defecto | Descripción | Prioridad | Registrado en |
|---|---|---|---|
| | | | `01_REGISTRO_DEFECTOS.md` |

## 12. Tiempo y seguimiento

- Tiempo de ejecución: lote 3 por API
- Tiempo dedicado al análisis del defecto:
- Tiempo de corrección:
- Tiempo de reejecución:
- Observaciones: Comportamiento anotado: el último que guarda gana y no hay aviso de conflicto. Si se quiere avisar, es una mejora a decidir.
