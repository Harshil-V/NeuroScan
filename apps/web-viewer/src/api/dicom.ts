import { apiUpload } from "./client";
import type { UploadResult } from "../types";

export const dicomApi = {
  upload: (file: File) => apiUpload<UploadResult>("/api/dicom/upload", file),
};
