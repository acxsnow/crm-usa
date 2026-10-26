# [INS-013] Enlace de firma del cliente: reenviar, vencido e inválido

## 1. Información general

- **ID:** INS-013
- **Módulo:** Instalación en campo
- **Prioridad:** P1
- **Tipo de prueba:** Seguridad
- **Estado:** APROBADO
- **Fecha de ejecución:** 2026-10-25 (parte por API)
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 15 min de ejecución
- **Tiempo real:** lote 3 por API
- **Versión o commit probado:** devjj 67141f2 + D-013, D-015 a D-018 (base QA reiniciada con seed_qa)

## 2. Objetivo

El enlace público de firma solo sirve para su acta, una vez.

## 3. Precondiciones

- Una obra con la instalación cerrada y la firma del cliente pendiente.

## 4. Datos de prueba

- El enlace enviado (registros de la API).

## 5. Procedimiento paso a paso

1. [ ] **Reenviar enlace** y comprobar que el anterior deja de servir (o anotar si sigue sirviendo).
2. [ ] Cambiar un carácter del token en la URL y abrirla.
3. [ ] Abrir el enlace sin el token.

## 6. Resultado esperado

- Token alterado: «Este enlace de firma no es válido.»; sin token: «Enlace incompleto».

## 7. Resultado obtenido

- Qué pasó: Lote 3 por API (25 oct, base QA reiniciada): 10 de 10 comprobaciones bien. Al reenviar el enlace, el anterior deja de servir; el token alterado responde «El enlace no es válido o ya expiró.»; sin token se rechaza; el cliente firma con el vigente y el mismo enlace no sirve otra vez.
- Diferencias con lo esperado: Sin token la API responde «El enlace no es válido o ya expiró.»; el «Enlace incompleto» es de la pantalla.
- Comprobaciones por API (10 de 10):
  - ✔ El técnico envía el enlace de firma (vez 1) — `200 {"status":"sent","recipient_email":"qa.1025212450.363@example.com","expires_at":"2026-10-28T21:42:32.752626Z"}`
  - ✔ El técnico envía el enlace de firma (vez 2) — `200 {"status":"sent","recipient_email":"qa.1025212450.363@example.com","expires_at":"2026-10-28T21:42:32.926991Z"}`
  - ✔ Administración (sin evidence.create) no lo envía (403; anotar) — `{"detail":"No tienes permiso para realizar esta acción.","code":"http_403","request_id":"737a0325-6fcf-4d32-b209-d0a6b1f`
  - ✔ Se enviaron 2 enlaces de firma (el segundo es el reenvío) — `2`
  - ✔ Al reenviar, el enlace anterior deja de servir — `404 {"detail":"El enlace no es válido o ya expiró.","code":"public_signature_not_found","request_id":"404000dc-6268-4de7-8470-39e6d5991551"}`
  - ✔ El enlace vigente abre el acta — `200`
  - ✔ Token alterado: «El enlace no es válido o ya expiró.» — `404 {"detail":"El enlace no es válido o ya expiró.","code":"public_signature_not_found","request_id":"68b03d41-49ed-4a1b-bce1-046802f5b42f"}`
  - ✔ Sin token: se rechaza (la pantalla dice «Enlace incompleto») — `404 {"detail":"El enlace no es válido o ya expiró.","code":"public_signature_token_missing","request_id":"e3602b59-e4e7-46c7-90d7-5cc4e5464668"}`
  - ✔ El cliente firma con el enlace vigente — `200 {"id":"f8c50ad7-0b47-42ec-9e61-42454c1da435","project_id":"3bef2257-ecde-4305-99e3-25e6fd5b6e16","technician_user_id":null,"technician_signed_at":null`
  - ✔ El mismo enlace no sirve para firmar otra vez — `404 {"detail":"El enlace no es válido o ya expiró.","code":"public_signature_not_found","request_id":"108fe8d5-5165-4963-86a4-b761a4baac74"}`

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`): ver las comprobaciones de la sección 7 (script `lote3` por API).
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] La página pública no muestra datos de otra obra ni del técnico más allá del acta.

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

- Tiempo de ejecución: lote 3 por API
- Tiempo dedicado al análisis del defecto:
- Tiempo de corrección:
- Tiempo de reejecución:
- Observaciones: El enlace lo envía quien llena la obra (técnico o Administrador, permiso `evidence.create`); Administración recibe 403.
