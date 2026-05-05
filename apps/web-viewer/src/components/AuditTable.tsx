import type { AuditEvent } from "../types";

export default function AuditTable({ items }: { items: AuditEvent[] }) {
  if (items.length === 0) return <p>No events yet.</p>;
  return (
    <table>
      <thead>
        <tr>
          <th>Time</th>
          <th>Type</th>
          <th>Status</th>
          <th>Study UID</th>
          <th>Message</th>
        </tr>
      </thead>
      <tbody>
        {items.map((e) => (
          <tr key={e.event_id}>
            <td>{new Date(e.created_at).toLocaleString()}</td>
            <td>{e.event_type}</td>
            <td style={{ color: e.status === "success" ? "#0a6b1f" : "#a4282b" }}>
              {e.status}
            </td>
            <td>{e.study_instance_uid ?? "-"}</td>
            <td>{e.message ?? "-"}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
