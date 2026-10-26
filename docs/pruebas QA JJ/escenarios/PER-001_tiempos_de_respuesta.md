# [PER-001] Tiempos de respuesta de las pantallas principales

## 1. Información general

- **ID:** PER-001
- **Módulo:** Rendimiento
- **Prioridad:** P1
- **Tipo de prueba:** Rendimiento
- **Estado:** En ejecución
- **Fecha de ejecución:** 2026-10-25 (parte por API)
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 30 min de ejecución
- **Tiempo real:** lote 3 por API
- **Versión o commit probado:** devjj 67141f2 + D-013, D-015 a D-018 (base QA del lote 3)

## 2. Objetivo

Medir y dejar la línea base de las APIs más usadas.

## 3. Precondiciones

- Datos de varias pruebas cargados (al final del ciclo).
- F12 › Network sin caché.

## 4. Datos de prueba

- Inicio, Mi día, Expedientes, Por revisar, Proyectos, Agenda, Existencias, Salidas, Facturas, Mapa.

## 5. Procedimiento paso a paso

1. [ ] Abrir cada pantalla 3 veces.
2. [ ] Anotar el tiempo de la llamada más lenta y el total.

## 6. Resultado esperado

- Cada llamada < 500 ms en local; ninguna pantalla > 2 s.

## 7. Resultado obtenido

- Qué pasó: Lote 3 por API (25 oct): 1 de 1 comprobaciones bien. Inicio, expedientes, por revisar, proyectos, agenda, existencias, salidas, facturas, mapa, avisos y buscador: cada llamada responde en menos de 500 ms (3 veces cada una, en local, con la base QA).
- Diferencias con lo esperado: Falta medir el total de cada pantalla en el navegador (F12 › Network).
- Comprobaciones por API (1 de 1):
  - ✔ Cada llamada responde en menos de 500 ms (3 veces cada una, en local) — `{"Inicio": [131, 200], "Expedientes": [186, 200], "Por revisar": [127, 200], "Proyectos": [95, 200], "Agenda": [166, 200], "Existencias": [217, 200], "Salidas":`

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`): ver las comprobaciones de la sección 7 (script `lote3` por API).
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] Anotar el número de llamadas por pantalla (más de 10 es señal de N+1).

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

- Tiempo de ejecución: lote 3 por API
- Tiempo dedicado al análisis del defecto:
- Tiempo de corrección:
- Tiempo de reejecución:
- Observaciones:
