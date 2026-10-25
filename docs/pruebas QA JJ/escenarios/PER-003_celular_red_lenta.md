# [PER-003] Carga inicial de la app en celular con red lenta

## 1. Información general

- **ID:** PER-003
- **Módulo:** Rendimiento
- **Prioridad:** P1
- **Tipo de prueba:** Rendimiento · celular
- **Estado:** Pendiente
- **Fecha de ejecución:**
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 15 min de ejecución
- **Tiempo real:**
- **Versión o commit probado:** main 23260ae (anotar el que se pruebe de verdad)

## 2. Objetivo

La PWA abre aceptablemente con señal de parque.

## 3. Precondiciones

- Build de producción (`npm run build` y `npm run preview`) o Render.

## 4. Datos de prueba

- Perfil Slow 3G, CPU 4× más lenta.

## 5. Procedimiento paso a paso

1. [ ] Abrir el ingreso y Mi agenda en frío.
2. [ ] Volver a abrir (con caché).

## 6. Resultado esperado

- Anotar los tiempos; con caché debe abrir casi inmediato.

## 7. Resultado obtenido

- Qué pasó:
- Diferencias con lo esperado:

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`):
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] Peso total del JS inicial (anotarlo).

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
