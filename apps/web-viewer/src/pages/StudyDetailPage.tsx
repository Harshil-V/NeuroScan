import { useParams } from "react-router-dom";
import { useQueries, useQuery } from "@tanstack/react-query";
import { studiesApi } from "../api/studies";
import PreviewImage from "../components/PreviewImage";
import type { Series } from "../types";

export default function StudyDetailPage() {
  const { studyInstanceUid = "" } = useParams();
  const { data: study, isLoading, error } = useQuery({
    queryKey: ["study", studyInstanceUid],
    queryFn: () => studiesApi.detail(studyInstanceUid),
    enabled: !!studyInstanceUid,
  });

  const seriesQueries = useQueries({
    queries: (study?.series ?? []).map((s: Series) => ({
      queryKey: ["series-instances", s.series_instance_uid],
      queryFn: () => studiesApi.seriesInstances(s.series_instance_uid),
    })),
  });

  if (isLoading) return <p>Loading...</p>;
  if (error) return <p>Error: {(error as Error).message}</p>;
  if (!study) return null;

  return (
    <section>
      <h1>Study {study.study_description ?? study.study_instance_uid}</h1>
      <p>
        Patient: {study.patient_id ?? "-"} · Modality: {study.modality ?? "-"} · Date:{" "}
        {study.study_date ?? "-"}
      </p>

      {study.series.map((s, idx) => {
        const instances = seriesQueries[idx]?.data?.items ?? [];
        return (
          <div key={s.series_instance_uid} style={{ marginTop: "1.5rem" }}>
            <h2>
              Series {s.series_number ?? "?"} — {s.series_description ?? s.series_instance_uid}
            </h2>
            <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
              {instances.map((i) => (
                <PreviewImage
                  key={i.orthanc_instance_id}
                  orthancInstanceId={i.orthanc_instance_id}
                  alt={`Instance ${i.instance_number ?? i.sop_instance_uid}`}
                />
              ))}
            </div>
          </div>
        );
      })}
    </section>
  );
}
