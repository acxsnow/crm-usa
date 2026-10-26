export interface AuditEvent {
  id: string;
  actor_user_id: string | null;
  action: string;
  entity_type: string | null;
  entity_id: string | null;
  created_at: string;
  /** Lo que había antes y lo que quedó (D-020); los secretos llegan ocultos. */
  before_data: Record<string, unknown> | null;
  after_data: Record<string, unknown> | null;
  ip_address: string | null;
}
