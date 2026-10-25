# [BOD-009] Conteo físico con diferencias (ajuste)

## 1. Información general

- **ID:** BOD-009
- **Módulo:** Bodega
- **Prioridad:** P1
- **Tipo de prueba:** Funcional · auditoría
- **Estado:** Pendiente
- **Fecha de ejecución:**
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 20 min de ejecución
- **Tiempo real:**
- **Versión o commit probado:** main 23260ae (anotar el que se pruebe de verdad)

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

- Qué pasó:
- Diferencias con lo esperado:

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`):
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] El ajuste guarda quién contó y cuándo.
- [ ] El valor de la bodega cambia en lo ajustado.

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
