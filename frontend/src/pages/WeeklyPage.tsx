import { useState } from "react";
import { useIndex, useDigest } from "../hooks/useData";
import { Card, EmptyState, ErrorCard, SectionHeading, Spinner } from "../components/ui";
import DigestView from "../components/DigestView";
import clsx from "clsx";

export default function WeeklyPage() {
  const { index, loading, error } = useIndex();
  const [selectedFile, setSelectedFile] = useState<string | null>(null);
  const { digest, loading: digestLoading, error: digestError } = useDigest(selectedFile);

  if (loading) return <Spinner className="mt-20" />;
  if (error)   return <ErrorCard message={error} />;

  const items = index?.weekly ?? [];

  if (items.length === 0) {
    return (
      <EmptyState message="No weekly digests yet. They are generated every Monday by the pipeline." />
    );
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-[220px_1fr] gap-6">
      {/* Sidebar */}
      <aside className="space-y-1 lg:sticky lg:top-20 lg:self-start">
        <SectionHeading>Weekly Digests</SectionHeading>
        {items.map((item) => {
          const isActive = item.file === selectedFile;
          return (
            <button
              key={item.file}
              onClick={() => setSelectedFile(item.file)}
              className={clsx(
                "w-full text-left px-3 py-2 rounded-lg text-sm transition-colors",
                isActive
                  ? "bg-brand-600/20 text-brand-300 border border-brand-700/40"
                  : "text-slate-400 hover:bg-slate-800/60 hover:text-slate-200"
              )}
            >
              📅 {item.label}
            </button>
          );
        })}
      </aside>

      {/* Main */}
      <main>
        {!selectedFile ? (
          <Card className="flex items-center justify-center h-64 text-slate-600">
            <p className="text-sm">← Select a week to read the digest</p>
          </Card>
        ) : digestLoading ? (
          <Spinner className="mt-20" />
        ) : digestError ? (
          <ErrorCard message={digestError} />
        ) : digest ? (
          <DigestView digest={digest} />
        ) : null}
      </main>
    </div>
  );
}
