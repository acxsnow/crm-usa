# [SEC-002] API sin token, con token vencido o alterado

## 1. Información general

- **ID:** SEC-002
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

Ninguna ruta privada responde sin una sesión válida.

## 3. Precondiciones

- Token de cada usuario (F12 › Network › cabecera Authorization) y una herramienta para llamar la API (Postman, curl o la consola del navegador con `fetch`).

## 4. Datos de prueba

- `http://localhost:8000/api/v1/cases`, `/customers`, `/warehouse/stock`, `/invoices`.

## 5. Procedimiento paso a paso

1. [ ] Llamar cada una sin cabecera.
2. [ ] Con un token con un carácter cambiado.
3. [ ] Con un token de hace más de 15 minutos.
4. [ ] Con el token de refresco en lugar del de acceso.

## 6. Resultado esperado

- 401 en todos los casos, sin datos.

## 7. Resultado obtenido

- Qué pasó:
- Diferencias con lo esperado:

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`):
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] El mensaje de error no revela detalles internos (sin trazas).

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
