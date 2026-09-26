# Preguntas para Delta HVAC

Fecha: 17 de septiembre de 2026. Preparadas por José Javier Miranda.
Fuente: `validacion-pdf-vs-modulos.md` §3. Están ordenadas por urgencia:
las del bloque 1 bloquean la configuración del formulario del vendedor.

## 1. Formulario del vendedor

- El flujo operativo (§2.4) exige que el vendedor registre amperaje del
  panel eléctrico, climatización existente, cocina de inducción, water heater
  y viabilidad eléctrica. Las plantillas de Arizona y TECH Clean que nos
  enviaron no tienen esos campos. ¿Se agregan a todos los programas? ¿Con qué
  valores? (amperaje: lista 100/125/150/200 A o número libre; water heater:
  sí/no o tipo y capacidad; viabilidad: adecuada / requiere adecuación / no
  viable).
- ¿El sistema debe decidir para qué programa califica el cliente a partir de
  sus respuestas, o el vendedor elige el programa y el sistema solo valida
  que esté completo? Si decide, necesitamos las reglas por programa
  (beneficios que califican, topes de ingreso, tipo de vivienda, estado).
- ¿Se guarda foto o escaneo del documento de identidad del cliente en el
  expediente, o solo se marca "verificado físicamente"? Si se guarda, ¿quién
  puede verlo y se envía al programa?
- Cuando el cliente no tiene beneficio y califica por ingresos (taxes): ¿se
  captura el ingreso anual y se adjunta la declaración? ¿Cuáles son los topes
  por programa y tamaño del hogar?

## 2. Términos, condiciones y firma

- ¿Los T&C y la autorización van en inglés, español o bilingüe? ¿Quién
  entrega el texto legal definitivo y su versión para cada programa?
- ¿Se le entrega al cliente un PDF firmado (correo, WhatsApp, impreso)?
- Arizona aparece a nombre de Desert Alliance Properties LLC y TECH Clean a
  nombre de Delta HVAC Service Inc. ¿Qué nombre, logo y texto ve el cliente
  en cada programa, y qué entidad aparece en el invoice?

## 3. Datos sensibles

- Discapacidad, condición médica, beneficios públicos, ingresos y documento
  de identidad: ¿quién dentro de Delta HVAC puede verlos? ¿Deben ocultarse en
  reportes y exportaciones? ¿Se conservan indefinidamente como el resto?

## 4. Trabajo en campo

- ¿Los vendedores tienen señal de celular en los parques? ¿Necesitan
  capturar sin conexión y sincronizar después?
- ¿Qué programas deben estar configurados al arranque además de Arizona y
  TECH Clean (Edison, Go Zero, LADWP, HEEHRA)? ¿Tienen el formulario oficial
  de cada uno? ¿Hay algún programa para Nevada?
- El título o decal de la mobile home: ¿bloquea la aplicación del vendedor
  o la instalación? El documento de requerimientos dice "según la etapa
  definida" y falta definirla.
- ¿Quieren registrar cada puerta tocada (no abrió, no interesado, no
  califica) para medir la productividad del vendedor por zona? ¿Se registra
  la autorización del administrador del parque (nombre, fecha, contacto)?

## 5. Microsoft Forms

- El flujo operativo pide "incrustar o sincronizar Microsoft Forms". ¿Los
  formularios de Microsoft Forms que usan hoy desaparecen cuando entre el
  CRM, o hay alguno que deba seguir vivo por exigencia de un programa? Nuestra
  recomendación es que el CRM los reemplace; sincronizar duplica la fuente de
  verdad.

## 6. Administración (no bloquea al vendedor, pero sí a Administración)

- Contador de días en "Pendiente Aprobación": la referencia es 2–3 días
  hábiles. ¿A partir de qué día se alerta y a quién? ¿Con qué calendario de
  feriados?
- Inspección: ¿quién la agenda (ciudad, programa, ambos)? ¿Qué datos se
  registran? Si falla, ¿el caso vuelve a "Listo para instalar" o hay un
  estado de corrección técnica?
- Permisos municipales: ¿el sistema debe generar y llenar los formularios de
  la ciudad, o solo registrar número, fecha y estado del permiso? Si genera,
  ¿qué ciudades y qué formularios?
- ¿Los permisos tienen fecha de vencimiento? ¿Cuál es el plazo típico?
- ¿Cuál es el checklist exacto para radicar el cobro en cada programa
  (aprobación, código, T&C firmado, fotos, invoice, formulario del programa)?
- Gestor documental: ¿necesitan que el CRM convierta o comprima archivos y
  arme un paquete descargable por cliente para subir al portal del programa?
  ¿Qué formatos y límites exige cada portal?

## 7. Técnicos

- Además de la foto de la etiqueta, ¿el programa exige registrar marca,
  modelo, serial, BTU y cantidad de cada equipo instalado? ¿Debe ir en el
  invoice?
- ¿Basta una agenda diaria por técnico o quieren ruta en mapa con orden de
  visitas? ¿Lista de materiales por orden o control de inventario?

## 8. Contabilidad (alcance: ¿entra en esta fase?)

- Gastos de campo, proveedores y cuentas por pagar, conciliación bancaria,
  P&L por proyecto y reportes gerenciales: ¿entran en esta entrega o en una
  fase posterior? Hoy no tienen módulo ni responsable.
- Si entran: categorías de gasto y quién los registra; facturas de
  proveedor con vencimiento y pagos parciales; conciliación por importación
  de extracto o registro manual; exportación a QuickBooks, Xero o Excel;
  qué información llega cuando el programa rechaza una factura y si se
  reabre el mismo invoice o se emite uno nuevo; facturación a clientes
  particulares fuera de programa.

## 9. Roles

- El flujo habla de Vendedor, Administración, Técnico, Contabilidad y
  Gerencia. ¿Qué personas ocupan cada rol y alguien cumple dos (por ejemplo,
  Administración y Contabilidad)?
