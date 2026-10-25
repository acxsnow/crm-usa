# Datos de prueba

Todo vive en la base local de Docker. Clave de todos los usuarios: `ChangeMe123!`.

## Reiniciar la base al estado inicial

Borra TODA la base local y la vuelve a cargar (se niega a correr fuera de `ENVIRONMENT=development` o contra otra base):

```
docker compose exec api python -m scripts.seed_qa --reiniciar --si-borrar-todo
docker compose restart worker beat
```

Sin `--reiniciar` solo completa lo que falte (correrlo dos veces no duplica nada).

Respaldo de la base anterior al QA (25 de octubre de 2026, 10:13): `C:\Users\JHOANNA\crm-respaldos\crm-antes-de-QA-20261025-1013.dump`. Para volver a ella:

```
docker compose cp C:\Users\JHOANNA\crm-respaldos\crm-antes-de-QA-20261025-1013.dump postgres:/tmp/r.dump
docker compose exec postgres pg_restore -U crm -d crm --clean --if-exists /tmp/r.dump
```

## Estado inicial (verificado el 25 de octubre de 2026)

| Dato | Valor |
|---|---|
| Organizaciones | 2 (Demo Organization y Organización Ajena QA) |
| Usuarios | 22 |
| Técnicos | 15, cada uno con su camioneta |
| Artículos | 245 (244 de AC Pro + 1 de la organización ajena) |
| Unidades en bodega | 648 |
| Valor en bodega | USD 13,209.22 |
| Listas predefinidas | 1, «Instalación 3 ton desde cero», 46 renglones |
| Programas | 2 (Eficiencia de Arizona y TECH Clean California) |
| Expedientes, obras, clientes de la demo | 0 |

## Usuarios por rol

| Rol | Nombre | Correo |
|---|---|---|
| Administrador | Demo Admin | `admin@demo-org.com` |
| Administración | Andrés Administración | `administracion@demo-org.com` |
| Vendedor | Vicky Vendedora | `vendedor@demo-org.com` |
| Vendedor | Valeria Ventas | `vendedor2@demo-org.com` |
| Contabilidad | Clara Contable | `contabilidad@demo-org.com` |
| Gerencia | Gabriel Gerencia | `gerencia@demo-org.com` |
| Administrador de la otra organización | Admin Ajena | `admin@otra-org.com` |

## Técnicos

| # | Nombre | Correo | Camioneta |
|---|---|---|---|
| 1 | Tito Técnico | `tecnico@demo-org.com` | Camioneta · Tito Técnico |
| 2 | Toño Segundo | `tecnico02@demo-org.com` | Camioneta · Toño Segundo |
| 3 | Carlos Ramírez | `tecnico03@demo-org.com` | Camioneta · Carlos Ramírez |
| 4 | Luis Herrera | `tecnico04@demo-org.com` | Camioneta · Luis Herrera |
| 5 | Miguel Torres | `tecnico05@demo-org.com` | Camioneta · Miguel Torres |
| 6 | José Castillo | `tecnico06@demo-org.com` | Camioneta · José Castillo |
| 7 | Pedro Vargas | `tecnico07@demo-org.com` | Camioneta · Pedro Vargas |
| 8 | Andrés Morales | `tecnico08@demo-org.com` | Camioneta · Andrés Morales |
| 9 | Diego Jiménez | `tecnico09@demo-org.com` | Camioneta · Diego Jiménez |
| 10 | Jorge Rojas | `tecnico10@demo-org.com` | Camioneta · Jorge Rojas |
| 11 | Raúl Mendoza | `tecnico11@demo-org.com` | Camioneta · Raúl Mendoza |
| 12 | Fernando Ortiz | `tecnico12@demo-org.com` | Camioneta · Fernando Ortiz |
| 13 | Ricardo Silva | `tecnico13@demo-org.com` | Camioneta · Ricardo Silva |
| 14 | Manuel Navarro | `tecnico14@demo-org.com` | Camioneta · Manuel Navarro |
| 15 | Héctor Ruiz | `tecnico15@demo-org.com` | Camioneta · Héctor Ruiz |

## Inventario

- Fuente: `docs/bodega/partes.pdf` (kit «3 TON HOME MATERIALS FROM SCRATCH») y `docs/bodega/bodega.pdf` (carrito de material frecuente) de AC Pro.
- Transcrito en `backend/scripts/qa_data/catalogo_ac_pro.csv` (244 artículos). La cantidad del PDF entra como conteo inicial; los códigos repetidos en los dos PDF suman sus cantidades.
- Con serial: las dos unidades de equipo (85980 y 85977).
- La lista «Instalación 3 ton desde cero» está en `backend/scripts/qa_data/kit_3ton.csv`.

## Datos para la organización ajena (pruebas de aislamiento)

- `admin@otra-org.com`, cliente «Cliente Ajeno QA», artículo «Artículo Ajeno QA» (SKU `AJENO-1`).

## Procedimientos de preparación

### P-01 · Obra nacida de un expediente aprobado (unos 25 min)

1. Como Vicky: VEN-004 con una puerta nueva (cambiar el número: 301, 302, …) y un cliente nuevo.
2. Como Andrés: aceptar todos los documentos (REV-001 sin rechazar ninguno).
3. Avanzar con el programa y aprobar con un código nuevo (`AZ-QA-0002`, …) como en REV-003.
4. Anotar el número del expediente y de la obra.

### P-02 · Obra lista para instalar (unos 15 min más)

1. P-01.
2. INS-001 (técnico y fecha) e INS-002 (permiso aprobado).

### P-03 · Programas listos para vender y cobrar (unos 15 min, una sola vez después de reiniciar la base)

La base limpia trae los dos programas sin zonas ni tarifas. Sin esto, la venta dice «Elige primero el programa del expediente» y el cobro dice «no tiene tarifa vigente» o «la dirección no está en la zona».

1. **Zona de venta del vendedor**, en Configuración de programas:
   - una zona de Arizona (Phoenix, AZ) para Eficiencia de Arizona;
   - una de California (San Fernando, CA) para TECH Clean California;
   - asignar a Vicky (y a Valeria, si va a vender) en cada una.
2. **Tarifa vigente de cada programa**, en Facturación y cobros › configuración del programa: por ejemplo USD 6,500.00 desde hace un mes.
3. **Zona de cobro de cada programa** (ciudad o código postal con vigencia): Phoenix para Arizona y San Fernando para TECH.
4. TECH no exige inspección este año: desactivar ese requisito en la configuración de cobro de TECH.

El lote 2 por API (`ejecucion/lote2.py`) hace estos cuatro pasos solo.

## Llaves de servicios externos

- **Stripe y Plaid:** van solo en `backend/.env` local, en modo de prueba, nunca en el repositorio. Pedirlas a Mateo por un canal privado. Sin ellas, PAR-004 y FIN-004 quedan BLOQUEADOS.
- **Correo:** en modo consola los enlaces salen en `docker compose logs api`.
- **SMS (Masiv):** por verificar (módulo 7); fuera de este ciclo.

## Limpiar los intentos de ingreso (si una prueba bloquea un usuario)

```
docker compose exec redis sh -c 'redis-cli --scan --pattern "ratelimit:*" | xargs -r redis-cli del'
```
