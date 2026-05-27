import { useQueries } from "@tanstack/react-query";
import { storageApi } from "../api/storage";
import type { AuditEvent } from "../types";

function StatusCell({ status }: { status: AuditEvent["status"] }) {
  const color =
    status === "success"
      ? "#0a6b1f"
      : status === "success_minio_skipped"
        ? "#a47900"
        : "#a4282b";
  return <span style={{ color }}>{status}</span>;
}

function ShareLinkButton({ objectId }: { objectId: number }) {
  const onClick = async () => {
    try {
      const result = await storageApi.presignedUrl(objectId, 300);
      await navigator.clipboard.writeText(result.url);
      alert(
        `Presigned URL copied (expires ${new Date(result.expires_at).toLocaleTimeString()})`,
      );
    } catch (e) {
      alert(`Failed to mint URL: ${(e as Error).message}`);
    }
  };
  return (
    <button onClick={onClick} style={{ fontSize: 12 }}>
      Share link
    </button>
  );
}

export default function AuditTable({ items }: { items: AuditEvent[] }) {
  const checksums = Array.from(
    new Set(items.map((e) => e.checksum_sha256).filter(Boolean) as string[]),
  );
  const queries = useQueries({
    queries: checksums.map((sha) => ({
      queryKey: ["storage-by-sha", sha],
      queryFn: () => storageApi.list({ sha256: sha, limit: 1 }),
      staleTime: 60_000,
    })),
  });

  const shaToObjectId: Record<string, number | null> = {};
  checksums.forEach((sha, i) => {
    const data = queries[i].data;
    shaToObjectId[sha] = data && data.items.length > 0 ? data.items[0].id : null;
  });

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
          <th>Share</th>
        </tr>
      </thead>
      <tbody>
        {items.map((e) => {
          const objectId = e.checksum_sha256
            ? shaToObjectId[e.checksum_sha256]
            : null;
          return (
            <tr key={e.event_id}>
              <td>{new Date(e.created_at).toLocaleString()}</td>
              <td>{e.event_type}</td>
              <td>
                <StatusCell status={e.status} />
              </td>
              <td>{e.study_instance_uid ?? "-"}</td>
              <td>{e.message ?? "-"}</td>
              <td>{objectId ? <ShareLinkButton objectId={objectId} /> : "-"}</td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}
