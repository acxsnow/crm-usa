import { useEffect } from "react";
import { useSearchParams } from "react-router-dom";

/**
 * El «Ver todos» y los resultados del buscador global abren los listados con
 * `?q=<texto>`. Las pantallas que guardan sus filtros en su propio estado (y no
 * en la dirección) usan esto para recibirlo: cada vez que llega un `q` nuevo en
 * la dirección, se lo pasan a su filtro de texto.
 */
export function useSearchTextFromUrl(onText: (text: string) => void) {
  const [params] = useSearchParams();
  const texto = params.get("q") ?? "";
  useEffect(() => {
    if (texto) onText(texto);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- solo cuando cambia el texto de la dirección.
  }, [texto]);
}
