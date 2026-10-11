/** API del módulo 7: avisos, preferencias y administración. */
import { apiClient } from "@/lib/apiClient";
import { fetchPage } from "@/lib/pagination";

export interface Notice { id: string; event: string; title: string; body: string; link: string | null; read: boolean; created_at: string }
export interface Preferences { email_enabled: boolean; sms_enabled: boolean; sms_phone: string | null; email: string }
export interface Delivery {
  id: string; channel: "email" | "sms"; to: string; subject: string | null; status: "pending" | "sent" | "failed" | "skipped";
  attempts: number; last_error: string | null; event: string; notice_label: string; title: string; created_at: string; sent_at: string | null;
}
export interface ChannelText { subject: string; body: string; active: boolean; customized: boolean }
export interface TemplateRow { code: string; label: string; audience: string; channels: Record<"in_app" | "email" | "sms", ChannelText> }
export interface NoticeSettings {
  approval_alert_business_days: number; permit_expiry_alert_days: number; customer_sms_enabled: boolean;
  email_provider: string; sms_provider: string;
}

export const noticeKeys = {
  count: ["notices-count"] as const,
  list: (unread: boolean) => ["notices", unread] as const,
  prefs: ["notice-prefs"] as const,
  deliveries: (status: string) => ["notice-deliveries", status] as const,
  templates: ["notice-templates"] as const,
  settings: ["notice-settings"] as const,
};

export const unreadCount = async () => (await apiClient.get<{ unread: number }>("/notifications/unread-count")).data.unread;
export const listNotices = async (unread = false, limit = 30) =>
  (await apiClient.get<{ items: Notice[]; unread: number }>("/notifications", { params: { unread, limit } })).data;
export const markRead = async (id: string) => (await apiClient.post<Notice>(`/notifications/${id}/read`)).data;
export const markAllRead = async () => (await apiClient.post("/notifications/read-all")).data;
export const getPrefs = async () => (await apiClient.get<Preferences>("/notifications/preferences")).data;
export const setPrefs = async (body: Omit<Preferences, "email">) =>
  (await apiClient.put<Preferences>("/notifications/preferences", body)).data;
export const listDeliveries = async (status: string) =>
  (await apiClient.get<Delivery[]>("/notifications/deliveries", { params: status ? { status } : {} })).data;
export const resendDelivery = async (id: string) => (await apiClient.post(`/notifications/deliveries/${id}/resend`)).data;
export const listTemplates = async () => (await apiClient.get<TemplateRow[]>("/notifications/templates")).data;
export const saveTemplate = async (code: string, channel: string, body: { subject?: string; body: string; active: boolean }) =>
  (await apiClient.put(`/notifications/templates/${code}/${channel}`, body)).data;
export const resetTemplate = async (code: string, channel: string) =>
  (await apiClient.delete(`/notifications/templates/${code}/${channel}`)).data;
export const getNoticeSettings = async () => (await apiClient.get<NoticeSettings>("/notifications/settings")).data;
export const setNoticeSettings = async (body: { approval_alert_business_days: number; permit_expiry_alert_days: number }) =>
  (await apiClient.put<NoticeSettings>("/notifications/settings", body)).data;

export function timeAgo(iso: string): string {
  const min = Math.round((Date.now() - new Date(iso).getTime()) / 60000);
  if (min < 1) return "ahora";
  if (min < 60) return `hace ${min} min`;
  const h = Math.round(min / 60);
  if (h < 24) return `hace ${h} h`;
  return new Date(iso).toLocaleDateString("es-CO", { day: "numeric", month: "short" });
}

// ---------------------------------------------------------------------------
// Campañas de productos por SMS y correo
// ---------------------------------------------------------------------------

export type CampaignChannel = "sms" | "email" | "both";
export type ConsentState = "granted" | "none" | "revoked" | "no_phone" | "no_email";
export interface Product { id: string; name: string; description: string | null; price: string | null; active: boolean }
export interface Audience { selected?: string[]; program_ids?: string[]; states?: string[]; search?: string; include_contacts?: boolean }
export interface Contact {
  key: string; kind: "customer" | "contact"; customer_id: string | null; contact_id: string | null;
  name: string; phone: string | null; email: string | null; state: string | null; city: string | null;
  program: string | null; stage: string | null; consent: ConsentState; email_consent: ConsentState;
}
export interface AudienceSummary { total: number; with_consent: number; without_consent: number; opted_out: number; no_address: number }
export interface CampaignStats { pending: number; sent: number; failed: number; skipped: number }
export interface Campaign {
  id: string; name: string; product_id: string | null; channel: CampaignChannel; subject: string | null; preview_subject: string;
  message: string; audience: Audience & { launch_summary?: { queued: number; without_consent: number; opted_out: number } };
  status: "draft" | "scheduled" | "sending" | "sent" | "cancelled"; scheduled_at: string | null; finished_at: string | null;
  created_at: string | null; preview: string; stats: CampaignStats;
}
export interface Recipient { id: string; name: string | null; channel: "sms" | "email"; address: string; status: string; attempts: number;
  last_error: string | null; next_attempt_at: string | null; sent_at: string | null }
export interface OwnContact { id: string; name: string | null; phone: string | null; email: string | null }

export const campaignKeys = {
  list: ["campaigns"] as const, one: (id: string) => ["campaign", id] as const, products: ["products"] as const,
  recipients: (id: string) => ["campaign-recipients", id] as const, optOuts: ["opt-outs"] as const,
  contacts: ["own-contacts"] as const,
};
export const listProducts = async () => (await apiClient.get<Product[]>("/products")).data;
export const saveProduct = async (p: Partial<Product> & { name: string }) =>
  (p.id ? await apiClient.put<Product>(`/products/${p.id}`, p) : await apiClient.post<Product>("/products", p)).data;
export const getAudience = async (a: Audience) =>
  (await apiClient.post<{ summary: AudienceSummary; email_summary: AudienceSummary; contacts: Contact[] }>("/campaigns/audience", a)).data;
export const grantConsent = async (keys: string[], source: string, channel: CampaignChannel) =>
  (await apiClient.post<{ granted: number }>("/campaigns/consents", { keys, source, channel, confirm: true })).data;
export const listCampaigns = async () => (await apiClient.get<Campaign[]>("/campaigns")).data;
export const getCampaign = async (id: string) => (await apiClient.get<Campaign>(`/campaigns/${id}`)).data;
export const saveCampaign = async (id: string | null, body: { name: string; product_id: string | null; channel: CampaignChannel;
  subject: string | null; message: string; audience: Audience }) =>
  (id ? await apiClient.put<Campaign>(`/campaigns/${id}`, body) : await apiClient.post<Campaign>("/campaigns", body)).data;
export const launchCampaign = async (id: string, scheduled_at?: string) =>
  (await apiClient.post<{ summary: { queued: number }; campaign: Campaign }>(`/campaigns/${id}/launch`, { scheduled_at: scheduled_at || null })).data;
export const cancelCampaign = async (id: string) => (await apiClient.post<Campaign>(`/campaigns/${id}/cancel`)).data;
export const testCampaign = async (id: string, channel: "sms" | "email", phone?: string) =>
  (await apiClient.post<{ result: string; text: string; to?: string }>(`/campaigns/${id}/test`, { channel, phone: phone || null })).data;
/** Destinatarios de una campaña, por páginas (pueden ser miles). */
export const listRecipients = (id: string, page: number, pageSize: number) =>
  fetchPage<Recipient>(`/campaigns/${id}/recipients`, page, pageSize);
/** Bajas de SMS y correo juntas, por páginas (solo se acumulan). */
export const listOptOuts = (page: number, pageSize: number) =>
  fetchPage<{ channel: "sms" | "email"; address: string; reason: string | null; at: string | null }>("/campaigns/opt-outs", page, pageSize);
export const addOptOut = async (value: string, reason: string) =>
  (await apiClient.post("/campaigns/opt-outs", value.includes("@") ? { email: value, reason } : { phone: value, reason })).data;
/** Contactos propios, por páginas (se importan en masa). */
export const listOwnContacts = (page: number, pageSize: number) => fetchPage<OwnContact>("/campaigns/contacts", page, pageSize);
export const importOwnContacts = async (text: string, source: string) =>
  (await apiClient.post<{ created: number; updated: number; invalid: string[]; already_opted_out: number }>(
    "/campaigns/contacts/import", { text, source, confirm: true })).data;
export const deleteOwnContact = async (id: string) => (await apiClient.delete(`/campaigns/contacts/${id}`)).data;
