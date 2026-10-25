# [PAR-001] Cotización particular: armar, enviar y aceptar

## 1. Información general

- **ID:** PAR-001
- **Módulo:** Trabajo particular y facturación
- **Prioridad:** P1
- **Tipo de prueba:** Funcional
- **Estado:** Pendiente
- **Fecha de ejecución:**
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 20 min de ejecución
- **Tiempo real:**
- **Versión o commit probado:** main 23260ae (anotar el que se pruebe de verdad)

## 2. Objetivo

El trabajo particular se cotiza desde el price book sin tocar ningún expediente.

## 3. Precondiciones

- Sesión de `contabilidad@demo-org.com`.
- Un cliente particular creado en **Clientes** (con su autorización de datos).

## 4. Datos de prueba

- Cliente «QA Particular Gómez»; 2 renglones del price book y 1 libre (USD 120.00).

## 5. Procedimiento paso a paso

1. [ ] **Cotizaciones** › **Armar la cotización** con los renglones.
2. [ ] Enviarla al cliente.
3. [ ] Marcarla aceptada.
4. [ ] Crear otra y marcarla «No aceptada».

## 6. Resultado esperado

- Totales correctos con el impuesto que aplique.
- Los estados cambian a Aceptadas / No aceptada.

## 7. Resultado obtenido

- Qué pasó:
- Diferencias con lo esperado:

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`):
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] Ningún expediente cambió de etapa (`case_stage_events` sin filas nuevas).

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
