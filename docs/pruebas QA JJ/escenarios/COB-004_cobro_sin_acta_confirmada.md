# [COB-004] No se puede cobrar sin acta confirmada ni permiso aprobado

## 1. Información general

- **ID:** COB-004
- **Módulo:** Cobro al programa
- **Prioridad:** P0
- **Tipo de prueba:** Funcional · seguridad
- **Estado:** Pendiente
- **Fecha de ejecución:**
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 15 min de ejecución
- **Tiempo real:**
- **Versión o commit probado:** main 23260ae (anotar el que se pruebe de verdad)

## 2. Objetivo

Las guardas del cobro no se saltan ni por la pantalla ni por la API.

## 3. Precondiciones

- Una obra con la instalación cerrada pero sin confirmar (INS-004 sin INS-005).

## 4. Datos de prueba

- Token de contabilidad.

## 5. Procedimiento paso a paso

1. [ ] Buscar la obra en Cobros de programas.
2. [ ] `POST` de creación del cobro por la API con el id de la obra.
3. [ ] Intentar `transition` del expediente a `billing_in_progress`.

## 6. Resultado esperado

- La pantalla dice «Se habilita al confirmar el acta»; la API responde 409/422 con el motivo; nada cambia.

## 7. Resultado obtenido

- Qué pasó:
- Diferencias con lo esperado:

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`):
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] Ningún cobro creado.

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
