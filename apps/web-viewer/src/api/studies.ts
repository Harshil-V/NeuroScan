import { apiGet } from "./client";
import type { Instance, Paginated, Study, StudyDetail } from "../types";

export const studiesApi = {
  list: (limit = 50, offset = 0) =>
    apiGet<Paginated<Study>>(`/api/studies?limit=${limit}&offset=${offset}`),
  detail: (studyInstanceUid: string) =>
    apiGet<StudyDetail>(`/api/studies/${encodeURIComponent(studyInstanceUid)}`),
  seriesInstances: (seriesInstanceUid: string) =>
    apiGet<{ items: Instance[] }>(
      `/api/series/${encodeURIComponent(seriesInstanceUid)}/instances`
    ),
};
