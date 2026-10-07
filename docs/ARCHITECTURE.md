# Architecture

| Module | Responsibility |
|---|---|
| `services/ingestion_service.py` | scan → extract → clean → chunk → embed → Chroma; SHA-256 incremental; background job with progress; index *signature* (embedder + chunk size) forces rebuild when it changes |
| `rag/vector_store.py` | ChromaDB wrapper (cosine space, we supply embeddings); filters by `rel_path`; neighbours; ephemeral stores for eval sweeps |
| `rag/retriever.py` | embed query → Chroma (`FETCH_K`) → similarity cut → optional MMR → optional rerank → `TOP_K`, with per-stage debug/timings |
| `rag/query_rewriter.py` | LLM rewrites follow-ups into standalone questions (temperature 0, skipped without history) |
| `rag/prompt_builder.py` | Jinja2 prompt, token budget: drops lowest-ranked chunks until it fits |
| `rag/citations.py` | parses `[n]`, drops invalid numbers, de-duplicates, lists uncited chunks as "also consulted" |
| `services/chat_service.py` | orchestrates a turn and emits SSE events; persists messages (+ debug JSON); saves partial answers on Stop |
| `services/eval_service.py` | hit-rate@k, MRR, LLM-judge scores, parameter sweeps |

## Data
- **Chroma** collection `docs`: id `"{file_id}:{chunk_index}"`, document = clean chunk text, metadata `file_id, rel_path, page, chunk_index, sha256, ext, char_start, char_end`.
- **SQLite**: `files`, `chat_sessions`, `messages (citations_json, debug_json)`, `eval_sets`, `eval_runs`, `meta` (index signature).

## Decisions & trade-offs
- **Embed with a header, display without it** – `File: x, Page: n` before the text helps queries that mention a file or page; the stored text stays clean for display and citations.
- **Scope = explicit file list** – folders are expanded against the indexed-files table (Chroma has no prefix filter). An unknown scope yields an impossible path → *zero* results, never "everything".
- **No LLM call when nothing relevant is found** – cheaper, faster and removes a hallucination opportunity; the answer is the exact fixed sentence.
- **Prompt budget before generation** – prompt + answer must fit `CONTEXT_TOKENS`, otherwise Ollama silently truncates the *start* of the prompt (rules and top chunks!).
- **Validate first, stream second** – unknown sessions etc. fail with proper HTTP errors; once streaming starts, problems arrive as `error` events.
- **Closing the stream = cancelling generation** – the SSE generator is closed on disconnect, which closes the Ollama HTTP request; the partial answer is stored with “(stopped)”.
- **Eval sweeps build throw-away in-memory indexes** for other chunk sizes, so the real index is untouched.
- **Judge failures are excluded, not zero** – unparsable judge output doesn't drag the average down.
