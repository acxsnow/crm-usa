# Estimación del ciclo de QA

Tiempos estimados de una persona que ya conoce la aplicación. Se reemplazan por los reales a medida que se ejecuta (columna «Tiempo real» del índice).

## Ejecución por módulo

| Módulo | Escenarios | Ejecución | Preparación | Subtotal |
|---|---|---|---|---|
| Acceso y sesión | 8 | 2 h 05 min | 0 min | 2 h 05 min |
| Venta puerta a puerta | 6 | 1 h 35 min | 0 min | 1 h 35 min |
| Revisión administrativa | 6 | 1 h 35 min | 0 min | 1 h 35 min |
| Instalación en campo | 16 | 5 h 35 min | 1 h 25 min | 7 h 00 min |
| Técnicos | 5 | 1 h 20 min | 30 min | 1 h 50 min |
| Bodega | 17 | 4 h 30 min | 0 min | 4 h 30 min |
| Cobro al programa | 4 | 1 h 10 min | 0 min | 1 h 10 min |
| Trabajo particular y facturación | 4 | 1 h 20 min | 0 min | 1 h 20 min |
| Finanzas | 6 | 2 h 00 min | 0 min | 2 h 00 min |
| Turnos, asistencia y mapa | 10 | 2 h 25 min | 0 min | 2 h 25 min |
| Notificaciones y buscador | 4 | 50 min | 0 min | 50 min |
| Seguridad | 10 | 3 h 45 min | 0 min | 3 h 45 min |
| API y paginación | 6 | 1 h 35 min | 0 min | 1 h 35 min |
| Rendimiento | 4 | 1 h 30 min | 20 min | 1 h 50 min |
| Concurrencia | 3 | 50 min | 0 min | 50 min |
| **Total** | **109** | **32 h 05 min** | **2 h 15 min** | **34 h 20 min** |

La preparación es la de los escenarios que necesitan datos propios (por ejemplo, otra obra completa). Los demás reutilizan lo que dejó el anterior, por eso el orden del índice importa.

## Ciclo completo

| Concepto | Supuesto | Tiempo |
|---|---|---|
| Ejecución y preparación | suma de los escenarios | 34 h 20 min |
| Evidencias y registro | 15 % de la ejecución | 5 h 09 min |
| Análisis de defectos | 20 % (supone que 1 de cada 4 escenarios encuentra algo) | 6 h 52 min |
| Reejecuciones y regresión | 25 % | 8 h 35 min |
| **Total QA** | | **54 h 56 min** |

Con 6 horas efectivas de prueba al día: **unos 9.2 días hábiles** para una persona.

## Fuera de esta cuenta

- **Corrección de defectos:** depende de lo que aparezca. Se registra por defecto en `01_REGISTRO_DEFECTOS.md`.
- **D-001** (visita fallida, límite de reagendamiento y cancelación): desarrollo estimado en 1,5 a 2 días con pruebas automáticas, manual y aviso a Mateo; luego INS-010 a INS-012 (1 h 20 min).
- **Stripe y Plaid:** PAR-004 y FIN-004 (45 min) cuando estén las llaves de prueba.
- **Prueba en celular real sobre Render:** ya hecha antes; se repite solo si cambia algo de campo.

## Supuestos

- Docker local estable y la base reiniciada al empezar.
- Los porcentajes de evidencias, análisis y reejecución son supuestos de arranque: se ajustan con los tiempos reales de la primera semana.
