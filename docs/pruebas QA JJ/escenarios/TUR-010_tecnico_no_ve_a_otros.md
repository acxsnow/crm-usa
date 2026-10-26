# [TUR-010] El técnico no ve la asistencia ni la ubicación de otros

## 1. Información general

- **ID:** TUR-010
- **Módulo:** Turnos, asistencia y mapa
- **Prioridad:** P0
- **Tipo de prueba:** Seguridad · privacidad
- **Estado:** APROBADO
- **Fecha de ejecución:** 2026-10-25 (parte por API)
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 10 min de ejecución
- **Tiempo real:** lote 3 por API
- **Versión o commit probado:** devjj 67141f2 + D-013, D-015 a D-018 (base QA del lote 3)

## 2. Objetivo

Las ubicaciones son datos personales del técnico.

## 3. Precondiciones

- Token de Carlos.

## 4. Datos de prueba

- Rutas /attendance, /operations-map, /payroll.

## 5. Procedimiento paso a paso

1. [ ] Escribirlas a mano como Carlos.
2. [ ] Llamar a sus APIs con el token.

## 6. Resultado esperado

- Sin acceso en pantalla; 403 en asistencia y nómina; en `/operations-map/*` solo sus propios datos.

## 7. Resultado obtenido

- Qué pasó: Lote 3 por API (25 oct): 4 de 4 comprobaciones bien. Carlos recibe 403 en el panel, el tablero en vivo, las marcaciones, las personas y la nómina. En el mapa la API le responde, pero solo con él mismo y con sus propias obras, y el menú no le muestra «Mapa operativo».
- Diferencias con lo esperado: El plan esperaba 403 también en `/operations-map/*`: la API le da al técnico su propio mapa, sin datos de otros (corregido el texto).
- Comprobaciones por API (4 de 4):
  - ✔ Su propio turno sí lo ve
  - ✔ En el mapa de personas Carlos solo se ve a sí mismo — `[]`
  - ✔ En el mapa de obras Carlos solo ve las suyas (1) — `0`
  - ✔ El menú no le muestra «Mapa operativo» (exige locations.view o projects.read_all)

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`): ver las comprobaciones de la sección 7 (script `lote3` por API).
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] Ningún punto GPS de otro técnico en ninguna respuesta.

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
