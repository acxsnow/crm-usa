/** API del módulo 7: avisos, preferencias y administración. */
import { apiClient } from "@/lib/apiClient";

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
