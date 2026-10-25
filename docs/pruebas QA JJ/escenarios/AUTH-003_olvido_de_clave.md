# [AUTH-003] Olvidé mi contraseña: enlace de un solo uso, 60 minutos y 3 por hora

## 1. Información general

- **ID:** AUTH-003
- **Módulo:** Acceso y sesión
- **Prioridad:** P1
- **Tipo de prueba:** Funcional · seguridad
- **Estado:** Pendiente
- **Fecha de ejecución:**
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 15 min de ejecución
- **Tiempo real:**
- **Versión o commit probado:** main 23260ae (anotar el que se pruebe de verdad)

## 2. Objetivo

Recuperar la clave sin intervención, con un enlace que sirve una sola vez.

## 3. Precondiciones

- Correo en modo consola: el enlace aparece en `docker compose logs api` (o en el buzón si hay SMTP).

## 4. Datos de prueba

- `gerencia@demo-org.com`; clave nueva `Nueva12345!`.

## 5. Procedimiento paso a paso

1. [ ] En el ingreso tocar **¿Olvidaste tu contraseña?** y pedirlo para `gerencia@demo-org.com`.
2. [ ] Buscar el enlace en los registros (`docker compose logs api | grep reset`).
3. [ ] Abrir el enlace, poner `Nueva12345!` y confirmar.
4. [ ] Entrar con la clave nueva.
5. [ ] Volver a abrir el mismo enlace.
6. [ ] Pedir el enlace 4 veces seguidas para el mismo correo.
7. [ ] Dejar la clave de nuevo en `ChangeMe123!` con un enlace nuevo (al terminar la prueba).

## 6. Resultado esperado

- Entra con la clave nueva; la sesión anterior de ese usuario queda cerrada.
- El enlace usado responde que ya no es válido.
- La 4.ª solicitud en la misma hora se rechaza o no envía correo.

## 7. Resultado obtenido

- Qué pasó:
- Diferencias con lo esperado:

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`):
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] Pantallas en español.
- [ ] La respuesta de «pedir enlace» es igual exista o no el correo.

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
