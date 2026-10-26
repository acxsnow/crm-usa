# [NOT-002] Correos y SMS en modo de prueba

## 1. Información general

- **ID:** NOT-002
- **Módulo:** Notificaciones y buscador
- **Prioridad:** P2
- **Tipo de prueba:** Integración
- **Estado:** APROBADO
- **Fecha de ejecución:** 2026-10-25 (parte por API)
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 10 min de ejecución
- **Tiempo real:** lote 3 por API
- **Versión o commit probado:** devjj 67141f2 + D-013, D-015 a D-018 (base QA reiniciada con seed_qa)

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

- Qué pasó: Lote 3 por API (25 oct, base QA reiniciada): 3 de 3 comprobaciones bien. El olvido de clave y los enlaces de firma salen a la consola del api (EMAIL_PROVIDER=console) y la API responde que se envió.
- Diferencias con lo esperado: Ninguna.
- Comprobaciones por API (3 de 3):
  - ✔ Pedir el olvido de clave responde que se envió — `{"message":"Si hay una cuenta activa con ese correo, te enviamos un enlace para recuperar la contraseña."}`
  - ✔ El olvido de clave salió a la consola (1 correos) — `1`
  - ✔ El enlace de firma salió a la consola (2 correos) — `2`

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`): ver las comprobaciones de la sección 7 (script `lote3` por API).
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] SMS Masiv sigue por verificar (módulo 7): anotarlo como fuera de alcance.

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
- Observaciones:
