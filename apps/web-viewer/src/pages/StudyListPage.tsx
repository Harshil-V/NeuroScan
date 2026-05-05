import { useQuery } from "@tanstack/react-query";
import { studiesApi } from "../api/studies";
import StudyTable from "../components/StudyTable";

export default function StudyListPage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["studies"],
    queryFn: () => studiesApi.list(),
  });
  if (isLoading) return <p>Loading studies...</p>;
  if (error) return <p>Error loading studies: {(error as Error).message}</p>;
  return (
    <section>
      <h1>Studies</h1>
      <StudyTable items={data?.items ?? []} />
    </section>
  );
}
