import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import type { Customer } from "@/types/crm";
import { listCustomersPage } from "./api";

/** Espera tras la última tecla antes de consultar. */
const ESPERA_MS = 300;
const MAXIMO = 8;

/**
 * Elegir un cliente buscándolo en el servidor por nombre, correo, teléfono o
 * dirección (la de facturación o la de la casa de sus expedientes). Reemplaza
 * al `<select>` con todos los clientes, que además solo traía la primera página.
 */
export function CustomerSearch({ id, value, onChange }: {
  id: string;
  value: Customer | null;
  onChange: (c: Customer | null) => void;
}) {
  const [texto, setTexto] = useState("");
  const [buscado, setBuscado] = useState("");
  useEffect(() => {
    const t = setTimeout(() => setBuscado(texto.trim()), ESPERA_MS);
    return () => clearTimeout(t);
  }, [texto]);
  const { data, isFetching } = useQuery({
    queryKey: ["customers-search", buscado],
    queryFn: () => listCustomersPage(1, MAXIMO, { q: buscado, status: "active" }),
    enabled: buscado.length >= 2 && !value,
  });

  if (value) {
    return (
      <div className="customer-search-picked">
        <span><strong>{value.legal_name}</strong>
          {(value.billing_address || value.main_phone) && <small>{[value.billing_address, value.main_phone].filter(Boolean).join(" · ")}</small>}
        </span>
        <button type="button" className="acta-btn is-quiet" onClick={() => { onChange(null); setTexto(""); }}>Cambiar</button>
      </div>
    );
  }
  const resultados = buscado.length >= 2 ? data?.items ?? [] : [];
  return (
    <div className="customer-search">
      <input id={id} type="search" autoComplete="off" value={texto} placeholder="Nombre, teléfono o dirección"
        onChange={(e) => setTexto(e.target.value)} />
      {buscado.length >= 2 && (
        <ul className="customer-search-results" role="listbox" aria-label="Clientes encontrados">
          {resultados.map((c) => (
            <li key={c.id}>
              <button type="button" role="option" aria-selected={false} onClick={() => onChange(c)}>
                <strong>{c.legal_name}</strong>
                {(c.billing_address || c.main_phone) && <small>{[c.billing_address, c.main_phone].filter(Boolean).join(" · ")}</small>}
              </button>
            </li>
          ))}
          {!isFetching && resultados.length === 0 && <li className="customer-search-empty">Ningún cliente con «{buscado}».</li>}
        </ul>
      )}
    </div>
  );
}
