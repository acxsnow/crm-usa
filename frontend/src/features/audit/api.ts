import { fetchPage, type Page } from "@/lib/pagination";
import type { AuditEvent } from "@/types/audit";

export async function listAuditEventsPage(
  page: number,
  pageSize: number,
  extraParams: Record<string, string> = {}
): Promise<Page<AuditEvent>> {
  return fetchPage<AuditEvent>("/audit-events", page, pageSize, extraParams);
}
