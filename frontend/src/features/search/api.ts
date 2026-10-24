import { apiClient } from "@/lib/apiClient";

export interface SearchResult {
  id: string;
  title: string;
  subtitle: string | null;
  /** Dirección de la pantalla del registro dentro de la aplicación. */
  url: string;
}

export interface SearchGroup {
  key: string;
  label: string;
  results: SearchResult[];
  /** El listado del grupo filtrado con el mismo texto («Ver todos»). */
  more_url: string;
}

export interface SearchResponse {
  q: string;
  groups: SearchGroup[];
}

/** Lo que el servidor exige para buscar; con menos no se pregunta. */
export const SEARCH_MIN_LENGTH = 2;

export const globalSearch = async (q: string, signal?: AbortSignal) =>
  (await apiClient.get<SearchResponse>("/search", { params: { q }, signal })).data;
