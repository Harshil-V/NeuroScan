import { apiGet, apiUpload } from "./client";
import type {
  Paginated,
  ReconstructionJob,
  ReconstructionJobCreated,
} from "../types";

export const reconstructionApi = {
  submit: (file: File) =>
    apiUpload<ReconstructionJobCreated>("/api/reconstruction/jobs", file),

  get: (jobId: string) =>
    apiGet<ReconstructionJob>(
      `/api/reconstruction/jobs/${encodeURIComponent(jobId)}`,
    ),

  list: (params: { limit?: number; status?: string } = {}) => {
    const q = new URLSearchParams();
    q.set("limit", String(params.limit ?? 50));
    if (params.status) q.set("status", params.status);
    return apiGet<Paginated<ReconstructionJob>>(
      `/api/reconstruction/jobs?${q.toString()}`,
    );
  },
};
