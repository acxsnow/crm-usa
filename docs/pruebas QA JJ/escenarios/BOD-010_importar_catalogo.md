# [BOD-010] Importar el catálogo desde Excel

## 1. Información general

- **ID:** BOD-010
- **Módulo:** Bodega
- **Prioridad:** P1
- **Tipo de prueba:** Funcional · validación
- **Estado:** APROBADO
- **Fecha de ejecución:** 2026-10-25 (parte por API)
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 20 min de ejecución
- **Tiempo real:** lote 2 por API (≈1 min)
- **Versión o commit probado:** devjj 07e97c7 (base QA reiniciada con seed_qa)

## 2. Objetivo

La importación crea los nuevos, reconoce los existentes y reporta los errores por fila.

## 3. Precondiciones

- Sesión de `administracion@demo-org.com`.

## 4. Datos de prueba

- Un .xlsx con 3 filas: un artículo nuevo, uno existente (3496) con otro costo y una fila con costo «abc».

## 5. Procedimiento paso a paso

1. [ ] **Importar catálogo** con **Archivo del catálogo (.xlsx)** sin marcar reemplazar existencia.
2. [ ] Repetir el mismo archivo.
3. [ ] Repetir marcando reemplazar existencia.
4. [ ] Subir un PDF renombrado a .xlsx.

## 6. Resultado esperado

- 1 creado, 1 actualizado, 1 error con su número de fila.
- La segunda vez no duplica.
- Con reemplazar, la existencia se corrige con un ajuste en el libro.
- El archivo falso se rechaza.

## 7. Resultado obtenido

- Qué pasó: Por API, 7 de 7 comprobaciones bien.
- Diferencias con lo esperado: Ninguna.
- Comprobaciones por API (7 de 7):
  - ✔ Administración sube el Excel del catálogo
  - ✔ Subir el mismo Excel otra vez no suma la existencia dos veces — `{"creados": 0, "actualizados": 3, "omitidos": 0, "conteo_inicial": 0, "errores": [], "categorias_nuevas": [], "sheet": "Cat\u00e1logo", "rows_read": 3}`
  - ✔ Un archivo que no es Excel → 400 — `400 {"detail":"El archivo no es un Excel (.xlsx) válido.","code":"invalid_workbook","request_id":"768173af-d0dd-401e-ac59-25`
  - ✔ El técnico no puede importar el catálogo
  - ✔ Los tres artículos quedaron en el catálogo — `['QA1025164900-CAP', 'QA1025164900-CIN', 'QA1025164900-CU38']`
  - ✔ Existencia inicial del tubo: 200 ft — `200.00`
  - ✔ El capacitor (4, mínimo 5) cuenta como «por reponer» — `{"low_count": 2}`

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`): ver las comprobaciones de la sección 7 (script `lote2` por API).
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] Ningún 500.

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
