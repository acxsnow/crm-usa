export type InvoiceStatus = "pending" | "sent" | "paid" | "overdue" | "cancelled";

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
  project_id: string;
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
}
