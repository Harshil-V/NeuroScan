export interface Study {
  orthanc_study_id: string;
  study_instance_uid: string;
  patient_id: string | null;
  modality: string | null;
  study_date: string | null;
  study_description: string | null;
  series_count: number;
  instance_count: number;
}

export interface Series {
  orthanc_series_id: string;
  series_instance_uid: string;
  series_description: string | null;
  modality: string | null;
  series_number: number | null;
  instance_count: number;
}

export interface StudyDetail extends Study {
  series: Series[];
}

export interface Instance {
  orthanc_instance_id: string;
  sop_instance_uid: string;
  instance_number: number | null;
  rows: number | null;
  columns: number | null;
}

export interface Paginated<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

export interface UploadResult {
  status: string;
  study_instance_uid: string;
  series_instance_uid: string;
  sop_instance_uid: string;
  orthanc_instance_id: string;
  checksum_sha256: string;
}

export interface ApiError {
  detail: string;
  code?: string;
}

export interface AuditEvent {
  event_id: string;
  event_type: string;
  status: "success" | "failure";
  message: string | null;
  actor: string;
  study_instance_uid: string | null;
  series_instance_uid: string | null;
  sop_instance_uid: string | null;
  orthanc_instance_id: string | null;
  checksum_sha256: string | null;
  created_at: string;
}
