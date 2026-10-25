# [VEN-001] La puerta no abrió (sin contacto)

## 1. Información general

- **ID:** VEN-001
- **Módulo:** Venta puerta a puerta
- **Prioridad:** P1
- **Tipo de prueba:** Funcional
- **Estado:** Pendiente
- **Fecha de ejecución:**
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 10 min de ejecución
- **Tiempo real:**
- **Versión o commit probado:** main 23260ae (anotar el que se pruebe de verdad)

## 2. Objetivo

Registrar una visita sin contacto, sin pedir datos del cliente, para volver otro día.

## 3. Precondiciones

- Sesión de `vendedor@demo-org.com` (Vicky Vendedora).

## 4. Datos de prueba

- Puerta: dirección «101 QA Mobile Park Dr», espacio «Spc 1», Phoenix, AZ, 85006.

## 5. Procedimiento paso a paso

1. [ ] Menú **Mi día** › **Tocar una puerta**.
2. [ ] Escribir la dirección indicada (sin cliente).
3. [ ] Elegir el resultado **No abrió** («Volver otro día») y guardar.
4. [ ] Volver a **Mi día** y abrir **Expedientes** (activar «Mostrar puertas cerradas»).

## 6. Resultado esperado

- Se guarda sin pedir nombre, teléfono ni autorización de datos.
- El expediente queda en la etapa «Sin contacto» y no aparece en el tablero hasta mostrar las puertas cerradas.

## 7. Resultado obtenido

- Qué pasó:
- Diferencias con lo esperado:

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`):
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] En la base: `cases` con `stage_code = no_contact` y sin `customer_id`.
- [ ] Historial de etapas con una entrada inicial (quién, cuándo).

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
