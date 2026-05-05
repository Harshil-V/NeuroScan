import { Link, useNavigate } from "react-router-dom";
import type { Study } from "../types";

export default function StudyTable({ items }: { items: Study[] }) {
  const navigate = useNavigate();

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
          <th></th>
        </tr>
      </thead>
      <tbody>
        {items.map((s) => (
          <tr
            key={s.orthanc_study_id}
            onClick={() => navigate(`/studies/${encodeURIComponent(s.study_instance_uid)}`)}
            style={{ cursor: "pointer" }}
          >
            <td>{s.study_date ?? "-"}</td>
            <td>{s.patient_id ?? "-"}</td>
            <td>{s.modality ?? "-"}</td>
            <td>{s.study_description ?? "-"}</td>
            <td>{s.series_count}</td>
            <td>{s.instance_count}</td>
            <td>
              <Link
                to={`/studies/${encodeURIComponent(s.study_instance_uid)}`}
                onClick={(e) => e.stopPropagation()}
                style={{ whiteSpace: "nowrap" }}
              >
                View →
              </Link>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
