# [INS-004] Instalación completa: jornada, checklist, equipos y acta firmada

## 1. Información general

- **ID:** INS-004
- **Módulo:** Instalación en campo
- **Prioridad:** P0
- **Tipo de prueba:** Funcional · celular
- **Estado:** En ejecución
- **Fecha de ejecución:** 2026-10-25 (parte por API)
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 40 min de ejecución
- **Tiempo real:** lote 2 por API (≈1 min)
- **Versión o commit probado:** devjj 07e97c7 (base QA reiniciada con seed_qa)

## 2. Objetivo

El camino feliz del técnico en el celular, del primer día al acta firmada por técnico y cliente.

## 3. Precondiciones

- INS-002 e INS-003 hechos.
- Celular real o 390 px; ubicación concedida.

## 4. Datos de prueba

- Seriales de prueba: condensadora `QA-COND-0001`, evaporadora `QA-EVAP-0001`. Correo del cliente: qa.rivera@example.com.

## 5. Procedimiento paso a paso

1. [ ] Como Carlos, en **Mi agenda** abrir la obra y **Registrar la jornada** (qué se hizo, con quién, ayudantes).
2. [ ] Llenar el **Checklist de instalación** con **Tomar foto** en cada punto que la exige.
3. [ ] Marcar un punto como **No aplica en esta casa** con su motivo.
4. [ ] **Guardar equipos instalados** con los seriales de prueba.
5. [ ] **Cerrar instalación**: firmar como técnico en el recuadro.
6. [ ] Para la firma del cliente: **Enviar enlace por correo** y abrir el enlace (registros de la API) en otra ventana sin sesión.
7. [ ] Firmar como cliente (con la autorización de datos) y volver a la obra: **Consultar si ya firmó**.
8. [ ] **Descargar acta firmada (PDF)**.

## 6. Resultado esperado

- No deja cerrar con puntos obligatorios sin foto.
- El acta queda «Firmada por el técnico y el cliente» y el expediente pasa a la etapa de inspección pendiente cuando corresponde.
- El PDF trae equipos, seriales, firmas y fecha.

## 7. Resultado obtenido

- Qué pasó: Por API, 11 de 11 comprobaciones bien.
- Diferencias con lo esperado: Falta la parte del celular: fotos con «Tomar foto», firma con el dedo y el PDF abierto.
- Comprobaciones por API (11 de 11):
  - ✔ Cerrar sin completar está bloqueado — `{'can_close': False, 'missing': ['Verificar orden y dirección', 'Confirmar distribución de la vivienda (habitaciones, cocina y sala)', 'Foto de la fachada', 'Re`
  - ✔ Cerrar instalación incompleta se rechaza
  - ✔ Checklist resuelto (14 ítems) — `[]`
  - ✔ Equipo instalado con serial
  - ✔ Guardar equipos instalados
  - ✔ Firma del técnico en el acta
  - ✔ Firma del cliente en el acta
  - ✔ Cerrar instalación
  - ✔ Equipo después del cierre se bloquea
  - ✔ Descargar acta firmada (PDF) — `200 application/pdf`
  - ✔ Etapa del expediente después del cierre — `installed`

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`): ver las comprobaciones de la sección 7 (script `lote2` por API).
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] Fotos con marca de agua GPS y fecha.
- [ ] `data_consents` registra la firma pública del cliente.
- [ ] El enlace de firma ya usado responde «Este enlace de firma no es válido.»

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
