# [SEC-005] Subida de archivos: tipo, tamaño y nombre

## 1. Información general

- **ID:** SEC-005
- **Módulo:** Seguridad
- **Prioridad:** P0
- **Tipo de prueba:** Seguridad
- **Estado:** Pendiente
- **Fecha de ejecución:**
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 20 min de ejecución
- **Tiempo real:**
- **Versión o commit probado:** main 23260ae (anotar el que se pruebe de verdad)

## 2. Objetivo

Solo entran imágenes y PDF reales, de tamaño razonable.

## 3. Precondiciones

- Una obra en curso o un expediente en edición.

## 4. Datos de prueba

- Un .exe renombrado .jpg, un .svg con script, un JPG de 30 MB, un nombre `../../etc/passwd.jpg`, un PDF real.

## 5. Procedimiento paso a paso

1. [ ] Subir cada uno como evidencia.
2. [ ] Abrir el archivo subido.

## 6. Resultado esperado

- Rechaza los falsos y el de 30 MB (anotar el tope); acepta el PDF real.
- El nombre con `../` no sale de la carpeta de archivos.

## 7. Resultado obtenido

- Qué pasó:
- Diferencias con lo esperado:

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`):
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] Las imágenes aceptadas llevan marca de agua con GPS y fecha.

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
