# [INS-012] Cancelar una obra y reintegrar el material

## 1. Información general

- **ID:** INS-012
- **Módulo:** Instalación en campo
- **Prioridad:** P0
- **Tipo de prueba:** Funcional · integración
- **Estado:** Pendiente
- **Fecha de ejecución:**
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 30 min de ejecución
- **Tiempo real:**
- **Versión o commit probado:** main 23260ae (anotar el que se pruebe de verdad)

## 2. Objetivo

Cancelar exige motivo, salidas de bodega resueltas y el material reintegrado o explicado; la obra queda en solo lectura y el expediente se cierra.

## 3. Precondiciones

- La obra de INS-011 con material entregado y una salida nueva «Por autorizar».

## 4. Datos de prueba

- Motivo «El cliente desistió del programa»; devolver todo menos 1 unidad; nota «Se quedó cortado en la casa».

## 5. Procedimiento paso a paso

1. [ ] Como Carlos, buscar **Cancelar la obra…** (no debe tenerlo).
2. [ ] Como administración, **Cancelar la obra…**: leer lo que muestra (salidas abiertas y material afuera).
3. [ ] Intentar cancelar con la salida «Por autorizar»: anotar el mensaje. Rechazarla en Bodega › Salidas.
4. [ ] Intentar cancelar sin explicar el material: anotar el mensaje con la lista.
5. [ ] En Bodega › Movimientos registrar la **Devolución** de casi todo con la obra; volver y ver que la lista baja.
6. [ ] Escribir qué pasó con lo que falta y el motivo; **Cancelar la obra**.
7. [ ] Revisar la obra (aviso «Obra cancelada»), el expediente y la existencia de bodega.
8. [ ] Como Carlos: ver el aviso de la campana e intentar registrar algo en la obra.

## 6. Resultado esperado

- Sin motivo, con salidas abiertas o con material sin explicar no cancela, y dice qué falta.
- Cancelada: solo lectura, sin «Orden liberada» ni acciones de campo; el expediente queda «Cerrado» con el motivo.
- La existencia sube en lo devuelto.

## 7. Resultado obtenido

- Qué pasó:
- Diferencias con lo esperado:

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`):
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] No se puede crear cobro ni pedir material para la obra cancelada.
- [ ] Auditoría: `projects.cancelled` con el material afuera y la explicación.
- [ ] Una instalación ya cerrada no se cancela (`installation_closed`).

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
