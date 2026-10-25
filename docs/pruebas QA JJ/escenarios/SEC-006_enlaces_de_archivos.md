# [SEC-006] Enlaces directos a archivos de otros

## 1. Información general

- **ID:** SEC-006
- **Módulo:** Seguridad
- **Prioridad:** P0
- **Tipo de prueba:** Seguridad
- **Estado:** Pendiente
- **Fecha de ejecución:**
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 15 min de ejecución
- **Tiempo real:**
- **Versión o commit probado:** main 23260ae (anotar el que se pruebe de verdad)

## 2. Objetivo

Un archivo no se descarga solo con conocer su dirección.

## 3. Precondiciones

- Una foto de una obra de Carlos.

## 4. Datos de prueba

- La URL de descarga de esa foto.

## 5. Procedimiento paso a paso

1. [ ] Abrirla sin sesión.
2. [ ] Abrirla como Luis.
3. [ ] Abrirla como admin ajeno.

## 6. Resultado esperado

- Sin sesión: 401; Luis y ajeno: 404.

## 7. Resultado obtenido

- Qué pasó:
- Diferencias con lo esperado:

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`):
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] Si la URL es firmada, anotar cuánto dura.

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
