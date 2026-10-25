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
