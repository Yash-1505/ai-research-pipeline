import React from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import clsx from "clsx";

// ── Spinner ───────────────────────────────────────────────────────────────────
export function Spinner({ className }: { className?: string }) {
  return (
    <div className={clsx("flex items-center justify-center", className)}>
      <div className="w-8 h-8 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
    </div>
  );
}

// ── ErrorCard ─────────────────────────────────────────────────────────────────
export function ErrorCard({ message }: { message: string }) {
  return (
    <div className="rounded-xl bg-red-950/40 border border-red-800/50 p-6 text-red-300">
      <p className="font-semibold mb-1">⚠ Error</p>
      <p className="text-sm font-mono">{message}</p>
    </div>
  );
}

// ── Empty State ───────────────────────────────────────────────────────────────
export function EmptyState({ message }: { message: string }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-20 text-slate-500">
      <span className="text-5xl">📭</span>
      <p className="text-sm">{message}</p>
    </div>
  );
}

// ── Badge ─────────────────────────────────────────────────────────────────────
const tagColors: Record<string, string> = {
  AI:            "bg-brand-900/60 text-brand-300 border-brand-700/40",
  ML:            "bg-violet-900/60 text-violet-300 border-violet-700/40",
  research:      "bg-emerald-900/60 text-emerald-300 border-emerald-700/40",
  industry:      "bg-amber-900/60 text-amber-300 border-amber-700/40",
  business:      "bg-orange-900/60 text-orange-300 border-orange-700/40",
  "open-source": "bg-pink-900/60 text-pink-300 border-pink-700/40",
  default:       "bg-slate-800/60 text-slate-300 border-slate-700/40",
};

export function Tag({ label }: { label: string }) {
  const cls = tagColors[label] ?? tagColors.default;
  return (
    <span className={clsx("inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border", cls)}>
      {label}
    </span>
  );
}

// ── Markdown Renderer ─────────────────────────────────────────────────────────
export function MarkdownContent({ content }: { content: string }) {
  return (
    <div className="prose-ai">
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
    </div>
  );
}

// ── Stats Row ─────────────────────────────────────────────────────────────────
export function StatBadge({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="flex flex-col items-center px-4 py-2 rounded-lg bg-slate-800/50 border border-slate-700/50">
      <span className="text-xl font-bold text-brand-400">{value}</span>
      <span className="text-xs text-slate-400 mt-0.5">{label}</span>
    </div>
  );
}

// ── Section Heading ───────────────────────────────────────────────────────────
export function SectionHeading({ children }: { children: React.ReactNode }) {
  return (
    <h2 className="text-xs font-semibold uppercase tracking-widest text-slate-500 mb-3">
      {children}
    </h2>
  );
}

// ── Card ─────────────────────────────────────────────────────────────────────
export function Card({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={clsx(
        "rounded-xl bg-slate-900/70 border border-slate-700/50 backdrop-blur-sm",
        className
      )}
    >
      {children}
    </div>
  );
}
