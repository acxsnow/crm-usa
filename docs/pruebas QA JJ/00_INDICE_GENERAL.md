# Plan de QA manual · Delta HVAC CRM

Carpeta de pruebas de José Javier Miranda. Versión de partida: `main 23260ae`. Creada el 25 de octubre de 2026.

## Cómo se usa

1. Antes de empezar, dejar la base en el estado inicial: `04_DATOS_DE_PRUEBA.md`.
2. Tomar los escenarios en el orden de esta tabla (están ordenados para que cada uno deje listo al siguiente).
3. En el archivo del escenario, marcar cada paso `[x]` a medida que se hace y llenar las secciones 7 a 12.
4. Copiar aquí el estado, el tiempo real y los defectos.
5. Cada defecto va a `01_REGISTRO_DEFECTOS.md` con su ID (`D-###`) y se anota en el escenario.
6. Después de cada corrección, reejecutar lo que dice `02_PLAN_REGRESION.md`.

**Estados:** Pendiente · En ejecución · APROBADO · FALLIDO · BLOQUEADO · PENDIENTE DE CORRECCIÓN · PENDIENTE DE REEJECUCIÓN.
Un escenario solo se marca APROBADO si se ejecutó completo y todo lo esperado se cumplió. Ninguno viene aprobado de antemano.

**Prioridad:** P0 bloquea la salida a producción · P1 importante, se corrige antes de salir · P2 se puede salir con él documentado.

## Resumen por módulo

| Módulo | Escenarios | P0 | Bloqueados | Ejecución | Preparación | Aprobados | Fallidos | Defectos |
|---|---|---|---|---|---|---|---|---|
| Acceso y sesión | 8 | 1 | 0 | 2 h 05 min | 0 min | 0 | 1 | 2 |
| Venta puerta a puerta | 6 | 2 | 0 | 1 h 35 min | 0 min | 4 | 0 | 0 |
| Revisión administrativa | 6 | 2 | 0 | 1 h 35 min | 0 min | 4 | 0 | 0 |
| Instalación en campo | 16 | 8 | 0 | 5 h 40 min | 1 h 25 min | 9 | 1 | 1 |
| Técnicos | 5 | 2 | 0 | 1 h 20 min | 30 min | 2 | 0 | 0 |
| Bodega | 17 | 5 | 0 | 4 h 30 min | 0 min | 13 | 3 | 4 |
| Cobro al programa | 4 | 3 | 0 | 1 h 10 min | 0 min | 4 | 0 | 0 |
| Trabajo particular y facturación | 4 | 1 | 1 | 1 h 20 min | 0 min | 0 | 0 | 0 |
| Finanzas | 6 | 0 | 1 | 2 h 00 min | 0 min | 0 | 0 | 0 |
| Turnos, asistencia y mapa | 10 | 2 | 0 | 2 h 25 min | 0 min | 0 | 0 | 0 |
| Notificaciones y buscador | 4 | 0 | 0 | 50 min | 0 min | 0 | 0 | 0 |
| Seguridad | 10 | 7 | 0 | 3 h 45 min | 0 min | 2 | 1 | 1 |
| API y paginación | 6 | 1 | 0 | 1 h 35 min | 0 min | 2 | 1 | 1 |
| Rendimiento | 4 | 0 | 0 | 1 h 30 min | 20 min | 0 | 0 | 0 |
| Concurrencia | 3 | 1 | 0 | 50 min | 0 min | 1 | 1 | 1 |
| **Total** | **109** | **35** | **2** | **32 h 10 min** | **2 h 15 min** | **41** | **8** | **10** |

## Avance

- Ejecutados completos: 49 de 109 (44 %). En ejecución (parte hecha): 14.
- Aprobados: 41 · Fallidos: 8 · Bloqueados: 2 (faltan las llaves de prueba de Stripe/Plaid).
- Defectos: ver `01_REGISTRO_DEFECTOS.md`.

## Escenarios

| ID | Módulo | Escenario | Prioridad | Tipo | Archivo | Estado | Tiempo estimado (min) | Tiempo real | Defectos | Reejecución | Observaciones |
|---|---|---|---|---|---|---|---|---|---|---|---|
| AUTH-001 | Acceso y sesión | Ingreso válido con cada uno de los 6 roles | P0 | Funcional · seguridad | [AUTH-001_ingreso_valido_por_rol.md](escenarios/AUTH-001_ingreso_valido_por_rol.md) | En ejecución | 15 | 1 min (API) |  |  | API ok; falta pantalla |
| AUTH-002 | Acceso y sesión | Credenciales inválidas y bloqueo tras 5 intentos | P1 | Seguridad | [AUTH-002_credenciales_invalidas_y_bloqueo.md](escenarios/AUTH-002_credenciales_invalidas_y_bloqueo.md) | FALLIDO | 10 | 1 min (API) | D-005, D-006 |  | Bloqueo funciona; mensajes y auditoría fallan |
| AUTH-003 | Acceso y sesión | Olvidé mi contraseña: enlace de un solo uso, 60 minutos y 3 por hora | P1 | Funcional · seguridad | [AUTH-003_olvido_de_clave.md](escenarios/AUTH-003_olvido_de_clave.md) | Pendiente | 15 | | | | |
| AUTH-004 | Acceso y sesión | Invitar un usuario, aceptar la invitación y entrar | P1 | Funcional | [AUTH-004_invitacion_de_usuario.md](escenarios/AUTH-004_invitacion_de_usuario.md) | Pendiente | 15 | | | | |
| AUTH-005 | Acceso y sesión | Sesión vencida y pérdida de señal | P2 | Funcional · celular | [AUTH-005_sesion_vencida_y_sin_senal.md](escenarios/AUTH-005_sesion_vencida_y_sin_senal.md) | Pendiente | 25 | | | | |
| AUTH-006 | Acceso y sesión | Escribir a mano la dirección de una pantalla sin permiso | P1 | Seguridad | [AUTH-006_rutas_sin_permiso_por_url.md](escenarios/AUTH-006_rutas_sin_permiso_por_url.md) | En ejecución | 15 | 1 min (API) |  |  | API 20/20; falta pantalla |
| AUTH-007 | Acceso y sesión | Rol nuevo sin permisos marcados | P1 | Seguridad | [AUTH-007_rol_sin_permisos.md](escenarios/AUTH-007_rol_sin_permisos.md) | Pendiente | 15 | | | | |
| AUTH-008 | Acceso y sesión | Quitar un permiso a un rol con usuarios conectados | P2 | Seguridad | [AUTH-008_cambiar_rol_en_caliente.md](escenarios/AUTH-008_cambiar_rol_en_caliente.md) | Pendiente | 15 | | | | |
| VEN-001 | Venta puerta a puerta | La puerta no abrió (sin contacto) | P1 | Funcional | [VEN-001_puerta_no_abrio.md](escenarios/VEN-001_puerta_no_abrio.md) | En ejecución | 10 | lote 2 por API (≈1 min) |  |  | API 4/4; falta pantalla |
| VEN-002 | Venta puerta a puerta | No le interesa y no califica | P2 | Funcional | [VEN-002_puerta_no_le_interesa_y_no_califica.md](escenarios/VEN-002_puerta_no_le_interesa_y_no_califica.md) | APROBADO | 10 | lote 2 por API (≈1 min) |  |  | 5/5 |
| VEN-003 | Venta puerta a puerta | La misma puerta otra vez reabre su expediente | P1 | Funcional · integridad | [VEN-003_misma_puerta_dos_veces.md](escenarios/VEN-003_misma_puerta_dos_veces.md) | APROBADO | 10 | lote 2 por API (≈1 min) |  |  | 5/5 |
| VEN-004 | Venta puerta a puerta | Venta completa: abrió, formulario, autorización, firma y envío | P0 | Funcional · integración | [VEN-004_venta_completa_hasta_revision.md](escenarios/VEN-004_venta_completa_hasta_revision.md) | En ejecución | 35 | lote 2 por API (≈1 min) |  |  | API 12/12; falta pantalla |
| VEN-005 | Venta puerta a puerta | Datos inválidos en el formulario | P2 | Funcional · validación | [VEN-005_datos_invalidos_formulario.md](escenarios/VEN-005_datos_invalidos_formulario.md) | APROBADO | 15 | lote 2 por API (≈1 min) |  |  | 6/6 |
| VEN-006 | Venta puerta a puerta | Un vendedor no ve los expedientes del otro | P0 | Seguridad | [VEN-006_vendedor_ve_solo_lo_suyo.md](escenarios/VEN-006_vendedor_ve_solo_lo_suyo.md) | APROBADO | 15 | lote 2 por API (≈1 min) |  |  | 5/5 |
| REV-001 | Revisión administrativa | Revisar documentos: aceptar, rechazar con nota y agregar uno | P1 | Funcional | [REV-001_revisar_documentos.md](escenarios/REV-001_revisar_documentos.md) | En ejecución | 20 | lote 2 por API (≈1 min) |  |  | API 8/8; falta pantalla |
| REV-002 | Revisión administrativa | Devolver al vendedor con motivo y reenviar | P1 | Funcional · integración | [REV-002_devolver_al_vendedor_y_reenviar.md](escenarios/REV-002_devolver_al_vendedor_y_reenviar.md) | En ejecución | 20 | lote 2 por API (≈1 min) |  |  | API 8/8; falta pantalla |
| REV-003 | Revisión administrativa | Aprobar con el código del programa: nace la obra | P0 | Funcional · integración | [REV-003_aprobar_expediente.md](escenarios/REV-003_aprobar_expediente.md) | APROBADO | 15 | lote 2 por API (≈1 min) |  |  | 8/8 |
| REV-004 | Revisión administrativa | Poner en espera, rechazar con motivo y reenviar un rechazado | P2 | Funcional | [REV-004_espera_rechazo_y_reenvio.md](escenarios/REV-004_espera_rechazo_y_reenvio.md) | APROBADO | 20 | lote 2 por API (≈1 min) |  |  | 17/17 |
| REV-005 | Revisión administrativa | Cerrar un expediente desde cualquier etapa | P2 | Funcional | [REV-005_cierre_administrativo.md](escenarios/REV-005_cierre_administrativo.md) | APROBADO | 10 | lote 2 por API (≈1 min) |  |  | 7/7 |
| REV-006 | Revisión administrativa | El vendedor no puede aprobar su propio expediente (SEG-07) | P0 | Seguridad | [REV-006_vendedor_no_aprueba.md](escenarios/REV-006_vendedor_no_aprueba.md) | APROBADO | 10 | lote 2 por API (≈1 min) |  |  | 1/1 |
| INS-001 | Instalación en campo | Asignar técnico y fecha a la obra | P0 | Funcional | [INS-001_asignar_tecnico_y_fecha.md](escenarios/INS-001_asignar_tecnico_y_fecha.md) | APROBADO | 15 + 25 prep. | lote 2 por API (≈1 min) |  |  | 8/8 |
| INS-002 | Instalación en campo | Permiso municipal: sin permiso no se instala | P0 | Funcional · regla de negocio | [INS-002_permiso_municipal.md](escenarios/INS-002_permiso_municipal.md) | APROBADO | 20 | lote 2 por API (≈1 min) |  |  | 6/6 |
| INS-003 | Instalación en campo | Salida de material con la lista «3 ton desde cero» | P0 | Funcional · integración | [INS-003_salida_de_material_con_lista.md](escenarios/INS-003_salida_de_material_con_lista.md) | APROBADO | 25 | lote 2 por API (≈1 min) |  |  | 13/13 |
| INS-004 | Instalación en campo | Instalación completa: jornada, checklist, equipos y acta firmada | P0 | Funcional · celular | [INS-004_instalacion_completa_y_acta.md](escenarios/INS-004_instalacion_completa_y_acta.md) | En ejecución | 40 | lote 2 por API (≈1 min) |  |  | API 11/11; falta pantalla |
| INS-005 | Instalación en campo | Administración devuelve el acta al técnico y luego la confirma | P0 | Funcional | [INS-005_acta_devuelta_al_tecnico.md](escenarios/INS-005_acta_devuelta_al_tecnico.md) | APROBADO | 20 | lote 2 por API (≈1 min) |  |  | 5/5 |
| INS-006 | Instalación en campo | Inspección municipal aprobada | P1 | Funcional | [INS-006_inspeccion_aprobada.md](escenarios/INS-006_inspeccion_aprobada.md) | APROBADO | 15 | lote 2 por API (≈1 min) |  |  | 5/5 |
| INS-007 | Instalación en campo | Inspección fallida: la obra vuelve a campo | P1 | Funcional · regla de negocio | [INS-007_inspeccion_fallida_y_reinspeccion.md](escenarios/INS-007_inspeccion_fallida_y_reinspeccion.md) | APROBADO | 25 + 60 prep. | lote 2 por API (≈1 min) |  |  | 5/5 |
| INS-008 | Instalación en campo | Cambiar el técnico de una obra en curso (rotación) | P0 | Funcional · seguridad | [INS-008_rotacion_de_tecnico.md](escenarios/INS-008_rotacion_de_tecnico.md) | FALLIDO | 20 | lote 2 por API (≈1 min) | D-011 |  | D-011 |
| INS-009 | Instalación en campo | Cambiar las fechas de una obra programada | P2 | Funcional | [INS-009_reprogramar_fechas.md](escenarios/INS-009_reprogramar_fechas.md) | APROBADO | 10 | lote 2 por API (≈1 min) |  |  | 3/3 |
| INS-010 | Instalación en campo | El técnico llega y el cliente no estaba (visita fallida) | P0 | Funcional · regla de negocio | [INS-010_cliente_no_estaba.md](escenarios/INS-010_cliente_no_estaba.md) | En ejecución | 25 | lote 2 por API (≈1 min) |  |  | API 16/16; falta pantalla |
| INS-011 | Instalación en campo | Límite parametrizable de reagendamientos | P1 | Funcional · regla de negocio | [INS-011_limite_de_reagendamientos.md](escenarios/INS-011_limite_de_reagendamientos.md) | En ejecución | 30 | lote 2 por API (≈1 min) |  |  | API 14/14; falta pantalla |
| INS-012 | Instalación en campo | Cancelar una obra y reintegrar el material | P0 | Funcional · integración | [INS-012_cancelar_obra_con_reintegro.md](escenarios/INS-012_cancelar_obra_con_reintegro.md) | En ejecución | 30 | lote 2 por API (≈1 min) |  |  | API 13/13; falta pantalla |
| INS-013 | Instalación en campo | Enlace de firma del cliente: reenviar, vencido e inválido | P1 | Seguridad | [INS-013_enlace_de_firma_del_cliente.md](escenarios/INS-013_enlace_de_firma_del_cliente.md) | Pendiente | 15 | | | | |
| INS-014 | Instalación en campo | Material comprado en la obra (no sale de bodega) | P2 | Funcional | [INS-014_material_comprado_en_la_obra.md](escenarios/INS-014_material_comprado_en_la_obra.md) | APROBADO | 10 | lote 2 por API (≈1 min) |  |  | 3/3 |
| INS-015 | Instalación en campo | Señal débil: subir fotos y guardar con red lenta | P1 | Rendimiento · celular | [INS-015_senal_debil_en_campo.md](escenarios/INS-015_senal_debil_en_campo.md) | Pendiente | 20 | | | | |
| INS-016 | Instalación en campo | Obra de varios días con cuadrilla y ayudantes | P2 | Funcional | [INS-016_obra_de_varios_dias.md](escenarios/INS-016_obra_de_varios_dias.md) | APROBADO | 20 | lote 2 por API (≈1 min) |  |  | 7/7 |
| TEC-001 | Técnicos | Cada técnico ve solo su agenda y sus obras | P0 | Seguridad | [TEC-001_agenda_solo_lo_suyo.md](escenarios/TEC-001_agenda_solo_lo_suyo.md) | APROBADO | 15 | lote 2 por API (≈1 min) |  |  | 3/3 |
| TEC-002 | Técnicos | El técnico no autoriza salidas ni confirma su propia acta | P0 | Seguridad | [TEC-002_tecnico_no_autoriza_ni_confirma.md](escenarios/TEC-002_tecnico_no_autoriza_ni_confirma.md) | APROBADO | 15 | lote 2 por API (≈1 min) |  |  | 5/5 |
| TEC-003 | Técnicos | Agenda con los 15 técnicos cargados | P2 | Rendimiento · usabilidad | [TEC-003_quince_tecnicos_en_agenda.md](escenarios/TEC-003_quince_tecnicos_en_agenda.md) | Pendiente | 20 + 30 prep. | | | | |
| TEC-004 | Técnicos | Desactivar un técnico que tiene obras y camioneta con material | P1 | Funcional · integridad | [TEC-004_tecnico_desactivado_con_obras.md](escenarios/TEC-004_tecnico_desactivado_con_obras.md) | Pendiente | 15 | | | | |
| TEC-005 | Técnicos | Cobro en efectivo en campo y efectivo por entregar | P1 | Funcional · dinero | [TEC-005_efectivo_por_entregar.md](escenarios/TEC-005_efectivo_por_entregar.md) | Pendiente | 15 | | | | |
| BOD-001 | Bodega | La carga inicial cuadra con los PDF de AC Pro | P0 | Datos · integridad | [BOD-001_carga_inicial_cuadra.md](escenarios/BOD-001_carga_inicial_cuadra.md) | APROBADO | 20 | 2 min (API + SQL) |  |  | 19/19 |
| BOD-002 | Bodega | Crear y editar un artículo con validaciones | P1 | Funcional · validación | [BOD-002_crear_y_editar_articulo.md](escenarios/BOD-002_crear_y_editar_articulo.md) | FALLIDO | 15 | lote 2 por API (≈1 min) | D-009, D-010 |  | D-009, D-010 |
| BOD-003 | Bodega | Entrada de mercancía de proveedor | P1 | Funcional | [BOD-003_entrada_de_mercancia.md](escenarios/BOD-003_entrada_de_mercancia.md) | APROBADO | 10 | lote 2 por API (≈1 min) |  |  | 4/4 |
| BOD-004 | Bodega | Entrega parcial y rechazo de una salida | P0 | Funcional · regla de negocio | [BOD-004_salida_parcial_y_rechazo.md](escenarios/BOD-004_salida_parcial_y_rechazo.md) | APROBADO | 20 | lote 2 por API (≈1 min) |  |  | 6/6 |
| BOD-005 | Bodega | Pedir más de lo que hay en bodega | P0 | Funcional · integridad | [BOD-005_existencia_insuficiente.md](escenarios/BOD-005_existencia_insuficiente.md) | APROBADO | 15 | lote 2 por API (≈1 min) |  |  | 4/4 |
| BOD-006 | Bodega | Reintegro: el material vuelve de la camioneta a bodega | P0 | Funcional · dinero | [BOD-006_reintegro_a_bodega.md](escenarios/BOD-006_reintegro_a_bodega.md) | FALLIDO | 20 | lote 2 por API (≈1 min) | D-008 |  | D-008 |
| BOD-007 | Bodega | Obra que consume todo: sin reintegro | P1 | Funcional | [BOD-007_obra_sin_reintegro.md](escenarios/BOD-007_obra_sin_reintegro.md) | Pendiente | 10 | | | | |
| BOD-008 | Bodega | Traslado de material entre camionetas | P1 | Funcional | [BOD-008_traslado_entre_camionetas.md](escenarios/BOD-008_traslado_entre_camionetas.md) | APROBADO | 15 | lote 2 por API (≈1 min) |  |  | 2/2 |
| BOD-009 | Bodega | Conteo físico con diferencias (ajuste) | P1 | Funcional · auditoría | [BOD-009_conteo_y_ajuste.md](escenarios/BOD-009_conteo_y_ajuste.md) | APROBADO | 20 | lote 2 por API (≈1 min) |  |  | 4/4 |
| BOD-010 | Bodega | Importar el catálogo desde Excel | P1 | Funcional · validación | [BOD-010_importar_catalogo.md](escenarios/BOD-010_importar_catalogo.md) | APROBADO | 20 | lote 2 por API (≈1 min) |  |  | 7/7 |
| BOD-011 | Bodega | Equipos con serial: rastreo por equipo | P1 | Funcional · integridad | [BOD-011_articulo_con_serial.md](escenarios/BOD-011_articulo_con_serial.md) | FALLIDO | 15 | lote 2 por API (≈1 min) | D-007 |  | D-007 |
| BOD-012 | Bodega | Bajo mínimo y compras sugeridas | P2 | Funcional | [BOD-012_minimos_y_compras_sugeridas.md](escenarios/BOD-012_minimos_y_compras_sugeridas.md) | APROBADO | 10 | lote 2 por API (≈1 min) |  |  | 3/3 |
| BOD-013 | Bodega | Crear, editar y borrar listas predefinidas | P2 | Funcional | [BOD-013_listas_predefinidas.md](escenarios/BOD-013_listas_predefinidas.md) | APROBADO | 15 | lote 2 por API (≈1 min) |  |  | 22/22 |
| BOD-014 | Bodega | Presupuesto de la obra contra lo real | P1 | Funcional · dinero | [BOD-014_presupuesto_vs_real.md](escenarios/BOD-014_presupuesto_vs_real.md) | APROBADO | 20 | lote 2 por API (≈1 min) |  |  | 6/6 |
| BOD-015 | Bodega | Cantidades y costos extremos | P2 | Validación | [BOD-015_valores_extremos.md](escenarios/BOD-015_valores_extremos.md) | APROBADO | 15 | lote 2 por API (≈1 min) |  |  | 7/7 |
| BOD-016 | Bodega | Dos entregas a la vez sobre la misma existencia | P0 | Concurrencia | [BOD-016_concurrencia_misma_existencia.md](escenarios/BOD-016_concurrencia_misma_existencia.md) | APROBADO | 20 | lote 2 por API (≈1 min) |  |  | 3/3 |
| BOD-017 | Bodega | El técnico ve su camioneta sin costos | P1 | Seguridad | [BOD-017_tecnico_ve_sin_costos.md](escenarios/BOD-017_tecnico_ve_sin_costos.md) | APROBADO | 10 | lote 2 por API (≈1 min) |  |  | 12/12 |
| COB-001 | Cobro al programa | Crear el cobro al programa y radicarlo | P0 | Funcional · integración | [COB-001_crear_y_radicar_cobro.md](escenarios/COB-001_crear_y_radicar_cobro.md) | APROBADO | 20 | lote 2 por API (≈1 min) |  |  | 5/5 |
| COB-002 | Cobro al programa | El programa rechaza el cobro: corregir y volver a radicar | P1 | Funcional | [COB-002_cobro_rechazado_y_corregido.md](escenarios/COB-002_cobro_rechazado_y_corregido.md) | APROBADO | 20 | lote 2 por API (≈1 min) |  |  | 3/3 |
| COB-003 | Cobro al programa | El programa paga: expediente pagado y cerrado | P0 | Funcional · dinero | [COB-003_pago_del_programa_y_cierre.md](escenarios/COB-003_pago_del_programa_y_cierre.md) | APROBADO | 15 | lote 2 por API (≈1 min) |  |  | 7/7 |
| COB-004 | Cobro al programa | No se puede cobrar sin acta confirmada ni permiso aprobado | P0 | Funcional · seguridad | [COB-004_cobro_sin_acta_confirmada.md](escenarios/COB-004_cobro_sin_acta_confirmada.md) | APROBADO | 15 | lote 2 por API (≈1 min) |  |  | 2/2 |
| PAR-001 | Trabajo particular y facturación | Cotización particular: armar, enviar y aceptar | P1 | Funcional | [PAR-001_cotizacion_particular.md](escenarios/PAR-001_cotizacion_particular.md) | Pendiente | 20 | | | | |
| PAR-002 | Trabajo particular y facturación | Emitir y anular una factura | P0 | Funcional · dinero | [PAR-002_factura_emitir_anular.md](escenarios/PAR-002_factura_emitir_anular.md) | Pendiente | 20 | | | | |
| PAR-003 | Trabajo particular y facturación | Registrar el pago de una factura (efectivo, cheque, transferencia) | P1 | Funcional · dinero | [PAR-003_pago_manual_de_factura.md](escenarios/PAR-003_pago_manual_de_factura.md) | Pendiente | 15 | | | | |
| PAR-004 | Trabajo particular y facturación | Cobrar en línea con tarjeta (Stripe, modo prueba) | P1 | Integración | [PAR-004_cobro_en_linea_stripe.md](escenarios/PAR-004_cobro_en_linea_stripe.md) | Bloqueado (faltan llaves de prueba de Stripe/Plaid) | 25 | | | | |
| FIN-001 | Finanzas | Gasto de campo: enviar, aprobar y rechazar | P1 | Funcional · dinero | [FIN-001_gasto_de_campo.md](escenarios/FIN-001_gasto_de_campo.md) | Pendiente | 20 | | | | |
| FIN-002 | Finanzas | Proveedor, factura de compra y pago | P1 | Funcional · dinero | [FIN-002_proveedor_y_cuenta_por_pagar.md](escenarios/FIN-002_proveedor_y_cuenta_por_pagar.md) | Pendiente | 20 | | | | |
| FIN-003 | Finanzas | Banca: importar extracto CSV y categorizar | P1 | Funcional | [FIN-003_banca_extracto_csv.md](escenarios/FIN-003_banca_extracto_csv.md) | Pendiente | 20 | | | | |
| FIN-004 | Finanzas | Banca: conectar una cuenta con Plaid (sandbox) | P2 | Integración | [FIN-004_banca_plaid.md](escenarios/FIN-004_banca_plaid.md) | Bloqueado (faltan llaves de prueba de Stripe/Plaid) | 20 | | | | |
| FIN-005 | Finanzas | Conciliación y rentabilidad por obra | P1 | Funcional · dinero | [FIN-005_conciliacion_y_rentabilidad.md](escenarios/FIN-005_conciliacion_y_rentabilidad.md) | Pendiente | 25 | | | | |
| FIN-006 | Finanzas | Contabilidad no opera campo ni gerencia escribe | P1 | Seguridad | [FIN-006_contabilidad_solo_lectura_de_campo.md](escenarios/FIN-006_contabilidad_solo_lectura_de_campo.md) | Pendiente | 15 | | | | |
| TUR-001 | Turnos, asistencia y mapa | Armar la malla de turnos de la semana | P1 | Funcional | [TUR-001_malla_de_turnos.md](escenarios/TUR-001_malla_de_turnos.md) | Pendiente | 20 | | | | |
| TUR-002 | Turnos, asistencia y mapa | Marcar entrada y salida con GPS | P0 | Funcional · celular | [TUR-002_marcar_entrada_y_salida.md](escenarios/TUR-002_marcar_entrada_y_salida.md) | Pendiente | 15 | | | | |
| TUR-003 | Turnos, asistencia y mapa | Llegada tarde con tolerancia de 10 minutos | P1 | Regla de negocio | [TUR-003_tolerancia_de_llegada.md](escenarios/TUR-003_tolerancia_de_llegada.md) | Pendiente | 15 | | | | |
| TUR-004 | Turnos, asistencia y mapa | Ausencia y novedades del día | P1 | Funcional | [TUR-004_ausencia_y_novedad.md](escenarios/TUR-004_ausencia_y_novedad.md) | Pendiente | 15 | | | | |
| TUR-005 | Turnos, asistencia y mapa | Horas extra y almuerzo según la forma de pago | P1 | Regla de negocio · dinero | [TUR-005_horas_extra_y_almuerzo.md](escenarios/TUR-005_horas_extra_y_almuerzo.md) | Pendiente | 20 | | | | |
| TUR-006 | Turnos, asistencia y mapa | Corregir una jornada mal marcada | P2 | Funcional · auditoría | [TUR-006_corregir_la_jornada.md](escenarios/TUR-006_corregir_la_jornada.md) | Pendiente | 10 | | | | |
| TUR-007 | Turnos, asistencia y mapa | Mapa operativo: técnicos y obras | P1 | Funcional | [TUR-007_mapa_operativo.md](escenarios/TUR-007_mapa_operativo.md) | Pendiente | 15 | | | | |
| TUR-008 | Turnos, asistencia y mapa | Retención de 90 días y borrado de ubicaciones | P2 | Privacidad | [TUR-008_retencion_y_borrado_de_ubicaciones.md](escenarios/TUR-008_retencion_y_borrado_de_ubicaciones.md) | Pendiente | 15 | | | | |
| TUR-009 | Turnos, asistencia y mapa | Monitor de técnicos y novedades del día | P2 | Funcional | [TUR-009_monitor_de_tecnicos.md](escenarios/TUR-009_monitor_de_tecnicos.md) | Pendiente | 10 | | | | |
| TUR-010 | Turnos, asistencia y mapa | El técnico no ve la asistencia ni la ubicación de otros | P0 | Seguridad · privacidad | [TUR-010_tecnico_no_ve_a_otros.md](escenarios/TUR-010_tecnico_no_ve_a_otros.md) | Pendiente | 10 | | | | |
| NOT-001 | Notificaciones y buscador | Campana de avisos en cada paso del flujo | P1 | Funcional | [NOT-001_campana_y_avisos.md](escenarios/NOT-001_campana_y_avisos.md) | Pendiente | 15 | | | | |
| NOT-002 | Notificaciones y buscador | Correos y SMS en modo de prueba | P2 | Integración | [NOT-002_correo_y_sms_en_consola.md](escenarios/NOT-002_correo_y_sms_en_consola.md) | Pendiente | 10 | | | | |
| BUS-001 | Notificaciones y buscador | Buscador global por nombre, número y dirección | P1 | Funcional | [BUS-001_buscador_global.md](escenarios/BUS-001_buscador_global.md) | Pendiente | 15 | | | | |
| BUS-002 | Notificaciones y buscador | Buscador con entradas raras | P2 | Seguridad · validación | [BUS-002_buscador_entradas_raras.md](escenarios/BUS-002_buscador_entradas_raras.md) | En ejecución | 10 | 1 min (API) |  |  | API 8/8; falta pantalla |
| SEC-001 | Seguridad | Aislamiento entre organizaciones (IDOR) | P0 | Seguridad | [SEC-001_aislamiento_entre_organizaciones.md](escenarios/SEC-001_aislamiento_entre_organizaciones.md) | APROBADO | 30 | 1 min (API) |  |  | 16/16; repetir con expedientes y facturas |
| SEC-002 | Seguridad | API sin token, con token vencido o alterado | P0 | Seguridad | [SEC-002_api_sin_token_y_token_alterado.md](escenarios/SEC-002_api_sin_token_y_token_alterado.md) | APROBADO | 15 | 1 min (API) |  |  | 25/25 |
| SEC-003 | Seguridad | Cada rol contra cada grupo de rutas | P0 | Seguridad | [SEC-003_permiso_por_ruta_backend.md](escenarios/SEC-003_permiso_por_ruta_backend.md) | Pendiente | 45 | | | | |
| SEC-004 | Seguridad | Inyección SQL y XSS en formularios y filtros | P0 | Seguridad | [SEC-004_inyeccion_sql_y_xss.md](escenarios/SEC-004_inyeccion_sql_y_xss.md) | FALLIDO | 25 | 1 min (API) | D-004 |  | Sin inyección; comodines sin escapar |
| SEC-005 | Seguridad | Subida de archivos: tipo, tamaño y nombre | P0 | Seguridad | [SEC-005_subida_de_archivos.md](escenarios/SEC-005_subida_de_archivos.md) | Pendiente | 20 | | | | |
| SEC-006 | Seguridad | Enlaces directos a archivos de otros | P0 | Seguridad | [SEC-006_enlaces_de_archivos.md](escenarios/SEC-006_enlaces_de_archivos.md) | Pendiente | 15 | | | | |
| SEC-007 | Seguridad | Campos que el cliente no debe poder fijar | P1 | Seguridad | [SEC-007_asignacion_masiva.md](escenarios/SEC-007_asignacion_masiva.md) | Pendiente | 20 | | | | |
| SEC-008 | Seguridad | Autorización de datos en los cuatro puntos de captura | P0 | Privacidad · cumplimiento | [SEC-008_datos_personales_y_consentimiento.md](escenarios/SEC-008_datos_personales_y_consentimiento.md) | Pendiente | 25 | | | | |
| SEC-009 | Seguridad | Secretos fuera del navegador y cabeceras de seguridad | P1 | Seguridad | [SEC-009_secretos_y_cabeceras.md](escenarios/SEC-009_secretos_y_cabeceras.md) | En ejecución | 15 | 1 min (API) |  |  | API ok; falta navegador |
| SEC-010 | Seguridad | Bitácora de auditoría de acciones sensibles | P1 | Auditoría | [SEC-010_auditoria_de_acciones.md](escenarios/SEC-010_auditoria_de_acciones.md) | Pendiente | 15 | | | | |
| API-001 | API y paginación | Paginación: límite por defecto, máximo y total | P0 | API · rendimiento | [API-001_paginacion_limites.md](escenarios/API-001_paginacion_limites.md) | En ejecución | 20 | 1 min (API) |  |  | API 8/8; falta pantalla |
| API-002 | API y paginación | Orden estable entre páginas | P1 | API | [API-002_orden_estable.md](escenarios/API-002_orden_estable.md) | FALLIDO | 15 | 1 min (API) | D-003 |  | 243 de 244 distintos |
| API-003 | API y paginación | Filtros y búsqueda en listas | P2 | API | [API-003_filtros_y_busqueda.md](escenarios/API-003_filtros_y_busqueda.md) | APROBADO | 15 | 1 min (API) |  |  | 5/5 |
| API-004 | API y paginación | Códigos HTTP y formato de error uniformes | P1 | API · contrato | [API-004_errores_y_codigos.md](escenarios/API-004_errores_y_codigos.md) | APROBADO | 15 | 1 min (API) |  |  | 15/15 |
| API-005 | API y paginación | Límite de peticiones (rate limit) | P2 | Seguridad · disponibilidad | [API-005_limite_de_peticiones.md](escenarios/API-005_limite_de_peticiones.md) | En ejecución | 10 | 1 min (API) |  |  | Olvido de clave ok; falta firma pública |
| API-006 | API y paginación | Las transiciones del expediente respetan su contrato | P1 | API · contrato | [API-006_contratos_del_expediente.md](escenarios/API-006_contratos_del_expediente.md) | Pendiente | 20 | | | | |
| PER-001 | Rendimiento | Tiempos de respuesta de las pantallas principales | P1 | Rendimiento | [PER-001_tiempos_de_respuesta.md](escenarios/PER-001_tiempos_de_respuesta.md) | Pendiente | 30 | | | | |
| PER-002 | Rendimiento | Listas con volumen alto | P2 | Rendimiento | [PER-002_volumen_de_datos.md](escenarios/PER-002_volumen_de_datos.md) | Pendiente | 30 + 20 prep. | | | | |
| PER-003 | Rendimiento | Carga inicial de la app en celular con red lenta | P1 | Rendimiento · celular | [PER-003_celular_red_lenta.md](escenarios/PER-003_celular_red_lenta.md) | Pendiente | 15 | | | | |
| PER-004 | Rendimiento | Tareas programadas (Celery beat) no bloquean la app | P2 | Rendimiento · operación | [PER-004_tareas_programadas.md](escenarios/PER-004_tareas_programadas.md) | Pendiente | 15 | | | | |
| CON-001 | Concurrencia | Doble clic y reintentos en acciones que crean cosas | P0 | Concurrencia | [CON-001_doble_clic_y_reintentos.md](escenarios/CON-001_doble_clic_y_reintentos.md) | FALLIDO | 20 | lote 2 por API (≈1 min) | D-012 |  | D-012 |
| CON-002 | Concurrencia | Numeración consecutiva con emisiones simultáneas | P1 | Concurrencia · dinero | [CON-002_numeracion_simultanea.md](escenarios/CON-002_numeracion_simultanea.md) | APROBADO | 15 | lote 2 por API (≈1 min) |  |  | 1/1 |
| CON-003 | Concurrencia | Dos personas editando lo mismo | P2 | Concurrencia | [CON-003_edicion_simultanea.md](escenarios/CON-003_edicion_simultanea.md) | Pendiente | 15 | | | | |

## Documentos de control

- `01_REGISTRO_DEFECTOS.md`: defectos con su estado.
- `02_PLAN_REGRESION.md`: qué volver a correr después de cada corrección.
- `03_ESTIMACION_QA.md`: cuánto toma el ciclo completo.
- `04_DATOS_DE_PRUEBA.md`: usuarios, técnicos, inventario, procedimientos de preparación y cómo reiniciar la base.
- `05_MATRIZ_PERMISOS.md`: qué puede hacer cada rol, sacado del código.
