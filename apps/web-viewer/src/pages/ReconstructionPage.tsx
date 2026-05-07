import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { reconstructionApi } from "../api/reconstruction";
import { ApiClientError } from "../api/client";
import KspaceUploadDropzone from "../components/KspaceUploadDropzone";
import ReconstructionJobTable from "../components/ReconstructionJobTable";
import SideBySidePreview from "../components/SideBySidePreview";

const ACTIVE_STATUSES = new Set(["queued", "running"]);

export default function ReconstructionPage() {
  const queryClient = useQueryClient();
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const { data, isLoading, error } = useQuery({
    queryKey: ["reconstructionJobs"],
    queryFn: () => reconstructionApi.list({ limit: 50 }),
    refetchInterval: (query) => {
      const items = query.state.data?.items ?? [];
      return items.some((j) => ACTIVE_STATUSES.has(j.status)) ? 2000 : false;
    },
  });

  const mutation = useMutation({
    mutationFn: (file: File) => reconstructionApi.submit(file),
    onSuccess: () => {
      setErrorMsg(null);
      queryClient.invalidateQueries({ queryKey: ["reconstructionJobs"] });
    },
    onError: (e: unknown) => {
      if (e instanceof ApiClientError) {
        setErrorMsg(`${e.code ?? "error"}: ${e.message}`);
      } else {
        setErrorMsg(String(e));
      }
    },
  });

  const items = data?.items ?? [];
  const expandedJob = items.find((j) => j.job_id === expandedId) ?? null;

  return (
    <section>
      <h1>Reconstruction</h1>
      <p style={{ color: "#666" }}>
        Upload k-space data (.npy / .npz / .h5). The service runs an inverse FFT,
        stores the result as DICOM in the local archive, and computes PSNR + SSIM
        when ground truth is embedded (forward-generated .npz files).
      </p>

      <KspaceUploadDropzone
        onFile={(f) => mutation.mutate(f)}
        disabled={mutation.isPending}
      />

      {mutation.isPending && <p>Uploading…</p>}
      {errorMsg && (
        <p data-testid="recon-error" style={{ color: "#a4282b" }}>
          {errorMsg}
        </p>
      )}

      <h2 style={{ marginTop: "1.5rem" }}>Recent jobs</h2>
      {isLoading ? (
        <p>Loading…</p>
      ) : error ? (
        <p style={{ color: "#a4282b" }}>Error: {(error as Error).message}</p>
      ) : (
        <ReconstructionJobTable
          items={items}
          expandedId={expandedId}
          onToggleExpand={(id) =>
            setExpandedId((current) => (current === id ? null : id))
          }
        />
      )}

      {expandedJob && <SideBySidePreview job={expandedJob} />}
    </section>
  );
}
