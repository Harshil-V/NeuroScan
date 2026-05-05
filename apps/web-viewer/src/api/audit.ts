import { apiGet } from "./client";
import type { AuditEvent, Paginated } from "../types";

export const auditApi = {
  list: (params: { limit?: number; eventType?: string; status?: string } = {}) => {
    const q = new URLSearchParams();
    q.set("limit", String(params.limit ?? 100));
    if (params.eventType) q.set("event_type", params.eventType);
    if (params.status) q.set("status", params.status);
    return apiGet<Paginated<AuditEvent>>(`/api/audit/events?${q.toString()}`);
  },
};
