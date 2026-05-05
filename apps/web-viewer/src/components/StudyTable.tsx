import { Link } from "react-router-dom";
import type { Study } from "../types";

export default function StudyTable({ items }: { items: Study[] }) {
  if (items.length === 0) {
    return (
      <p>
        No studies yet. <Link to="/upload">Upload one</Link>.
      </p>
    );
  }
  return (
    <table>
      <thead>
        <tr>
          <th>Study Date</th>
          <th>Patient ID</th>
          <th>Modality</th>
          <th>Description</th>
          <th>Series</th>
          <th>Instances</th>
        </tr>
      </thead>
      <tbody>
        {items.map((s) => (
          <tr
            key={s.orthanc_study_id}
            onClick={() => {
              window.location.href = `/studies/${encodeURIComponent(s.study_instance_uid)}`;
            }}
          >
            <td>{s.study_date ?? "-"}</td>
            <td>{s.patient_id ?? "-"}</td>
            <td>{s.modality ?? "-"}</td>
            <td>{s.study_description ?? "-"}</td>
            <td>{s.series_count}</td>
            <td>{s.instance_count}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
