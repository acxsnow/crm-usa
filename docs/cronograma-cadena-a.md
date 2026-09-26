# Cronograma — José Javier Miranda (Cadena A)

Fecha: 18 de septiembre de 2026. Revisado contra el PDF, el `.md` §18–§19,
`decisiones.md` y el calendario. Estimado trabajando con Claude, con el
ciclo de trabajo completo del `CLAUDE.md` (TDD, verificación, navegador).

Las fechas ya descuentan los festivos de Colombia: 12 de octubre, 2 de
noviembre, 16 de noviembre, 8 de diciembre y 25 de diciembre.

Hay dos opciones según lo que responda el cliente sobre señal en los
parques (`preguntas-cliente.md`, bloque 4). La diferencia está solo en el
módulo 2; todo lo demás es igual.

## Módulo 0 — Usuarios, roles y acceso por módulo

- Duración: 1 semana.
- Inicio: lunes 21 de septiembre de 2026.
- **Entrega: viernes 25 de septiembre de 2026.**
- Paquetes: `users`, `auth`, `organizations`, `shared/permissions.py`.
- Incluye también los códigos de permiso reservados para los módulos de
  Mateo (`projects.*`, `checklists.*`, `evidence.*`, `permits.*`,
  `inspections.*`, `invoices.*`, `billing.*`, `notifications.*`) para que
  él no tenga que tocar la matriz al arrancar.

## Contrato del esqueleto — miércoles 30 de septiembre

Son los primeros tres días del módulo 1. Es lo mínimo que Mateo necesita
para trabajar por su cuenta, y es un contrato: lo que está aquí no cambia
sin avisar. Idéntico en `cronograma-cadena-b.md`.

- `Program` mínimo: id, organización, código, nombre, activo, marca de
  plantilla del sistema. Nada más por ahora.
- `Case` con: organización, `program_id`, `customer_id` (opcional hasta
  que alguien abra la puerta), dirección de la propiedad (calle, unidad o
  espacio, ciudad, estado, ZIP, GPS, dirección normalizada), vendedor,
  `application_number`, `approval_code`, `funder_status_id`,
  `scheduled_install_date`, **etapa** (lista completa: `Sin contacto`,
  `No interesado`, `No califica`, `Nuevo Prospecto`, `Pendiente Aprobación`,
  `Aprobado`, `Rechazado`, `En espera`, `Permiso en Trámite`, `Listo para
  Instalar`, `Instalado`, `Inspección Pendiente`, `En Proceso de Cobro`,
  `Pagado`, `Cerrado`) y **sub-estado** (texto libre por etapa, definido
  por el dueño de la etapa).
- `case_stage_events`: historial de cada cambio de etapa o sub-estado con
  quién, cuándo y motivo. Es lo que permite medir tiempos de aprobación y
  rechazos (PDF §7) sin reconstruir nada después.
- `transition(case, to_stage, actor, reason)` en `cases/service.py` con la
  tabla completa de transiciones permitidas de punta a punta. Cada uno
  registra sus reglas de guarda para sus etapas (José hasta `Pendiente
  Aprobación`, Mateo desde `Aprobado`). Mateo puede mover un case a
  `Aprobado` desde sus tests sin esperar el módulo 4.
- `Project.case_id` (opcional, con relleno desde `opportunity_id`). **Es la
  única vez que José toca `field_ops`**, avisando antes. `Opportunity` queda
  viva y marcada obsoleta hasta que Mateo cambie el disparador de creación
  del proyecto (antes del 7 de octubre).
- `shared/events.py` con `emit(nombre, datos)` que por ahora solo registra
  en log. José emite desde el módulo 2; Mateo lo conecta en el módulo 7.
- `storage.py` y `watermark.py` pasan de `field_ops` a `app/shared/files/`
  como infraestructura común. Lo mueve Mateo (es su código) esa misma
  semana; a partir de ahí se cambia solo de común acuerdo.
- Dirección de las referencias: las tablas de Mateo apuntan a `Program`
  (`ChecklistTemplate.program_id`, `InvoiceTemplate.program_id`), no al
  revés. José no toca esas tablas.
- Swagger publicado con lo anterior y `docs/contratos-cadena-a.md` iniciado.

## Módulo 1 — Programa: catálogo, constructor de flujos y zonas

- Duración: 3 semanas y media.
- Inicio: lunes 28 de septiembre de 2026 (los tres primeros días son el
  esqueleto de arriba).
- **Entrega: jueves 22 de octubre de 2026.**
- Paquetes: `programs`, `cases`, `crm` (Lead, Customer; retiro de
  Opportunity y Quote).
- Incluye:
  - Programa completo: funder, qué nombre y logo ve el cliente, texto de
    autorización, entidad del invoice, términos y condiciones por versión e
    idioma.
  - Catálogo de campos: cada pregunta existe una sola vez con su clave,
    tipo (los 18 del `.md` §2.3), opciones y reglas (formato, mínimo y
    máximo, opciones que no se combinan). Se marca cuál es de uso interno y
    cuál es dato sensible (solo lo ve quien tenga permiso; se enmascara en
    exportaciones).
  - Constructor del flujo por programa: fases (con rol responsable) →
    pasos → campos, con orden, obligatorio/opcional/condicional y
    condiciones desde la pantalla. Se publica como versión y una versión
    publicada no se edita. En esta primera versión el orden se cambia con
    botones subir/bajar, no arrastrando: ahorra dos días y no pierde nada.
  - Vista previa de cómo lo va a ver el vendedor.
  - Zonas del programa y asignación de vendedores a zonas.
  - Plantillas base del sistema que cada empresa copia y ajusta (para
    vender el producto a otras empresas).
  - Arizona y TECH Clean cargados de inicio, incluida la sección técnica
    del vendedor que pide el PDF §2.4 (panel, climatización, inducción,
    water heater, viabilidad) y los campos de §4.5 del `.md` que no están
    en el catálogo (electrodomésticos, pedestal, título y decal).
  - Última semana (16–22 de octubre), ya con Mateo desenganchado: retirar
    `Opportunity`, `Quote`, la pantalla Pipeline y la migración de datos
    que convierte cada Opportunity existente en un `Case`.
- Es el módulo más cargado del cronograma.

## Módulo 2 — Fase del vendedor: visitas, case, pasos, T&C y firma

### Opción A — sin offline (la app necesita señal)

- Duración: 3 semanas.
- Inicio: viernes 23 de octubre de 2026.
- **Entrega: viernes 13 de noviembre de 2026.**

### Opción B — con offline (captura sin señal y sincroniza después)

- Duración: 4 semanas y media.
- Inicio: viernes 23 de octubre de 2026.
- **Entrega: miércoles 25 de noviembre de 2026.**
- Lo que agrega: cola de envíos y fotos guardada en el teléfono, definición
  del flujo disponible sin señal, subida en segundo plano con reintentos
  sin duplicar, hora y GPS tomados en el teléfono, pantalla de pendientes
  por subir, pruebas de corte de señal a mitad de paso.

En ambas opciones el módulo incluye:

- Al entrar, el vendedor ve su programa y su zona asignada.
- Cada puerta que toca queda registrada en el expediente con GPS, hora y
  resultado, aunque no le abran ("no abrió", "no interesado", "no
  califica"; se reabren si después sí).
- Una sola pantalla que dibuja cualquier paso del formulario, sea cual sea
  el tipo de campo (texto, número, teléfono, sí/no, lista, fecha, foto,
  firma…), sin programar una pantalla por paso.
- Lo que el vendedor envía en cada paso queda guardado y no se edita; una
  corrección es una versión nueva y la anterior queda como historial.
- Los datos clave (nombre, teléfono, dirección) se guardan en la tabla de
  clientes y en el expediente como datos reales, no dentro de un JSON.
- Antes de enviar, el sistema revisa qué obligatorio falta y se lo dice al
  vendedor; si falta algo, no deja enviar.
- El expediente pasa de "Nuevo prospecto" a "Pendiente aprobación" al
  enviar; de ahí en adelante lo maneja Administración (Cadena B). Al
  enviar y al recibir devolución se emiten eventos para notificaciones.
- Términos y condiciones de cada programa con versión e idioma, para saber
  exactamente qué texto aceptó el cliente; IP y dispositivo si la política
  lo permite.
- El cliente firma en pantalla; el vendedor queda identificado por su
  usuario.
- Resumen de todo antes de enviar.
- **Kanban de expedientes** con las etapas del PDF (reemplaza la pantalla
  Pipeline que se retiró) y pantalla de inicio por rol. Los cierres
  tempranos no se muestran por defecto.
- Pruebas automáticas de la pantalla de paso.

## Módulo 3 — Documentos, fotos y videos

- Duración: 1 semana.
- Opción A: martes 17 de noviembre → **lunes 23 de noviembre de 2026.**
- Opción B: jueves 26 de noviembre → **miércoles 2 de diciembre de 2026.**
- Paquete: `documents`. Usa `shared/files/` (común); no crea otra capa de
  archivos ni de marca de agua.

## Handoff Cadena A → Mateo

- **Opción A: martes 24 de noviembre de 2026.**
- **Opción B: jueves 3 de diciembre de 2026.**
- Se entrega: migraciones aplicadas, `docs/contratos-cadena-a.md` completo
  + Swagger, catálogo de `field_key`, códigos `program_code`, versiones de
  Arizona y TECH Clean, datos de prueba (un case por programa en cada
  etapa), validaciones documentadas, roles definitivos.

## Módulo 8 — Calidad, seguridad y entrega integrada

- Duración: 2 semanas.
- Inicio: cuando Mateo entregue el módulo 4 (ver `cronograma-cadena-b.md`).
- Opción A: jueves 10 de diciembre → **miércoles 23 de diciembre de 2026.**
- Opción B: jueves 17 de diciembre → **viernes 8 de enero de 2027** (no se
  cuenta la semana del 24 de diciembre al 1 de enero).

## Resumen

- **Sin offline: Cadena A entregada el 24 de noviembre; sistema completo
  probado el 23 de diciembre de 2026.**
- **Con offline: Cadena A entregada el 3 de diciembre; sistema completo
  probado el 8 de enero de 2027.**
- La decisión A/B hay que tomarla antes del 23 de octubre. El módulo 2
  deja la puerta abierta en ambos casos; el offline se puede agregar
  después con el mismo costo de semana y media.

## Trabajo en paralelo con Mateo

Mateo no espera la Cadena A completa. Necesita de José los roles (25 de
septiembre) y el esqueleto (30 de septiembre), y desde el 1 de octubre
trabaja por su cuenta en los módulos 5, 6 y 7. El módulo 4 es el único que
depende del formulario del vendedor y lo hace al final. Detalle y fechas
en `cronograma-cadena-b.md`.

Reglas para no pisarse:

- Paquetes de José: `users`, `auth`, `organizations`, `crm`, `programs`,
  `cases`, `documents`. Paquetes de Mateo: `field_ops`, `billing`,
  `notifications`. Nadie edita el del otro; si necesita algo, lo pide.
  Única excepción: `Project.case_id` en el esqueleto, avisada.
- Archivos compartidos (`alembic/env.py`, `tests/conftest.py`,
  `api/v1/router.py`, `shared/permissions.py`, `app/router.tsx`,
  `DashboardLayout.tsx`): solo se agregan líneas, nunca se reordenan ni se
  borran las del otro.
- `Case` es de José; las transiciones desde `Aprobado` en adelante las
  registra Mateo en `transition()`, sin tocar el modelo.
- `shared/files/` y `shared/events.py` son comunes: cambios de común
  acuerdo.
- Integración a `main` todos los viernes con `pytest` verde y `tsc` +
  `vite build` limpios. Quien integra segundo renumera su migración de
  Alembic encima de la del otro.
- `docs/contratos-cadena-a.md` (José) y `docs/contratos-cadena-b.md`
  (Mateo) siempre al día, más Swagger.
- Revisión conjunta corta cada viernes sobre `main`.

## Cambios al `.md` §18.2 que requieren el OK de Mateo

- Orden de la Cadena B: 5 → 6 → 7 → 4 (el 4 depende de la Cadena A).
- Quitar "José debe entregar la Cadena A completamente funcional antes de
  iniciar la integración" y "Mateo debe entregar la Cadena B completa antes
  de comunicaciones"; reemplazar por integración por contrato, semanal.
- Módulo 5: agregar checklist configurable por programa, equipos
  instalados como dato, permiso con vencimiento, inspección con resultado y
  reintento, lista de materiales por orden.
- Módulo 6: agregar expediente de cobro con checklist y fecha de
  radicación, estado rechazado con motivo y refacturación, dashboard de
  cobros con alerta por tiempo.
- Módulo 7: agregar contador de días en "Pendiente Aprobación" y alertas
  de vencimiento de permiso e inspección.
- Sección nueva "Contrato del esqueleto — 30 de septiembre" (la de arriba).

## Lo que necesito de Mateo la semana del 21 de septiembre

- OK a D1 (roles) y D2 (`Case`; `Project.case_id`; sus tablas apuntan a
  `Program`).
- OK a los cambios del `.md` de arriba.
- Enviar al cliente `preguntas-cliente.md`; la respuesta sobre señal en los
  parques define la opción A o B.

Si eso se cierra esa semana, las fechas se sostienen. Si no, cada día
corre un día y se avisa el mismo día.
