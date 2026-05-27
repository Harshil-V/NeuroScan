import type { PhiFindingsSummary } from "../types";

const SEV_COLOR: Record<"high" | "medium", string> = {
  high: "#fee2e2",
  medium: "#fef3c7",
};
const SEV_TEXT: Record<"high" | "medium", string> = {
  high: "#991b1b",
  medium: "#92400e",
};

export default function PhiFindingsBanner({
  findings,
}: {
  findings: PhiFindingsSummary;
}) {
  if (findings.total === 0) return null;
  return (
    <div
      style={{
        background: "#fef9c3",
        border: "1px solid #facc15",
        borderRadius: 6,
        padding: "12px 16px",
        margin: "12px 0",
      }}
    >
      <div style={{ fontWeight: 600, marginBottom: 8 }}>
        ⚠ PHI detected: <strong>{findings.high} high-severity</strong> and{" "}
        <strong>{findings.medium} medium-severity</strong> identifiers found
        in this DICOM. The file was uploaded as-is (no tag stripping).
      </div>
      <table style={{ width: "100%", fontSize: 13, borderCollapse: "collapse" }}>
        <thead>
          <tr style={{ borderBottom: "1px solid #facc15", textAlign: "left" }}>
            <th style={{ padding: "4px 8px" }}>Tag</th>
            <th style={{ padding: "4px 8px" }}>Name</th>
            <th style={{ padding: "4px 8px" }}>Severity</th>
          </tr>
        </thead>
        <tbody>
          {findings.items.map((item) => (
            <tr key={item.tag}>
              <td style={{ padding: "4px 8px", fontFamily: "monospace" }}>
                {item.tag}
              </td>
              <td style={{ padding: "4px 8px" }}>{item.tag_name}</td>
              <td style={{ padding: "4px 8px" }}>
                <span
                  style={{
                    background: SEV_COLOR[item.severity],
                    color: SEV_TEXT[item.severity],
                    padding: "2px 8px",
                    borderRadius: 4,
                    fontSize: 12,
                  }}
                >
                  {item.severity}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
