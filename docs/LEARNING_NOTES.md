# Learning notes

## Concepts
- **Why RAG reduces hallucination** — instead of answering from its memory, the model reads passages we retrieved and must cite them. It can still err, but each claim is checkable, and "not in the documents" is an allowed answer.
- **Embeddings vs keywords** — embeddings place similar *meaning* near each other ("vacation days" ≈ "annual leave"); keyword search needs the same words. Embeddings can miss exact identifiers (invoice numbers) — that is why hybrid BM25+vector is a common bonus.
- **Chunk size / overlap** — small chunks = precise but lose context; big chunks = more context but diluted embeddings and fewer fit in the prompt. Overlap (12 %) keeps sentences that straddle a boundary retrievable.
- **top-k, FETCH_K, MMR** — fetch many candidates (20), keep the best few (5). MMR trades relevance for diversity so five near-identical paragraphs don't crowd out other sources.
- **Reranking** — a cross-encoder reads (question, passage) *together*: slower but sharper than comparing two precomputed vectors. Use it on the small candidate set.
- **Query rewriting** — "what about the second one?" is meaningless to a vector search; the LLM turns it into a standalone question first.
- **Grounding prompt + citations** — numbered context, "cite like [1]", a fixed refusal sentence. Citation faithfulness = does chunk [1] really support the claim? (The LLM judge's *faithfulness* score approximates this.)
- **Metrics** — hit-rate@k (was an expected file retrieved?), MRR (how high?), answer correctness & faithfulness (judge, 0–2). Retrieval metrics are cheap and deterministic: tune them first.
- **Debugging a bad answer** — open Debug: (1) was the right chunk retrieved? no → chunking/embedding/`MIN_SIMILARITY`/query rewrite; (2) retrieved but not used → prompt, `TOP_K`, context trimming ("dropped for budget"); (3) used but misread → model size/temperature.

## Tuning notes (how to run your own experiments)
Run `python eval/run_eval.py eval/questions.sample.jsonl --chunk-tokens 200 400 800 --top-k 1 3 5 --judge` against your own documents and fill in:

| chunk tokens | top-k | hit@k | MRR | answer | faithful | notes |
|---|---|---|---|---|---|---|
| _your results_ | | | | | | |

Rules of thumb to test: hit@k rises with k but answer quality can fall (distraction); larger chunks help questions needing context, hurt precise lookups; MMR helps broad questions, can hurt single-fact ones; rerank helps most when `FETCH_K` ≫ `TOP_K`. Results depend entirely on your documents, embedder and model, so none are pre-filled here.

## Milestones
**M0** scaffold/health (Chroma + Ollama). **M1** safe FS + explorer with **file and folder checkboxes**. **M2** extractors, cleaner (de-hyphenation!), chunker with pages. **M3** embedding + Chroma + ingestion job (*mistake found by tests:* an error on a *new* file inserted the row twice and killed the job — now an upsert). **M4** incremental by hash (add / modify / delete). **M5** retrieval API + debug (no LLM yet). **M6** grounded generation, streaming, citations, "I could not find this". **M7** sessions, history, follow-up rewriting. **M8** source panel with neighbours, scope. **M9** MMR + rerank toggles, A/B in Debug. **M10** evaluation harness + sweeps. **M11** polish, injection test document, docs, demo.
