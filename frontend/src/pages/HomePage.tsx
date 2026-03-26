import { useIndex, useDigest } from "../hooks/useData";
import { EmptyState, ErrorCard, Spinner } from "../components/ui";
import DigestView from "../components/DigestView";

export default function HomePage() {
  const { index, loading: indexLoading, error: indexError } = useIndex();

  const latestFile = index?.daily?.[0]?.file ?? null;
  const { digest, loading: digestLoading, error: digestError } = useDigest(latestFile);

  if (indexLoading || digestLoading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="text-center space-y-3">
          <Spinner />
          <p className="text-slate-500 text-sm">Loading today's briefing…</p>
        </div>
      </div>
    );
  }

  if (indexError) return <ErrorCard message={indexError} />;
  if (digestError) return <ErrorCard message={digestError} />;

  if (!index || index.daily.length === 0) {
    return (
      <EmptyState message="No daily digests yet. Run the pipeline to generate your first briefing." />
    );
  }

  if (!digest) return <Spinner className="mt-20" />;

  return <DigestView digest={digest} />;
}
