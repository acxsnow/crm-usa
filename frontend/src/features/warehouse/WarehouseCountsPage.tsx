import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import "../billing/billing.css";
import "../programs/programs.css";
import "../notifications/notifications.css";
import "../finance/finance.css";
import "./receipts.css";
import { useAuth } from "@/features/auth/AuthContext";
import { apiErrorMessage } from "@/features/field-ops/module5Api";
import { money } from "@/features/finance/api";
import { warehouseCatalogs, warehouseKeys } from "./api";
import { PaginationControls } from "@/components/PaginationControls";
import { usePaginatedQuery } from "@/lib/usePaginatedQuery";
import { listActiveLocations, receiptKeys, registerCount, type CountResult, type CountSheetRow } from "./receiptsApi";

const num = (v: string) => {
  const n = Number(String(v).replace(",", "."));
  return Number.isFinite(n) ? n : NaN;
};
const cant = (n: number) => String(Math.round(n * 100) / 100);
const POR_PAGINA = 50;

/**
 * Conteo físico (respuesta 8: mensual; respuesta 12: el inicial, un fin de semana).
 *
 * Se elige la bodega o una camioneta, se escribe lo que se contó y la pantalla
 * muestra la diferencia con lo que dice el sistema. Solo se registran los
 * artículos con cantidad escrita: se puede contar por partes (un estante, una
 * categoría). Cada diferencia queda en el libro como ajuste del conteo.
 *
 * El «conteo inicial» es el del arranque: lo que aparece entra como inventario
 * inicial (no como ganancia) y se le puede poner el costo con que arranca.
 */
export function WarehouseCountsPage() {
  const qc = useQueryClient();
  const { hasPermission } = useAuth();
  const veCostos = hasPermission("warehouse.read") || hasPermission("warehouse.manage");
  const { data: cat } = useQuery({ queryKey: warehouseKeys.catalogs, queryFn: warehouseCatalogs, staleTime: Infinity });
  const { data: lugares = [] } = useQuery({ queryKey: receiptKeys.locations, queryFn: listActiveLocations, staleTime: 60_000 });
  const [lugar, setLugar] = useState("");
  const ubicacion = lugar || lugares.find((l) => l.kind === "warehouse")?.id || "";
  const [buscar, setBuscar] = useState("");
  const [buscado, setBuscado] = useState("");
  const [categoria, setCategoria] = useState("");
  const [soloDif, setSoloDif] = useState(false);
  // La planilla viene por páginas (búsqueda y categoría las filtra el backend).
  const lista = usePaginatedQuery<CountSheetRow>({
    key: ["warehouse-count-sheet"], path: "/warehouse/counts/sheet", pageSize: POR_PAGINA,
    params: { location_id: ubicacion || undefined, q: buscado || undefined, category: categoria || undefined },
    enabled: Boolean(ubicacion),
  });
  // Lo contado se guarda por artículo: pasar de página no lo borra, y al
  // registrar se mandan todos los contados de todas las páginas.
  const [vistos, setVistos] = useState<Record<string, CountSheetRow>>({});
  useEffect(() => {
    if (lista.items.length) setVistos((v) => ({ ...v, ...Object.fromEntries(lista.items.map((f) => [f.item_id, f])) }));
  }, [lista.items]);
  useEffect(() => {
    const t = setTimeout(() => setBuscado(buscar.trim()), 350);
    return () => clearTimeout(t);
  }, [buscar]);
  const isLoading = lista.isLoading;
  const [inicial, setInicial] = useState(false);
  const [contado, setContado] = useState<Record<string, string>>({});
  const [costos, setCostos] = useState<Record<string, string>>({});
  const [seriales, setSeriales] = useState<Record<string, string>>({});
  const [nota, setNota] = useState("");
  const [confirmar, setConfirmar] = useState(false);
  const [resultado, setResultado] = useState<CountResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const escritos = Object.keys(contado).filter((id) => contado[id] !== "" && vistos[id]).map((id) => vistos[id]);
  const malos = escritos.filter((f) => !(num(contado[f.item_id]) >= 0));
  const conDiferencia = escritos.filter((f) => num(contado[f.item_id]) !== Number(f.system_quantity));

  // «Solo con diferencia» muestra los contados de todas las páginas; si no, la página actual.
  const visibles = useMemo(() => (soloDif ? conDiferencia : lista.items),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [soloDif, lista.items, contado, vistos]);

  const guardar = useMutation({
    mutationFn: () => registerCount({
      location_id: ubicacion, initial: inicial, note: nota.trim() || null,
      lines: escritos.map((f) => ({
        item_id: f.item_id, counted_quantity: contado[f.item_id],
        unit_cost: inicial && (costos[f.item_id] ?? "") !== "" ? costos[f.item_id] : null,
        serials: inicial && f.has_serial ? (seriales[f.item_id] ?? "").split(/\n|,/).map((s) => s.trim()).filter(Boolean) : null,
      })),
    }),
    onSuccess: (r) => {
      setError(null); setResultado(r); setConfirmar(false); setContado({}); setCostos({}); setSeriales({}); setNota(""); setVistos({});
      [warehouseKeys.stock, warehouseKeys.items, warehouseKeys.movements, warehouseKeys.summary].forEach((k) =>
        qc.invalidateQueries({ queryKey: k }));
      qc.invalidateQueries({ queryKey: ["warehouse-count-sheet"] });
      window.scrollTo({ top: 0, behavior: "smooth" });
    },
    onError: (e) => { setConfirmar(false); setError(apiErrorMessage(e)); },
  });

  const nombreLugar = lugares.find((l) => l.id === ubicacion)?.name ?? "Bodega";

  return (
    <div className="billing-page notices-page fin-page">
      <header className="billing-head">
        <div>
          <h1>Conteo físico</h1>
          <p>Escribe lo que contaste; la pantalla muestra la diferencia con el sistema. Puedes contar por partes: solo se registran los artículos con cantidad escrita.</p>
        </div>
      </header>

      {resultado && (
        <div className="info-banner" role="status">
          Conteo {resultado.initial ? "inicial " : ""}de {resultado.location_name} registrado: {resultado.revisados} artículos revisados,{" "}
          {resultado.sin_cambio} sin diferencia y {resultado.ajustes.length} con {resultado.initial ? "entrada o ajuste" : "ajuste"}.
          {resultado.ajustes.length > 0 && (
            <ul>{resultado.ajustes.slice(0, 15).map((a) => (
              <li key={a.item_id}>{a.item_name}: {cant(Number(a.antes))} → {cant(Number(a.contado))} ({Number(a.diferencia) > 0 ? "+" : ""}{cant(Number(a.diferencia))})</li>
            ))}</ul>
          )}
          {resultado.ajustes.length > 15 && <p>…y {resultado.ajustes.length - 15} más (están en Movimientos).</p>}
        </div>
      )}

      <article className="acta">
        <div className="count-toolbar">
          <div className="form-field">
            <label className="form-label" htmlFor="cnt-lugar">Qué se cuenta</label>
            <select id="cnt-lugar" value={ubicacion} onChange={(e) => { setLugar(e.target.value); setContado({}); setCostos({}); setSeriales({}); setVistos({}); }}>
              {lugares.map((l) => <option key={l.id} value={l.id}>{l.name}</option>)}
            </select>
          </div>
          <div className="form-field">
            <label className="form-label" htmlFor="cnt-buscar">Buscar</label>
            <input id="cnt-buscar" value={buscar} onChange={(e) => setBuscar(e.target.value)} placeholder="Nombre, código o marca" />
          </div>
          <div className="form-field">
            <label className="form-label" htmlFor="cnt-cat">Categoría</label>
            <select id="cnt-cat" value={categoria} onChange={(e) => setCategoria(e.target.value)}>
              <option value="">Todas</option>
              {Object.entries(cat?.categories ?? {}).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
          </div>
        </div>
        <label className="billing-check">
          <input type="checkbox" checked={inicial} onChange={(e) => setInicial(e.target.checked)} />
          Es el conteo inicial (el del arranque): lo que aparece entra como inventario inicial y puedo escribir su costo
        </label>
        <label className="billing-check">
          <input type="checkbox" checked={soloDif} onChange={(e) => setSoloDif(e.target.checked)} />
          Ver solo los que tienen diferencia
        </label>

        {isLoading ? <p>Cargando artículos…</p> : (
          <table className="count-sheet">
            <thead>
              <tr>
                <th>Artículo</th>
                <th className="num">Sistema</th>
                <th>Contado</th>
                <th className="num">Diferencia</th>
                {inicial && veCostos && <th>Costo unitario</th>}
                {inicial && <th>Seriales (si aplica)</th>}
              </tr>
            </thead>
            <tbody>
              {visibles.map((f) => {
                const escrito = contado[f.item_id] ?? "";
                const sistema = Number(f.system_quantity);
                const dif = escrito === "" ? null : num(escrito) - sistema;
                return (
                  <tr key={f.item_id} className={dif ? "is-diff" : undefined}>
                    <td>
                      <strong>{f.name}</strong>
                      <small> {[f.sku, f.category_label, f.unit_label].filter(Boolean).join(" · ")}</small>
                    </td>
                    <td className="num" data-label="Sistema">{cant(sistema)}</td>
                    <td data-label="Contado">
                      <input inputMode="decimal" aria-label={`Contado de ${f.name}`} value={escrito}
                        onChange={(e) => setContado((v) => ({ ...v, [f.item_id]: e.target.value }))} />
                    </td>
                    <td className="num" data-label="Diferencia">
                      {dif === null || Number.isNaN(dif) ? "—" : dif === 0 ? "0" : (
                        <span className={dif > 0 ? "count-diff-up" : "count-diff-down"}>{dif > 0 ? "+" : ""}{cant(dif)}</span>
                      )}
                    </td>
                    {inicial && veCostos && (
                      <td data-label="Costo unitario">
                        <input inputMode="decimal" aria-label={`Costo de ${f.name}`} placeholder={f.unit_cost ? String(Number(f.unit_cost)) : ""}
                          value={costos[f.item_id] ?? ""} onChange={(e) => setCostos((v) => ({ ...v, [f.item_id]: e.target.value }))} />
                      </td>
                    )}
                    {inicial && f.has_serial && (
                      <td data-label="Seriales">
                        <textarea rows={2} aria-label={`Seriales de ${f.name}`} placeholder="Uno por línea"
                          value={seriales[f.item_id] ?? ""}
                          onChange={(e) => setSeriales((v) => ({ ...v, [f.item_id]: e.target.value }))} />
                      </td>
                    )}
                  </tr>
                );
              })}
              {visibles.length === 0 && <tr><td colSpan={5}>Ningún artículo con este filtro.</td></tr>}
            </tbody>
          </table>
        )}
        {!soloDif && <PaginationControls {...lista.controls} />}

        <div className="count-footer">
          <span>{escritos.length} contados · {conDiferencia.length} con diferencia</span>
          <div className="acta-actions">
            <button type="button" className="acta-btn is-primary" disabled={escritos.length === 0 || malos.length > 0 || guardar.isPending}
              onClick={() => setConfirmar(true)}>
              Registrar conteo
            </button>
          </div>
        </div>
        {malos.length > 0 && <p className="form-error" role="alert">Revisa la cantidad de «{malos[0].name}»: debe ser un número mayor o igual a cero.</p>}
        {error && <p className="form-error" role="alert">{error}</p>}

        {confirmar && (
          <div className="fin-box" role="dialog" aria-label="Confirmar conteo">
            <p>
              Vas a registrar el conteo {inicial ? "inicial " : ""}de <strong>{nombreLugar}</strong>: {escritos.length} artículos,{" "}
              {conDiferencia.length} con diferencia. Cada diferencia queda en el libro de movimientos y no se puede borrar
              (si te equivocas, se corrige con otro conteo).
              {veCostos && conDiferencia.length > 0 && (
                <> Valor aproximado de las diferencias: {money(conDiferencia.reduce((s, f) =>
                  s + Math.abs(num(contado[f.item_id]) - Number(f.system_quantity)) * Number(costos[f.item_id] || f.unit_cost || 0), 0).toFixed(2))}.</>
              )}
            </p>
            <div className="form-field">
              <label className="form-label" htmlFor="cnt-nota">Nota (opcional)</label>
              <input id="cnt-nota" value={nota} maxLength={1000} onChange={(e) => setNota(e.target.value)} placeholder="Ej. Conteo de noviembre, estante A" />
            </div>
            <div className="acta-actions">
              <button type="button" className="acta-btn is-primary" disabled={guardar.isPending} onClick={() => guardar.mutate()}>
                {guardar.isPending ? "Registrando…" : "Confirmar"}
              </button>
              <button type="button" className="acta-btn is-quiet" onClick={() => setConfirmar(false)}>Volver</button>
            </div>
          </div>
        )}
      </article>
    </div>
  );
}
