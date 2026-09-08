import type { AxiosRequestConfig } from "axios";
import { apiClient } from "./apiClient";

export interface Page<T> {
  items: T[];
  total: number;
}

/** Fetches one page of a `?limit=&offset=`-paginated list endpoint
 * (app/shared/pagination.py on the backend) and reads the total row count
 * back from the `X-Total-Count` response header. */
export async function fetchPage<T>(
  path: string,
  page: number,
  pageSize: number,
  extraParams: Record<string, string | number | boolean | undefined> = {},
  config: AxiosRequestConfig = {}
): Promise<Page<T>> {
  const res = await apiClient.get<T[]>(path, {
    ...config,
    params: { ...extraParams, limit: pageSize, offset: (page - 1) * pageSize, ...config.params },
  });
  const totalHeader = res.headers["x-total-count"];
  const total = totalHeader !== undefined ? Number(totalHeader) : res.data.length;
  return { items: res.data, total };
}
