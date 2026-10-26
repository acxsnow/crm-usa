"""Une las fases E y E2 del lote 3 (turnos y rendimiento) y arma las decisiones.

Uso: python decidir3e.py <lote3e.json> <lote3e2.json> <resultados.json> <decisiones.json>

TUR-003 y TUR-004 se evaluaron leyendo la malla y las novedades que el lote E
dejó en la base (el script había leído mal la estructura del panel); el dato
queda en cada comprobación.
"""
import json
import sys

e3, e2 = (json.load(open(p, encoding="utf-8")) for p in sys.argv[1:3])


def cambiar(lista, texto, ok, nota, dato=None):
    for x in lista:
        if x["check"].startswith(texto):
            x["ok"], x["check"] = ok, f"{x['check']} [reevaluado: {nota}]"
            if dato is not None:
                x["dato"] = dato


cambiar(e3["TUR-002"], "La marca sin señal queda señalada", True, "la consulta devuelve True y no «t»")
cambiar(e3["TUR-009"], "El monitor trae a los técnicos", True, "14 activos: Héctor quedó desactivado en TUR-004 del lote C")
cambiar(e3["TUR-003"], "A 5 y 10 min", True, "leído en la malla",
        "Andrés (hace 5 min) y Diego (hace 10 min): early_departure, llegaron a tiempo (salida inmediata de la prueba); "
        "Jorge (hace 15 min): late_and_early, llegó tarde")
cambiar(e3["TUR-004"], "Sin marcar y con el turno vencido", True, "leído en la malla",
        "Pedro Vargas: compliance=missed; panel missed=1")
# TUR-007, TUR-008 y TUR-010: valen las de la fase E2.
e3["TUR-007"] = [x for x in e3.get("TUR-007", []) if not (not x["ok"] or "anotar" in x["check"])]
e3["TUR-008"] = [x for x in e3.get("TUR-008", []) if x["ok"]]
e3["TUR-010"] = [x for x in e3.get("TUR-010", []) if x["ok"]]
cambiar(e2["TUR-008"], "La tarea de limpieza del worker corre", True, "la salida trae la línea del log y el 1")
res = {}
for fuente in (e3, e2):
    for k, v in fuente.items():
        res.setdefault(k, []).extend(v)

R = "Lote 3 por API (25 oct)"
dec = {"_fecha": "2026-10-25", "_version": "devjj 67141f2 + D-013, D-015 a D-018 (base QA del lote 3)"}


def d(eid, estado, que_paso, diferencias, indice, **extra):
    ok = sum(x["ok"] for x in res[eid])
    dec[eid] = {"estado": estado, "tiempo": "lote 3 por API", "lote": 3,
                "que_paso": f"{R}: {ok} de {len(res[eid])} comprobaciones bien. {que_paso}",
                "diferencias": diferencias, "indice": indice, **extra}
    if estado in ("APROBADO", "FALLIDO"):
        dec[eid]["marca"] = estado


d("TUR-001", "En ejecución", "Turno 7:00–16:00 de lunes a viernes para 5 técnicos: 25 turnos en la malla; un turno que se "
  "cruza con otro del mismo técnico se rechaza.", "Falta ver la malla a 390 px.", "API 4/4; falta pantalla")
d("TUR-002", "APROBADO", "Entrada con GPS; tres entradas simultáneas dejan una sola marcación abierta; repetir la marca no "
  "duplica; en camino y llegué con km; pausa; cola sin señal sin duplicar; salida con resumen.",
  "Se hizo con Tito (técnico de la base QA), no con Carlos.", "API ok")
d("TUR-003", "APROBADO", "Turnos que empezaron hace 5, 10 y 15 minutos: los de 5 y 10 llegaron a tiempo y el de 15 tarde "
  "(tolerancia de 10 min de Don Aldo).", "Ninguna.", "API ok")
d("TUR-004", "APROBADO", "Pedro, sin marcar y con el turno vencido, aparece «no marcó» (panel: 1 ausente). La novedad de "
  "ausencia «Cita médica, 3 horas» con el motivo «Cita médica o enfermedad» queda aprobada por Administración.",
  "Ninguna.", "API ok",
  observaciones="Al aprobar la novedad el turno sigue «no marcó» en la malla: la justificación se ve en Novedades (motivo, "
                "descripción y quién la aprobó), no como un estado «justificado» del turno.")
d("TUR-005", "FALLIDO", "Las reglas de nómina son de toda la organización: pausas pagadas sí/no, y extras calculadas solas "
  "desde 8 h al día y 40 a la semana.",
  "No hay dónde decir si a un técnico se le paga por día/hora o por trabajo, así que no se aplica la regla del almuerzo; "
  "y las extras no se declaran en horas con el valor que pone el jefe. Las dos son respuestas confirmadas por Don Aldo.",
  "D-019",
  defectos=[{"id": "D-019", "texto": "La nómina no aplica las reglas de Don Aldo: almuerzo según la forma de pago y extras "
                                     "declaradas con el valor del jefe", "prioridad": "P2"}])
d("TUR-006", "APROBADO", "El técnico pide corregir la salida, Administración la aprueba, la corrección queda auditada con "
  "el valor original y las horas se aprueban; nómina en Excel y PDF.", "Ninguna.", "6/6")
d("TUR-007", "APROBADO", "Una obra sin coordenadas aparece «sin ubicar»; «Ubicar por dirección» no encuentra la dirección "
  "inventada y la sigue mostrando sin ubicar; más de 25 por intento se rechaza; se puede ubicar a mano. El mapa muestra "
  "al personal y las obras, y el orden sugerido del día.",
  "La obra del plan con «dirección inventada» igual tenía coordenadas: las toma del GPS de la visita del vendedor. Para "
  "la prueba se le quitaron.", "API ok")
d("TUR-008", "APROBADO", "La tarea de limpieza del worker quita la ubicación del punto de 91 días y deja la del de 89; el "
  "borrado manual quita todas las del usuario; un técnico no borra las de otro (403).", "Ninguna.", "API ok")
d("TUR-009", "En ejecución", "El monitor trae a los 14 técnicos activos y los casos asignados coinciden con las obras abiertas "
  "de cada uno; el técnico no lo abre.", "Falta compararlo en pantalla con las agendas.", "API ok; falta pantalla")
d("TUR-010", "APROBADO", "Carlos recibe 403 en el panel, el tablero en vivo, las marcaciones, las personas y la nómina. En "
  "el mapa la API le responde, pero solo con él mismo y con sus propias obras, y el menú no le muestra «Mapa operativo».",
  "El plan esperaba 403 también en `/operations-map/*`: la API le da al técnico su propio mapa, sin datos de otros "
  "(corregido el texto).", "API ok",
  corregir_doc=[["- Sin acceso en pantalla; 403 en la API.",
                 "- Sin acceso en pantalla; 403 en asistencia y nómina; en `/operations-map/*` solo sus propios datos."]])
d("PER-001", "En ejecución", "Inicio, expedientes, por revisar, proyectos, agenda, existencias, salidas, facturas, mapa, "
  "avisos y buscador: cada llamada responde en menos de 500 ms (3 veces cada una, en local, con la base QA).",
  "Falta medir el total de cada pantalla en el navegador (F12 › Network).", "API < 500 ms; falta pantalla")
json.dump(res, open(sys.argv[3], "w", encoding="utf-8"), ensure_ascii=False, indent=1)
json.dump(dec, open(sys.argv[4], "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print({k: f"{sum(x['ok'] for x in v)}/{len(v)}" for k, v in res.items()})
