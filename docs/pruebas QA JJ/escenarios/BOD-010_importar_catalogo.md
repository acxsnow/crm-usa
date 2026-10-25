# [BOD-010] Importar el catálogo desde Excel

## 1. Información general

- **ID:** BOD-010
- **Módulo:** Bodega
- **Prioridad:** P1
- **Tipo de prueba:** Funcional · validación
- **Estado:** Pendiente
- **Fecha de ejecución:**
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 20 min de ejecución
- **Tiempo real:**
- **Versión o commit probado:** main 23260ae (anotar el que se pruebe de verdad)

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

- Qué pasó:
- Diferencias con lo esperado:

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`):
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] Ningún 500.

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
