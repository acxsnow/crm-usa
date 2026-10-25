# [AUTH-002] Credenciales inválidas y bloqueo tras 5 intentos

## 1. Información general

- **ID:** AUTH-002
- **Módulo:** Acceso y sesión
- **Prioridad:** P1
- **Tipo de prueba:** Seguridad
- **Estado:** Pendiente
- **Fecha de ejecución:**
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 10 min de ejecución
- **Tiempo real:**
- **Versión o commit probado:** main 23260ae (anotar el que se pruebe de verdad)

## 2. Objetivo

El ingreso con clave errada no da pistas de qué está mal y se bloquea a los 5 intentos en 15 minutos.

## 3. Precondiciones

- Ningún intento fallido reciente (si hace falta: `docker compose exec redis sh -c 'redis-cli --scan --pattern "ratelimit:*" | xargs -r redis-cli del'`).

## 4. Datos de prueba

- `vendedor@demo-org.com` con clave `Errada123!`; un correo que no existe: `nadie@demo-org.com`.

## 5. Procedimiento paso a paso

1. [ ] Entrar con `nadie@demo-org.com` / `ChangeMe123!`. Anotar el mensaje.
2. [ ] Entrar con `vendedor@demo-org.com` / `Errada123!`. Anotar el mensaje y compararlo con el anterior.
3. [ ] Repetir la clave errada hasta completar 5 intentos.
4. [ ] En el 6.º intento usar la clave correcta `ChangeMe123!`.
5. [ ] Limpiar los intentos con el comando de las precondiciones y entrar con la clave correcta.

## 6. Resultado esperado

- Los dos primeros mensajes son iguales: no revelan si el correo existe.
- Tras 5 fallidos, el 6.º se rechaza aunque la clave sea correcta (bloqueo de 15 min).
- Después de limpiar, el ingreso funciona.

## 7. Resultado obtenido

- Qué pasó:
- Diferencias con lo esperado:

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`):
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] La respuesta HTTP del rechazo es 401 o 429, nunca 500.
- [ ] Auditoría (admin › Auditoría): quedan registrados los intentos fallidos o el bloqueo.

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
