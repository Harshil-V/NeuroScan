import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { dicomApi } from "../api/dicom";
import UploadDropzone from "../components/UploadDropzone";
import { ApiClientError } from "../api/client";
import type { UploadResult } from "../types";

export default function UploadPage() {
  const queryClient = useQueryClient();
  const [result, setResult] = useState<UploadResult | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: (file: File) => dicomApi.upload(file),
    onSuccess: (data) => {
      setResult(data);
      setErrorMsg(null);
      queryClient.invalidateQueries({ queryKey: ["studies"] });
    },
    onError: (e: unknown) => {
      setResult(null);
      if (e instanceof ApiClientError) {
        setErrorMsg(`${e.code ?? "error"}: ${e.message}`);
      } else {
        setErrorMsg(String(e));
      }
    },
  });

  return (
    <section>
      <h1>Upload DICOM</h1>
      <UploadDropzone
        onFile={(f) => mutation.mutate(f)}
        disabled={mutation.isPending}
      />
      {mutation.isPending && <p>Uploading...</p>}
      {result && (
        <div data-testid="upload-success" style={{ marginTop: "1rem", color: "#0a6b1f" }}>
          <p>Uploaded successfully.</p>
          <ul>
            <li>Study UID: {result.study_instance_uid}</li>
            <li>Series UID: {result.series_instance_uid}</li>
            <li>SOP UID: {result.sop_instance_uid}</li>
            <li>Checksum: {result.checksum_sha256}</li>
          </ul>
          <Link to={`/studies/${encodeURIComponent(result.study_instance_uid)}`}>
            Open study
          </Link>
        </div>
      )}
      {errorMsg && (
        <p data-testid="upload-error" style={{ color: "#a4282b" }}>{errorMsg}</p>
      )}
    </section>
  );
}
