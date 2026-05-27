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

export type PhiSeverity = "high" | "medium";

export interface PhiFindingItem {
  tag: string;
  tag_name: string;
  severity: PhiSeverity;
}

export interface PhiFindingItemWithHash extends PhiFindingItem {
  value_sha256: string | null;
}

export interface PhiFindingsSummary {
  total: number;
  high: number;
  medium: number;
  items: PhiFindingItem[];
}

export interface PhiFindingsDetail {
  audit_event_id: string;
  total: number;
  high: number;
  medium: number;
  items: PhiFindingItemWithHash[];
}

export interface UploadResult {
  status: string;
  study_instance_uid: string;
  series_instance_uid: string;
  sop_instance_uid: string;
  orthanc_instance_id: string;
  checksum_sha256: string;
  phi_findings: PhiFindingsSummary;
}

export interface ApiError {
  detail: string;
  code?: string;
}

export interface AuditEvent {
  event_id: string;
  event_type: string;
  status: "success" | "failure" | "success_minio_skipped";
  message: string | null;
  actor: string;
  study_instance_uid: string | null;
  series_instance_uid: string | null;
  sop_instance_uid: string | null;
  orthanc_instance_id: string | null;
  checksum_sha256: string | null;
  created_at: string;
}

export interface ReconstructionJob {
  job_id: string;
  status: "queued" | "running" | "completed" | "failed";
  input_file_name: string;
  input_format: "npy" | "npz" | "h5";
  input_shape: string | null;
  output_dicom_uid: string | null;
  output_orthanc_instance_id: string | null;
  psnr_db: number | null;
  ssim: number | null;
  duration_ms: number | null;
  error_message: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
}

export interface ReconstructionJobCreated {
  job_id: string;
  status: "queued";
  input_file_name: string;
  input_format: "npy" | "npz" | "h5";
  created_at: string;
}

export interface StorageObject {
  id: number;
  bucket: string;
  object_key: string;
  sha256: string;
  content_type: string;
  size_bytes: number;
  source: "dicom_upload" | "reconstruction_output";
  created_at: string;
}

export interface PresignedUrl {
  url: string;
  expires_at: string;
}
