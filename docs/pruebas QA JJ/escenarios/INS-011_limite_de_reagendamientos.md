# [INS-011] Límite parametrizable de reagendamientos

## 1. Información general

- **ID:** INS-011
- **Módulo:** Instalación en campo
- **Prioridad:** P1
- **Tipo de prueba:** Funcional · regla de negocio
- **Estado:** Pendiente
- **Fecha de ejecución:**
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 30 min de ejecución
- **Tiempo real:**
- **Versión o commit probado:** main 23260ae (anotar el que se pruebe de verdad)

## 2. Objetivo

Al llegar al límite de la organización (2 por defecto) ya no se agenda: Administración autoriza otro intento con motivo o cancela la obra. El límite se cambia en pantalla.

## 3. Precondiciones

- INS-010 hecho (1 de 2) y la obra reagendada.

## 4. Datos de prueba

- Motivo del intento extra: «El cliente llamó y confirmó que estará».

## 5. Procedimiento paso a paso

1. [ ] Como Carlos, registrar una segunda visita fallida.
2. [ ] Leer el aviso de la sección Visitas fallidas y el de la campana de administración («Llegó al límite…»).
3. [ ] Como administración, intentar **Liberar orden**: anotar el mensaje.
4. [ ] Como Carlos, buscar el botón **Autorizar otro intento** (no debe tenerlo).
5. [ ] Como administración, **Autorizar otro intento** con el motivo y luego **Liberar orden**.
6. [ ] En **Cancelar la obra…** › **Límite de visitas fallidas (todas las obras)**: probar 0 y 11, luego guardar 3.
7. [ ] Registrar otra visita fallida y comprobar el nuevo tope.

## 6. Resultado esperado

- Con el límite alcanzado, agendar responde «La obra ya tuvo 2 visitas fallidas (límite 2)…».
- Autorizar otro intento sube el tope a 3 y permite agendar.
- 0 y 11 se rechazan; 3 se guarda y aplica de inmediato a todas las obras.

## 7. Resultado obtenido

- Qué pasó:
- Diferencias con lo esperado:

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`):
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] Solo quien tiene `projects.close` (Administrador y Administración) cambia el límite; `dispatch.manage` autoriza intentos.
- [ ] Auditoría: `projects.extra_visit_authorized` y `field_ops.settings_updated` con el valor anterior y el nuevo.

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
