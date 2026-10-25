# [INS-015] Señal débil: subir fotos y guardar con red lenta

## 1. Información general

- **ID:** INS-015
- **Módulo:** Instalación en campo
- **Prioridad:** P1
- **Tipo de prueba:** Rendimiento · celular
- **Estado:** Pendiente
- **Fecha de ejecución:**
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 20 min de ejecución
- **Tiempo real:**
- **Versión o commit probado:** main 23260ae (anotar el que se pruebe de verdad)

## 2. Objetivo

En un parque sin buena señal no se pierden fotos ni se duplican registros.

## 3. Precondiciones

- Una obra en curso; F12 › Network con perfil **Slow 3G**.

## 4. Datos de prueba

- 3 fotos de ~4 MB del celular.

## 5. Procedimiento paso a paso

1. [ ] Subir las 3 fotos del checklist con Slow 3G.
2. [ ] Registrar la jornada y tocar Guardar dos veces seguidas.
3. [ ] Pasar a Offline a mitad de una subida y volver a Online.

## 6. Resultado esperado

- Cada foto muestra «Subiendo…» y termina, o falla con «No se pudo subir la foto.» y se puede reintentar.
- El doble toque no crea dos jornadas.

## 7. Resultado obtenido

- Qué pasó:
- Diferencias con lo esperado:

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`):
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] Anotar el tiempo de cada subida.
- [ ] Ninguna foto a medias queda guardada.

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
