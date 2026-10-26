# [AUTH-005] Sesión vencida y pérdida de señal

## 1. Información general

- **ID:** AUTH-005
- **Módulo:** Acceso y sesión
- **Prioridad:** P2
- **Tipo de prueba:** Funcional · celular
- **Estado:** En ejecución
- **Fecha de ejecución:** 2026-10-25 (parte por API)
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 25 min de ejecución
- **Tiempo real:** lote 3 por API (≈2 min)
- **Versión o commit probado:** devjj 67141f2 + D-013 (base QA reiniciada con seed_qa)

## 2. Objetivo

Con la sesión corta vencida la app se renueva sola; sin señal no saca al usuario.

## 3. Precondiciones

- Sesión del técnico `tecnico@demo-org.com`.

## 4. Datos de prueba

- Token corto de 15 min; sesión larga de 14 días.

## 5. Procedimiento paso a paso

1. [ ] Entrar como técnico y dejar la app abierta 16 minutos sin tocarla.
2. [ ] Tocar **Agenda**: debe cargar sin pedir clave.
3. [ ] F12 › Network › marcar **Offline**. Navegar a otra pantalla.
4. [ ] Quitar **Offline** y seguir navegando.
5. [ ] Tocar **Salir** y luego el botón Atrás del navegador.

## 6. Resultado esperado

- A los 16 min sigue dentro (renovó la sesión).
- Sin red muestra error de conexión pero no lo manda al ingreso.
- Después de Salir, Atrás no muestra datos: lleva al ingreso.

## 7. Resultado obtenido

- Qué pasó: Lote 3 por API (25 oct, base QA reiniciada): 5 de 5 comprobaciones bien. La cookie renueva la sesión sin pedir clave y la Agenda carga con el token nuevo; la cookie ya rotada no sirve otra vez; después de Salir, renovar responde 401.
- Diferencias con lo esperado: Falta la parte de pantalla: 16 minutos sin tocar, sin red (Offline) y Atrás después de Salir.
- Comprobaciones por API (5 de 5):
  - ✔ Ingreso del técnico con la cookie de sesión larga — `200`
  - ✔ Renovar con la cookie da un token nuevo sin pedir clave — `200`
  - ✔ La cookie anterior (ya rotada) no sirve otra vez — `401`
  - ✔ Después de Salir, renovar responde 401 (lleva al ingreso) — `401`
  - ✔ Con el token renovado la Agenda carga — `200`

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`): ver las comprobaciones de la sección 7 (script `lote3` por API).
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] No queda ninguna clave ni token en `localStorage` (F12 › Application), salvo el perfil.

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

- Tiempo de ejecución: lote 3 por API (≈2 min)
- Tiempo dedicado al análisis del defecto:
- Tiempo de corrección:
- Tiempo de reejecución:
- Observaciones:
