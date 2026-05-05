import { previewUrl } from "../api/client";

export default function PreviewImage({
  orthancInstanceId,
  alt,
}: {
  orthancInstanceId: string;
  alt: string;
}) {
  return (
    <img
      src={previewUrl(orthancInstanceId)}
      alt={alt}
      style={{
        maxWidth: 256,
        maxHeight: 256,
        background: "black",
        border: "1px solid #ccc",
      }}
    />
  );
}
