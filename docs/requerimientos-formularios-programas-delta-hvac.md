# Requerimientos de formularios y flujo operativo

## Delta HVAC — versión de trabajo

**Programas iniciales:**

1. Eficiencia de Arizona — Desert Alliance Properties LLC.
2. TECH Clean California.

Este documento consolida los insumos entregados por el cliente, el flujo operativo de Delta HVAC, la solicitud de preaprobación y los formatos de documentación e invoice revisados. Sirve como base funcional para construir un formulario dinámico, configurable y extensible a nuevos programas sin cambiar el código principal.

> Las dos imágenes entregadas por Mateo son el insumo confirmado para la primera versión de los campos de Arizona y TECH Clean. Lo pendiente no es descubrir esos campos, sino configurarlos en el motor dinámico y validar las reglas/documentos que aplican a cada programa.

---

## 1. Objetivo del sistema

Centralizar en un expediente digital único el proceso completo:

`Prospecto → Elegibilidad → Aplicación → Revisión administrativa → Aprobación → Permiso → Instalación → Inspección → Cobro → Pago → Rentabilidad`

El expediente debe conservar:

- Datos del prospecto y cliente.
- Programa seleccionado y versión del formulario.
- Respuestas del formulario.
- Documentos y evidencias.
- Términos y condiciones aceptados.
- Firma presencial del cliente.
- Vendedor responsable.
- Historial de revisiones y cambios.
- Proyecto, instalación, inspección e invoice relacionados.

---

## 2. Principios del formulario dinámico

### 2.1 Configuración por programa

Cada programa debe tener su propia configuración:

- Código interno estable.
- Nombre comercial.
- Estado activo/inactivo.
- Estado o versión vigente.
- Entidad o funder responsable.
- Texto de autorización.
- Términos y condiciones aplicables.
- Campos regulatorios.
- Documentos requeridos.
- Evidencias requeridas.
- Reglas de elegibilidad.
- Checklist técnico.
- Plantilla de invoice.

Ejemplos de códigos iniciales:

```text
AZ_EFFICIENCY
TECH_CLEAN_CA
```

El vendedor debe seleccionar el programa desde una lista configurada, no escribirlo libremente. Esto evita errores como `TECH_CLEAN_CA`, `Tech Clean`, `TECH CLEAN CA` y otros nombres equivalentes que después dificultan reportes y facturación.

### 2.2 Versionamiento

Una aplicación debe guardar la versión exacta con la que fue diligenciada:

- `program_code`.
- `form_version`.
- Fecha de publicación.
- Usuario que publicó la versión.
- Estado de la versión: borrador, activa, archivada.

Las modificaciones futuras no deben alterar aplicaciones ya creadas.

### 2.3 Tipos de campo requeridos

El motor debe soportar como mínimo:

- Texto corto.
- Texto largo.
- Número entero.
- Número decimal.
- Teléfono.
- Correo electrónico.
- Fecha.
- Hora.
- Sí/No.
- Selección única.
- Selección múltiple.
- Dirección dividida por campos.
- Carga de documento.
- Carga de foto.
- Carga de video.
- Firma.
- Campo calculado o informativo.
- Campo condicional.

Cada campo debe permitir configurar:

- Etiqueta visible.
- Ayuda o descripción.
- Clave interna.
- Tipo.
- Obligatorio u opcional.
- Opciones disponibles.
- Orden.
- Sección.
- Condición de visibilidad.
- Requisito documental asociado.
- Regla de validación.

### 2.4 Regla de configuración para el administrador

El catálogo de campos debe ser independiente del formulario de cada programa. El administrador selecciona qué campos aparecen y cómo se comportan en cada versión.

Cada asignación de campo a un programa debe tener, como mínimo:

| Propiedad | Descripción |
|---|---|
| `field_key` | Clave técnica estable, por ejemplo `customer.full_name` |
| `program_code` | Programa al que se asigna |
| `section` | Sección visual del formulario |
| `enabled` | Si el campo se muestra o no |
| `required` | Si bloquea el envío cuando está vacío |
| `requirement_level` | `required`, `optional` o `conditional` |
| `condition` | Regla para mostrarlo, si aplica |
| `label` | Texto visible para el vendedor |
| `help_text` | Instrucción o ejemplo |
| `field_type` | Tipo de control visual |
| `options` | Opciones para select, radio o multiselección |
| `sort_order` | Posición dentro de la sección |
| `form_version` | Versión a la que pertenece |

`enabled` y `required` son decisiones del administrador por programa. El mapa que aparece abajo propone la configuración inicial basada en las dos imágenes entregadas, pero no convierte todos los campos en obligatorios automáticamente.

### 2.5 Catálogo canónico de campos

Las claves deben permanecer estables aunque cambie la etiqueta o el idioma. Así se pueden reutilizar reportes, reglas, documentos e invoices.

| Clave (`field_key`) | Sección | Etiqueta inicial | Tipo |
|---|---|---|---|
| `customer.full_name` | Cliente | Nombre completo | `text` |
| `customer.phone` | Cliente | Teléfono | `phone` |
| `customer.email` | Cliente | Correo electrónico | `email` |
| `customer.address_street` | Cliente | Dirección | `text` |
| `customer.address_city` | Cliente | Ciudad | `text` |
| `customer.address_state` | Cliente | Estado | `text` |
| `customer.address_zip` | Cliente | ZIP | `text` |
| `customer.contact_preference` | Cliente | Hora conveniente para contactarle | `single_select` |
| `home.is_homeowner` | Vivienda | ¿Es propietario de la vivienda? | `single_select` |
| `home.residence_type` | Vivienda | Tipo de vivienda | `single_select` |
| `home.unit_number` | Vivienda | Número de unidad/espacio | `text` |
| `home.bedrooms` | Vivienda | Número de habitaciones | `integer` |
| `home.bathrooms` | Vivienda | Número de baños | `integer` |
| `home.household_members` | Hogar | Número de miembros del hogar | `integer` |
| `home.education_level` | Hogar | Nivel de educación del cliente | `single_select` |
| `home.has_disability_or_chronic_condition` | Hogar | ¿Existe discapacidad o condición médica crónica? | `single_select` |
| `home.disability_or_condition_detail` | Hogar | Especificar condición | `textarea` |
| `home.gas_type` | Hogar | Tipo de compañía/suministro de gas | `single_select` |
| `home.gas_company` | Hogar | Compañía de gas natural | `text` |
| `home.notes` | Hogar | Notas del hogar | `textarea` |
| `eligibility.programs` | Elegibilidad | Programas de beneficio en los que participa el hogar | `multi_select` |
| `eligibility.other_program` | Elegibilidad | Otro programa/documento aceptado | `text` |
| `authorization.customer_name` | Autorización | Nombre del cliente | `text` |
| `authorization.terms_accepted` | Autorización | Acepto la autorización y los T&C | `terms_checkbox` |
| `authorization.signature` | Autorización | Firma del cliente | `signature` |
| `authorization.signed_at` | Autorización | Fecha y hora de firma | `system_datetime` |
| `internal.salesperson` | Uso interno | Vendedor/promotor | `system_user` |
| `internal.result` | Uso interno | Resultado | `single_select` |
| `internal.notes` | Uso interno | Observaciones internas | `textarea` |
| `internal.reviewed_at` | Uso interno | Fecha de revisión | `system_datetime` |

### 2.6 Opciones normalizadas del catálogo

#### Tipo de vivienda

```text
single_family_home = Casa
mobile_home = Casa móvil (Mobile Home)
condominium = Condominio
duplex = Dúplex
```

#### Propietario

```text
yes = Sí
no = No
```

#### Hora de contacto

```text
morning = Mañana
afternoon = Tarde
anytime = Cualquier hora
```

#### Resultado interno

```text
preapproved = Preaprobado
pending = Pendiente
does_not_qualify = No califica
```

#### Programas de Arizona

```text
alice = ALICE
hip = Housing Improvement Program (HIP)
hopwa = Housing Opportunities for Persons with AIDS
fdpir = FDPIR
head_start = Head Start
lifeline = Lifeline Support for Communications
liheap = LIHEAP
medicaid_ahcccs = Medicaid / AHCCCS
public_housing = Public Housing
nslp = National School Lunch Program (NSLP - Free)
snap = SNAP
ssi = SSI
other_government_nonprofit = Programa gubernamental / sin ánimo de lucro acreditado
none = Ninguno de los anteriores
```

#### Programas de TECH Clean

```text
care = CARE
fera = FERA
medi_cal = Medi-Cal
calfresh = CalFresh (SNAP)
wic = WIC
calworks = CalWORKS
ssi = SSI
none = Ninguno
```

#### Nivel de educación de Arizona

```text
primary_secondary = Primaria / Secundaria
high_school = Preparatoria / High School
technical_associate = Educación Técnica / Associate Degree
bachelors = Licenciatura / Universidad
graduate = Posgrado / Maestría
prefer_not_to_answer = Prefiero no responder
```

#### Discapacidad o condición médica

```text
yes = Sí
no = No
prefer_not_to_answer = Prefiero no responder
```

#### Tipo de gas

```text
natural_gas = Gas Natural
lp_propane = Gas LP / Propano
no_gas = No tienen gas
```

---

## Anexo A. Mapa de campos por programa

Las siguientes matrices son el mapa de implementación de las dos imágenes recibidas. La columna `configuración inicial` es una propuesta de activación; el administrador debe poder modificarla por programa y versión.

### A.1 Eficiencia de Arizona

| Campo | Etiqueta | Tipo | Configuración inicial | Regla/observación |
|---|---|---|---|---|
| `customer.full_name` | Nombre completo | Texto | Obligatorio | Dato principal del cliente |
| `customer.phone` | Teléfono | Teléfono | Obligatorio | Validar formato básico |
| `customer.email` | Correo electrónico | Email | Obligatorio | Validar formato de email |
| `customer.address_street` | Dirección | Texto | Obligatorio | Dirección de la vivienda |
| `customer.address_city` | Ciudad | Texto | Obligatorio | — |
| `customer.address_zip` | ZIP | Texto | Obligatorio | 5 dígitos o formato definido por el programa |
| `home.is_homeowner` | ¿Es propietario de la vivienda? | Sí/No | Obligatorio | — |
| `home.residence_type` | Tipo de vivienda | Selección única | Obligatorio | Casa, mobile home, condominio, dúplex |
| `home.education_level` | Nivel de educación | Selección única | Activo / definir obligatoriedad | Incluye “prefiero no responder” |
| `home.household_members` | Miembros de la familia | Entero | Activo / definir obligatoriedad | Mayor o igual a 1 |
| `home.has_disability_or_chronic_condition` | Discapacidad o condición médica crónica | Selección única | Activo / definir obligatoriedad | Sí, no, prefiero no responder |
| `home.disability_or_condition_detail` | Especificar | Texto largo | Condicional | Visible si responde “Sí” |
| `home.gas_type` | Tipo de gas | Selección única | Activo / definir obligatoriedad | Gas natural, LP/propano, no gas |
| `home.gas_company` | Compañía de gas | Texto | Condicional | Visible si selecciona gas natural |
| `home.notes` | Notas | Texto largo | Opcional | — |
| `eligibility.programs` | Programas del hogar | Selección múltiple | Obligatorio | Usar catálogo Arizona |
| `eligibility.other_program` | Otro programa/documento | Texto | Condicional | Visible si selecciona otro |
| `authorization.customer_name` | Nombre del cliente | Texto | Obligatorio | Puede autocompletarse desde cliente |
| `authorization.terms_accepted` | Autorización/T&C | Casilla | Obligatorio | Debe aceptarse antes de firmar |
| `authorization.signature` | Firma del cliente | Firma | Obligatorio | Firma presencial con vendedor |
| `authorization.signed_at` | Fecha/hora de firma | Sistema | Automático | No editable por el usuario |
| `internal.salesperson` | Promotor | Usuario | Automático | Usuario autenticado |
| `internal.result` | Resultado | Selección única | Uso interno | Preaprobado, pendiente, no califica |
| `internal.notes` | Observaciones | Texto largo | Uso interno | No visible para el cliente |

### A.2 TECH Clean California

| Campo | Etiqueta | Tipo | Configuración inicial | Regla/observación |
|---|---|---|---|---|
| `customer.full_name` | Nombre completo | Texto | Obligatorio | Dato principal del cliente |
| `customer.phone` | Teléfono | Teléfono | Obligatorio | Validar formato básico |
| `customer.email` | Correo electrónico | Email | Obligatorio | Validar formato de email |
| `customer.address_street` | Dirección | Texto | Obligatorio | Dirección de la vivienda |
| `customer.address_city` | Ciudad | Texto | Obligatorio | — |
| `customer.address_zip` | ZIP | Texto | Obligatorio | 5 dígitos o formato definido por el programa |
| `home.is_homeowner` | ¿Es propietario de la vivienda? | Sí/No | Obligatorio | — |
| `home.residence_type` | Tipo de vivienda | Selección única | Obligatorio | Casa, mobile home, condominio, dúplex |
| `eligibility.programs` | Programas del hogar | Selección múltiple | Obligatorio | CARE, FERA, Medi-Cal, CalFresh, WIC, CalWORKS, SSI, ninguno |
| `authorization.customer_name` | Nombre del cliente | Texto | Obligatorio | Puede autocompletarse desde cliente |
| `authorization.terms_accepted` | Autorización/T&C | Casilla | Obligatorio | Texto específico de TECH Clean |
| `authorization.signature` | Firma del cliente | Firma | Obligatorio | Firma presencial con vendedor |
| `authorization.signed_at` | Fecha/hora de firma | Sistema | Automático | La plantilla muestra fecha |
| `internal.salesperson` | Vendedor | Usuario | Automático | Usuario autenticado |
| `internal.result` | Resultado | Selección única | Uso interno | Preaprobado, pendiente, no califica |
| `internal.notes` | Observaciones | Texto largo | Uso interno | — |

### A.3 Campos no compartidos inicialmente

Estos campos aparecen en Arizona y no aparecen en la imagen de TECH Clean:

- `home.education_level`.
- `home.household_members`.
- `home.has_disability_or_chronic_condition`.
- `home.disability_or_condition_detail`.
- `home.gas_type`.
- `home.gas_company`.
- `home.notes`.
- Catálogo de programas Arizona.

El administrador podrá activarlos en TECH Clean en una versión posterior sin crear campos nuevos ni modificar la base de datos.

### A.4 Campos adicionales que deben permanecer configurables

Aunque los campos de TECH Clean son más cortos, el administrador debe poder agregar posteriormente:

- Número de habitaciones y baños.
- Información de pedestal.
- Decal/título de mobile home.
- Documentos de elegibilidad.
- Campos técnicos propios del programa.
- Preguntas adicionales del funder.

---

## 3. Secciones comunes para ambos programas

Estas secciones deben existir en la estructura general, aunque cada programa pueda activar, desactivar o modificar campos.

### 3.1 Información del cliente

- Nombre completo.
- Teléfono.
- Correo electrónico.
- Dirección.
- Ciudad.
- Estado.
- ZIP.
- Hora conveniente para contactar:
  - Mañana.
  - Tarde.
  - Cualquier hora.

### 3.2 Información de la vivienda

- ¿Es propietario de la vivienda?
  - Sí.
  - No.
- Tipo de vivienda:
  - Casa.
  - Casa móvil/mobile home.
  - Condominio.
  - Duplex.
- Cantidad de habitaciones.
- Cantidad de baños.
- Número de unidad o espacio, cuando aplique.

### 3.3 Elegibilidad por beneficios

El formulario debe permitir selección múltiple y conservar la respuesta exacta del cliente. Opciones identificadas en los insumos:

- CARE.
- FERA.
- Medi-Cal.
- CalFresh/SNAP.
- WIC.
- CalWORKS.
- SSI.
- LIHEAP.
- ALICE.
- Housing Improvement Program/HIP.
- Housing Opportunities for Persons with AIDS.
- FDPIR.
- Head Start.
- Lifeline Support for Communications.
- Medicaid/AHCCCS.
- Public Housing.
- National School Lunch Program.
- Programa gubernamental o sin ánimo de lucro acreditado.
- Ninguno de los anteriores.
- Otro programa/documento aceptado.

Debe existir una regla para impedir seleccionar `Ninguno` junto con otros programas, salvo que el cliente confirme que el programa lo permite.

### 3.4 Datos adicionales del hogar

Campos identificados en la plantilla de Eficiencia de Arizona:

- Nivel de educación:
  - Primaria/secundaria.
  - Preparatoria/high school.
  - Educación técnica/associate degree.
  - Licenciatura/universidad.
  - Posgrado/maestría.
  - Prefiero no responder.
- Número de miembros de la familia que viven en la vivienda.
- ¿Algún miembro tiene discapacidad o condición médica crónica?
  - Sí.
  - No.
  - Prefiero no responder.
- Especificación opcional de la condición.
- Tipo de compañía o suministro de gas:
  - Gas natural, con compañía.
  - Gas LP/propano.
  - No tienen gas.
- Notas del hogar.

Estos campos deben ser configurables por programa porque pueden tratar información sensible. El sistema debe limitar quién puede verlos y registrar cada acceso o modificación.

### 3.5 Autorización, T&C y firma

La autorización debe mostrar el texto correspondiente al programa y registrar:

- Texto o referencia del documento aceptado.
- Versión del T&C.
- Casilla de aceptación.
- Fecha y hora de aceptación.
- Nombre del cliente.
- Firma dibujada presencialmente.
- Fecha de firma.
- Vendedor autenticado que acompañó el proceso.
- IP/dispositivo, si la política de privacidad y la implementación lo permiten.

La firma del cliente debe realizarse durante el alta con el vendedor. No debe depender de la firma posterior del técnico.

### 3.6 Uso interno

Cada aplicación debe tener información separada de la información que ve el cliente:

- Vendedor/promotor.
- Resultado preliminar:
  - Preaprobado.
  - Pendiente.
  - No califica.
- Observaciones internas.
- Usuario que revisó.
- Fecha de revisión.

---

## 4. Plantilla inicial: Eficiencia de Arizona

### 4.1 Identificación

- Nombre completo.
- Teléfono.
- Correo electrónico.
- Dirección.
- Ciudad.
- ZIP.

### 4.2 Vivienda

- Propietario: sí/no.
- Tipo de vivienda.
- Nivel de educación.
- Número de miembros del hogar.
- Discapacidad o condición médica crónica.
- Especificación opcional.
- Tipo de gas.
- Compañía de gas, si es gas natural.
- Notas.

### 4.3 Programas de apoyo

Selección múltiple de los programas identificados en la plantilla:

- ALICE.
- Housing Improvement Program.
- Housing Opportunities for Persons with AIDS.
- FDPIR.
- Head Start.
- Lifeline Support for Communications.
- LIHEAP.
- Medicaid/AHCCCS.
- Public Housing.
- National School Lunch Program.
- SNAP.
- SSI.
- Programa gubernamental o sin ánimo de lucro acreditado.
- Ninguno de los anteriores.

### 4.4 Autorización y revisión interna

- Autorización para usar la información exclusivamente para verificar elegibilidad.
- Nombre del cliente.
- Firma del cliente.
- Fecha.
- Promotor.
- Resultado.
- Observaciones.

### 4.5 Requisitos documentales y técnicos asociados

La documentación de soporte identificada para este flujo debe poder configurarse como requisitos independientes:

- Aplicación completa y firmada.
- Factura reciente de electricidad.
- Documento que demuestra el beneficio o elegibilidad.
- Foto del panel o subpanel.
- Foto del furnace existente.
- Fotos del sistema HVAC existente, interior y exterior.
- Foto del pedestal.
- Fotos adicionales para el instalador.
- Comentarios sobre acceso, mascotas, estacionamiento y condiciones especiales.
- Número de habitaciones y baños.
- Triturador de basura: sí/no, cantidad y ubicación.
- Ventilador: sí/no, cantidad y ubicación.
- Extractor: sí/no, cantidad y ubicación.
- Lavaplatos: sí/no.
- Título de la mobile home, si aplica.
- Decal de la mobile home, si aplica.

---

## 5. Plantilla inicial: TECH Clean California

### 5.1 Identificación

- Nombre completo.
- Teléfono.
- Correo electrónico.
- Dirección.
- Ciudad.
- ZIP.

### 5.2 Vivienda

- Propietario: sí/no.
- Tipo de vivienda:
  - Casa.
  - Casa móvil/mobile home.
  - Condominio.
  - Duplex.

### 5.3 Programas de elegibilidad

Selección múltiple de los programas mostrados en la plantilla:

- CARE.
- FERA.
- Medi-Cal.
- CalFresh/SNAP.
- WIC.
- CalWORKS.
- SSI.
- Ninguno.

### 5.4 Autorización y uso interno

- Texto de autorización exclusivo para verificar la posible elegibilidad de TECH Clean California.
- Nombre del cliente.
- Firma del cliente.
- Fecha.
- Vendedor.
- Resultado:
  - Preaprobado.
  - Pendiente.
  - No califica.
- Observaciones.

### 5.5 Documentos y requisitos técnicos

Debe poder reutilizar los requisitos documentales comunes y activar únicamente los que TECH Clean California solicite oficialmente:

- Aplicación completa y firmada.
- Bill de electricidad.
- Documento de elegibilidad.
- Foto del panel/subpanel.
- Foto del furnace.
- Fotos del HVAC existente.
- Foto del pedestal.
- Documentación de mobile home, cuando aplique.
- Fotos adicionales.
- Comentarios del vendedor para el instalador.

Los campos de la plantilla TECH Clean quedan definidos por la imagen compartida. La configuración podrá complementarse posteriormente con documentos o reglas adicionales si el programa los exige.

---

## 6. Repositorio de documentos de la aplicación

Cada requisito documental debe tener un registro propio y no depender únicamente del nombre del archivo.

### 6.1 Datos mínimos de un documento

- Aplicación relacionada.
- Programa.
- Requisito al que responde.
- Nombre original.
- Tipo MIME.
- Tamaño.
- Fecha de carga.
- Usuario que cargó.
- Estado:
  - Pendiente.
  - Cargado.
  - Aceptado.
  - Rechazado.
  - Reemplazado.
- Observación de revisión.
- Versión o reemplazo anterior, si existe.

### 6.2 Reglas

- No permitir someter la aplicación si falta un requisito obligatorio.
- Permitir varios archivos cuando un requisito tenga más de una página o evidencia.
- Permitir reemplazar un archivo sin borrar el historial.
- Mostrar vista previa de imágenes y PDF.
- Permitir descargar o abrir el documento a usuarios autorizados.
- Registrar la revisión administrativa.
- Validar tipo y tamaño del archivo.
- Mantener el almacenamiento local durante esta etapa; S3 no es necesario todavía.

---

## 7. Evidencias de campo: fotos y videos

La evidencia debe estar asociada a una categoría y, cuando corresponda, a un requisito concreto.

### 7.1 Categorías mínimas

- Fachada.
- Pedestal.
- Panel/subpanel eléctrico.
- Furnace o equipo existente.
- A/C central.
- A/C de ventana.
- Equipos viejos.
- Proceso de gas.
- Conductos y cableado eléctrico.
- Equipos nuevos.
- Etiqueta interior.
- Etiqueta exterior.
- Evidencia de eliminación de equipo de gas.
- Fotos adicionales.
- Video adicional.

### 7.2 Marca visible

Toda foto o video de evidencia debe procesarse antes de almacenarse con una marca visible incrustada en los píxeles:

- Coordenadas GPS.
- Fecha.
- Hora.
- Indicador de que no hubo GPS, si el dispositivo negó el permiso.

La marca no debe depender solamente de EXIF o metadata, porque esa información puede perderse al compartir el archivo.

### 7.3 Reglas de carga

- Aceptar fotos y videos.
- Solicitar permiso de geolocalización en el dispositivo.
- Mostrar el GPS capturado antes de cargar.
- Mostrar vista previa en cuadros.
- Abrir vista ampliada con zoom para imágenes.
- Reproducir videos con controles.
- Mostrar GPS y fecha en el visor de detalle.
- Mantener evidencia original y procesada, si la política de auditoría lo requiere.
- Bloquear el cierre cuando falte una evidencia obligatoria.

---

## 8. Checklist técnico del instalador

El checklist debe ser configurable por programa y por tipo de instalación. No debe exigir la firma del cliente al técnico, porque la firma del cliente se realiza durante la aplicación con el vendedor.

### 8.1 Requisitos generales

- Verificar orden y dirección.
- Confirmar distribución de la vivienda.
- Registrar cantidad de habitaciones y ubicación de cocina/living room.
- Capturar fachada/pedestal cuando aplique.
- Registrar equipo existente.
- Registrar panel eléctrico cuando aplique.
- Registrar furnace y sistema HVAC existente.

### 8.2 Instalación y cierre

- Instalación de equipos nuevos.
- Foto de cada unidad nueva.
- Foto de etiqueta interior con modelo y serial visibles.
- Foto de etiqueta exterior con modelo y serial visibles.
- Conductos y cableado.
- Proceso de gas, si se retiró furnace a gas.
- Prueba de funcionamiento.
- Explicación de uso y garantía.
- Resultado de inspección.
- Observaciones del técnico.

### 8.3 Reglas condicionales

- Si se retira un equipo de gas, exigir evidencia del estado anterior y de la desconexión segura.
- Si existe adecuación eléctrica, exigir panel y cableado.
- Si no existe el equipo, permitir marcar `No aplica` con motivo.
- Si el programa exige pedestal, bloquear cierre sin foto.
- Si el programa exige mobile home title/decal, bloquear la aplicación o instalación según la etapa definida.

---

## 9. Flujo del vendedor

1. Iniciar aplicación desde un prospecto.
2. Seleccionar uno de los programas activos.
3. Cargar los campos comunes y los campos dinámicos del programa.
4. Completar el cuestionario de elegibilidad.
5. Capturar información de vivienda.
6. Cargar documentos y evidencias iniciales.
7. Mostrar checklist de requisitos faltantes.
8. Presentar T&C y autorización del programa.
9. Obtener aceptación del cliente.
10. Capturar firma presencial del cliente.
11. Registrar vendedor, fecha y ubicación de la visita.
12. Enviar el expediente a revisión administrativa.

El vendedor no debe poder enviar una aplicación incompleta si falta un campo, documento o firma obligatorio.

---

## 10. Flujo administrativo

Estados sugeridos:

1. Borrador.
2. Pendiente de revisión.
3. Devuelta para corrección.
4. Lista para someter.
5. Sometida al programa.
6. En revisión del programa.
7. Aprobada.
8. Rechazada.
9. En espera.

En cada revisión Administración debe poder:

- Ver respuestas.
- Ver documentos.
- Ver imágenes y videos.
- Ver GPS y fecha de evidencia.
- Ver T&C y firma.
- Agregar observaciones.
- Marcar requisitos faltantes.
- Devolver con motivo.
- Aprobar internamente.
- Marcar como lista para someter.
- Registrar fecha y usuario responsable.

La aprobación administrativa interna no debe confundirse con la aprobación final del programa.

---

## 11. Flujo de proyecto, permisos e inspección

Después de la aprobación del programa:

1. Crear o activar el proyecto.
2. Registrar permiso municipal.
3. Asignar técnico.
4. Programar fecha y ventana de visita.
5. Liberar orden de instalación.
6. Ejecutar checklist y cargar evidencia.
7. Solicitar/agendar inspección.
8. Registrar resultado de inspección.
9. Habilitar expediente de cobro.

Estados operativos sugeridos:

- Nuevo prospecto.
- Pendiente de aprobación.
- Aprobado.
- Permiso en trámite.
- Listo para instalar.
- Instalación programada.
- Instalado.
- Inspección pendiente.
- Inspección aprobada.
- En proceso de cobro.
- Pagado.
- Cerrado.

---

## 12. Facturación e invoices

Los invoices revisados confirman que se necesitan plantillas variables, no una factura única rígida.

### 12.1 Campos comunes

- Nombre y logo de la compañía.
- Dirección, teléfono y correo.
- Cliente.
- Dirección del proyecto.
- Número de invoice.
- Número de trabajo/job.
- Fecha del servicio.
- Fecha de emisión.
- Programa.
- Código del servicio.
- Términos de pago.
- Líneas de servicio.
- Cantidad.
- Descripción.
- Materiales.
- Mano de obra.
- Permisos.
- Subtotal.
- Rebate/incentivo.
- Total del trabajo.
- Pagos recibidos.
- Balance.
- Notas y condiciones.

### 12.2 Motor de plantillas

Cada programa debe poder seleccionar:

- Plantilla visual.
- Campos visibles.
- Campos obligatorios.
- Grupos de servicios.
- Fórmulas de subtotal.
- Rebate o incentivo.
- Texto legal.
- Datos de contacto.

Los dos formatos revisados se pueden manejar inicialmente como plantillas distintas:

- Invoice tipo GoZero/HousecallPro.
- Invoice tipo pedestal/Charge Ready Home Program.

---

## 13. Seguridad, auditoría y privacidad

El sistema debe:

- Restringir expedientes por organización y rol.
- Limitar documentos sensibles a usuarios autorizados.
- Registrar quién crea, modifica, revisa, devuelve o aprueba.
- Mantener historial de versiones.
- Evitar que el cliente vea observaciones internas.
- Evitar que una aplicación aprobada sea modificada sin dejar trazabilidad.
- Proteger URLs de archivos.
- Validar permisos antes de descargar documentos.
- Mantener separados T&C, firma del cliente y firma/identidad del vendedor.

---

## 14. Requerimientos que se pueden implementar ya

No dependen de la respuesta final de los dos programas:

- Catálogo de programas.
- Versionamiento de formularios.
- Campos comunes.
- Secciones y orden dinámico.
- Checklist de documentos.
- Vista previa de documentos.
- Pantalla administrativa de expediente.
- Devolución con observaciones.
- Checklist técnico por categorías.
- Asociación de evidencia a requisito.
- Evidencia de foto y video con GPS/fecha.
- Agenda y asignación de técnicos.
- Registro de permisos e inspecciones.
- Motor inicial de invoices.
- Auditoría y control de acceso.

---

## 15. Requerimientos pendientes de configuración o confirmación operativa

Los campos base de **Eficiencia de Arizona** y **TECH Clean California** ya fueron entregados en las dos imágenes y se consideran definidos para esta primera versión. No deben volver a solicitarse como información pendiente.

Lo que todavía debe configurarse o confirmarse para operar sin ambigüedad es:

- Nombre oficial y código.
- Reglas de elegibilidad y validaciones automáticas.
- Documentos obligatorios.
- Evidencias obligatorias.
- Requisitos condicionales.
- Texto exacto de autorización.
- T&C aplicable y versión.
- Resultado y estados oficiales.
- Datos que deben someterse al programa.
- Código de aprobación.
- Plantilla de invoice correspondiente.
- Fórmula del rebate.
- Reglas de inspección y cobro.

---

## 16. Criterio de aceptación

El trabajo se considerará listo para estos dos programas cuando:

- El vendedor pueda seleccionar Arizona o TECH Clean.
- El formulario muestre únicamente los campos de ese programa.
- Los campos obligatorios bloqueen el envío.
- Los documentos estén asociados a requisitos concretos.
- La firma y T&C queden guardados en la aplicación.
- Administración pueda revisar el expediente completo.
- Administración pueda devolverlo con observaciones.
- No se pueda someter con requisitos pendientes.
- Las evidencias de foto y video tengan GPS + fecha visibles.
- El técnico pueda completar su checklist sin firmar al cliente.
- El sistema genere el invoice con la plantilla correcta.
- Todo cambio quede auditado.

---

## 17. Alertas y decisiones de negocio pendientes

### 17.1 Identidad de la plantilla de Arizona

La imagen de Eficiencia de Arizona está encabezada por **Desert Alliance Properties LLC**, mientras que el flujo operativo y la plantilla de TECH Clean identifican a **Delta HVAC Service Inc.** Los campos de Arizona sí están definidos; lo que debe confirmarse antes de publicar o generar documentos es la relación entre ambas entidades:

- Si Desert Alliance es el administrador/funder del programa.
- Si Delta HVAC es el vendedor, contratista o participante.
- Qué nombre, logo, texto de autorización y firma deben aparecer frente al cliente.
- Qué entidad debe aparecer en el invoice.

La aplicación debe separar la identidad de la organización operadora, el funder/programa y el contratista que realiza el trabajo.

### 17.2 Diferencias entre programas

Con base en las imágenes, no se debe obligar a TECH Clean a responder campos que solo pertenecen a Arizona, como educación, tipo de gas o programas ALICE/AHCCCS. Tampoco se deben eliminar campos comunes solo porque una de las plantillas no los muestre.

La configuración debe permitir que cada programa defina:

- Campos propios.
- Campos compartidos.
- Documentos propios.
- Evidencias propias.
- Reglas propias.
- Texto de autorización propio.
- Invoice propio.

### 17.3 Datos sensibles

Discapacidad, condición médica, beneficios públicos e información de ingresos potencialmente pueden ser datos sensibles. El cliente debe confirmar qué campos se almacenan, quién puede verlos, durante cuánto tiempo y si deben ocultarse en reportes, invoices o exportaciones.

---

## Referencias revisadas

- `Delta_HVAC_Flujo_de_Trabajo_Operativo.pdf`.
- `pre_approval_application_letter.pdf`.
- `Requirements per client.pdf` — cuatro páginas revisadas.
- `Silvia Giron INVOICEGOZERO.pdf`.
- `INVOICE PEDESTAL Domingo Palacio #1.pdf`.

---

## 18. División de trabajo

La distribución vigente está definida en la sección **18.2 División vigente por propietario de módulo**. Cada módulo tiene una sola persona responsable de inicio a fin. No existe división de inicio/finalización entre personas.

## 18.2 División vigente por propietario de módulo

La regla vigente cambia la distribución anterior:

- La persona que inicia un módulo también lo termina.
- Cada módulo tiene un único responsable funcional y técnico.
- El responsable realiza frontend, backend, base de datos, validaciones y pruebas.
- Los módulos que forman una cadena dependiente permanecen con la misma persona.
- La otra persona revisa el contrato y prueba la integración, pero no queda como responsable del módulo.

### Cadena A — Formularios y expediente de aplicación

**Responsable completo: José Javier Miranda**  
**Orden de ejecución:** módulo 1 → módulo 2 → módulo 3

#### Módulo 1 — Catálogo y constructor de formularios dinámicos

José Javier desarrolla y termina:

- Catálogo de programas.
- Catálogo de campos.
- Secciones y orden.
- Campos comunes, Arizona y TECH Clean.
- Activación/desactivación por programa.
- Obligatorio, opcional y condicional.
- Opciones de selección.
- Versiones y publicación.
- Panel administrativo.
- Modelo, migraciones y API.
- Validaciones.
- Vista previa.
- Pruebas del módulo.

#### Módulo 2 — Aplicación del vendedor, T&C y firma

José Javier desarrolla y termina:

- Formulario dinámico del vendedor.
- Respuestas por `field_key`.
- Preguntas condicionales.
- Resumen previo al envío.
- T&C y autorización.
- Firma presencial del cliente.
- Registro de vendedor, fecha y versión.
- Estados de aplicación.
- Validación frontend y backend.
- Pruebas de aplicación y firma.

#### Módulo 3 — Documentos, fotos y videos

José Javier desarrolla y termina:

- Checklist visual de documentos.
- Carga y reemplazo de archivos.
- Asociación con requisitos.
- Vista previa de documentos.
- Vista ampliada de imágenes.
- Reproductor de videos.
- Estados de revisión documental.
- API, almacenamiento y permisos.
- Marca visible de GPS + fecha.
- Validación de archivos.
- Pruebas del flujo documental.

José Javier debe entregar la Cadena A completamente funcional antes de iniciar la integración con la Cadena B.

### Cadena B — Revisión, operación de campo y facturación

**Responsable completo: Mateo Mazo**  
**Orden de ejecución:** módulo 4 → módulo 5 → módulo 6

#### Módulo 4 — Revisión administrativa y sometimiento

Mateo desarrolla y termina:

- Estados y transiciones válidas.
- API de aprobar, devolver y someter.
- Observaciones administrativas.
- Motivo obligatorio de devolución.
- Validación de expediente completo.
- Registro de usuario y fecha.
- Pantalla de bandeja administrativa.
- Vista completa del expediente.
- Revisión de respuestas, documentos, evidencias, T&C y firma.
- Historial de revisión.
- Pruebas del módulo.

#### Módulo 5 — Proyecto, checklist técnico y evidencias de instalación

Mateo desarrolla y termina:

- Creación del proyecto después de la aprobación.
- Estados operativos.
- Asignación y agenda del técnico.
- Checklist técnico por categorías.
- Reglas condicionales.
- Requisitos de fachada, pedestal, panel, furnace, HVAC, equipos nuevos y etiquetas.
- Opción `No aplica` con motivo.
- Bloqueo de cierre por evidencia faltante.
- Permisos e inspección.
- Asociación de evidencias a requisitos.
- Pruebas de operación de campo.

#### Módulo 6 — Invoices, pagos y plantillas por programa

Mateo desarrolla y termina:

- Invoice con líneas de servicio.
- Materiales, mano de obra y permisos.
- Subtotal, rebate, total y balance.
- Pagos y estados.
- Plantillas GoZero/HousecallPro y pedestal/Charge Ready.
- Campos visibles por programa.
- API y generación de invoice.
- Editor y vista previa.
- Reglas de cálculo.
- Auditoría y pruebas.

Mateo debe entregar la Cadena B completamente funcional antes de iniciar la integración de comunicaciones.

### Módulo 7 — Notificaciones, correo y SMS Masiv

**Responsable completo: Mateo Mazo**

Este módulo se ejecuta después de la Cadena B porque consume eventos de aplicaciones, revisión, proyectos, inspecciones, invoices y pagos.

Mateo desarrolla y termina:

- Eventos de notificación.
- Centro visual de notificaciones.
- Plantillas de correo y SMS.
- Configuración de preferencias.
- Adaptador de correo.
- Adaptador configurable de Masiv.
- Variables de entorno para credenciales.
- Modo de prueba sin envío real.
- Historial de entregas y errores.
- Reenvío controlado.
- Pruebas de integración.

### Módulo 8 — Calidad, seguridad y entrega integrada

**Responsable completo: José Javier Miranda**

Este módulo se ejecuta después de las Cadenas A y B y del Módulo 7.

José Javier desarrolla y termina:

- Pruebas end-to-end de Arizona.
- Pruebas end-to-end de TECH Clean.
- Pruebas responsive en móvil y computador.
- Accesibilidad básica.
- Estados de carga, vacío y error.
- Revisión visual completa.
- Pruebas de firma y documentos.
- Pruebas de preview de fotos, videos e invoices.
- Validación del flujo con datos reales de prueba.
- Registro de defectos y cierre de incidencias.

Mateo debe entregar a José Javier un ambiente funcional, contratos API y datos de prueba para que el Módulo 8 no dependa de cambios pendientes.

### Handoffs obligatorios

#### Handoff José → Mateo

José entrega la Cadena A con:

- Migraciones aplicadas.
- Contratos API documentados.
- Catálogo de `field_key`.
- Códigos `program_code`.
- Versiones de Arizona y TECH Clean.
- Datos de prueba.
- Validaciones documentadas.

#### Handoff Mateo → José

Mateo entrega la Cadena B y el Módulo 7 con:

- Migraciones aplicadas.
- Contratos API documentados.
- Estados definitivos.
- Permisos por rol.
- Datos de prueba.
- Eventos y respuestas de error.
- Ambiente integrado.

No se debe comenzar el siguiente módulo de una cadena si el módulo anterior no tiene su API, migración, pantalla principal y pruebas mínimas terminadas.

## 19. Integración conjunta

Antes de unir cada entrega, ambos deben acordar:

- Nombres exactos de las rutas API.
- Estructura de los objetos JSON.
- Claves `field_key`.
- Códigos `program_code`.
- Estados permitidos.
- Formato de errores.
- Reglas de permisos.
- Comportamiento cuando un campo está desactivado.
- Comportamiento cuando un campo es condicional.

### Prueba conjunta mínima

1. Administración crea o activa Eficiencia de Arizona.
2. Administración activa los campos definidos en el mapa.
3. Administración marca algunos campos como obligatorios.
4. José Javier verifica la vista previa.
5. El vendedor crea una aplicación.
6. El sistema bloquea el envío si faltan campos o documentos obligatorios.
7. El vendedor carga documentos y evidencia.
8. El cliente acepta T&C y firma presencialmente.
9. Administración revisa el expediente.
10. Administración devuelve la aplicación con observaciones.
11. El vendedor corrige y vuelve a enviar.
12. Administración marca la aplicación como lista para someter.
13. El proyecto se crea con el checklist correspondiente.
14. Se cargan fotos/videos con GPS y fecha visibles.
15. Se genera el invoice con la plantilla correcta.
16. Todas las acciones aparecen en auditoría.

La misma prueba debe repetirse para TECH Clean California, verificando que no aparezcan campos exclusivos de Arizona.
