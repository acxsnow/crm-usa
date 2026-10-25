# [NOT-002] Correos y SMS en modo de prueba

## 1. Información general

- **ID:** NOT-002
- **Módulo:** Notificaciones y buscador
- **Prioridad:** P2
- **Tipo de prueba:** Integración
- **Estado:** Pendiente
- **Fecha de ejecución:**
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 10 min de ejecución
- **Tiempo real:**
- **Versión o commit probado:** main 23260ae (anotar el que se pruebe de verdad)

## 2. Objetivo

Sin SMTP real ni SMS Masiv, los mensajes salen a la consola sin romper el flujo.

## 3. Precondiciones

- Correo en modo consola.

## 4. Datos de prueba

- Un olvido de clave y un enlace de firma.

## 5. Procedimiento paso a paso

1. [ ] Disparar los dos.
2. [ ] Revisar `docker compose logs api worker`.

## 6. Resultado esperado

- Aparecen en los registros; la pantalla dice que se envió.

## 7. Resultado obtenido

- Qué pasó:
- Diferencias con lo esperado:

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`):
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] SMS Masiv sigue por verificar (módulo 7): anotarlo como fuera de alcance.

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
