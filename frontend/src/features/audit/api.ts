import { apiClient } from "@/lib/apiClient";
import type { AuditEventPage } from "@/types/audit";

export async function listAuditEvents(page: number, pageSize = 50): Promise<AuditEventPage> {
  const res = await apiClient.get<AuditEventPage>("/audit-events", { params: { page, page_size: pageSize } });
  return res.data;
}
