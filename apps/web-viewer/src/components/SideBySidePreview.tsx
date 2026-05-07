import { Link } from "react-router-dom";
import { previewUrl } from "../api/client";
import type { ReconstructionJob } from "../types";

export default function SideBySidePreview({
  job,
}: {
  job: ReconstructionJob;
}) {
  if (job.status !== "completed") {
    if (job.status === "failed") {
      return (
        <div style={{ marginTop: "0.75rem", color: "#a4282b" }}>
          <strong>Failed:</strong> {job.error_message ?? "unknown error"}
        </div>
      );
    }
    return (
      <p style={{ marginTop: "0.75rem", color: "#666" }}>
        {job.status === "running" ? "Reconstructing…" : "Queued…"}
      </p>
    );
  }

  const reconUrl = job.output_orthanc_instance_id
    ? previewUrl(job.output_orthanc_instance_id)
    : null;
  const hasGroundTruth = job.psnr_db !== null && job.ssim !== null;

  return (
    <div
      style={{
        marginTop: "0.75rem",
        padding: "1rem",
        background: "#fafbfc",
        border: "1px solid #e3e5ec",
        borderRadius: 6,
      }}
    >
      <div style={{ display: "flex", gap: "1.5rem", flexWrap: "wrap" }}>
        {hasGroundTruth && (
          <div>
            <div style={{ fontSize: 12, marginBottom: 4 }}>Original (note: not stored — preview shows reconstruction)</div>
            <div
              style={{
                width: 256,
                height: 256,
                background: "#222",
                color: "#888",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontSize: 13,
              }}
            >
              Ground truth shown as metrics only
            </div>
          </div>
        )}
        {reconUrl && (
          <div>
            <div style={{ fontSize: 12, marginBottom: 4 }}>Reconstructed</div>
            <img
              src={reconUrl}
              alt="Reconstructed image"
              style={{
                width: 256,
                height: 256,
                objectFit: "contain",
                background: "#000",
                border: "1px solid #ccc",
              }}
            />
          </div>
        )}
      </div>
      {hasGroundTruth && (
        <p style={{ marginTop: "0.75rem" }}>
          <strong>PSNR:</strong> {job.psnr_db?.toFixed(2)} dB &nbsp;·&nbsp;{" "}
          <strong>SSIM:</strong> {job.ssim?.toFixed(3)}
        </p>
      )}
      {job.output_dicom_uid && (
        <p style={{ marginTop: "0.5rem" }}>
          <Link to={`/studies/${encodeURIComponent(job.output_dicom_uid)}`}>
            Open reconstructed study →
          </Link>
        </p>
      )}
    </div>
  );
}
