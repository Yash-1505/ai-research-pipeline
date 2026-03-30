import { useState } from "react";
import { format, parseISO } from "date-fns";
import { useIndex, useDigest } from "../hooks/useData";
import { Card, EmptyState, ErrorCard, SectionHeading, Spinner } from "../components/ui";
import DigestView from "../components/DigestView";
import clsx from "clsx";

export default function ArchivePage() {
  const { index, loading, error } = useIndex();
  const [selectedFile, setSelectedFile] = useState<string | null>(null);
  const { digest, loading: digestLoading, error: digestError } = useDigest(selectedFile);

  if (loading) return <Spinner className="mt-20" />;
  if (error)   return <ErrorCard message={error} />;

  const items = index?.daily ?? [];

  if (items.length === 0) {
    return <EmptyState message="No archive entries yet. Run the daily pipeline to start building history." />;
  }

  // Group by year-month — guard against missing/malformed date fields
  const grouped: Record<string, typeof items> = {};
  for (const item of items) {
    const key = item.date?.slice(0, 7) || "unknown";
    (grouped[key] ??= []).push(item);
  }

  function formatItemDate(dateStr: string): string {
    try {
      return format(parseISO(dateStr), "EEE, MMM d");
    } catch {
      return dateStr || "Unknown date";
    }
  }

  function formatMonthHeader(monthKey: string): string {
    if (monthKey === "unknown") return "Unknown date";
    try {
      return format(parseISO(`${monthKey}-01`), "MMMM yyyy");
    } catch {
      return monthKey;
    }
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-[280px_1fr] gap-6">
      {/* Sidebar: date list */}
      <aside className="space-y-5 lg:sticky lg:top-20 lg:self-start lg:max-h-[calc(100vh-6rem)] lg:overflow-y-auto scrollbar-thin pr-1">
        <SectionHeading>Archive</SectionHeading>
        {Object.entries(grouped)
          .sort(([a], [b]) => b.localeCompare(a))
          .map(([month, entries]) => (
            <div key={month}>
              <p className="text-xs text-slate-500 font-semibold mb-1.5 px-1">
                {formatMonthHeader(month)}
              </p>
              <div className="space-y-1">
                {entries.map((item) => {
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
                      <span className="font-medium">
                        {formatItemDate(item.date)}
                      </span>
                      {item.article_count != null && (
                        <span className="ml-2 text-xs text-slate-600">
                          {item.article_count} articles
                        </span>
                      )}
                    </button>
                  );
                })}
              </div>
            </div>
          ))}
      </aside>

      {/* Main: selected digest */}
      <main>
        {!selectedFile ? (
          <Card className="flex items-center justify-center h-64 text-slate-600">
            <p className="text-sm">← Select a date to read that day's briefing</p>
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
