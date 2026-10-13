# Pasos para cerrar y salir a producción

Actualizado: 13 de octubre de 2026, después del QA de punta a punta (`docs/qa/`).
El código de los módulos 0 a 7 está terminado y probado. Esto es lo que falta, en orden.

## 1. Decisiones del cliente (bloquean la salida)

- [ ] **Entidad que factura cada programa** (Delta HVAC Service Inc. o Desert Alliance Properties LLC). Cargarla en *Facturación → Configuración del programa → Perfil* (nombre, dirección, teléfono, correo). Hoy TECH y LADWP no tienen emisor.
- [ ] **TECH sin inspección:** confirmar y, en *Configuración del programa → Requisitos*, desactivar «Inspección aprobada con firma del inspector» (viene activo por defecto).
- [ ] **Norma de protección de datos** aplicable en California, Arizona y Nevada (hallazgo abierto).
- [ ] **Piloto:** con un vendedor primero (recomendado) o apertura total.
- [ ] Valores definitivos de los formularios de Arizona y TECH (hoy provisionales).

## 2. Infraestructura en AWS

- [ ] Base de datos en **RDS PostgreSQL** con respaldos automáticos y recuperación a un punto en el tiempo (mínimo 7 días). Probar una restauración.
- [ ] **Redis** (ElastiCache) para Celery y límites de intentos de ingreso.
- [ ] Contenedores de **api**, **worker** y **beat** (ECS o similar). El worker y el beat son obligatorios: sin ellos no salen avisos, alertas ni campañas.
- [ ] Archivos en **S3** (`S3_BUCKET`, hoy disco local).
- [ ] Dominio con **HTTPS** (el GPS del celular lo exige) y `FRONTEND_APP_URL` / `PUBLIC_API_URL` con ese dominio.
- [ ] **CloudWatch:** logs de los tres servicios y alarmas de caída, errores 5xx y cola de Celery atascada.
- [ ] `JWT_SECRET_KEY` largo y aleatorio; `ENVIRONMENT=production`, `DEBUG=false`.
- [ ] `alembic upgrade head` y `python -m scripts.seed` (sin `--demo-org`) en la base nueva.

## 3. Mensajería (ver comentarios en `backend/.env.example`)

- [ ] **Masiv:** usuario y contraseña de la API de SMS con envío a EE. UU. y **registro 10DLC** confirmado. `SMS_PROVIDER=masiv`.
- [ ] **Webhook de respuestas (STOP/START):** generar `MASIV_WEBHOOK_TOKEN` y pedir a Masiv que reenvíe a `https://<dominio>/api/v1/webhooks/masiv/inbound?token=…`.
- [ ] **Correo de campañas:** buzón nuevo `promociones@<dominio de Delta HVAC>` en **Amazon SES** (dominio verificado con DKIM/SPF/DMARC, fuera del sandbox), credenciales SMTP y `MARKETING_POSTAL_ADDRESS`. `MARKETING_EMAIL_PROVIDER=smtp`.
- [ ] **Correo de avisos** (`EMAIL_*`): pasar de Gmail a SES con un remitente del dominio (`no-reply@…`).
- [ ] Prueba real: SMS y correo de prueba al celular y correo propios desde *Campañas → Probar*.

## 4. Repositorio

- [ ] En GitHub, **proteger la rama `main`**: exigir que pase el flujo `CI` antes de cualquier merge.
- [ ] José integra su rama `cadenaA` cuando vuelva (hoy no tiene cambios pendientes).

## 5. Seguridad

- [ ] **Prueba de intrusión externa** antes de cargar datos reales de clientes (recomendación de la auditoría).
- [ ] Revisar que ninguna credencial esté en el repositorio (solo en variables del servidor).

## 6. Piloto en campo

- [ ] Un vendedor en un parque real con teléfono: visita, formulario, fotos con GPS, firma, envío.
- [ ] Administración revisa y aprueba; técnico instala con el acta desde el celular.
- [ ] Revisar que lleguen los avisos (campana y correo) y que las fotos lleven la marca de agua.
- [ ] Repetir el QA automático contra el servidor de pruebas: `QA_API=https://<dominio>/api/v1 python -m scripts.qa_e2e`
  (solo en un ambiente de pruebas: crea registros).

## 7. Gastos, proveedores, conciliación y reportes (hechos el 13 oct 2026)

Ya no queda nada en gris en el menú (QA-02 cerrado). Falta confirmar con el cliente los supuestos de
`docs/superpowers/specs/2026-10-13-modulos-gastos-proveedores-finanzas-design.md`:

- [ ] Quién es Aldo Martínez en la plataforma (rol Gerencia o Administrador) para que apruebe y programe pagos.
- [ ] Umbral de doble aprobación (hoy 10.000 USD) y tope por gasto de campo (hoy 5.000 USD).
- [ ] Categorías de gasto de campo y si la comisión del vendedor entra en la rentabilidad.
- [ ] Cargar sus proveedores desde QuickBooks (Proveedores → Importar CSV).
