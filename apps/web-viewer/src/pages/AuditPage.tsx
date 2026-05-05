import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { auditApi } from "../api/audit";
import AuditTable from "../components/AuditTable";

export default function AuditPage() {
  const [statusFilter, setStatusFilter] = useState<string>("");
  const { data, isLoading, error } = useQuery({
    queryKey: ["audit", statusFilter],
    queryFn: () => auditApi.list({ status: statusFilter || undefined }),
  });
  return (
    <section>
      <h1>Audit Log</h1>
      <label>
        Status:{" "}
        <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
          <option value="">All</option>
          <option value="success">Success</option>
          <option value="failure">Failure</option>
        </select>
      </label>
      {isLoading ? (
        <p>Loading...</p>
      ) : error ? (
        <p>Error: {(error as Error).message}</p>
      ) : (
        <AuditTable items={data?.items ?? []} />
      )}
    </section>
  );
}
