import { useState, useEffect } from "react";
import type { DataIndex, DigestEntry } from "../utils/types";

const BASE = (import.meta.env.VITE_DATA_BASE_URL ?? "").replace(/\/$/, "");

async function fetchJSON<T>(path: string): Promise<T> {
  // Build URL explicitly — never produce a protocol-relative "//..." URL.
  // If BASE is empty (default on Vercel), path is served from the root.
  const url = BASE ? `${BASE}/${path}` : `/${path}`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`HTTP ${res.status} for ${path}`);
  return res.json() as Promise<T>;
}

// ── useIndex ─────────────────────────────────────────────────────────────────
export function useIndex() {
  const [index, setIndex]   = useState<DataIndex | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError]   = useState<string | null>(null);

  useEffect(() => {
    fetchJSON<DataIndex>("index.json")
      .then(setIndex)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  return { index, loading, error };
}

// ── useDigest ────────────────────────────────────────────────────────────────
export function useDigest(filePath: string | null) {
  const [digest, setDigest]   = useState<DigestEntry | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState<string | null>(null);

  useEffect(() => {
    if (!filePath) { setDigest(null); return; }
    setLoading(true);
    setError(null);
    fetchJSON<DigestEntry>(filePath)
      .then(setDigest)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, [filePath]);

  return { digest, loading, error };
}
