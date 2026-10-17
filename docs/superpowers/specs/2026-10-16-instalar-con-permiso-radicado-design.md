# Instalar con el permiso solo radicado (variable de entorno)

Fecha: 16 de octubre de 2026. Pedido por José en la revisión manual. Toca el
paquete de Mateo (`field_ops`: guarda, permisos y la pantalla del permiso): se le
avisa antes de integrar.

## Pedido

Hoy, para pasar de «Permiso en trámite» a «Listo para instalar» (y poder liberar
la orden), cada permiso tiene que estar **aprobado por la ciudad y vigente**, o
marcado «No requerido». José dice que en la operación real basta con haber
**radicado** la solicitud: la aprobación llega después y se registra cuando
llegue, pero no debe frenar la instalación. Como la regla puede cambiar, se pide
un interruptor por variable de entorno.

## Decisión

Variable `PERMIT_FILED_ALLOWS_INSTALL` (booleana, en `app/core/config.py` y
`backend/.env.example`):

- `false` (por defecto): **como hoy**. Para instalar, cada permiso aprobado y
  vigente, o «No requerido».
- `true`: también deja pasar un permiso **radicado** (aún sin aprobar).

En los dos casos siguen bloqueando: un permiso **rechazado** y uno **aprobado pero
vencido**. Y sigue haciendo falta al menos un permiso registrado.

## Lo que NO cambia

- **El cobro al programa.** Su requisito «Permiso municipal aprobado»
  (`billing/requirements.py`, `permit_approved`) usa la regla estricta
  (`all_cleared`, `is_cleared`): para radicar el cobro el permiso tiene que estar
  aprobado, con la variable en `true` o en `false`. Lo que se destraba es la
  instalación, no el cobro.
- **La inspección**: agendarla exige permiso radicado y aprobarla exige el
  permiso firmado por el inspector, como hoy.
- `is_cleared` de cada permiso sigue significando «aprobado y vigente o no
  requerido».

## Diseño

- `field_ops/permits.py`: `allows_install(permit, today)` y
  `all_allow_install(permits, today)` = `all_cleared` más, si la variable está en
  `true`, los permisos `submitted`. La usan:
  - `field_ops/guards.py::guard_permits_cleared` (la puerta de «Listo para
    instalar», también por la ruta manual), con un mensaje que dice qué falta
    según la variable;
  - `permits._finish` (el avance automático al registrar o actualizar un permiso).
- La respuesta de cada permiso suma `allows_install` (campo nuevo) para que la
  pantalla no tenga que conocer la variable.
- **Pantalla** (`PermitsPanel.tsx`): la frase de arriba y la tarjeta usan
  `allows_install`. Con la variable en `true` y el permiso radicado: «Radicado.
  Ya se puede instalar; registra la aprobación cuando la ciudad responda», y el
  botón «La ciudad lo aprobó» sigue ahí.
- Cambiar la variable exige reiniciar la API. No mueve expedientes que ya están
  en «Permiso en trámite»: avanzan la próxima vez que se registre o actualice un
  permiso de ese proyecto.

## Pruebas

- Con `false`: un permiso radicado no deja pasar a «Listo para instalar» (como
  hoy); aprobado sí.
- Con `true`: registrar un permiso radicado lleva el expediente a «Listo para
  instalar»; uno rechazado o aprobado y vencido sigue bloqueando; la ruta manual
  respeta lo mismo.
- Con `true`, el requisito de cobro `permit_approved` sigue en falso hasta que
  se apruebe.
- `allows_install` en la respuesta.
