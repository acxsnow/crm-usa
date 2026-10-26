# [AUTH-002] Credenciales inválidas y bloqueo tras 5 intentos

## 1. Información general

- **ID:** AUTH-002
- **Módulo:** Acceso y sesión
- **Prioridad:** P1
- **Tipo de prueba:** Seguridad
- **Estado:** APROBADO
- **Fecha de ejecución:** 2026-10-25 (parte por API)
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 10 min de ejecución
- **Tiempo real:** 1 min (API)
- **Versión o commit probado:** devjj deee0d8 (base QA de seed_qa)

## 2. Objetivo

El ingreso con clave errada no da pistas de qué está mal y se bloquea a los 5 intentos en 15 minutos.

## 3. Precondiciones

- Ningún intento fallido reciente (si hace falta: `docker compose exec redis sh -c 'redis-cli --scan --pattern "ratelimit:*" | xargs -r redis-cli del'`).

## 4. Datos de prueba

- `vendedor@demo-org.com` con clave `Errada123!`; un correo que no existe: `nadie@demo-org.com`.

## 5. Procedimiento paso a paso

1. [x] Entrar con `nadie@demo-org.com` / `ChangeMe123!`. Anotar el mensaje.
2. [x] Entrar con `vendedor@demo-org.com` / `Errada123!`. Anotar el mensaje y compararlo con el anterior.
3. [x] Repetir la clave errada hasta completar 5 intentos.
4. [x] En el 6.º intento usar la clave correcta `ChangeMe123!`.
5. [x] Limpiar los intentos con el comando de las precondiciones y entrar con la clave correcta.

## 6. Resultado esperado

- Los dos primeros mensajes son iguales: no revelan si el correo existe.
- Tras 5 fallidos, el 6.º se rechaza aunque la clave sea correcta (bloqueo de 15 min).
- Después de limpiar, el ingreso funciona.

## 7. Resultado obtenido

- Qué pasó: El correo inexistente y la clave errada responden igual (401, mismo mensaje). Tras 5 fallidos, el 6.º con la clave correcta da 429; al limpiar los contadores entra.
- Diferencias con lo esperado: 1) La API responde en inglés («Invalid email or password.», «Too many attempts. Try again later.») y la pantalla de ingreso muestra siempre «El correo o la contraseña no son correctos», también cuando la cuenta quedó bloqueada: quien está bloqueado cree que la clave está mal y sigue intentando. 2) La auditoría no registra intentos fallidos ni bloqueos (solo `auth.login.success`).
- Reejecución (25 oct, tras corregir los P2 y D-007, base QA reiniciada): 5 de 5. Los mensajes salen en español (401 «El correo o la contraseña no son correctos.», 429 «Demasiados intentos de ingreso. Espera 15 minutos…») y la auditoría tiene `auth.login.failed` y `auth.login.locked` (D-005 y D-006). Falta ver en pantalla que el bloqueo se muestra con su propio mensaje (D-005).
- Comprobaciones por API (3 de 5):
  - ✔ correo inexistente y clave errada: mismo código y mismo mensaje (solo cambia request_id) — `401 {'detail': 'Invalid email or password.', 'code': 'http_401', 'request_id': '0fe3c9f6-36aa-40df-bd66-c21c79c3e0a9'} | 401 {'detail': 'Invalid email or passwo`
  - ✔ 5 fallidos y el 6.º con la clave correcta se rechaza — `intentos=[401, 401, 401, 401, 401] sexto=429 {"detail":"Too many attempts. Try again later.","code":"http_429","request_id":"d75c6313-b21b-4d03-9f0d-081287021cd`
  - ✘ el mensaje del bloqueo está en español — `{"detail":"Too many attempts. Try again later.","code":"http_429","request_id":"d75c6313-b21b-4d03-9f0d-081287021cd9"}`
  - ✔ después de limpiar los contadores entra — `200`
  - ✘ auditoría registra los intentos fallidos o el bloqueo — `audit_events solo tiene auth.login.success (26); ningún fallido ni bloqueo`


### Pantalla (probado por Claude, 2026-10-25, Playwright)

- Con la clave errada la pantalla dice «El correo o la contraseña no son correctos.»; al sexto intento, «Demasiados intentos de ingreso. Espera 15 minutos e inténtalo de nuevo, o recupera tu contraseña.» (D-005).
- Comprobaciones (2 de 2):
  - ✔ Con la clave errada: «El correo o la contraseña no son correctos.» — `P
PAP CRM
Iniciar sesión
Correo
Contraseña

El correo o la contraseña no son correctos.

Entrar
¿Olvidaste tu contraseña?`
  - ✔ Al sexto intento la pantalla dice que la cuenta está bloqueada (no «clave errada») — `P
PAP CRM
Iniciar sesión
Correo
Contraseña

Demasiados intentos de ingreso. Espera 15 minutos e inténtalo de nuevo, o recupera tu contraseña`
- Capturas:
  - [bloqueo.jpg](../evidencias/pantalla/AUTH-002/bloqueo.jpg)
- Pendiente: revisión de José en su propio equipo.

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`): ver las comprobaciones de la sección 7 (script `lote1` por API).
- Consultas de verificación: `select action, count(*) from audit_events where action ilike '%login%'` → solo auth.login.success.

## 9. Validaciones complementarias

- [x] La respuesta HTTP del rechazo es 401 o 429, nunca 500.
- [ ] Auditoría (admin › Auditoría): quedan registrados los intentos fallidos o el bloqueo.

## 10. Resultado final

- [x] APROBADO
- [ ] FALLIDO
- [ ] BLOQUEADO
- [ ] PENDIENTE DE CORRECCIÓN
- [ ] PENDIENTE DE REEJECUCIÓN

## 11. Defectos encontrados

| ID defecto | Descripción | Prioridad | Registrado en |
|---|---|---|---|
| D-005 | Ingreso: mensajes de la API en inglés y la pantalla no distingue el bloqueo | P2 | `01_REGISTRO_DEFECTOS.md` |
| D-006 | Los intentos fallidos y los bloqueos de ingreso no quedan en la auditoría | P2 | `01_REGISTRO_DEFECTOS.md` |

## 12. Tiempo y seguimiento

- Tiempo de ejecución: 1 min (API)
- Tiempo dedicado al análisis del defecto:
- Tiempo de corrección:
- Tiempo de reejecución:
- Observaciones:
