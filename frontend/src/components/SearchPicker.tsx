import { useEffect, useId, useState, type KeyboardEvent, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";

/** Espera tras la última tecla antes de consultar: escribir «tubo» es una sola petición. */
const ESPERA_MS = 300;

export interface SearchPickerProps<T> {
  /** Nombre accesible del campo («Artículo del renglón 3»). */
  label: string;
  /** Lo elegido; `null` si el campo está vacío. */
  value: T | null;
  onChange: (item: T | null) => void;
  /** Busca en el servidor. Recibe lo escrito, o "" al abrir sin escribir. */
  search: (q: string) => Promise<T[]>;
  /** Base de la clave de caché; se le suma lo escrito. */
  queryKey: readonly unknown[];
  getKey: (item: T) => string;
  /** Texto del campo cuando hay algo elegido. */
  getLabel: (item: T) => string;
  /** Cómo se ve cada opción de la lista; por defecto, `getLabel`. */
  renderOption?: (item: T) => ReactNode;
  /** Cuántas opciones trae la búsqueda: si llegan todas, se pide afinar. */
  pageSize: number;
  placeholder?: string;
  /** Si se da, aparece una «×» para dejar el campo vacío, con este nombre. */
  clearLabel?: string;
  /** Mientras se resuelve un valor que llegó solo con su id. */
  pendingLabel?: string;
  disabled?: boolean;
}

/**
 * Campo que busca en el servidor mientras se escribe y deja elegir de la lista.
 *
 * Reemplaza a los `<select>` que traían una sola página (200) de catálogos que
 * crecen: el de bodega son ~600 artículos de AC Pro, y lo que no cabía en la
 * primera página no se podía elegir. La lista va debajo del campo y no flota,
 * para que la tabla que la contiene (que en el celular se desplaza de lado)
 * no la recorte.
 */
export function SearchPicker<T>({
  label, value, onChange, search, queryKey, getKey, getLabel, renderOption, pageSize,
  placeholder = "Escribe para buscar", clearLabel, pendingLabel, disabled,
}: SearchPickerProps<T>) {
  const listaId = useId();
  const [abierto, setAbierto] = useState(false);
  const [texto, setTexto] = useState("");
  const [buscado, setBuscado] = useState("");
  const [activo, setActivo] = useState(0);

  useEffect(() => {
    const t = setTimeout(() => setBuscado(texto.trim()), ESPERA_MS);
    return () => clearTimeout(t);
  }, [texto]);

  const { data, isFetching, isError } = useQuery({
    queryKey: [...queryKey, "buscar", buscado],
    queryFn: () => search(buscado),
    enabled: abierto,
    staleTime: 30_000,
  });
  const opciones = data ?? [];

  useEffect(() => setActivo(0), [buscado]);

  function abrir() {
    if (disabled) return;
    setTexto("");
    setBuscado("");
    setAbierto(true);
  }

  function elegir(item: T) {
    onChange(item);
    setAbierto(false);
  }

  function teclas(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      if (!abierto) abrir();
      else setActivo((i) => Math.min(i + 1, opciones.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActivo((i) => Math.max(i - 1, 0));
    } else if (e.key === "Enter" && abierto) {
      // Sin esto, Enter manda el formulario que contiene el campo.
      e.preventDefault();
      if (opciones[activo]) elegir(opciones[activo]);
    } else if (e.key === "Escape" && abierto) {
      e.preventDefault();
      setAbierto(false);
    }
  }

  const mostrado = abierto ? texto : value ? getLabel(value) : "";
  const opcionId = (i: number) => `${listaId}-op-${i}`;

  return (
    <div className={abierto ? "search-picker is-open" : "search-picker"}>
      <div className="search-picker-field">
        <input
          role="combobox"
          aria-label={label}
          aria-expanded={abierto}
          aria-controls={listaId}
          aria-autocomplete="list"
          aria-activedescendant={abierto && opciones[activo] ? opcionId(activo) : undefined}
          autoComplete="off"
          value={mostrado}
          placeholder={!abierto && !value && pendingLabel ? pendingLabel : placeholder}
          disabled={disabled}
          onFocus={abrir}
          onClick={() => { if (!abierto) abrir(); }}
          onChange={(e) => { setTexto(e.target.value); if (!abierto) setAbierto(true); }}
          onBlur={() => setAbierto(false)}
          onKeyDown={teclas}
        />
        {clearLabel && value && !disabled && (
          <button type="button" className="search-picker-clear" aria-label={clearLabel}
            onMouseDown={(e) => e.preventDefault()} onClick={() => onChange(null)}>×</button>
        )}
      </div>
      {abierto && (
        <ul className="search-picker-list" id={listaId} role="listbox" aria-label={label}>
          {isError ? (
            <li className="search-picker-note" role="presentation">No se pudo buscar. Revisa la conexión e inténtalo de nuevo.</li>
          ) : opciones.length === 0 ? (
            <li className="search-picker-note" role="presentation">
              {isFetching ? "Buscando…" : buscado ? `Sin resultados para «${buscado}».` : "No hay nada para elegir."}
            </li>
          ) : (
            opciones.map((item, i) => (
              <li key={getKey(item)} id={opcionId(i)} role="option" aria-selected={i === activo}
                className={i === activo ? "search-picker-option is-active" : "search-picker-option"}
                // mousedown y no click: el click llega después del blur, que ya cerró la lista.
                onMouseDown={(e) => { e.preventDefault(); elegir(item); }}
                onMouseEnter={() => setActivo(i)}>
                {renderOption ? renderOption(item) : getLabel(item)}
              </li>
            ))
          )}
          {opciones.length >= pageSize && (
            <li className="search-picker-note" role="presentation">
              Se muestran los primeros {pageSize}. Escribe más para afinar.
            </li>
          )}
        </ul>
      )}
    </div>
  );
}
