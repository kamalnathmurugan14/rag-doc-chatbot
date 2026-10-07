import { useEffect, useState } from "react";
import type { ChatOptions } from "../api/client";

const KEY = "rag-options";
const DEFAULTS: ChatOptions = { top_k: 5, mmr: true, rerank: false, temperature: 0.1 };

/** Retrieval/generation options, remembered in localStorage (best effort). */
export function useOptions(): [ChatOptions, (o: ChatOptions) => void] {
  const [opts, setOpts] = useState<ChatOptions>(() => {
    try {
      return { ...DEFAULTS, ...JSON.parse(localStorage.getItem(KEY) ?? "{}") };
    } catch {
      return DEFAULTS;
    }
  });
  useEffect(() => {
    try {
      localStorage.setItem(KEY, JSON.stringify(opts));
    } catch {
      /* ignore */
    }
  }, [opts]);
  return [opts, setOpts];
}
