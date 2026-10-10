import { useEffect, useState } from "react";
import { useCitySuggestions } from "@/features/programs/api";

/** Espera tras la última tecla antes de consultar: escribir «phoe» es una sola petición. */
const ESPERA_MS = 300;

/**
 * Sugerencias de ciudad para un `<input list={id}>`: busca en el servidor
 * (tabla `geo_cities`) las ciudades del estado que contienen lo escrito y
 * muestra las primeras 20. Al abrir el campo sin escribir, muestra las 20
 * primeras del estado. El campo sigue siendo libre: sugiere, no obliga.
 */
export function CitySuggestions({ id, state, value }: { id: string; state: string | undefined; value: string }) {
  const [buscado, setBuscado] = useState(value.trim());
  useEffect(() => {
    const t = setTimeout(() => setBuscado(value.trim()), ESPERA_MS);
    return () => clearTimeout(t);
  }, [value]);
  const { data } = useCitySuggestions(state, buscado);
  return (
    <datalist id={id}>
      {(data ?? []).map((ciudad) => (
        <option key={ciudad} value={ciudad} />
      ))}
    </datalist>
  );
}
