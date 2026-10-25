# [VEN-005] Datos inválidos en el formulario

## 1. Información general

- **ID:** VEN-005
- **Módulo:** Venta puerta a puerta
- **Prioridad:** P2
- **Tipo de prueba:** Funcional · validación
- **Estado:** Pendiente
- **Fecha de ejecución:**
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 15 min de ejecución
- **Tiempo real:**
- **Versión o commit probado:** main 23260ae (anotar el que se pruebe de verdad)

## 2. Objetivo

Los campos rechazan formatos imposibles en la pantalla y en la API.

## 3. Precondiciones

- Un expediente de Vicky en «Nuevo prospecto» (iniciar uno nuevo como en VEN-004 sin enviarlo).

## 4. Datos de prueba

- Puerta: dirección «202 QA Mobile Park Dr», espacio «Spc 22», Phoenix, AZ, 85006. Valores: correo «sin-arroba», teléfono «abc», número por encima del máximo del catálogo, archivo .exe renombrado a .jpg.

## 5. Procedimiento paso a paso

1. [ ] Escribir cada valor inválido en su campo y tocar **Guardar y seguir**.
2. [ ] Subir el .exe renombrado como foto.
3. [ ] Con F12 › Network, anotar la respuesta de la API en cada intento.

## 6. Resultado esperado

- Cada valor inválido se rechaza con un mensaje claro en español.
- El archivo falso se rechaza por su contenido real (400), no por la extensión.

## 7. Resultado obtenido

- Qué pasó:
- Diferencias con lo esperado:

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`):
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] Ningún 500.
- [ ] Lo rechazado no queda guardado a medias.

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
