# [AUTH-004] Invitar un usuario, aceptar la invitación y entrar

## 1. Información general

- **ID:** AUTH-004
- **Módulo:** Acceso y sesión
- **Prioridad:** P1
- **Tipo de prueba:** Funcional
- **Estado:** APROBADO
- **Fecha de ejecución:** 2026-10-25 (parte por API)
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 15 min de ejecución
- **Tiempo real:** lote 3 por API (≈2 min)
- **Versión o commit probado:** devjj 67141f2 + D-013 (base QA reiniciada con seed_qa)

## 2. Objetivo

El Administrador da de alta personal nuevo sin tocar la base.

## 3. Precondiciones

- Sesión de `admin@demo-org.com`.

## 4. Datos de prueba

- Correo nuevo `tecnico16@demo-org.com`, nombre «Técnico Dieciséis», rol Técnico.

## 5. Procedimiento paso a paso

1. [ ] Menú **Equipo** › invitar con los datos indicados.
2. [ ] Buscar el enlace de invitación en `docker compose logs api`.
3. [ ] En otra ventana de incógnito abrir el enlace, crear la clave `ChangeMe123!`.
4. [ ] Entrar como `tecnico16@demo-org.com`.
5. [ ] Como admin, en Equipo: desactivar a «Técnico Dieciséis».
6. [ ] Intentar entrar de nuevo como `tecnico16@demo-org.com`.

## 6. Resultado esperado

- La invitación llega y crea la cuenta con el rol elegido.
- Desactivado, no puede entrar y su sesión abierta deja de funcionar.

## 7. Resultado obtenido

- Qué pasó: Lote 3 por API (25 oct, base QA reiniciada): 8 de 8 comprobaciones bien. La invitación crea la cuenta con el rol Técnico, entra y no se usa dos veces; desactivado no entra y su sesión abierta deja de funcionar.
- Diferencias con lo esperado: Ninguna.
- Comprobaciones por API (8 de 8):
  - ✔ Admin invita a «Técnico Dieciséis» como Técnico — `201 {"id":"d3b1dec2-a0f4-40e0-a395-673a76759b9a","email":"tecnico16@demo-org.com","full_name":"Técnico Dieciséis","status":"invited","roles":["field_techn`
  - ✔ Abrir la invitación y crear la clave — `200 {"id":"d3b1dec2-a0f4-40e0-a395-673a76759b9a","email":"tecnico16@demo-org.com","full_name":"Técnico Dieciséis","organization_id":"a86681e1-01d1-48b8-a9`
  - ✔ Entra como tecnico16 — `200`
  - ✔ La cuenta quedó con el rol Técnico — `['field_technician']`
  - ✔ La misma invitación no se usa dos veces — `400`
  - ✔ Admin desactiva a «Técnico Dieciséis»
  - ✔ Desactivado, no puede entrar
  - ✔ Su sesión abierta deja de funcionar [reevaluado: responde 403 «Tu cuenta no está activa» en toda acción y 401 al renovar] — `403`

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`): ver las comprobaciones de la sección 7 (script `lote3` por API).
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] El enlace vence a las 72 h (no se prueba esperando: revisar el dato en la respuesta o la base).
- [ ] Un usuario no se borra: queda inactivo y su historial se conserva.

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
- Observaciones: La sesión abierta del desactivado responde 403 «Tu cuenta no está activa. Contacta al administrador.» en toda acción y 401 al renovar (como máximo 15 min después vuelve al ingreso).
