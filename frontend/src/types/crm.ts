export interface Address {
  address_street?: string | null;
  address_unit?: string | null;
  address_city?: string | null;
  address_state?: string | null;
  address_zip?: string | null;
  latitude?: number | null;
  longitude?: number | null;
}

export type LeadStatus = "new" | "contacted" | "qualified" | "disqualified" | "converted";

export interface Lead extends Address {
  id: string;
  full_name: string;
  company_name?: string | null;
  phone?: string | null;
  email?: string | null;
  source?: string | null;
  benefit_type?: string | null;
  funder_program?: string | null;
  interested_service?: string | null;
  assigned_owner_user_id?: string | null;
  status: LeadStatus;
  notes?: string | null;
  converted_customer_id?: string | null;
  converted_opportunity_id?: string | null;
  created_at: string;
}

export interface LeadDuplicateWarning {
  lead_id: string;
  full_name: string;
  matched_on: string[];
}

export interface LeadCreateResult {
  lead: Lead;
  possible_duplicates: LeadDuplicateWarning[];
}

export interface CustomerContact {
  id: string;
  full_name: string;
  role_title?: string | null;
  email?: string | null;
  phone?: string | null;
  preferred_contact_method?: string | null;
  is_primary: boolean;
}

export interface Customer {
  id: string;
  legal_name: string;
  customer_type: "individual" | "business";
  main_phone?: string | null;
  email?: string | null;
  website?: string | null;
  billing_address?: string | null;
  status: "active" | "inactive";
  tags?: string[] | null;
  notes?: string | null;
  contacts: CustomerContact[];
}

export interface PipelineStage {
  id: string;
  code: string;
  name: string;
  sort_order: number;
  is_won: boolean;
  is_lost: boolean;
}

export interface FunderStatus {
  id: string;
  code: string;
  name: string;
  sort_order: number;
}

export interface Opportunity extends Address {
  id: string;
  customer_id: string;
  primary_contact_id?: string | null;
  title: string;
  description?: string | null;
  estimated_amount?: number | null;
  currency: string;
  probability?: number | null;
  expected_close_date?: string | null;
  stage: PipelineStage;
  owner_user_id?: string | null;
  loss_reason?: string | null;
  benefit_type?: string | null;
  funder_program?: string | null;
  application_number?: string | null;
  approval_code?: string | null;
  funder_status?: FunderStatus | null;
  utility_account_number?: string | null;
  meter_number?: string | null;
  unit_type?: string | null;
  scheduled_install_date?: string | null;
  created_at: string;
}

export interface Activity {
  id: string;
  type: "call" | "email" | "meeting" | "note" | "task" | "follow_up";
  subject: string;
  notes?: string | null;
  owner_user_id: string;
  due_date?: string | null;
  completed_at?: string | null;
  reminder_at?: string | null;
  customer_id?: string | null;
  opportunity_id?: string | null;
  created_at: string;
}

export interface QuoteLineItem {
  id: string;
  description: string;
  quantity: number;
  unit_price: number;
  discount: number;
  tax_value: number;
  line_total: number;
}

export interface Quote {
  id: string;
  quote_number: string;
  customer_id: string;
  opportunity_id?: string | null;
  project_description?: string | null;
  issue_date?: string | null;
  expiry_date?: string | null;
  currency: string;
  status: "draft" | "sent" | "accepted" | "rejected" | "expired";
  notes?: string | null;
  total_amount: number;
  line_items: QuoteLineItem[];
}

export interface Customer360 {
  customer: Customer;
  opportunities: Opportunity[];
  activities: Activity[];
  quotes: Quote[];
}

export interface ImportSummary {
  total_rows: number;
  created: number;
  skipped_duplicates: number;
  errors: string[];
}
