# [AUTH-001] Ingreso válido con cada uno de los 6 roles

## 1. Información general

- **ID:** AUTH-001
- **Módulo:** Acceso y sesión
- **Prioridad:** P0
- **Tipo de prueba:** Funcional · seguridad
- **Estado:** En ejecución
- **Fecha de ejecución:** 2026-10-25 (parte por API)
- **Responsable:** José Javier Miranda
- **Tiempo estimado:** 15 min de ejecución
- **Tiempo real:** 1 min (API)
- **Versión o commit probado:** devjj deee0d8 (base QA de seed_qa)

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

- Qué pasó: Los 6 roles entran y `/auth/me` responde con su rol y su número de permisos (91, 58, 14, 15, 32 y 21, iguales a la matriz).
- Diferencias con lo esperado: Ninguna en la parte de API. Falta revisar el menú de cada rol en pantalla y a 390 px.
- Comprobaciones por API (6 de 6):
  - ✔ admin: ingresa y /auth/me responde — `Demo Admin · roles=['organization_admin'] · permisos=91 · 96 ms`
  - ✔ administracion: ingresa y /auth/me responde — `Andrés Administración · roles=['admin_staff'] · permisos=58 · 106 ms`
  - ✔ vendedor: ingresa y /auth/me responde — `Vicky Vendedora · roles=['salesperson'] · permisos=14 · 88 ms`
  - ✔ tecnico: ingresa y /auth/me responde — `Tito Técnico · roles=['field_technician'] · permisos=15 · 111 ms`
  - ✔ contabilidad: ingresa y /auth/me responde — `Clara Contable · roles=['accounting'] · permisos=32 · 131 ms`
  - ✔ gerencia: ingresa y /auth/me responde — `Gabriel Gerencia · roles=['management'] · permisos=21 · 149 ms`

## 8. Evidencias

- Capturas:
- Identificadores (expediente, obra, salida, factura…):
- Respuestas HTTP (F12 › Network, filtrar `api/v1`): ver las comprobaciones de la sección 7 (script `lote1` por API).
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

- Tiempo de ejecución: 1 min (API)
- Tiempo dedicado al análisis del defecto:
- Tiempo de corrección:
- Tiempo de reejecución:
- Observaciones:
