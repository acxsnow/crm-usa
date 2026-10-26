# [AUTH-003] Olvidé mi contraseña: enlace de un solo uso, 60 minutos y 3 por hora

## 1. Información general

- **ID:** AUTH-003
- **Módulo:** Acceso y sesión
- **Prioridad:** P1
- **Tipo de prueba:** Funcional · seguridad
- **Estado:** APROBADO
- **Fecha de ejecución:** 2026-10-25 (parte por API)
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 15 min de ejecución
- **Tiempo real:** lote 3 por API (≈2 min)
- **Versión o commit probado:** devjj 67141f2 + D-013 (base QA reiniciada con seed_qa)

## 2. Objetivo

Recuperar la clave sin intervención, con un enlace que sirve una sola vez.

## 3. Precondiciones

- Correo en modo consola: el enlace aparece en `docker compose logs api` (o en el buzón si hay SMTP).

## 4. Datos de prueba

- `gerencia@demo-org.com`; clave nueva `NuevaClave123!` (mínimo 12 caracteres).

## 5. Procedimiento paso a paso

1. [ ] En el ingreso tocar **¿Olvidaste tu contraseña?** y pedirlo para `gerencia@demo-org.com`.
2. [ ] Buscar el enlace en los registros (`docker compose logs api | grep reset`).
3. [ ] Abrir el enlace, poner `NuevaClave123!` y confirmar.
4. [ ] Entrar con la clave nueva.
5. [ ] Volver a abrir el mismo enlace.
6. [ ] Pedir el enlace 4 veces seguidas para el mismo correo.
7. [ ] Dejar la clave de nuevo en `ChangeMe123!` con un enlace nuevo (al terminar la prueba).

## 6. Resultado esperado

- Entra con la clave nueva; la sesión anterior de ese usuario queda cerrada.
- El enlace usado responde que ya no es válido.
- La 4.ª solicitud en la misma hora se rechaza o no envía correo.

## 7. Resultado obtenido

- Qué pasó: Lote 3 por API (25 oct, base QA reiniciada): 9 de 9 comprobaciones bien. El enlace cambia la clave (menos de 12 caracteres se rechaza), entra con la nueva y no con la anterior, la sesión abierta queda cerrada y el mismo enlace ya no sirve; 4 pedidos seguidos crean 3 enlaces. La clave volvió a ChangeMe123! con un enlace nuevo.
- Diferencias con lo esperado: La clave del plan («Nueva12345!», 11 caracteres) no cumple el mínimo de 12: se usó «NuevaClave123!» (corregido el texto).
- Comprobaciones por API (9 de 9):
  - ✔ ¿Olvidaste tu contraseña? para gerencia responde con el mensaje genérico — `{"message":"Si hay una cuenta activa con ese correo, te enviamos un enlace para recuperar la contraseña."}`
  - ✔ Una clave de menos de 12 caracteres se rechaza — `422`
  - ✔ Abrir el enlace y poner la clave nueva — `200 {"message":"Tu contraseña se cambió."}`
  - ✔ Entra con la clave nueva
  - ✔ Con la clave anterior ya no entra
  - ✔ La sesión que estaba abierta queda cerrada — `401`
  - ✔ El mismo enlace otra vez responde que ya no es válido — `400 {"detail":"El enlace para restablecer la contraseña no es válido o ya venció.","code":"invalid_reset_token","request_id":"d5a52c83-a645-4230-a16a-0a65`
  - ✔ 4 pedidos seguidos: no se crean más de 3 enlaces en la hora [reevaluado: los 4 pedidos crearon 3 enlaces (de 1 a 4): el 1 previo era de la fase A, cuyo contador borró el script al limpiar los intentos de ingreso] — `respuestas=[200, 200, 200, 200] enlaces en la hora: 1 → 4`
  - ✔ Pedir un enlace nuevo para dejar la clave en ChangeMe123! (fase C) — `200`

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`): ver las comprobaciones de la sección 7 (script `lote3` por API).
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] Pantallas en español.
- [ ] La respuesta de «pedir enlace» es igual exista o no el correo.

## 10. Resultado final

- [x] APROBADO
- [ ] FALLIDO
- [ ] BLOQUEADO
- [ ] PENDIENTE DE CORRECCIÓN
- [ ] PENDIENTE DE REEJECUCIÓN

## 11. Defectos encontrados

| ID defecto | Descripción | Prioridad | Registrado en |
|---|---|---|---|
| | | | `01_REGISTRO_DEFECTOS.md` |

## 12. Tiempo y seguimiento

- Tiempo de ejecución: lote 3 por API (≈2 min)
- Tiempo dedicado al análisis del defecto:
- Tiempo de corrección:
- Tiempo de reejecución:
- Observaciones:
