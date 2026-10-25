# [FIN-003] Banca: importar extracto CSV y categorizar

## 1. Información general

- **ID:** FIN-003
- **Módulo:** Finanzas
- **Prioridad:** P1
- **Tipo de prueba:** Funcional
- **Estado:** Pendiente
- **Fecha de ejecución:**
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 20 min de ejecución
- **Tiempo real:**
- **Versión o commit probado:** main 23260ae (anotar el que se pruebe de verdad)

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
- La regla categoriza sola los siguientes.

## 7. Resultado obtenido

- Qué pasó:
- Diferencias con lo esperado:

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`):
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] `bankfeeds.manage` solo para admin y contabilidad.

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
