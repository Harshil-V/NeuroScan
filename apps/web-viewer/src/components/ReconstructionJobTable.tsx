import type { ReconstructionJob } from "../types";

const STATUS_LABELS: Record<ReconstructionJob["status"], string> = {
  queued: "queued",
  running: "running",
  completed: "done",
  failed: "failed",
};

const STATUS_COLORS: Record<ReconstructionJob["status"], string> = {
  queued: "#666",
  running: "#a47900",
  completed: "#0a6b1f",
  failed: "#a4282b",
};

function formatNumber(n: number | null, decimals = 2): string {
  if (n === null || n === undefined) return "—";
  return n.toFixed(decimals);
}

function formatDuration(ms: number | null): string {
  if (ms === null || ms === undefined) return "—";
  if (ms < 1000) return `${ms} ms`;
  return `${(ms / 1000).toFixed(1)} s`;
}

export default function ReconstructionJobTable({
  items,
  expandedId,
  onToggleExpand,
}: {
  items: ReconstructionJob[];
  expandedId: string | null;
  onToggleExpand: (jobId: string) => void;
}) {
  if (items.length === 0) {
    return <p>No reconstruction jobs yet. Drop a k-space file above to start.</p>;
  }
  return (
    <table>
      <thead>
        <tr>
          <th>Created</th>
          <th>File</th>
          <th>Status</th>
          <th>PSNR</th>
          <th>SSIM</th>
          <th>Duration</th>
        </tr>
      </thead>
      <tbody>
        {items.map((job) => (
          <tr
            key={job.job_id}
            onClick={() => onToggleExpand(job.job_id)}
            style={{
              cursor: "pointer",
              background: expandedId === job.job_id ? "#eef3ff" : undefined,
            }}
          >
            <td>{new Date(job.created_at).toLocaleString()}</td>
            <td>{job.input_file_name}</td>
            <td style={{ color: STATUS_COLORS[job.status] }}>
              {STATUS_LABELS[job.status]}
            </td>
            <td>{formatNumber(job.psnr_db, 1)}</td>
            <td>{formatNumber(job.ssim, 3)}</td>
            <td>{formatDuration(job.duration_ms)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
