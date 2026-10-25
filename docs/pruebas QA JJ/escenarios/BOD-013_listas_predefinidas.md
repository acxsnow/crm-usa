# [BOD-013] Crear, editar y borrar listas predefinidas

## 1. Información general

- **ID:** BOD-013
- **Módulo:** Bodega
- **Prioridad:** P2
- **Tipo de prueba:** Funcional
- **Estado:** Pendiente
- **Fecha de ejecución:**
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 15 min de ejecución
- **Tiempo real:**
- **Versión o commit probado:** main 23260ae (anotar el que se pruebe de verdad)

## 2. Objetivo

Las listas se mantienen sin afectar las órdenes que ya las usaron.

## 3. Precondiciones

- Sesión de `administracion@demo-org.com`.

## 4. Datos de prueba

- Lista «Mantenimiento QA» con 3 renglones.

## 5. Procedimiento paso a paso

1. [ ] **Nueva lista predefinida** con secciones y obligatorios.
2. [ ] Usarla en una salida.
3. [ ] Editar la lista (quitar un renglón) y abrir la salida anterior.
4. [ ] Borrarla.

## 6. Resultado esperado

- Las órdenes que ya la usaron no cambian.

## 7. Resultado obtenido

- Qué pasó:
- Diferencias con lo esperado:

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`):
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] La lista «3 ton desde cero» sigue con 46 renglones.

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
