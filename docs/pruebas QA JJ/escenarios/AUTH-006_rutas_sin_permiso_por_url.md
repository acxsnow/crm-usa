# [AUTH-006] Escribir a mano la dirección de una pantalla sin permiso

## 1. Información general

- **ID:** AUTH-006
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

Que esconder el menú no sea la única barrera: la pantalla y su API rechazan al rol equivocado.

## 3. Precondiciones

- Sesiones de vendedor y técnico.

## 4. Datos de prueba

- Rutas: /banking, /payables, /users, /roles, /audit-log, /warehouse, /invoices, /attendance, /payroll.

## 5. Procedimiento paso a paso

1. [ ] Como vendedor, escribir cada ruta de la lista en la barra del navegador.
2. [ ] Como técnico, repetir.
3. [ ] Con F12 abierto, mirar qué responde la API en cada intento.

## 6. Resultado esperado

- Cada ruta sin permiso lleva al Inicio (o muestra «sin acceso») sin mostrar datos.
- Las llamadas a la API de esas pantallas responden 403.

## 7. Resultado obtenido

- Qué pasó:
- Diferencias con lo esperado:

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`):
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] Ningún 500.
- [ ] Ningún dato de la pantalla alcanza a verse antes de redirigir.

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
