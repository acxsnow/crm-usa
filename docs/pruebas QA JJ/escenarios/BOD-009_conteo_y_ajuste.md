# [BOD-009] Conteo físico con diferencias (ajuste)

## 1. Información general

- **ID:** BOD-009
- **Módulo:** Bodega
- **Prioridad:** P1
- **Tipo de prueba:** Funcional · auditoría
- **Estado:** APROBADO
- **Fecha de ejecución:** 2026-10-25 (parte por API)
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 20 min de ejecución
- **Tiempo real:** lote 2 por API (≈1 min)
- **Versión o commit probado:** devjj 07e97c7 (base QA reiniciada con seed_qa)

## 2. Objetivo

El conteo del fin de semana corrige la existencia con un ajuste trazable.

## 3. Precondiciones

- Sesión de `administracion@demo-org.com`.

## 4. Datos de prueba

- Contar 3 artículos: uno igual, uno con 2 menos y uno con 1 más.

## 5. Procedimiento paso a paso

1. [ ] Registrar el conteo de los 3.
2. [ ] Ver la existencia y el libro.

## 6. Resultado esperado

- Solo los 2 con diferencia generan `ajuste`, con la diferencia exacta.

## 7. Resultado obtenido

- Qué pasó: Por API, 4 de 4 comprobaciones bien.
- Diferencias con lo esperado: Ninguna.
- Comprobaciones por API (4 de 4):
  - ✔ Carga 3 artículos y su conteo inicial; la fila de ejemplo no entra — `{"creados": 3, "actualizados": 0, "omitidos": 0, "conteo_inicial": 3, "errores": [], "categorias_nuevas": [], "sheet": "Cat\u00e1logo", "rows_read": 3}`
  - ✔ Conteo mensual: la cinta tenía 28, no 30
  - ✔ El conteo cuadra el saldo con un ajuste
  - ✔ El ajuste queda en el libro de movimientos — `[{"id": "2c5cac0b-5926-4361-898a-f259581a0290", "item_id": "5f7f025f-71e2-44d3-8a4a-01d237d08b89", "item_name": "QA 1025164900 Cinta de aluminio", "un`

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`): ver las comprobaciones de la sección 7 (script `lote2` por API).
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] El ajuste guarda quién contó y cuándo.
- [ ] El valor de la bodega cambia en lo ajustado.

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
