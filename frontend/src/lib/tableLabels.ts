/**
 * Etiquetas de columna para las tablas hechas a mano (las que no usan
 * `DataTable`): copia el título de cada columna a `data-label` de sus celdas,
 * igual que hace `DataTable`. Con eso la regla común de `sistema.css` vuelve
 * cualquier tabla una tarjeta por fila en el celular, con cada dato rotulado
 * (QA de José, 31 oct: Listas, Salidas y otras se cortaban a lo ancho).
 *
 * Observa el contenido de la app porque las tablas se pintan después de
 * cargar sus datos. Solo escribe el atributo si cambia, así que no se dispara
 * a sí misma.
 */
function rotular(tabla: HTMLTableElement) {
  const titulos = Array.from(tabla.tHead?.rows[0]?.cells ?? []).map((th) => th.textContent?.trim() ?? "");
  if (!titulos.some(Boolean)) return;
  for (const cuerpo of Array.from(tabla.tBodies)) {
    for (const fila of Array.from(cuerpo.rows)) {
      let columna = 0;
      for (const celda of Array.from(fila.cells)) {
        const titulo = celda.colSpan > 1 ? "" : titulos[columna] ?? "";
        if (celda.getAttribute("data-label") !== titulo) celda.setAttribute("data-label", titulo);
        columna += celda.colSpan;
      }
    }
  }
}

export function startTableLabels(raiz: HTMLElement = document.body) {
  let pendiente = false;
  const pasar = () => {
    pendiente = false;
    raiz.querySelectorAll<HTMLTableElement>(".app-content table:not(.data-table)").forEach(rotular);
  };
  const observador = new MutationObserver(() => {
    if (pendiente) return;
    pendiente = true;
    requestAnimationFrame(pasar);
  });
  observador.observe(raiz, { childList: true, subtree: true });
  pasar();
  return () => observador.disconnect();
}
