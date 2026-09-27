import type { Case } from "@/features/cases/api";

export interface Address {
  address_street?: string | null;
  address_unit?: string | null;
  address_city?: string | null;
  address_state?: string | null;
  address_zip?: string | null;
  latitude?: number | null;
  longitude?: number | null;
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

export interface FunderStatus {
  id: string;
  code: string;
  name: string;
  sort_order: number;
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

export interface Customer360 {
  customer: Customer;
  /** Todos los expedientes de este cliente. Reemplazó a oportunidades y cotizaciones. */
  cases: Case[];
  activities: Activity[];
}

