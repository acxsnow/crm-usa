# [FIN-003] Banca: importar extracto CSV y categorizar

## 1. Información general

- **ID:** FIN-003
- **Módulo:** Finanzas
- **Prioridad:** P1
- **Tipo de prueba:** Funcional
- **Estado:** APROBADO
- **Fecha de ejecución:** 2026-10-25 (parte por API)
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 20 min de ejecución
- **Tiempo real:** lote 3 por API
- **Versión o commit probado:** devjj 67141f2 + D-013, D-015 a D-018 (base QA reiniciada con seed_qa)

## 2. Objetivo

Sin Plaid, el extracto en CSV entra, se categoriza y se concilia.

## 3. Precondiciones

- Sesión de `contabilidad@demo-org.com`.

## 4. Datos de prueba

- CSV de 5 movimientos (incluir uno repetido y uno con monto mal formado).

## 5. Procedimiento paso a paso

1. [ ] **Banca** › **Importar extracto** con el archivo.
2. [ ] Crear una regla (**Editar regla**) por comercio.
3. [ ] Marcar uno como «Es otra cosa (comisión, traspaso…)».
4. [ ] Importar el mismo archivo otra vez.

## 6. Resultado esperado

- Entran 4, el mal formado se reporta; la segunda importación no duplica.
- Las reglas por comercio (Banca, con Plaid) no aplican al extracto CSV de Conciliación: el CSV se concilia contra pagos y gastos.

## 7. Resultado obtenido

- Qué pasó: Lote 3 por API (25 oct, base QA reiniciada): 9 de 10 comprobaciones bien. El extracto en CSV entra con 4 movimientos (el repetido del mismo día también) y reporta el mal formado; la comisión se marca «Es otra cosa». Importarlo otra vez duplicaba todo: D-017, corregido (ahora responde «Ese extracto ya estaba importado» y un extracto que se solapa solo agrega lo nuevo).
- Diferencias con lo esperado: Las reglas por comercio son de Banca (cuentas conectadas con Plaid) y no se aplican al extracto en CSV de Conciliación: el plan las pedía para el CSV (corregido el texto).
- Comprobaciones por API (9 de 10):
  - ✔ Importar extracto del banco
  - ✔ Comisión marcada como «otro»
  - ✔ Gerencia no concilia
  - ✔ Importar el extracto: entran 4 y el mal formado se reporta (['fila 6']) — `201 {"statement_id":"998329fe-d427-4a55-99e4-0e8d7d12fd55","lines":4,"auto_matched":0,"invalid":["fila 6"]}`
  - ✘ Importar el mismo archivo otra vez no duplica (9 líneas del extracto en total) [encontró D-017; corregido y reejecutado abajo] — `segunda importación: 201 {'statement_id': 'c52cef4a-7b79-4333-b88c-3923b8756f16', 'lines': 4, 'auto_matched': 0, 'invalid': ['fila 6']}`
  - ✔ Marcar la comisión como «Es otra cosa» — `200`
  - ✔ Reglas por comercio (Banca): 200 (anotar si aplican al CSV) — `[]`
  - ✔ Entran 4 (el repetido del mismo día también) y el mal formado se reporta (['fila 6']) — `201 {"statement_id":"6f32036d-5b25-44e4-a298-d0650c1d0961","lines":4,"auto_matched":0,"invalid":["fila 6"],"duplicated":0}`
  - ✔ Importar el mismo archivo otra vez no duplica (D-017: 409 «ya estaba importado») — `409 {"detail":"Ese extracto ya estaba importado: todos sus movimientos ya están en la cuenta.","code":"statement_already_imported","request_id":"ed930d53-`
  - ✔ Quedan 4 movimientos de ese extracto (4) — `4`

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`): ver las comprobaciones de la sección 7 (script `lote3` por API).
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] `bankfeeds.manage` solo para admin y contabilidad.

## 10. Resultado final

- [x] APROBADO
- [ ] FALLIDO
- [ ] BLOQUEADO
- [ ] PENDIENTE DE CORRECCIÓN
- [ ] PENDIENTE DE REEJECUCIÓN

## 11. Defectos encontrados

| ID defecto | Descripción | Prioridad | Registrado en |
|---|---|---|---|
| D-017 | Importar dos veces el mismo extracto duplica los movimientos | P2 | `01_REGISTRO_DEFECTOS.md` |

## 12. Tiempo y seguimiento

- Tiempo de ejecución: lote 3 por API
- Tiempo dedicado al análisis del defecto:
- Tiempo de corrección:
- Tiempo de reejecución:
- Observaciones:
