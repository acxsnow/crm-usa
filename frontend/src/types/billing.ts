/** Estado del pago a la fecha de la organización (lo calcula el backend). */
export type InvoiceStatus = "unpaid" | "partial" | "paid" | "overdue" | "draft" | "void";

export const INVOICE_STATUS_LABELS: Record<InvoiceStatus, string> = {
  unpaid: "Sin pagar",
  partial: "Pago parcial",
  paid: "Pagada",
  overdue: "Vencida",
  draft: "Borrador",
  void: "Anulada",
};

export interface InvoiceLine {
  id: string;
  kind: string;
  description: string;
  service_code?: string | null;
  quantity: number;
  unit_price: number;
  amount: number;
}

export interface InvoicePayment {
  id: string;
  amount: number;
  paid_at: string;
  method?: string | null;
  reference?: string | null;
  notes?: string | null;
}

export interface InvoiceAttachment {
  id: string;
  original_filename?: string | null;
  mime_type?: string | null;
  size_bytes?: number | null;
  created_at: string;
}

export interface Invoice {
  id: string;
  kind: "rebate" | "particular";
  project_id?: string | null;
  case_id?: string | null;
  replaces_invoice_id?: string | null;
  claim_id?: string | null;
  quote_id?: string | null;
  subtotal: number;
  rebate_total: number;
  customer_total: number;
  document_status: "draft" | "issued" | "void";
  void_reason?: string | null;
  lines: InvoiceLine[];
  customer_id: string;
  invoice_number: string;
  funder_program?: string | null;
  amount: number;
  paid_amount: number;
  balance: number;
  status: InvoiceStatus;
  issue_date?: string | null;
  due_date?: string | null;
  sent_at?: string | null;
  paid_at?: string | null;
  notes?: string | null;
  payments: InvoicePayment[];
  attachments: InvoiceAttachment[];
  created_at: string;
}

export interface FinanceDashboard {
  total_invoiced: number;
  total_paid: number;
  total_outstanding: number;
  total_overdue: number;
  invoice_count: number;
  overdue_count: number;
  due_soon_count: number;
  /** Pagos registrados este mes (programas y particulares). */
  paid_this_month: number;
}

// ---------------------------------------------------------------------------
// Cobro de rebate (módulo 6)
// ---------------------------------------------------------------------------

export type ClaimStatus = "preparing" | "submitted" | "rejected" | "paid" | "withdrawn";

export const CLAIM_STATUS_LABELS: Record<ClaimStatus, string> = {
  preparing: "Por radicar",
  submitted: "Radicado",
  rejected: "Rechazado, en corrección",
  paid: "Pagado",
  withdrawn: "Retirado",
};

export const REJECTION_CATEGORIES: Record<string, string> = {
  documentary: "Documental",
  technical: "Técnico",
  other: "Otro",
};

export interface EligibleProgram {
  program_id: string;
  program_code: string;
  program_name: string;
  applies: boolean;
  jurisdiction_label: string | null;
  rate: number | null;
  claim_id: string | null;
  claim_status: ClaimStatus | null;
}

export interface Eligibility {
  project_id: string;
  installation_date: string | null;
  evaluated_on: string;
  technician_info_confirmed: boolean;
  /** Programa del expediente: si existe, `programs` trae solo ese. */
  case_program_id: string | null;
  programs: EligibleProgram[];
}

export interface ClaimAttempt {
  id: string;
  submitted_on: string;
  portal_reference: string | null;
  result: "pending" | "paid" | "rejected";
  rejection_category: string | null;
  rejection_reason: string | null;
  resolved_on: string | null;
}

export interface ClaimRequirement {
  code: string;
  label: string;
  kind: "auto" | "manual";
  met: boolean;
  detail: string | null;
  confirmed_at: string | null;
  note: string | null;
}

export interface Claim {
  id: string;
  project_id: string;
  case_id: string | null;
  case_number: string | null;
  customer_name: string | null;
  address: string | null;
  program_id: string;
  program_code: string;
  program_name: string;
  status: ClaimStatus;
  status_label: string;
  amount: number;
  installation_date: string;
  applies: boolean;
  jurisdiction_label: string | null;
  override_reason: string | null;
  paid_on: string | null;
  paid_amount: number | null;
  difference: number | null;
  payment_reference: string | null;
  withdrawn_reason: string | null;
  invoice: Invoice | null;
  attempts: ClaimAttempt[];
  created_at: string;
}

export interface ClaimDetail extends Claim {
  requirements: ClaimRequirement[];
  ready_to_submit: boolean;
}

interface DashboardItem {
  project_id: string;
  customer_name: string | null;
  address: string | null;
  case_id: string | null;
  case_number: string | null;
  days: number;
  alert: boolean;
}

interface DashboardClaim extends DashboardItem {
  claim_id: string;
  program_id: string;
  program_code: string;
  program_name: string;
  amount: number;
}

export interface BillingDashboard {
  today: string;
  to_create: (DashboardItem & { confirmed_on: string; installation_date: string | null })[];
  to_submit: (DashboardClaim & { ready_to_submit: boolean; pending_requirements: number })[];
  submitted: (DashboardClaim & { submitted_on: string; expected_payment_days: number })[];
  rejected: (DashboardClaim & { rejection_reason: string | null; rejection_category: string | null })[];
  paid_this_month: (DashboardClaim & { paid_on: string; paid_amount: number; difference: number | null })[];
  /** Lo que deben los programas por antigüedad de la factura (cobros abiertos). */
  aging: { d0_30: number; d31_45: number; d46_plus: number; open_total: number };
  by_program: { program_id: string; program_code: string; program_name: string; paid_this_month: number;
    expected: number; submitted_count: number }[];
  particular: { overdue_count: number; overdue_total: number; due_soon_count: number; due_soon_total: number;
    outstanding_total: number; draft_count: number };
}

// ---------------------------------------------------------------------------
// Configuración por programa
// ---------------------------------------------------------------------------

export interface ProgramSummary { id: string; code: string; name: string; active: boolean }

export interface ProgramProfile {
  program_id: string;
  issuer_name: string | null;
  issuer_address: string | null;
  issuer_phone: string | null;
  issuer_email: string | null;
  legal_text: string | null;
  expected_payment_days: number;
}

export interface ProgramRate { id: string; amount: number; valid_from: string; valid_to: string | null; notes: string | null }

export interface ProgramJurisdiction {
  id: string; kind: "city" | "zip"; value: string; label: string; valid_from: string; valid_to: string | null;
}

export interface ProgramRequirement {
  id: string; code: string; label: string; kind: "auto" | "manual"; sort_order: number; active: boolean;
}

// ---------------------------------------------------------------------------
// Trabajo particular: cotizaciones
// ---------------------------------------------------------------------------

export type QuoteStatus = "draft" | "sent" | "accepted" | "rejected" | "superseded" | "expired";

export interface LineInput {
  kind: string;
  description: string;
  quantity: number;
  unit_price: number;
}

export const LINE_KIND_LABELS: Record<string, string> = {
  service: "Servicio",
  material: "Material",
  labor: "Mano de obra",
  permit: "Permiso",
  equipment: "Equipo",
  other: "Otro",
};

export interface Quote {
  id: string;
  quote_number: string;
  version: number;
  previous_version_id: string | null;
  customer_id: string;
  project_id: string | null;
  status: QuoteStatus;
  status_label: string;
  title: string | null;
  valid_until: string | null;
  notes: string | null;
  sent_at: string | null;
  decided_at: string | null;
  rejection_reason: string | null;
  total: number;
  lines: InvoiceLine[];
  created_at: string;
}

export interface QuoteDetail extends Quote {
  versions: { id: string; version: number; status: QuoteStatus; total: number; created_at: string }[];
  invoice: Invoice | null;
}
