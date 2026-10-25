# [AUTH-005] Sesión vencida y pérdida de señal

## 1. Información general

- **ID:** AUTH-005
- **Módulo:** Acceso y sesión
- **Prioridad:** P2
- **Tipo de prueba:** Funcional · celular
- **Estado:** Pendiente
- **Fecha de ejecución:**
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 25 min de ejecución
- **Tiempo real:**
- **Versión o commit probado:** main 23260ae (anotar el que se pruebe de verdad)

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

- Qué pasó:
- Diferencias con lo esperado:

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`):
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

- Tiempo de ejecución:
- Tiempo dedicado al análisis del defecto:
- Tiempo de corrección:
- Tiempo de reejecución:
- Observaciones:
