# [INS-011] Límite parametrizable de reagendamientos

## 1. Información general

- **ID:** INS-011
- **Módulo:** Instalación en campo
- **Prioridad:** P1
- **Tipo de prueba:** Funcional · regla de negocio
- **Estado:** Bloqueado (D-001)
- **Fecha de ejecución:**
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 30 min de ejecución
- **Tiempo real:**
- **Versión o commit probado:** main 23260ae (anotar el que se pruebe de verdad)

## 2. Objetivo

Al llegar al límite configurado ya no se reagenda sola: pasa a decisión de Administración (cancelar o autorizar un intento más).

## 3. Precondiciones

- D-001 implementado.
- Límite configurado en 2.

## 4. Datos de prueba

- La obra de INS-010.

## 5. Procedimiento paso a paso

1. [ ] Reagendar y registrar una segunda visita fallida.
2. [ ] Intentar reagendar una tercera vez como técnico y como administración.
3. [ ] Cambiar el límite a 3 y volver a intentar.

## 6. Resultado esperado

- Con el límite alcanzado el sistema lo bloquea y avisa a Administración.
- El cambio de límite aplica sin reiniciar.

## 7. Resultado obtenido

- Qué pasó:
- Diferencias con lo esperado:

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`):
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] Solo el Administrador cambia el límite.
- [ ] Cada intento queda en el historial.

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
