import { format, parseISO } from "date-fns";
import type { DigestEntry, DailyEntry } from "../utils/types";
import { Card, EmptyState, MarkdownContent, StatBadge, Tag } from "./ui";

interface Props {
  digest: DigestEntry;
}

function humanLabel(digest: DigestEntry): string {
  if (digest.type === "daily") {
    try { return format(parseISO(digest.date), "EEEE, MMMM d, yyyy"); }
    catch { return digest.date; }
  }
  if (digest.type === "weekly") return `Week ${digest.week_label}`;
  return `Report — ${digest.month_label}`;
}

function typeIcon(type: DigestEntry["type"]) {
  return type === "daily" ? "📰" : type === "weekly" ? "📅" : "📊";
}

export default function DigestView({ digest }: Props) {
  const label = humanLabel(digest);
  const generatedAt = (() => {
    try { return format(parseISO(digest.generated_at), "MMM d, yyyy 'at' HH:mm 'UTC'"); }
    catch { return digest.generated_at; }
  })();

  const daily = digest.type === "daily" ? (digest as DailyEntry) : null;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="text-2xl">{typeIcon(digest.type)}</span>
            <h1 className="text-2xl font-bold text-slate-100">{label}</h1>
          </div>
          <p className="text-xs text-slate-500">Generated {generatedAt}</p>
        </div>

        {/* Stats */}
        {daily && (
          <div className="flex items-center gap-3 shrink-0">
            <StatBadge label="Articles" value={daily.article_count} />
            <StatBadge label="Sources"  value={daily.sources.length} />
          </div>
        )}
      </div>

      {/* Sources row */}
      {daily && daily.sources.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {daily.sources.map((s) => (
            <span key={s} className="px-2 py-0.5 text-xs rounded-md bg-slate-800 text-slate-400 border border-slate-700/40">
              {s}
            </span>
          ))}
        </div>
      )}

      {/* Summary */}
      <Card className="p-6">
        {digest.summary
          ? <MarkdownContent content={digest.summary} />
          : <EmptyState message="No summary available." />
        }
      </Card>

      {/* Article list (daily only) */}
      {daily && daily.articles.length > 0 && (
        <div>
          <p className="text-xs font-semibold uppercase tracking-widest text-slate-500 mb-3">
            Source Articles ({daily.articles.length})
          </p>
          <div className="divide-y divide-slate-800">
            {daily.articles.map((art) => (
              <div key={art.link} className="py-3 flex flex-col sm:flex-row sm:items-start gap-2">
                <div className="flex-1 min-w-0">
                  <a
                    href={art.link}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-sm font-medium text-slate-200 hover:text-brand-400 transition-colors line-clamp-2"
                  >
                    {art.title}
                  </a>
                  <p className="text-xs text-slate-500 mt-0.5">
                    {art.source} · {art.date}
                  </p>
                </div>
                <div className="flex flex-wrap gap-1 shrink-0">
                  {art.tags.slice(0, 3).map((t) => <Tag key={t} label={t} />)}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
