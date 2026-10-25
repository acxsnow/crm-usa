# [FIN-004] Banca: conectar una cuenta con Plaid (sandbox)

## 1. Información general

- **ID:** FIN-004
- **Módulo:** Finanzas
- **Prioridad:** P2
- **Tipo de prueba:** Integración
- **Estado:** Bloqueado (faltan llaves de prueba de Stripe/Plaid)
- **Fecha de ejecución:**
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 20 min de ejecución
- **Tiempo real:**
- **Versión o commit probado:** main 23260ae (anotar el que se pruebe de verdad)

## 2. Objetivo

La cuenta conectada trae movimientos sola.

## 3. Precondiciones

- Llaves de sandbox de Plaid en `backend/.env`.

## 4. Datos de prueba

- Usuario sandbox `user_good` / `pass_good`.

## 5. Procedimiento paso a paso

1. [ ] **Conectar cuenta**.
2. [ ] Sincronizar.
3. [ ] **Desconectar**.

## 6. Resultado esperado

- Aparece en «Cuentas conectadas» con sus movimientos.
- Al desconectar no se borran los movimientos traídos.

## 7. Resultado obtenido

- Qué pasó:
- Diferencias con lo esperado:

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`):
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] Ninguna llave ni token de Plaid se ve en el navegador.

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
