# Migración de CompanyCam a producción: pasos

Preparado el 28 de noviembre de 2026 sobre `main` en `35f7df8`. Lo ejecuta quien tenga acceso a Render (Mateo).
Lo probado: piloto local con 48 proyectos reales (todas las combinaciones de programa, etapa y vendedor), reversa
completa y vuelta a cargar, y la pantalla en computador y celular.

## Qué entra

| En CompanyCam | En el CRM |
| --- | --- |
| Proyecto archivado o eliminado | Expediente **Cerrado** |
| Proyecto activo de una cuenta «Vendedores N» | **Nuevo prospecto** (venta en proceso, por asignar) |
| Proyecto activo de cualquier otra persona | **En espera** |
| Etiqueta del proyecto TECH PROGRAM, TECH 2026… | Programa TECH Clean California |
| HEERA PROGRAM… | HEERA |
| LADWP | LADWP |
| GO ZERO SUBMITED, Needs Go Zero Application… | GoZero |
| PEDESTALES | Pedestales |
| Quality Services | Quality Services |
| Varias de esas etiquetas | Varios programas: el principal (TECH > HEERA > LADWP > Pedestales > Quality > GoZero) y los demás como adicionales |
| Las demás etiquetas (ciudad, estado del trámite) | Nota «Etiquetas en CompanyCam» del expediente |
| Lo creado por «Vendedores 4» | A nombre de la vendedora nueva (ya existe en producción, activa, rol Vendedor) |

Medido el 28 nov: 1.008 proyectos (557 archivados, 113 eliminados), unas 12.000 fotos (~4 GB).

## Antes de empezar

1. **Desplegar `main`** (API y sitio). El arranque aplica las migraciones 0055 y 0056 y el seed crea los programas
   HEERA, Pedestales y Quality Services. Comprobar en la Shell: `alembic current` debe decir `0056`.
2. **Token de CompanyCam** como variable de entorno del servicio de la API: `COMPANYCAM_TOKEN` (solo lectura;
   vence cerca del 27 de diciembre de 2026). Nunca en el repositorio.
3. **Espacio en disco:** `df -h /app/storage`. Hacen falta unos 5 GB libres; la descarga se detiene sola si quedan
   menos de 2 GB (`COMPANYCAM_MIN_FREE_GB`).
4. **No desplegar** mientras corre la importación: cada despliegue corta lo que esté corriendo (se puede relanzar;
   nada se duplica).

Organización de producción: `ca57533b-6042-4447-b0c6-40ed2e0d376d` («Demo Organization», la real de Delta HVAC).

## Pasos (Shell del servicio de la API en Render)

La caché va al disco del servicio para que sobreviva si se cae la sesión. `nohup` deja el proceso corriendo aunque
se cierre la Shell.

```sh
cd /app
export CC=/app/storage/companycam_export
ORG=ca57533b-6042-4447-b0c6-40ed2e0d376d

# 1) Extraer de CompanyCam (unos 40 minutos). Se puede relanzar: salta lo ya extraído.
nohup python -m scripts.companycam_import --cache $CC extract > /app/storage/cc_extract.log 2>&1 &
tail -f /app/storage/cc_extract.log        # termina con «Extracción: {...}»

# 2) Simular la carga (no guarda nada) y revisar los conteos.
python -m scripts.companycam_import --cache $CC load --org $ORG \
  --creator-email "Vendedores 4=<correo de la vendedora>" --dry-run
#   Esperado aprox. (conteo del 28 nov): cases_created ≈ 1008, stage_closed ≈ 662,
#   stage_new_prospect ≈ 131, stage_on_hold ≈ 215, cases_multi_program ≈ 81, sin «errors».
#   Si dice «Abortado», leer el motivo (falta un programa o el usuario destino) y no seguir.

# 3) Cargar de verdad (mismo comando sin --dry-run).
python -m scripts.companycam_import --cache $CC load --org $ORG \
  --creator-email "Vendedores 4=<correo de la vendedora>"

# 4) Descargar fotos y documentos con el worker de Celery (de noche; varias horas).
python -m scripts.companycam_download enqueue --org $ORG
python -m scripts.companycam_download status --org $ORG     # ver avance
python -m scripts.companycam_download retry-errors --org $ORG  # al final, reintentar los fallidos
```

Informes de la carga en `$CC/reports/` (clientes ambiguos, usuarios creados, errores).

## Revisar en pantalla

- **Expedientes** con el filtro «Origen: CompanyCam»: aparecen los importados con su etapa.
- Un expediente con dos programas muestra la sección **Programas** (principal y adicionales).
- Las ventas de «Vendedores 4» aparecen en **Mi día / Expedientes** de la vendedora como «Nuevo prospecto».

## Si algo sale mal

```sh
python -m scripts.companycam_import --cache $CC rollback --org $ORG --confirm
```

Borra lo importado que nadie ha tocado. Lo que una persona ya trabajó (programa elegido o decidido, archivos subidos,
etapa movida) se deja y se lista en `$CC/reports/rollback_bloqueados.csv`.

## Pendientes que no frenan la migración

- Decidir si un importado «En espera» puede «Aprobar» (hoy sí, y eso crea la obra).
- Textos y formularios reales de HEERA, Pedestales y Quality Services (hoy, el formulario de California provisional).
- Las cuentas «Vendedores 1» y «Vendedores 7» entran a nombre de un vendedor inactivo con ese nombre: Administración
  reasigna esos prospectos.
