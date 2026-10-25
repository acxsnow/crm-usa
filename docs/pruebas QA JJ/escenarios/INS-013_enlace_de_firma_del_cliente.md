# [INS-013] Enlace de firma del cliente: reenviar, vencido e inválido

## 1. Información general

- **ID:** INS-013
- **Módulo:** Instalación en campo
- **Prioridad:** P1
- **Tipo de prueba:** Seguridad
- **Estado:** Pendiente
- **Fecha de ejecución:**
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 15 min de ejecución
- **Tiempo real:**
- **Versión o commit probado:** main 23260ae (anotar el que se pruebe de verdad)

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

- Qué pasó:
- Diferencias con lo esperado:

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`):
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] La página pública no muestra datos de otra obra ni del técnico más allá del acta.

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
