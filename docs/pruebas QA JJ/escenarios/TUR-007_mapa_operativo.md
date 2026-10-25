# [TUR-007] Mapa operativo: técnicos y obras

## 1. Información general

- **ID:** TUR-007
- **Módulo:** Turnos, asistencia y mapa
- **Prioridad:** P1
- **Tipo de prueba:** Funcional
- **Estado:** Pendiente
- **Fecha de ejecución:**
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 15 min de ejecución
- **Tiempo real:**
- **Versión o commit probado:** main 23260ae (anotar el que se pruebe de verdad)

## 2. Objetivo

El mapa muestra dónde están los técnicos y las obras, y ubica las que no tienen coordenadas.

## 3. Precondiciones

- Obras creadas en P-01 con direcciones reales de Phoenix.

## 4. Datos de prueba

- Una obra con dirección inventada (sin coordenadas posibles).

## 5. Procedimiento paso a paso

1. [ ] **Mapa operativo**: revisar técnicos y obras.
2. [ ] Usar la geocodificación de obras sin coordenadas.
3. [ ] Abrir la obra inventada.

## 6. Resultado esperado

- Las reales quedan ubicadas; la inventada sigue avisando que no tiene coordenadas (máximo 25 por intento).

## 7. Resultado obtenido

- Qué pasó:
- Diferencias con lo esperado:

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`):
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] Solo Administrador y Administración ven el mapa.

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
