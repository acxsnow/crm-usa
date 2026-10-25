# [BOD-001] La carga inicial cuadra con los PDF de AC Pro

## 1. Información general

- **ID:** BOD-001
- **Módulo:** Bodega
- **Prioridad:** P0
- **Tipo de prueba:** Datos · integridad
- **Estado:** Pendiente
- **Fecha de ejecución:**
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 20 min de ejecución
- **Tiempo real:**
- **Versión o commit probado:** main 23260ae (anotar el que se pruebe de verdad)

## 2. Objetivo

El inventario de arranque es el de los PDF: si no cuadra, todas las pruebas de bodega parten mal.

## 3. Precondiciones

- Base en el estado inicial de QA (245 artículos, 648 unidades, USD 13,209.22 en bodega).
- Sesión de `administracion@demo-org.com`.

## 4. Datos de prueba

- `backend/scripts/qa_data/catalogo_ac_pro.csv` y `docs/bodega/partes.pdf` / `bodega.pdf`.

## 5. Procedimiento paso a paso

1. [ ] Menú **Bodega**: anotar Artículos activos, unidades y valor del resumen.
2. [ ] Buscar 5 artículos del PDF por su código AC Pro (por ejemplo 85980, 3496, 1578, 27948, 61052) y comparar cantidad y costo.
3. [ ] Abrir **Movimientos de bodega** y filtrar por uno de ellos.

## 6. Resultado esperado

- Resumen: 245 artículos (244 de AC Pro + ninguno ajeno visible), 648 unidades y USD 13,209.22.
- Cada artículo revisado coincide con el PDF; los repetidos suman sus cantidades.
- Cada uno tiene un solo movimiento de conteo inicial.

## 7. Resultado obtenido

- Qué pasó:
- Diferencias con lo esperado:

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`):
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] El «Artículo Ajeno QA» de la otra organización NO aparece.

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
