/** API de contabilidad: plan de cuentas, asientos, estados financieros e impuestos. */
import { apiClient } from "@/lib/apiClient";

export interface Account {
  id: string; code: string; name: string; account_type: string; account_type_label: string;
  system_key: string | null; tax_category: string | null; active: boolean;
}
export interface EntryLine { account_code: string; account_name: string; debit: string; credit: string; project_id: string | null; memo: string | null }
export interface Entry {
  id: string; number: string; entry_date: string; memo: string; automatic: boolean; source_type: string | null;
  is_reversal: boolean; reversed: boolean; total: string; lines: EntryLine[];
}
export interface StatementRow { account_id: string; code: string; name: string; amount: string }
export interface IncomeStatement {
  date_from: string; date_to: string; income: StatementRow[]; cogs: StatementRow[]; expenses: StatementRow[];
  total_income: string; total_cogs: string; gross_profit: string; total_expenses: string; net_income: string;
}
export interface BalanceSheet {
  as_of: string; assets: StatementRow[]; liabilities: StatementRow[]; equity: StatementRow[]; total_assets: string;
  total_liabilities: string; retained_earnings: string; total_equity: string; total_liabilities_equity: string; balanced: boolean;
}
export interface TrialBalance {
  as_of: string; balanced: boolean; total_debit: string; total_credit: string;
  rows: { account_id: string; code: string; name: string; account_type: string; debit: string; credit: string }[];
}
export interface TaxSummary {
  year: number; threshold_1099: string; total_income: string; total_costs: string; net_income: string;
  lines: { group: string; tax_category: string; amount: string; accounts: string[] }[];
  contractors_1099: { supplier_id: string; name: string; tax_id: string | null; address: string | null; total_paid: string; missing: string[] }[];
}
export interface Ledger {
  account: Account; opening_balance: string; closing_balance: string;
  rows: { id: string; entry_id: string; number: string; entry_date: string; memo: string; debit: string; credit: string; balance: string }[];
}

const R = "/accounting/reports";
export const usd = (v: string | number) => new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(Number(v));
export const getIncomeStatement = async (date_from: string, date_to: string) =>
  (await apiClient.get<IncomeStatement>(`${R}/income-statement`, { params: { date_from, date_to } })).data;
export const getBalanceSheet = async (as_of: string) =>
  (await apiClient.get<BalanceSheet>(`${R}/balance-sheet`, { params: { as_of } })).data;
export const getTrialBalance = async (as_of: string) =>
  (await apiClient.get<TrialBalance>(`${R}/trial-balance`, { params: { as_of } })).data;
export const getTaxSummary = async (year: number) =>
  (await apiClient.get<TaxSummary>(`${R}/tax-summary`, { params: { year } })).data;
export const getLedger = async (id: string, date_from?: string, date_to?: string) =>
  (await apiClient.get<Ledger>(`/accounting/accounts/${id}/ledger`, { params: { date_from, date_to } })).data;
export const getAllAccounts = async () =>
  (await apiClient.get<Account[]>("/accounting/accounts", { params: { limit: 200 } })).data;
export const saveAccount = async (body: Partial<Account>, id?: string) =>
  (id ? await apiClient.patch<Account>(`/accounting/accounts/${id}`, body) : await apiClient.post<Account>("/accounting/accounts", body)).data;
export const createEntry = async (body: { entry_date: string; memo: string; lines: { account_id: string; debit: string; credit: string }[] }) =>
  (await apiClient.post<Entry>("/accounting/entries", body)).data;
export const reverseEntry = async (id: string, reason: string) =>
  (await apiClient.post<Entry>(`/accounting/entries/${id}/reverse`, { reason })).data;
export const syncAccounting = async () =>
  (await apiClient.post<{ posted: number; reversed: number }>("/accounting/sync")).data;
export const getLock = async () =>
  (await apiClient.get<{ locked_through: string | null }>("/accounting/settings")).data;
export const setLock = async (locked_through: string | null) =>
  (await apiClient.put<{ locked_through: string | null }>("/accounting/settings/lock", { locked_through })).data;

export async function downloadCsv(path: string, params: Record<string, string | number>, nombre: string) {
  const r = await apiClient.get(`/accounting/export/${path}.csv`, { params, responseType: "blob" });
  const url = URL.createObjectURL(r.data as Blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${nombre}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}
