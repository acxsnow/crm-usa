export interface AuditEvent {
  id: string;
  actor_user_id: string | null;
  action: string;
  entity_type: string | null;
  entity_id: string | null;
  created_at: string;
}

export interface AuditEventPage {
  items: AuditEvent[];
  page: number;
  page_size: number;
}
