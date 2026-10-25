"""Genera `docs/pruebas QA JJ/`. Uso: python gen.py <raiz del repo>"""
import importlib.util
import sys
from collections import OrderedDict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from base import COMMIT, archivo, escribir  # noqa: E402
import m_auth, m_ventas, m_campo, m_bodega, m_cobro, m_turnos, m_seguridad  # noqa: E402,E401

RAIZ = Path(sys.argv[1])
DEST = RAIZ / "docs" / "pruebas QA JJ"
ESC = DEST / "escenarios"
TODOS = m_auth.E + m_ventas.E + m_campo.E + m_bodega.E + m_cobro.E + m_turnos.E + m_seguridad.E

ids = [e["id"] for e in TODOS]
assert len(ids) == len(set(ids)), "IDs repetidos"
for e in TODOS:
    for k in ("id", "slug", "nombre", "modulo", "prioridad", "tipo", "tiempo", "objetivo", "pre", "datos", "pasos",
              "esperado", "validaciones"):
        assert k in e, (e.get("id"), k)


def hm(minutos):
    h, m = divmod(int(round(minutos)), 60)
    return f"{h} h {m:02d} min" if h else f"{m} min"


def w(nombre, texto):
    (DEST / nombre).write_text(texto.strip() + "\n", encoding="utf-8")


# ---------------------------------------------------------------- índice
def indice():
    por_mod = OrderedDict()
    for e in TODOS:
        por_mod.setdefault(e["modulo"], []).append(e)
    filas = []
    for e in TODOS:
        est = e.get("estado", "Pendiente")
        t = f"{e['tiempo']}" + (f" + {e['prep']} prep." if e.get("prep") else "")
        filas.append(f"| {e['id']} | {e['modulo']} | {e['nombre']} | {e['prioridad']} | {e['tipo']} | "
                     f"[{archivo(e)}](escenarios/{archivo(e)}) | {est} | {t} | | | | |")
    resumen = []
    for mod, es in por_mod.items():
        ej = sum(x["tiempo"] for x in es)
        pr = sum(x.get("prep", 0) for x in es)
        p0 = sum(1 for x in es if x["prioridad"] == "P0")
        bl = sum(1 for x in es if x.get("estado", "").startswith("Bloqueado"))
        resumen.append(f"| {mod} | {len(es)} | {p0} | {bl} | {hm(ej)} | {hm(pr)} | 0 | 0 | 0 |")
    tot_ej = sum(x["tiempo"] for x in TODOS)
    tot_pr = sum(x.get("prep", 0) for x in TODOS)
    tot_bl = sum(1 for x in TODOS if x.get("estado", "").startswith("Bloqueado"))
    tot_p0 = sum(1 for x in TODOS if x["prioridad"] == "P0")
    return f"""
# Plan de QA manual · Delta HVAC CRM

Carpeta de pruebas de José Javier Miranda. Versión de partida: `{COMMIT}`. Creada el 25 de octubre de 2026.

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
{chr(10).join(resumen)}
| **Total** | **{len(TODOS)}** | **{tot_p0}** | **{tot_bl}** | **{hm(tot_ej)}** | **{hm(tot_pr)}** | 0 | 0 | 0 |

## Avance

- Ejecutados: 0 de {len(TODOS)} (0 %).
- Aprobados: 0 · Fallidos: 0 · Bloqueados: {tot_bl} (D-001 y llaves de Stripe/Plaid).
- Defectos abiertos: ver `01_REGISTRO_DEFECTOS.md`.

## Escenarios

| ID | Módulo | Escenario | Prioridad | Tipo | Archivo | Estado | Tiempo estimado (min) | Tiempo real | Defectos | Reejecución | Observaciones |
|---|---|---|---|---|---|---|---|---|---|---|---|
{chr(10).join(filas)}

## Documentos de control

- `01_REGISTRO_DEFECTOS.md`: defectos con su estado.
- `02_PLAN_REGRESION.md`: qué volver a correr después de cada corrección.
- `03_ESTIMACION_QA.md`: cuánto toma el ciclo completo.
- `04_DATOS_DE_PRUEBA.md`: usuarios, técnicos, inventario, procedimientos de preparación y cómo reiniciar la base.
- `05_MATRIZ_PERMISOS.md`: qué puede hacer cada rol, sacado del código.
"""


# ---------------------------------------------------------------- defectos
DEFECTOS = """
# Registro de defectos

Cada defecto con su ID `D-###`, en orden de aparición. Un defecto solo pasa a **Cerrado** después de reejecutar el escenario que lo encontró y su regresión.

**Estados:** Abierto · En análisis · En corrección · Corregido (pendiente de validar) · Cerrado · No es defecto · Diferido (con aprobación).

## Resumen

| ID | Título | Módulo | Prioridad | Estado | Encontrado en | Responsable | Fecha |
|---|---|---|---|---|---|---|---|
| D-001 | No existe la visita fallida de instalación, el reagendamiento con límite ni la cancelación de la obra | Instalación en campo / Bodega | P0 | Abierto | Diagnóstico de código (INS-010 a INS-012) | José Javier Miranda (paquetes de Mateo: avisarle) | 2026-10-25 |
| D-002 | El margen negativo en Rentabilidad se corta y muestra «$-80,705.0…» con formato «$-» | Finanzas | P2 | Abierto | Toma de capturas del manual (FIN-005) | Mateo Mazo | 2026-10-25 |

## D-001 · Visita fallida, reagendamiento con límite y cancelación de la obra

- **Módulo:** Instalación en campo (`field_ops`), Bodega (`warehouse`) y Proyectos.
- **Prioridad:** P0. Es un camino diario del negocio y hoy no tiene salida en el sistema.
- **Estado:** Abierto.
- **Encontrado en:** diagnóstico de código previo al QA (25 de octubre de 2026).
- **Qué pasa hoy (verificado en el código):**
  - La obra no tiene forma de registrar «llegué y el cliente no estaba». Solo se puede cambiar la fecha.
  - El estado `cancelled` de la obra existe, pero no hay acción que lo use: la edición de la obra solo acepta título y notas.
  - No hay contador ni límite de reagendamientos.
- **Qué se espera (lo pidió José el 25 de octubre de 2026):**
  1. El técnico registra la visita fallida con el motivo (cliente no estaba, no dejó entrar, falta material, otro), una nota y una foto con GPS.
  2. La obra vuelve a «por agendar» sin técnico ni fecha, y Administración recibe el aviso.
  3. Hay un contador de visitas fallidas y un límite que se configura por organización.
  4. Al llegar al límite ya no se reagenda sola: Administración decide entre cancelar o autorizar un intento más.
  5. Cancelar exige motivo, deja la obra en solo lectura y obliga a resolver el material: se reintegra a bodega o se traslada a otra obra o camioneta.
  6. Nada de esto cambia la etapa del expediente por fuera de `advance_case()` / `transition()`.
  7. Cada paso tiene su permiso, su prueba automática y queda en el manual.
- **Escenarios relacionados:** INS-010, INS-011, INS-012, BOD-006.
- **Evidencia:** no hay ruta en `field_ops/router.py` ni en `projects` que registre la visita fallida o cancele la obra.
- **Análisis / causa:** el alcance original solo cubría el camino de instalación exitosa.
- **Corrección:**
- **Commit:**
- **Validación (escenarios reejecutados):**
- **Tiempos:** análisis · corrección · reejecución.

## D-002 · Margen negativo cortado en Rentabilidad

- **Módulo:** Finanzas › Conciliación y rentabilidad.
- **Prioridad:** P2. Es visual y el dato es correcto, pero se lee mal.
- **Estado:** Abierto.
- **Encontrado en:** captura `rentabilidad` del manual de usuario (25 de octubre de 2026).
- **Qué pasa:** con pérdida, la columna del margen muestra «$-80,705.0…»: el número se corta y el signo queda después del símbolo.
- **Qué se espera:** «-$80,705.00» completo (o entre paréntesis), sin cortarse a 390 px ni en escritorio.
- **Escenarios relacionados:** FIN-005.
- **Evidencia:** `docs/manual/capturas/` (figura de Rentabilidad).
- **Responsable:** paquete de Mateo (`finance`): avisarle antes de tocarlo.
- **Corrección:**
- **Commit:**
- **Validación:**

## Plantilla para defectos nuevos

```
## D-### · Título corto

- Módulo:
- Prioridad: P0 / P1 / P2
- Estado: Abierto
- Encontrado en: escenario y paso
- Pasos para reproducir:
- Resultado obtenido:
- Resultado esperado:
- Evidencia: capturas, ids y respuesta HTTP
- Análisis / causa:
- Corrección y commit:
- Validación (escenarios reejecutados):
- Tiempos: análisis · corrección · reejecución
```
"""


# ---------------------------------------------------------------- regresión
def regresion():
    p0 = [e for e in TODOS if e["prioridad"] == "P0" and not e.get("estado", "").startswith("Bloqueado")]
    humo = ["AUTH-001", "VEN-004", "REV-003", "INS-003", "INS-004", "INS-005", "COB-001", "COB-003", "BOD-006",
            "SEC-001", "API-001"]
    t_humo = sum(e["tiempo"] for e in TODOS if e["id"] in humo)
    t_p0 = sum(e["tiempo"] for e in p0)
    filas_p0 = "\n".join(f"| {e['id']} | {e['nombre']} | {e['tiempo']} |" for e in p0)
    return f"""
# Plan de regresión

Qué volver a correr después de cada corrección, para confirmar que lo corregido no rompió otra cosa.

## 1. Siempre, antes de pasar una corrección a QA (automático)

Desde la raíz del repo, con Docker arriba:

| Qué | Comando | Debe dar |
|---|---|---|
| Pruebas del backend | `docker compose exec -T api python -m pytest -q -p no:cacheprovider` | 0 fallos (CI además exige cobertura ≥ 70 %) |
| Tipos y build del frontend | `docker compose exec -T frontend npm run build` | sin errores |
| Reglas de hooks de React | `python frontend/scripts/check_hooks.py` | sin hallazgos |
| Lint del backend (CI) | `docker compose exec -T api python -m ruff check app/api app/db app/modules/crm app/modules/field_ops app/modules/users` (lo mismo que corre CI) | sin hallazgos |

La integración continua de GitHub Actions corre lo mismo en `main`, `CadenaB` y `cadenaA`.

## 2. Humo: después de cada corrección ({hm(t_humo)})

El recorrido mínimo del negocio, de la puerta al pago:

{chr(10).join(f"- {i}" for i in humo)}

## 3. Por módulo tocado

| Si la corrección tocó… | Reejecutar además |
|---|---|
| `auth`, `users`, `roles`, `shared/permissions.py` | AUTH-*, SEC-003, SEC-007, FIN-006, TEC-002 |
| `cases`, `crm`, `programs` | VEN-*, REV-*, API-006, SEC-008 |
| `field_ops`, `projects` | INS-*, TEC-*, COB-004 |
| `warehouse` | BOD-*, INS-003, INS-014, FIN-005 |
| `billing`, `payments` | COB-*, PAR-*, CON-002 |
| `finance`, `banking` | FIN-* |
| `attendance`, `map` | TUR-* |
| `notifications`, `search` | NOT-*, BUS-* |
| `shared/files` | SEC-005, SEC-006, INS-004, INS-015 |
| `shared/pagination.py` o cualquier listado | API-001 a API-003 |

## 4. Antes de salir a producción: todos los P0 ({len(p0)} escenarios, {hm(t_p0)})

| ID | Escenario | Min |
|---|---|---|
{filas_p0}

Más los escenarios bloqueados una vez se desbloqueen (D-001 y llaves de Stripe/Plaid).

## 5. Reglas

- Cada reejecución se anota en la sección 12 del escenario y en la columna «Reejecución» del índice.
- Si la regresión encuentra un fallo nuevo, es un defecto nuevo (`D-###`), no se reabre el anterior.
- La base se reinicia (`04_DATOS_DE_PRUEBA.md`) antes de la regresión completa de P0.
"""


# ---------------------------------------------------------------- estimación
def estimacion():
    por_mod = OrderedDict()
    for e in TODOS:
        por_mod.setdefault(e["modulo"], []).append(e)
    filas = []
    tot = dict(ej=0, pr=0)
    for mod, es in por_mod.items():
        ej = sum(x["tiempo"] for x in es)
        pr = sum(x.get("prep", 0) for x in es)
        tot["ej"] += ej
        tot["pr"] += pr
        filas.append(f"| {mod} | {len(es)} | {hm(ej)} | {hm(pr)} | {hm(ej + pr)} |")
    base = tot["ej"] + tot["pr"]
    evid = base * 0.15
    analisis = base * 0.20
    reej = base * 0.25
    total = base + evid + analisis + reej
    dias = total / 60 / 6
    return f"""
# Estimación del ciclo de QA

Tiempos estimados de una persona que ya conoce la aplicación. Se reemplazan por los reales a medida que se ejecuta (columna «Tiempo real» del índice).

## Ejecución por módulo

| Módulo | Escenarios | Ejecución | Preparación | Subtotal |
|---|---|---|---|---|
{chr(10).join(filas)}
| **Total** | **{len(TODOS)}** | **{hm(tot['ej'])}** | **{hm(tot['pr'])}** | **{hm(base)}** |

La preparación es la de los escenarios que necesitan datos propios (por ejemplo, otra obra completa). Los demás reutilizan lo que dejó el anterior, por eso el orden del índice importa.

## Ciclo completo

| Concepto | Supuesto | Tiempo |
|---|---|---|
| Ejecución y preparación | suma de los escenarios | {hm(base)} |
| Evidencias y registro | 15 % de la ejecución | {hm(evid)} |
| Análisis de defectos | 20 % (supone que 1 de cada 4 escenarios encuentra algo) | {hm(analisis)} |
| Reejecuciones y regresión | 25 % | {hm(reej)} |
| **Total QA** | | **{hm(total)}** |

Con 6 horas efectivas de prueba al día: **unos {dias:.1f} días hábiles** para una persona.

## Fuera de esta cuenta

- **Corrección de defectos:** depende de lo que aparezca. Se registra por defecto en `01_REGISTRO_DEFECTOS.md`.
- **D-001** (visita fallida, límite de reagendamiento y cancelación): desarrollo estimado en 1,5 a 2 días con pruebas automáticas, manual y aviso a Mateo; luego INS-010 a INS-012 (1 h 20 min).
- **Stripe y Plaid:** PAR-004 y FIN-004 (45 min) cuando estén las llaves de prueba.
- **Prueba en celular real sobre Render:** ya hecha antes; se repite solo si cambia algo de campo.

## Supuestos

- Docker local estable y la base reiniciada al empezar.
- Los porcentajes de evidencias, análisis y reejecución son supuestos de arranque: se ajustan con los tiempos reales de la primera semana.
"""


# ---------------------------------------------------------------- datos
def datos():
    tecnicos = ["Tito Técnico | tecnico@demo-org.com"] + [
        f"{n} | tecnico{i:02d}@demo-org.com" for i, n in enumerate([
            "Toño Segundo", "Carlos Ramírez", "Luis Herrera", "Miguel Torres", "José Castillo", "Pedro Vargas",
            "Andrés Morales", "Diego Jiménez", "Jorge Rojas", "Raúl Mendoza", "Fernando Ortiz", "Ricardo Silva",
            "Manuel Navarro", "Héctor Ruiz"], start=2)]
    filas_t = "\n".join(f"| {i} | {t.split(' | ')[0]} | `{t.split(' | ')[1]}` | Camioneta · {t.split(' | ')[0]} |"
                        for i, t in enumerate(tecnicos, start=1))
    return f"""
# Datos de prueba

Todo vive en la base local de Docker. Clave de todos los usuarios: `ChangeMe123!`.

## Reiniciar la base al estado inicial

Borra TODA la base local y la vuelve a cargar (se niega a correr fuera de `ENVIRONMENT=development` o contra otra base):

```
docker compose exec api python -m scripts.seed_qa --reiniciar --si-borrar-todo
docker compose restart worker beat
```

Sin `--reiniciar` solo completa lo que falte (correrlo dos veces no duplica nada).

Respaldo de la base anterior al QA (25 de octubre de 2026, 10:13): `C:\\Users\\JHOANNA\\crm-respaldos\\crm-antes-de-QA-20261025-1013.dump`. Para volver a ella:

```
docker compose cp C:\\Users\\JHOANNA\\crm-respaldos\\crm-antes-de-QA-20261025-1013.dump postgres:/tmp/r.dump
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
{filas_t}

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

### P-03 · Cobro del programa configurado (unos 10 min, una sola vez)

1. Como admin: **Configuración de programas** › Eficiencia de Arizona.
2. Verificar que el programa tenga su valor de cobro y su checklist de radicación. Si falta, completarlo y anotarlo en el escenario (no es un defecto si el dato simplemente no se había cargado).

## Llaves de servicios externos

- **Stripe y Plaid:** van solo en `backend/.env` local, en modo de prueba, nunca en el repositorio. Pedirlas a Mateo por un canal privado. Sin ellas, PAR-004 y FIN-004 quedan BLOQUEADOS.
- **Correo:** en modo consola los enlaces salen en `docker compose logs api`.
- **SMS (Masiv):** por verificar (módulo 7); fuera de este ciclo.

## Limpiar los intentos de ingreso (si una prueba bloquea un usuario)

```
docker compose exec redis sh -c 'redis-cli --scan --pattern "ratelimit:*" | xargs -r redis-cli del'
```
"""


# ---------------------------------------------------------------- permisos
def matriz():
    spec = importlib.util.spec_from_file_location("perm", RAIZ / "backend" / "app" / "shared" / "permissions.py")
    perm = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(perm)
    roles = ["organization_admin", "admin_staff", "salesperson", "field_technician", "accounting", "management"]
    cortos = {"organization_admin": "Admin", "admin_staff": "Administración", "salesperson": "Vendedor",
              "field_technician": "Técnico", "accounting": "Contabilidad", "management": "Gerencia"}
    tiene = {r: set(perm.DEFAULT_ROLE_PERMISSIONS[r]) for r in roles}
    filas = []
    for code, desc in perm.PERMISSION_CATALOG:
        marcas = " | ".join("✔" if code in tiene[r] else "" for r in roles)
        filas.append(f"| `{code}` | {desc} | {marcas} | |")
    cuentas = " | ".join(str(len(tiene[r])) for r in roles)
    return f"""
# Matriz de permisos por rol

Sacada del código (`backend/app/shared/permissions.py`, `DEFAULT_ROLE_PERMISSIONS`) en `{COMMIT}`. Es lo que traen los roles de sistema al crear la organización; el Administrador puede cambiarlos en **Roles y permisos**.

En SEC-003 se prueba cada fila por la API con el token de cada rol y se anota en la última columna si coincide (✔) o el defecto (`D-###`).

| Permiso | Qué permite | {" | ".join(cortos[r] for r in roles)} | Verificado en SEC-003 |
|---|---|{"---|" * len(roles)}---|
{chr(10).join(filas)}
| **Total** | | {cuentas} | |
"""


DEST.mkdir(parents=True, exist_ok=True)
ESC.mkdir(exist_ok=True)
n = escribir(ESC, TODOS)
w("00_INDICE_GENERAL.md", indice())
if not (DEST / "01_REGISTRO_DEFECTOS.md").exists():
    w("01_REGISTRO_DEFECTOS.md", DEFECTOS)
w("02_PLAN_REGRESION.md", regresion())
w("03_ESTIMACION_QA.md", estimacion())
w("04_DATOS_DE_PRUEBA.md", datos())
w("05_MATRIZ_PERMISOS.md", matriz())
print(f"{len(TODOS)} escenarios ({n} archivos nuevos)")
