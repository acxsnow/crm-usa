# [AUTH-007] Rol nuevo sin permisos marcados

## 1. Información general

- **ID:** AUTH-007
- **Módulo:** Acceso y sesión
- **Prioridad:** P1
- **Tipo de prueba:** Seguridad
- **Estado:** Pendiente
- **Fecha de ejecución:**
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 15 min de ejecución
- **Tiempo real:**
- **Versión o commit probado:** main 23260ae (anotar el que se pruebe de verdad)

## 2. Objetivo

Un rol recién creado no abre nada hasta que se le den permisos.

## 3. Precondiciones

- Sesión de admin.

## 4. Datos de prueba

- Rol «QA sin permisos»; usuario invitado `sinrol@demo-org.com`.

## 5. Procedimiento paso a paso

1. [ ] Menú **Roles y permisos**: crear el rol «QA sin permisos» sin marcar nada.
2. [ ] Invitar a `sinrol@demo-org.com` con ese rol y aceptar la invitación (como en AUTH-004).
3. [ ] Entrar como `sinrol@demo-org.com` y recorrer el menú.
4. [ ] Escribir a mano /cases, /projects y /invoices.
5. [ ] Como admin, darle al rol solo «Ver clientes» y volver a entrar.

## 6. Resultado esperado

- Sin permisos solo ve el Inicio vacío; todo lo demás responde 403.
- Con «Ver clientes» aparece solo Clientes.

## 7. Resultado obtenido

- Qué pasó:
- Diferencias con lo esperado:

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`):
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] El cambio de permisos se refleja al volver a entrar, sin reiniciar nada.
- [ ] Auditoría registra la creación del rol y el cambio de permisos.

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
