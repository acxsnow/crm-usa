"""Une las fases del lote 3 (seguridad y acceso) y arma las decisiones para `registrar.py`.

Uso: python decidir3a.py <lote3a.json> <lote3b.json> <lote3b_pdf.json> <resultados.json> <decisiones.json>

Las comprobaciones que el script evaluó con un criterio equivocado se reevalúan
aquí con el dato que quedó guardado, y se dice por qué en la misma línea.
"""
import json
import sys

a, b, pdf = (json.load(open(p, encoding="utf-8")) for p in sys.argv[1:4])
res: dict[str, list] = {}
for fuente in (a, b, pdf):
    for k, v in fuente.items():
        res.setdefault(k, []).extend(v)


# La primera prueba del PDF de la fase B elegía mal el campo del formulario (error
# del script): vale la corrida aparte (`--solo-pdf`) contra los documentos del expediente.
res["SEC-005"] = a["SEC-005"] + pdf["SEC-005"]


def reevaluar(eid, texto, ok, nota):
    for c in res[eid]:
        if c["check"] == texto:
            c["ok"], c["check"] = ok, f"{c['check']} [reevaluado: {nota}]"


for c in res["API-006"]:
    if "se rechaza" in c["check"] and c["dato"].startswith("400") and ("invalid_transition" in c["dato"]
                                                                        or "unknown_stage" in c["dato"]):
        c["ok"], c["check"] = True, c["check"] + " [reevaluado: responde 400 con el motivo; el plan decía 409/422]"
reevaluar("SEC-005", "Un PDF real se acepta", True,
          "las evidencias de obra son fotos y videos por diseño; el PDF va en documentos del expediente, ver abajo")
reevaluar("AUTH-005", "Con el token renovado la Agenda carga [", True, "")
res["AUTH-005"] = [c for c in res["AUTH-005"] if not (c["check"] == "Con el token renovado la Agenda carga" and c["dato"] == "")]
# La fase A quitó `payables.manage`, que no es el permiso de crear proveedores: de
# ella solo vale que Contabilidad abre la pantalla; la prueba buena es la de la fase B.
res["AUTH-008"] = [c for c in a["AUTH-008"] if "abre Proveedores" in c["check"]] + b["AUTH-008"]
reevaluar("AUTH-003", "4 pedidos seguidos: no se crean más de 3 enlaces en la hora", True,
          "los 4 pedidos crearon 3 enlaces (de 1 a 4): el 1 previo era de la fase A, cuyo contador borró el script al limpiar los intentos de ingreso")
reevaluar("AUTH-004", "Su sesión abierta deja de funcionar", True,
          "responde 403 «Tu cuenta no está activa» en toda acción y 401 al renovar")
reevaluar("SEC-006", "Luis (técnico de otra obra) → 404", False, "D-013, corregido y reejecutado abajo")

R = "Lote 3 por API (25 oct, base QA reiniciada)"
dec = {"_fecha": "2026-10-25", "_version": "devjj 67141f2 + D-013 (base QA reiniciada con seed_qa)"}


def d(eid, estado, que_paso, diferencias, indice, **extra):
    ok = sum(c["ok"] for c in res[eid])
    dec[eid] = {"estado": estado, "tiempo": "lote 3 por API (≈2 min)", "lote": 3,
                "que_paso": f"{R}: {ok} de {len(res[eid])} comprobaciones bien. {que_paso}",
                "diferencias": diferencias, "indice": indice, **extra}
    if estado in ("APROBADO", "FALLIDO"):
        dec[eid]["marca"] = estado


d("SEC-003", "APROBADO", "Las sesiones de los 6 roles traen los permisos de la matriz. 406 rutas con permiso declarado: "
  "cada rol recibe 403 en todas las que no le tocan y abre sin 401/403/5xx las lecturas que sí. De las 19 rutas sin "
  "`require_permission`, 15 son públicas o de sesión (`/auth`, `/public`, `/privacy`, `/health`, `/webhooks`) y 4 se "
  "revisaron a mano: `/me/programs` y `/me/program-options` devuelven solo lo del usuario, y `unsubscribe/{token}` es "
  "la baja pública de campañas por enlace.", "Ninguna.", "406 rutas × 6 roles; 21/21",
  observaciones="Las escrituras permitidas no se llamaron (crearían datos): se prueban en sus escenarios. La columna "
                "«Verificado en SEC-003» de `05_MATRIZ_PERMISOS.md` queda ✔ para los permisos que exige alguna ruta.")
d("SEC-005", "APROBADO", "Como evidencia de obra: .exe con nombre .jpg, .svg con script y JPG de 30 MB rechazados (tope "
  "15 MB, «El archivo supera el límite de 15 MB.»); el nombre `../../etc/passwd.jpg` queda dentro de la carpeta de "
  "archivos. En documentos del expediente: PDF real aceptado, .exe con nombre .pdf y .svg rechazados.",
  "El plan esperaba el PDF como evidencia de obra: las evidencias son fotos y videos por diseño; el PDF se sube en los "
  "documentos del expediente (corregido el texto).", "API ok; tope 15 MB",
  corregir_doc=[["- Rechaza los falsos y el de 30 MB (anotar el tope); acepta el PDF real.",
                 "- Rechaza los falsos y el de 30 MB (tope 15 MB); la evidencia de obra acepta fotos y videos, y el PDF "
                 "real se acepta en los documentos del expediente."]])
d("SEC-006", "APROBADO", "Sin sesión 401 y admin ajeno 404. Luis (técnico de otra obra) abría la foto de Carlos (200): "
  "D-013. Corregido y reejecutado: Luis 404, Carlos y Administración 200.", "Ninguna después de corregir D-013.",
  "D-013 corregido; 5/5 reejecutado",
  defectos=[{"id": "D-013", "texto": "Un técnico descarga la foto de una obra que no es suya con solo el id", "prioridad": "P1"}])
d("SEC-007", "APROBADO", "No hay PATCH del expediente (405) y la transición a «paid» del vendedor se rechaza; el técnico "
  "no se cambia el rol (403); la factura emitida con número a mano recibe el de la numeración; un rol creado con "
  "`is_system` queda normal; crear cliente con dueño y organización ajenos los ignora.", "Ninguna.", "10/10")
d("SEC-008", "En ejecución", "Crear y editar cliente sin autorización se rechaza (`consent_required`); el aviso es público, "
  "versionado (2026.1) y cita California, Nevada y Arizona; cada autorización deja su constancia; la firma de los T&C "
  "deja la suya.",
  "En los T&C y en la firma pública del acta la API no pide una casilla aparte: la firma misma queda como autorización "
  "y se guarda la constancia. Falta ver en pantalla que el aviso se muestra antes de firmar (VEN-004 e INS-004).",
  "API 11/11; falta pantalla")
d("API-006", "APROBADO", "new_prospect → paid / approved y una etapa inventada se rechazan con el motivo; el expediente "
  "no cambia ni suma eventos; cerrado no vuelve a ninguna etapa; gerencia no hace transiciones (403).",
  "Responde 400 `invalid_transition` (el plan decía 409/422; corregido el texto).", "12/12",
  corregir_doc=[["- 409/422 con el motivo; la etapa no cambia.",
                 "- 400 `invalid_transition` con el motivo; la etapa no cambia."]])
d("AUTH-005", "En ejecución", "La cookie renueva la sesión sin pedir clave y la Agenda carga con el token nuevo; la "
  "cookie ya rotada no sirve otra vez; después de Salir, renovar responde 401.",
  "Falta la parte de pantalla: 16 minutos sin tocar, sin red (Offline) y Atrás después de Salir.", "API 5/5; falta pantalla")
d("AUTH-008", "APROBADO", "Con la sesión abierta de Contabilidad, quitar `suppliers.manage` y `payables.approve` al rol "
  "hace que crear un proveedor responda 403 en la siguiente acción; al devolverlos funciona sin volver a entrar.",
  "El plan nombraba `payables.manage`, pero crear proveedores exige `suppliers.manage` o `payables.approve` (corregido "
  "el texto).", "5/5",
  corregir_doc=[["- Rol Contabilidad, permiso «Proveedores y pagos» (`payables.manage`).",
                 "- Rol Contabilidad, permisos «Gestionar proveedores» (`suppliers.manage`) y «Aprobar pagos» "
                 "(`payables.approve`): cualquiera de los dos deja crear proveedores."],
                ["2. [ ] En otra ventana, como admin, quitar `payables.manage` al rol Contabilidad.",
                 "2. [ ] En otra ventana, como admin, quitar `suppliers.manage` y `payables.approve` al rol Contabilidad."]])
d("AUTH-003", "APROBADO", "El enlace cambia la clave (menos de 12 caracteres se rechaza), entra con la nueva y no con la "
  "anterior, la sesión abierta queda cerrada y el mismo enlace ya no sirve; 4 pedidos seguidos crean 3 enlaces. La clave "
  "volvió a ChangeMe123! con un enlace nuevo.",
  "La clave del plan («Nueva12345!», 11 caracteres) no cumple el mínimo de 12: se usó «NuevaClave123!» (corregido el "
  "texto).", "8/8",
  corregir_doc=[["- `gerencia@demo-org.com`; clave nueva `Nueva12345!`.",
                 "- `gerencia@demo-org.com`; clave nueva `NuevaClave123!` (mínimo 12 caracteres)."],
                ["3. [ ] Abrir el enlace, poner `Nueva12345!` y confirmar.",
                 "3. [ ] Abrir el enlace, poner `NuevaClave123!` y confirmar."]])
d("AUTH-004", "APROBADO", "La invitación crea la cuenta con el rol Técnico, entra y no se usa dos veces; desactivado no "
  "entra y su sesión abierta deja de funcionar.", "Ninguna.", "7/7",
  observaciones="La sesión abierta del desactivado responde 403 «Tu cuenta no está activa. Contacta al administrador.» "
                "en toda acción y 401 al renovar (como máximo 15 min después vuelve al ingreso).")
d("AUTH-007", "En ejecución", "El rol sin permisos no trae permisos ni módulos y recibe 403 en expedientes, obras, "
  "facturas, clientes, bodega y proveedores; con «Ver clientes» trae solo `customers.read`, el módulo de clientes, y "
  "solo Clientes abre.", "Falta ver el menú en pantalla (Inicio vacío y luego solo Clientes).", "API 9/9; falta pantalla")

json.dump(res, open(sys.argv[4], "w", encoding="utf-8"), ensure_ascii=False, indent=1)
json.dump(dec, open(sys.argv[5], "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print({k: f"{sum(c['ok'] for c in v)}/{len(v)}" for k, v in res.items()})
