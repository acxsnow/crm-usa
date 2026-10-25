# [AUTH-008] Quitar un permiso a un rol con usuarios conectados

## 1. Información general

- **ID:** AUTH-008
- **Módulo:** Acceso y sesión
- **Prioridad:** P2
- **Tipo de prueba:** Seguridad
- **Estado:** Pendiente
- **Fecha de ejecución:**
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 15 min de ejecución
- **Tiempo real:**
- **Versión o commit probado:** main 23260ae (anotar el que se pruebe de verdad)

## 2. Objetivo

Revocar un permiso corta el acceso en la siguiente operación, no días después.

## 3. Precondiciones

- Contabilidad con sesión abierta en Banca o Proveedores.

## 4. Datos de prueba

- Rol Contabilidad, permiso «Proveedores y pagos» (`payables.manage`).

## 5. Procedimiento paso a paso

1. [ ] Entrar como `contabilidad@demo-org.com` y abrir **Proveedores y pagos**.
2. [ ] En otra ventana, como admin, quitar `payables.manage` al rol Contabilidad.
3. [ ] Como contabilidad, recargar la pantalla y tratar de crear un proveedor.
4. [ ] Como admin, devolver el permiso.

## 6. Resultado esperado

- Tras quitar el permiso, la siguiente acción responde 403 (como máximo al renovar el token de 15 min).
- Al devolverlo vuelve a funcionar.

## 7. Resultado obtenido

- Qué pasó:
- Diferencias con lo esperado:

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`):
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] Anotar cuánto tardó en aplicarse el cambio (inmediato o al renovar).

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
