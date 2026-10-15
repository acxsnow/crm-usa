import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import "../billing/billing.css";
import "./sales.css";
import { useAuth } from "@/features/auth/AuthContext";
import { listPrograms } from "@/features/programs/api";
import { listUsersPage } from "@/features/users/api";
import { ApprovalDays } from "./ApprovalDays";
import { getBoard, getBoardColumn, salesKeys, type BoardColumn, type BoardFilters } from "./api";

/**
 * Paginación por ventana, por columna: cada columna tiene a lo sumo `VENTANA`
 * páginas de `PAGINA` tarjetas. Al bajar hasta el final pide la siguiente y
 * suelta la de arriba; al subir hasta el inicio pide la anterior y suelta la de
 * abajo. Así una columna con miles de expedientes nunca pesa más de
 * PAGINA × VENTANA tarjetas, y la base solo entrega una página por petición.
 */
const PAGINA = 20;
const VENTANA = 2;
/** Distancia (px) al borde de la columna a la que se pide la página siguiente o anterior. */
const MARGEN = 120;

const SUB: Record<string, string> = {
  returned: "Devuelto", pending_review: "En revisión", ready_to_submit: "Listo para el programa",
  submitted_to_program: "En el programa", program_review: "Revisión del programa",
};

type Tarjeta = BoardColumn["cases"][number];

/**
 * Expedientes por etapa (kanban, módulo 2). Los cierres tempranos (no abrió,
 * no le interesa, no califica) no se muestran salvo que se pidan. El vendedor
 * ve los suyos; Administración y Gerencia, todos, con filtros por vendedor,
 * programa y búsqueda (en el servidor, también para los totales).
 */
export function CasesBoardPage() {
  const { hasPermission } = useAuth();
  const [tempranos, setTempranos] = useState(false);
  const [buscar, setBuscar] = useState("");
  const [q, setQ] = useState("");
  const [vendedor, setVendedor] = useState("");
  const [programa, setPrograma] = useState("");
  // Espera a que se deje de escribir: una búsqueda por frase, no por tecla.
  useEffect(() => { const t = setTimeout(() => setQ(buscar.trim()), 350); return () => clearTimeout(t); }, [buscar]);

  const veTodos = hasPermission("cases.read_all");
  const puedeVendedores = veTodos && (hasPermission("users.read") || hasPermission("users.manage"));
  const puedeProgramas = hasPermission("programs.read") || hasPermission("programs.manage");
  const { data: vendedores } = useQuery({
    queryKey: ["board-salespeople"], enabled: puedeVendedores, staleTime: 5 * 60 * 1000,
    queryFn: () => listUsersPage(1, 200, { role: "salesperson", status: "active" }),
  });
  const { data: programas } = useQuery({
    queryKey: ["board-programs"], queryFn: listPrograms, enabled: puedeProgramas, staleTime: 5 * 60 * 1000,
  });

  const filtros = useMemo<BoardFilters>(() => ({
    q: q || undefined, salesperson_id: vendedor || undefined, program_id: programa || undefined,
  }), [q, vendedor, programa]);
  const hayFiltros = !!(q || vendedor || programa);

  // Revisa la revisión quien aprueba; el vendedor abre su formulario.
  const revisa = hasPermission("cases.review") || hasPermission("cases.approve");
  const { data, isLoading, isPlaceholderData } = useQuery({
    queryKey: [...salesKeys.board(tempranos), PAGINA, filtros],
    queryFn: () => getBoard(tempranos, false, PAGINA, filtros),
    placeholderData: (anterior) => anterior,
  });
  const columnas = (data ?? []).filter((c) => c.count > 0 || ["new_prospect", "pending_approval", "approved"].includes(c.code));
  // Si cambian los filtros, cada columna arranca de nuevo en su primera página.
  // Mientras llega la respuesta se muestran los datos anteriores; la columna se
  // vuelve a montar cuando llegan los del filtro nuevo (si no, se quedaba con
  // las tarjetas viejas y los totales nuevos).
  const firmaFiltros = JSON.stringify([tempranos, filtros, isPlaceholderData]);

  return (
    <div className="billing-page board-page">
      <header className="billing-head board-head">
        <div>
          <h1>Expedientes</h1>
          <p>Cada puerta con su etapa. {veTodos ? "Todos los vendedores." : "Los tuyos."}</p>
        </div>
        <div className="acta-actions">
          <label className="billing-check"><input type="checkbox" checked={tempranos} onChange={(e) => setTempranos(e.target.checked)} /> Mostrar puertas cerradas</label>
          {hasPermission("cases.create") && <Link to="/sales/visit" className="acta-btn is-primary">Tocar puerta</Link>}
        </div>
      </header>

      <div className="board-filters" role="search">
        <input type="search" aria-label="Buscar expedientes" placeholder="Buscar por expediente, dirección, ciudad o cliente"
          value={buscar} onChange={(e) => setBuscar(e.target.value)} />
        {puedeVendedores && (
          <select aria-label="Vendedor" value={vendedor} onChange={(e) => setVendedor(e.target.value)}>
            <option value="">Todos los vendedores</option>
            {(vendedores?.items ?? []).map((u) => <option key={u.id} value={u.id}>{u.full_name}</option>)}
          </select>
        )}
        {puedeProgramas && (
          <select aria-label="Programa" value={programa} onChange={(e) => setPrograma(e.target.value)}>
            <option value="">Todos los programas</option>
            {(programas ?? []).map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
          </select>
        )}
        {hayFiltros && (
          <button type="button" className="acta-btn is-quiet" onClick={() => { setBuscar(""); setQ(""); setVendedor(""); setPrograma(""); }}>
            Borrar filtros
          </button>
        )}
      </div>

      {isLoading ? <p className="acta-empty">Cargando…</p> : (
        <div className="board">
          {columnas.map((col) => (
            <ColumnaPaginada key={`${col.code}|${firmaFiltros}`} col={col} tempranos={tempranos} filtros={filtros} revisa={revisa} />
          ))}
        </div>
      )}
    </div>
  );
}

/** Una columna con su propia ventana de páginas (ver `PAGINA` y `VENTANA`). */
function ColumnaPaginada({ col, tempranos, filtros, revisa }: {
  col: BoardColumn; tempranos: boolean; filtros: BoardFilters; revisa: boolean;
}) {
  // `primera`: número de la primera página cargada (0 = la más reciente).
  const [primera, setPrimera] = useState(0);
  const [paginas, setPaginas] = useState<Tarjeta[][]>([col.cases]);
  const [cargando, setCargando] = useState(false);
  const caja = useRef<HTMLDivElement>(null);
  // Para que la tarjeta que se estaba viendo no salte al agregar o soltar páginas.
  const ancla = useRef<{ id: string; desde: number } | null>(null);

  // Cuando el tablero se vuelve a pedir (por ejemplo, al volver de aprobar un
  // expediente) llega la primera página nueva de cada columna. Si la columna
  // está al comienzo, se toman esas tarjetas: antes se quedaba con las de
  // antes y mostraba el total nuevo con tarjetas viejas («Aprobado 1» y vacío).
  useEffect(() => {
    if (primera === 0) setPaginas([col.cases]);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [col.cases]);

  const tarjetas = paginas.flat();
  const desde = primera * PAGINA;
  const hayDespues = desde + tarjetas.length < col.count;
  const hayAntes = primera > 0;

  const fijarAncla = () => {
    const el = caja.current;
    if (!el) return;
    const visible = [...el.querySelectorAll<HTMLElement>("[data-case]")].find((t) => t.offsetTop + t.offsetHeight > el.scrollTop);
    ancla.current = visible ? { id: visible.dataset.case!, desde: visible.offsetTop - el.scrollTop } : null;
  };
  useLayoutEffect(() => {
    const el = caja.current;
    const a = ancla.current;
    if (!el || !a) return;
    const t = el.querySelector<HTMLElement>(`[data-case="${a.id}"]`);
    if (t) el.scrollTop = t.offsetTop - a.desde;
    ancla.current = null;
  }, [paginas]);

  const pedir = useCallback(async (hacia: "siguiente" | "anterior") => {
    if (cargando) return;
    const numero = hacia === "siguiente" ? primera + paginas.length : primera - 1;
    setCargando(true);
    try {
      const nuevas = await getBoardColumn(col.code, tempranos, numero * PAGINA, PAGINA, filtros);
      fijarAncla();
      if (hacia === "siguiente") {
        const todas = [...paginas, nuevas];
        const sobran = Math.max(0, todas.length - VENTANA);
        setPaginas(todas.slice(sobran));
        setPrimera(primera + sobran);
      } else {
        setPaginas([nuevas, ...paginas].slice(0, VENTANA));
        setPrimera(numero);
      }
    } finally {
      setCargando(false);
    }
  }, [cargando, primera, paginas, col.code, tempranos, filtros]);

  const alDesplazar = () => {
    const el = caja.current;
    if (!el || cargando) return;
    if (hayDespues && el.scrollTop + el.clientHeight >= el.scrollHeight - MARGEN) pedir("siguiente");
    else if (hayAntes && el.scrollTop <= MARGEN) pedir("anterior");
  };

  return (
    <section className="board-col" aria-label={col.label}>
      <h2><span>{col.label}</span><span className="billing-count">{col.count}</span></h2>
      {col.count > tarjetas.length && tarjetas.length > 0 && (
        <p className="board-range" aria-live="polite">{desde + 1}–{desde + tarjetas.length} de {col.count}</p>
      )}
      <div ref={caja} className="board-col-scroll" onScroll={alDesplazar}>
        {hayAntes && <p className="board-edge">{cargando ? "Cargando…" : "Sube para ver los anteriores"}</p>}
        {tarjetas.length === 0 && <p className="acta-empty">Vacío</p>}
        <ul>
          {tarjetas.map((c) => (
            <li key={c.id} data-case={c.id}>
              <Link to={revisa && col.code !== "new_prospect" ? `/cases/${c.id}/review` : `/cases/${c.id}/form`} className="board-card">
                <strong>{c.customer_name ?? c.address ?? c.case_number}</strong>
                <small>{c.case_number}{c.program_name ? ` · ${c.program_name}` : ""}</small>
                {c.customer_name && <small>{c.address}</small>}
                {c.substatus_code && SUB[c.substatus_code] && (
                  <span className={`billing-chip ${c.substatus_code === "returned" ? "is-rejected" : "is-submitted"}`}>{SUB[c.substatus_code]}</span>
                )}
                <ApprovalDays wait={c.approval_wait} />
              </Link>
            </li>
          ))}
        </ul>
        {hayDespues && <p className="board-edge">{cargando ? "Cargando…" : "Baja para ver más"}</p>}
      </div>
    </section>
  );
}
