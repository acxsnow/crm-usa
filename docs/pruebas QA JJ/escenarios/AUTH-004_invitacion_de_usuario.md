# [AUTH-004] Invitar un usuario, aceptar la invitación y entrar

## 1. Información general

- **ID:** AUTH-004
- **Módulo:** Acceso y sesión
- **Prioridad:** P1
- **Tipo de prueba:** Funcional
- **Estado:** Pendiente
- **Fecha de ejecución:**
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 15 min de ejecución
- **Tiempo real:**
- **Versión o commit probado:** main 23260ae (anotar el que se pruebe de verdad)

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

- Qué pasó:
- Diferencias con lo esperado:

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`):
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] El enlace vence a las 72 h (no se prueba esperando: revisar el dato en la respuesta o la base).
- [ ] Un usuario no se borra: queda inactivo y su historial se conserva.

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
