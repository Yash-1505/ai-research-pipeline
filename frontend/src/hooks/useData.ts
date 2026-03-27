import { useState, useEffect } from "react";
import type { DataIndex, DigestEntry } from "../utils/types";

const GITHUB_RAW = "https://raw.githubusercontent.com/Yash-1505/ai-research-pipeline/main";

async function fetchJSON<T>(path: string): Promise<T> {
  const res = await fetch(`${GITHUB_RAW}/${path}`);
  if (!res.ok) throw new Error(`HTTP ${res.status} for ${path}`);
  return res.json() as Promise<T>;
}

export function useIndex() {
  const [index, setIndex]     = useState<DataIndex | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState<string | null>(null);

  useEffect(() => {
    fetchJSON<DataIndex>("data/index.json")
      .then(setIndex)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  return { index, loading, error };
}

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