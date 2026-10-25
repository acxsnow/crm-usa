# [INS-011] Límite parametrizable de reagendamientos

## 1. Información general

- **ID:** INS-011
- **Módulo:** Instalación en campo
- **Prioridad:** P1
- **Tipo de prueba:** Funcional · regla de negocio
- **Estado:** En ejecución
- **Fecha de ejecución:** 2026-10-25 (parte por API)
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 30 min de ejecución
- **Tiempo real:** lote 2 por API (≈1 min)
- **Versión o commit probado:** devjj 07e97c7 (base QA reiniciada con seed_qa)

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

- Qué pasó: Por API, 14 de 14 comprobaciones bien.
- Diferencias con lo esperado: Falta la pantalla: aviso del límite, «Autorizar otro intento» y «Límite de visitas fallidas».
- Comprobaciones por API (14 de 14):
  - ✔ Segunda visita fallida
  - ✔ Llegó al límite (2 de 2) — `{'failed_visits': 2, 'limit': 2, 'limit_reached': True, 'extra_visits_authorized': 0}`
  - ✔ Liberar orden con el límite alcanzado → 409 visit_limit_reached — `409 {"detail":"La obra ya tuvo 2 visitas fallidas (límite 2). Para agendarla otra vez, autoriza otro intento o cancela la obra.","code":"visit_limit_reached","r`
  - ✔ El técnico no autoriza otro intento
  - ✔ Administración autoriza otro intento con motivo
  - ✔ El tope sube a 3 — `{'failed_visits': 2, 'limit': 3, 'limit_reached': False, 'extra_visits_authorized': 1}`
  - ✔ Ahora sí agenda
  - ✔ Límite 0 se rechaza
  - ✔ Límite 11 se rechaza
  - ✔ El técnico no cambia el límite
  - ✔ Administración (projects.close) cambia el límite a 3
  - ✔ El nuevo límite aplica de inmediato (3 + 1 autorizada = 4) — `{'failed_visits': 2, 'limit': 4, 'limit_reached': False, 'extra_visits_authorized': 1}`
  - ✔ Volver el límite a 2
  - ✔ Auditoría de intento extra y de límite

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`): ver las comprobaciones de la sección 7 (script `lote2` por API).
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

- Tiempo de ejecución: lote 2 por API (≈1 min)
- Tiempo dedicado al análisis del defecto:
- Tiempo de corrección:
- Tiempo de reejecución:
- Observaciones:
