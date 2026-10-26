# [BUS-001] Buscador global por nombre, número y dirección

## 1. Información general

- **ID:** BUS-001
- **Módulo:** Notificaciones y buscador
- **Prioridad:** P1
- **Tipo de prueba:** Funcional
- **Estado:** APROBADO
- **Fecha de ejecución:** 2026-10-25 (parte por API)
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 15 min de ejecución
- **Tiempo real:** lote 3 por API
- **Versión o commit probado:** devjj 67141f2 + D-013, D-015 a D-018 (base QA reiniciada con seed_qa)

## 2. Objetivo

El buscador de arriba encuentra clientes, expedientes, obras y facturas del usuario.

## 3. Precondiciones

- Datos creados en VEN y PAR.

## 4. Datos de prueba

- El nombre de un cliente creado en PAR-001, el número CASE-…, «Mobile Park», el número de factura, «zzz».

## 5. Procedimiento paso a paso

1. [ ] Buscar cada término como admin.
2. [ ] Buscar «Rivera» como Valeria y como Carlos.
3. [ ] Buscar «Cliente Ajeno QA».

## 6. Resultado esperado

- Admin encuentra todo; cada rol solo lo suyo; «zzz» dice que no hay resultados.

## 7. Resultado obtenido

- Qué pasó: Lote 3 por API (25 oct, base QA reiniciada): 8 de 8 comprobaciones bien. Admin encuentra el cliente particular, el expediente, la factura y las direcciones «Mobile Park»; «zzz» y «Cliente Ajeno QA» no traen nada; Valeria y Carlos no encuentran el expediente ajeno.
- Diferencias con lo esperado: El plan buscaba «Rivera» y «QA Mobile»: los datos de prueba no tienen ese apellido y la calle es «… QA <n> Mobile Park Dr» (corregido el texto).
- Comprobaciones por API (8 de 8):
  - ✔ Admin busca «Particular Gómez» y lo encuentra — `200 3`
  - ✔ Admin busca «CASE-2026-0002» y lo encuentra — `200 2`
  - ✔ Admin busca «FAC-2026-0005» y lo encuentra — `200 1`
  - ✔ «zzz» no trae resultados — `0`
  - ✔ «Cliente Ajeno QA» (otra organización) no aparece — `0`
  - ✔ Valeria no encuentra un expediente que no es suyo — `200 0`
  - ✔ Carlos (técnico) no encuentra expedientes ajenos — `200 0`
  - ✔ Admin busca «Mobile Park» (las direcciones de prueba, p. ej. «456 QA 1025212450 Mobile Park Dr») y las encuentra — `2`

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`): ver las comprobaciones de la sección 7 (script `lote3` por API).
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] Nunca aparece nada de la organización ajena.
- [ ] Responde en menos de 500 ms.

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
