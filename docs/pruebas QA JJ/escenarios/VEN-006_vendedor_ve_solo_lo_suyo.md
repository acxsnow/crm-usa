# [VEN-006] Un vendedor no ve los expedientes del otro

## 1. Información general

- **ID:** VEN-006
- **Módulo:** Venta puerta a puerta
- **Prioridad:** P0
- **Tipo de prueba:** Seguridad
- **Estado:** Pendiente
- **Fecha de ejecución:**
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 15 min de ejecución
- **Tiempo real:**
- **Versión o commit probado:** main 23260ae (anotar el que se pruebe de verdad)

## 2. Objetivo

Aislamiento entre vendedores: ni por la lista, ni por el buscador, ni escribiendo la dirección.

## 3. Precondiciones

- VEN-004 hecho por Vicky.
- Ventana de incógnito con `vendedor2@demo-org.com` (Valeria Ventas).

## 4. Datos de prueba

- Expediente de VEN-004 (anotar su id de la URL `/cases/<id>/form`).

## 5. Procedimiento paso a paso

1. [ ] Como Valeria abrir **Expedientes** y **Mi día**.
2. [ ] Buscar «QA Venta Rivera» y el número del expediente en el buscador de arriba.
3. [ ] Pegar en la barra `/cases/<id>/form` y `/cases/<id>/review` con el id de Vicky.

## 6. Resultado esperado

- Valeria no ve el expediente en ninguna parte; la dirección escrita a mano responde «no existe» (404), no 403.

## 7. Resultado obtenido

- Qué pasó:
- Diferencias con lo esperado:

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`):
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] `GET /api/v1/cases/<id>` como Valeria responde 404.

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
