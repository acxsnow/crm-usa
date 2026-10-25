# [SEC-004] Inyección SQL y XSS en formularios y filtros

## 1. Información general

- **ID:** SEC-004
- **Módulo:** Seguridad
- **Prioridad:** P0
- **Tipo de prueba:** Seguridad
- **Estado:** Pendiente
- **Fecha de ejecución:**
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 25 min de ejecución
- **Tiempo real:**
- **Versión o commit probado:** main 23260ae (anotar el que se pruebe de verdad)

## 2. Objetivo

Lo que escribe el usuario nunca se ejecuta ni en la base ni en el navegador.

## 3. Precondiciones

- Sesión de admin.

## 4. Datos de prueba

- `' OR '1'='1`, `1; DROP TABLE cases; --`, `<img src=x onerror=alert(1)>`, `{{7*7}}`.

## 5. Procedimiento paso a paso

1. [ ] Ponerlos en: nombre de cliente, notas de obra, motivo de rechazo, filtro `q` de listas y nombre de artículo.
2. [ ] Abrir cada pantalla donde se muestran y el PDF del acta.

## 6. Resultado esperado

- Se guardan y se muestran como texto; ninguna alerta; ninguna consulta alterada.

## 7. Resultado obtenido

- Qué pasó:
- Diferencias con lo esperado:

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`):
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] La tabla `cases` sigue existiendo :)
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
