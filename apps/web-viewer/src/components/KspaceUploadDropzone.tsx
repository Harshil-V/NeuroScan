import { useState } from "react";

const ACCEPTED = ".npy,.npz,.h5,.hdf5";

export default function KspaceUploadDropzone({
  onFile,
  disabled,
}: {
  onFile: (file: File) => void;
  disabled?: boolean;
}) {
  const [over, setOver] = useState(false);

  return (
    <div
      data-testid="kspace-dropzone"
      onDragOver={(e) => {
        e.preventDefault();
        setOver(true);
      }}
      onDragLeave={() => setOver(false)}
      onDrop={(e) => {
        e.preventDefault();
        setOver(false);
        const file = e.dataTransfer.files?.[0];
        if (file) onFile(file);
      }}
      style={{
        border: "2px dashed #c9ccd5",
        background: over ? "#eef3ff" : "white",
        borderRadius: 8,
        padding: "1.5rem",
        textAlign: "center",
        opacity: disabled ? 0.5 : 1,
        pointerEvents: disabled ? "none" : "auto",
      }}
    >
      <p style={{ margin: 0 }}>Drop a k-space file (.npy / .npz / .h5)</p>
      <input
        type="file"
        accept={ACCEPTED}
        style={{ marginTop: "0.75rem" }}
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) onFile(f);
        }}
      />
    </div>
  );
}
