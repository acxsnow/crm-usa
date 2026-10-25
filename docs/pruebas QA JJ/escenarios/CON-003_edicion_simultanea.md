# [CON-003] Dos personas editando lo mismo

## 1. Información general

- **ID:** CON-003
- **Módulo:** Concurrencia
- **Prioridad:** P2
- **Tipo de prueba:** Concurrencia
- **Estado:** Pendiente
- **Fecha de ejecución:**
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 15 min de ejecución
- **Tiempo real:**
- **Versión o commit probado:** main 23260ae (anotar el que se pruebe de verdad)

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

- Qué pasó:
- Diferencias con lo esperado:

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`):
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] Si pisa sin aviso en datos de dinero, registrar defecto.

## 10. Resultado final

- [ ] APROBADO
- [ ] FALLIDO
- [ ] BLOQUEADO
- [ ] PENDIENTE DE CORRECCIÓN
- [ ] PENDIENTE DE REEJECUCIÓN

## 11. Defectos encontrados

| ID defecto | Descripción | Prioridad | Registrado en |
|---|---|---|---|
| | | | `01_REGISTRO_DEFECTOS.md` |

## 12. Tiempo y seguimiento

- Tiempo de ejecución:
- Tiempo dedicado al análisis del defecto:
- Tiempo de corrección:
- Tiempo de reejecución:
- Observaciones:
