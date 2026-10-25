# [AUTH-001] Ingreso válido con cada uno de los 6 roles

## 1. Información general

- **ID:** AUTH-001
- **Módulo:** Acceso y sesión
- **Prioridad:** P0
- **Tipo de prueba:** Funcional · seguridad
- **Estado:** Pendiente
- **Fecha de ejecución:**
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 15 min de ejecución
- **Tiempo real:**
- **Versión o commit probado:** main 23260ae (anotar el que se pruebe de verdad)

## 2. Objetivo

Cada rol entra y ve solo el menú de su rol. Si el ingreso falla para un rol, ese rol no puede operar.

## 3. Precondiciones

- Base en el estado inicial de QA (`seed_qa`).
- Navegador en ventana de incógnito.

## 4. Datos de prueba

- Usuarios de `04_DATOS_DE_PRUEBA.md`, clave `ChangeMe123!`.
- admin, administracion, vendedor, tecnico, contabilidad y gerencia @demo-org.com.

## 5. Procedimiento paso a paso

1. [ ] Abrir http://localhost:5173/login.
2. [ ] Entrar con `admin@demo-org.com`. Anotar las secciones del menú lateral.
3. [ ] Tocar **Salir** y repetir con los otros 5 usuarios.
4. [ ] Con cada uno, comparar el menú con la tabla «Roles y menú» del manual (sección 3).
5. [ ] Con el técnico, abrir el menú en un celular o a 390 px de ancho (F12 › modo dispositivo).

## 6. Resultado esperado

- Los 6 entran sin error y llegan al Inicio.
- Cada menú muestra solo lo de su rol (por ejemplo, el técnico no ve Clientes de facturación, ni Banca, ni Proveedores).
- En 390 px el menú se abre con **Menú** y la barra inferior se ve completa.

## 7. Resultado obtenido

- Qué pasó:
- Diferencias con lo esperado:

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`):
- Consultas de verificación:

## 9. Validaciones complementarias

- [ ] F12 › Network: ningún 403 ni 500 al cargar el Inicio de cada rol.
- [ ] El nombre y el rol que muestra la barra superior coinciden con el usuario.

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
