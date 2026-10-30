# [VEN-001] La puerta no abrió (sin contacto)

## 1. Información general

- **ID:** VEN-001
- **Módulo:** Venta puerta a puerta
- **Prioridad:** P1
- **Tipo de prueba:** Funcional
- **Estado:** APROBADO
- **Fecha de ejecución:** 2026-10-25 (parte por API)
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 10 min de ejecución
- **Tiempo real:** lote 2 por API (≈1 min)
- **Versión o commit probado:** devjj 07e97c7 (base QA reiniciada con seed_qa)

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

- Qué pasó: Por API, 4 de 4 comprobaciones bien.
- Diferencias con lo esperado: Falta ver en pantalla que no aparece en el tablero hasta «Mostrar puertas cerradas».
- Comprobaciones por API (4 de 4):
  - ✔ Visita «no_contact» en 201 QA 1025164900 Mobile Park Dr
  - ✔ Queda en «Sin contacto» — `no_contact`
  - ✔ No pide ni crea cliente — `None`
  - ✔ El historial de etapas tiene la entrada inicial — `1`


### Pantalla (probado por Claude, 2026-10-25, Playwright)

- Las puertas cerradas no salen en el tablero del vendedor hasta activar «Mostrar puertas cerradas»; con el filtro aparecen.
- Comprobaciones (2 de 2):
  - ✔ Las puertas cerradas no salen en el tablero sin activar el filtro
  - ✔ Con «Mostrar puertas cerradas» aparecen — `P
PAP.CRM
Inicio
OPERACIÓN COMERCIAL
Clientes
Mi día
Expedientes
TURNOS Y ASISTENCIA
Mi turno
FINANZAS
Gastos de campo
ADMINISTRACIÓN
Notifi`
- Capturas:
  - [puertas-cerradas.jpg](../evidencias/pantalla/VEN-001/puertas-cerradas.jpg)
- Pendiente: revisión de José en su propio equipo.

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`): ver las comprobaciones de la sección 7 (script `lote2` por API).
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] En la base: `cases` con `stage_code = no_contact` y sin `customer_id`.
- [ ] Historial de etapas con una entrada inicial (quién, cuándo).

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

- Tiempo de ejecución: lote 2 por API (≈1 min)
- Tiempo dedicado al análisis del defecto:
- Tiempo de corrección:
- Tiempo de reejecución:
- Observaciones:
