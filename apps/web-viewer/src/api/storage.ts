import { apiGet } from "./client";
import type { Paginated, PresignedUrl, StorageObject } from "../types";

export const storageApi = {
  list: (params: { sha256?: string; source?: string; limit?: number } = {}) => {
    const q = new URLSearchParams();
    q.set("limit", String(params.limit ?? 50));
    if (params.sha256) q.set("sha256", params.sha256);
    if (params.source) q.set("source", params.source);
    return apiGet<Paginated<StorageObject>>(`/api/storage/objects?${q.toString()}`);
  },

  get: (id: number) => apiGet<StorageObject>(`/api/storage/objects/${id}`),

  presignedUrl: (id: number, expiresSeconds = 300) =>
    apiGet<PresignedUrl>(
      `/api/storage/objects/${id}/presigned-url?expires=${expiresSeconds}`,
    ),
};
