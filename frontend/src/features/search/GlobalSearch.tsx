import { useEffect, useId, useMemo, useRef, useState, type KeyboardEvent } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { keepPreviousData, useQuery } from "@tanstack/react-query";

import { Icon } from "@/components/ui/Icon";
import { hasAnyPermission } from "@/config/navigation";
import { useAuth } from "@/features/auth/AuthContext";
import { globalSearch, SEARCH_MIN_LENGTH, type SearchResult } from "./api";

/** Los permisos de los grupos del buscador (backend `search/service.py`). */
const SEARCH_PERMISSIONS = [
  "customers.read", "cases.read_own", "cases.read_all", "projects.read_all", "projects.read_assigned",
  "invoices.read", "quotes.manage", "warehouse.read", "warehouse.manage", "warehouse.count",
  "warehouse.request_release", "warehouse.approve_release", "warehouse.deliver",
  "suppliers.manage", "payables.manage", "payables.approve", "users.manage",
];

const ESPERA_MS = 300;

/**
 * El buscador de la barra superior: clientes, expedientes, obras, facturas,
 * cotizaciones, artículos y salidas de bodega, proveedores y usuarios, cada
 * grupo solo si la persona lo puede ver (lo decide el servidor).
 *
 * En escritorio es la caja de la barra; en el celular, una lupa que abre el
 * buscador a pantalla completa. Se maneja con el teclado: «/» o Ctrl+K lo
 * enfocan, las flechas recorren los resultados, Enter abre y Escape cierra.
 * Con señal lenta, Enter no abre un resultado viejo: espera a que llegue la
 * respuesta del texto que está escrito.
 */
export function GlobalSearch() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const { pathname, search } = useLocation();
  const listId = useId();
  const caja = useRef<HTMLInputElement>(null);
  const contenedor = useRef<HTMLDivElement>(null);
  const [texto, setTexto] = useState("");
  const [buscado, setBuscado] = useState("");
  const [abierto, setAbierto] = useState(false);
  const [movil, setMovil] = useState(false);
  const [activo, setActivo] = useState(-1);

  const limpio = texto.trim().replace(/\s+/g, " ");
  useEffect(() => {
    const t = setTimeout(() => setBuscado(limpio), ESPERA_MS);
    return () => clearTimeout(t);
  }, [limpio]);

  const listo = buscado.length >= SEARCH_MIN_LENGTH;
  const { data, isError, isFetching } = useQuery({
    queryKey: ["global-search", buscado],
    queryFn: ({ signal }) => globalSearch(buscado, signal),
    enabled: listo && abierto,
    staleTime: 30_000,
    placeholderData: keepPreviousData,
  });
  // Lo que se ve corresponde a lo escrito solo cuando la respuesta es de ese texto.
  const pendiente = limpio !== buscado || isFetching || (data?.q ?? "") !== buscado;
  const grupos = useMemo(() => (pendiente ? [] : data?.groups ?? []), [pendiente, data]);
  const planos = useMemo(() => grupos.flatMap((g) => g.results), [grupos]);
  useEffect(() => setActivo(-1), [buscado]);

  // Al cambiar de pantalla se cierra (también el modo celular).
  useEffect(() => { setAbierto(false); setMovil(false); }, [pathname, search]);

  // Clic fuera cierra la lista.
  useEffect(() => {
    if (!abierto) return;
    const fuera = (e: MouseEvent) => {
      if (contenedor.current && !contenedor.current.contains(e.target as Node)) { setAbierto(false); setMovil(false); }
    };
    document.addEventListener("mousedown", fuera);
    return () => document.removeEventListener("mousedown", fuera);
  }, [abierto]);

  // «/» o Ctrl+K desde cualquier pantalla, salvo que se esté escribiendo en otro campo.
  useEffect(() => {
    const atajo = (e: globalThis.KeyboardEvent) => {
      const destino = e.target as HTMLElement | null;
      const escribiendo = destino && (["INPUT", "TEXTAREA", "SELECT"].includes(destino.tagName) || destino.isContentEditable);
      if ((e.key === "k" && (e.ctrlKey || e.metaKey)) || (e.key === "/" && !escribiendo)) {
        e.preventDefault();
        if (window.matchMedia("(max-width: 1023px)").matches) setMovil(true);
        setAbierto(true);
        requestAnimationFrame(() => caja.current?.focus());
      }
    };
    window.addEventListener("keydown", atajo);
    return () => window.removeEventListener("keydown", atajo);
  }, []);

  useEffect(() => { if (movil) requestAnimationFrame(() => caja.current?.focus()); }, [movil]);

  if (!hasAnyPermission(SEARCH_PERMISSIONS, user)) return null;

  const ir = (url: string) => {
    setTexto("");
    setBuscado("");
    setAbierto(false);
    setMovil(false);
    caja.current?.blur();
    navigate(url);
  };

  const teclas = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Escape") {
      setAbierto(false);
      setMovil(false);
      caja.current?.blur();
      return;
    }
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      setAbierto(true);
      if (!planos.length) return;
      const paso = e.key === "ArrowDown" ? 1 : -1;
      setActivo((i) => (i + paso + planos.length) % planos.length);
      return;
    }
    if (e.key === "Enter") {
      e.preventDefault();
      if (pendiente) return;
      const elegido = planos[activo] ?? planos[0];
      if (elegido) ir(elegido.url);
    }
  };

  const idDe = (r: SearchResult) => `${listId}-${r.id}`;
  const activoId = activo >= 0 && planos[activo] ? idDe(planos[activo]) : undefined;
  const verLista = abierto && limpio.length > 0;

  let indice = -1;
  return (
    <div ref={contenedor} className={`global-search${movil ? " is-mobile-open" : ""}`}>
      <button type="button" className="global-search-trigger" aria-label="Buscar"
        onClick={() => { setMovil(true); setAbierto(true); }}>
        <Icon name="search" />
      </button>
      <div className="topbar-search global-search-box">
        <Icon name="search" />
        <input ref={caja} type="search" role="combobox" aria-label="Buscar en toda la aplicación"
          aria-expanded={verLista} aria-controls={listId} aria-autocomplete="list" aria-activedescendant={activoId}
          placeholder="Buscar clientes, expedientes, obras, facturas…" autoComplete="off" enterKeyHint="search"
          value={texto} maxLength={100}
          onChange={(e) => { setTexto(e.target.value); setAbierto(true); }}
          onFocus={() => setAbierto(true)} onKeyDown={teclas} />
        <kbd className="global-search-hint" aria-hidden="true">/</kbd>
        {movil && (
          <button type="button" className="global-search-close" onClick={() => { setMovil(false); setAbierto(false); }}>
            Cerrar
          </button>
        )}
      </div>

      {(verLista || movil) && (
        <div className="global-search-panel" id={listId} role="listbox" aria-label="Resultados de la búsqueda">
          {limpio.length < SEARCH_MIN_LENGTH ? (
            <p className="global-search-note">Escribe al menos {SEARCH_MIN_LENGTH} letras: nombre, dirección, número de
              expediente, factura, código de artículo…</p>
          ) : pendiente && !isError ? (
            <p className="global-search-note" role="status">Buscando…</p>
          ) : isError ? (
            <p className="global-search-note" role="alert">No se pudo buscar. Revisa la conexión e inténtalo otra vez.</p>
          ) : grupos.length === 0 ? (
            <p className="global-search-note">Nada con «{buscado}».</p>
          ) : (
            grupos.map((g) => (
              <section key={g.key} className="global-search-group" role="group" aria-label={g.label}>
                <header>
                  <span>{g.label}</span>
                  <button type="button" className="link-button" onMouseDown={(e) => e.preventDefault()}
                    onClick={() => ir(g.more_url)}>Ver todos</button>
                </header>
                {g.results.map((r) => {
                  indice += 1;
                  const mio = indice;
                  return (
                    <div key={r.id} id={idDe(r)} role="option" aria-selected={mio === activo}
                      className={`global-search-option${mio === activo ? " is-active" : ""}`}
                      onMouseDown={(e) => e.preventDefault()} onMouseEnter={() => setActivo(mio)}
                      onClick={() => ir(r.url)}>
                      <strong>{r.title}</strong>
                      {r.subtitle && <small>{r.subtitle}</small>}
                    </div>
                  );
                })}
              </section>
            ))
          )}
        </div>
      )}
    </div>
  );
}
