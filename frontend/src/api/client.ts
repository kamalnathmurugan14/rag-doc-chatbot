// Tiny typed fetch wrapper. Every backend error has the shape { error: { code, message } }.
export const API_URL: string = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(
    public code: string,
    message: string,
    public status: number,
  ) {
    super(message);
  }
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, init);
  } catch {
    throw new ApiError("NETWORK", "Cannot reach the backend. Is it running on " + API_URL + "?", 0);
  }
  if (res.status === 204) return undefined as T;
  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new ApiError(
      body?.error?.code ?? "HTTP_" + res.status,
      body?.error?.message ?? res.statusText,
      res.status,
    );
  }
  return body as T;
}

export const post = <T>(path: string, body?: unknown) =>
  api<T>(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body ?? {}),
  });

export const qs = (params: Record<string, string | number | undefined>) =>
  new URLSearchParams(
    Object.entries(params)
      .filter(([, v]) => v !== undefined && v !== "")
      .map(([k, v]) => [k, String(v)]),
  ).toString();

// ---- types -------------------------------------------------------------
export interface Entry {
  name: string;
  type: "dir" | "file";
  size: number;
  modified: string;
  path: string;
}
export interface Tree {
  path: string;
  entries: Entry[];
}
export interface Source {
  n: number;
  chunk_id: string;
  rel_path: string;
  page: number;
  similarity: number;
  rerank: number | null;
  snippet: string;
}
export interface Debug {
  query: string;
  rewritten_query: string;
  fetched: number;
  below_min_similarity: number;
  stages: string[];
  rerank: string;
  embedder: string;
  timings_ms: Record<string, number>;
  options: { top_k: number; mmr: boolean; rerank: boolean; min_similarity: number };
  sources: Source[];
  prompt: string;
  dropped_for_budget: string[];
  usage?: { tokens_in: number; tokens_out: number };
  history_turns: number;
}
export interface ChatOptions {
  top_k?: number;
  mmr?: boolean;
  rerank?: boolean;
  temperature?: number;
}
export interface Scope {
  files: string[];
  folders: string[];
}
export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  streaming?: boolean;
  error?: string | null;
  sources?: Source[];
  citations?: Source[];
  alsoConsulted?: Source[];
  debug?: Debug;
  rewritten?: string | null;
}
export interface Session {
  id: number;
  title: string;
  created_at: string;
}
export interface SourceDetail {
  chunk_id: string;
  text: string;
  rel_path: string;
  page: number;
  char_start: number;
  char_end: number;
  neighbors: ({ chunk_id: string; text: string; page: number } | null)[];
}
export interface IngestStatus {
  job_id: string | null;
  state: "idle" | "running" | "done";
  done: number;
  total: number;
  current: string | null;
  errors: { rel_path: string; error: string }[];
  indexed_chunks: number;
}
export interface FileRow {
  rel_path: string;
  status: string;
  n_chunks: number;
  error: string | null;
  indexed_at: string | null;
}
export interface Health {
  status: string;
  version: string;
  chroma: boolean;
  ollama: boolean;
  embedder: string;
  indexed_chunks: number;
  model: string;
  reranker: boolean;
}
export interface EvalRun {
  id: number;
  status: string;
  hit_rate: number | null;
  mrr: number | null;
  avg_faithfulness: number | null;
  avg_answer_score: number | null;
  params: {
    chunk_tokens: number;
    top_k: number;
    mmr: boolean;
    rerank: boolean;
    judge: boolean;
    n_questions: number;
  };
  details?: {
    questions: {
      question: string;
      retrieved_files: string[];
      hit: boolean | null;
      rr: number | null;
      answer: string | null;
      correctness: number | null;
      faithfulness: number | null;
      keyword_score: number | null;
    }[];
    keyword_score: number | null;
  };
}
