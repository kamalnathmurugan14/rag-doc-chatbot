import { useEffect, useState } from "react";
import { api, post, type EvalRun } from "../api/client";

const SAMPLE = `{"question": "How many days of annual leave do employees get?", "expected_files": ["hr/leave_policy.txt"], "expected_keywords": ["24"]}`;
const nums = (s: string) =>
  s
    .split(",")
    .map((x) => Number(x.trim()))
    .filter((n) => Number.isFinite(n) && n > 0);
const f = (v: number | null) => (v == null ? "–" : v.toFixed(2));

export function EvalPage() {
  const [questions, setQuestions] = useState(SAMPLE);
  const [chunks, setChunks] = useState("300,600");
  const [ks, setKs] = useState("3,5");
  const [mmr, setMmr] = useState(true);
  const [rerank, setRerank] = useState(false);
  const [judge, setJudge] = useState(false);
  const [ids, setIds] = useState<number[]>([]);
  const [runs, setRuns] = useState<EvalRun[]>([]);
  const [detail, setDetail] = useState<EvalRun | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const start = async () => {
    setErr(null);
    setDetail(null);
    try {
      const inline = questions
        .split("\n")
        .filter((l) => l.trim())
        .map((l) => JSON.parse(l));
      const r = await post<{ run_ids: number[] }>("/eval/run", {
        inline,
        chunk_tokens: nums(chunks),
        top_k: nums(ks),
        mmr,
        rerank,
        judge,
      });
      setIds(r.run_ids);
    } catch (e) {
      setErr(e instanceof SyntaxError ? "Each line must be valid JSON (JSONL)." : (e as Error).message);
    }
  };
  useEffect(() => {
    if (ids.length === 0) return;
    const tick = async () => {
      const all = await Promise.all(ids.map((i) => api<EvalRun>(`/eval/runs/${i}`)));
      setRuns(all);
      return all.every((r) => r.status !== "running");
    };
    let stop = false;
    const loop = async () => {
      while (!stop && !(await tick().catch(() => true))) await new Promise((r) => setTimeout(r, 800));
    };
    void loop();
    return () => {
      stop = true;
    };
  }, [ids]);

  return (
    <>
      <h2>Evaluation</h2>
      <p className="muted">
        Measures how often retrieval finds the right file (hit-rate@k, MRR). Tick “LLM judge” to also score
        answers and faithfulness (needs Ollama).
      </p>
      <div className="card">
        <label>
          Questions (JSONL: question, expected_answer, expected_files, expected_keywords)
          <textarea
            className="mono"
            rows={5}
            value={questions}
            onChange={(e) => setQuestions(e.target.value)}
            aria-label="Questions"
          />
        </label>
        <div className="row">
          <label>
            Chunk tokens{" "}
            <input
              type="text"
              value={chunks}
              onChange={(e) => setChunks(e.target.value)}
              aria-label="Chunk tokens"
            />
          </label>
          <label>
            Top-k{" "}
            <input type="text" value={ks} onChange={(e) => setKs(e.target.value)} aria-label="Top-k values" />
          </label>
          <label className="row">
            <input type="checkbox" checked={mmr} onChange={(e) => setMmr(e.target.checked)} /> MMR
          </label>
          <label className="row">
            <input type="checkbox" checked={rerank} onChange={(e) => setRerank(e.target.checked)} /> rerank
          </label>
          <label className="row">
            <input type="checkbox" checked={judge} onChange={(e) => setJudge(e.target.checked)} /> LLM judge
          </label>
          <button className="primary" type="button" onClick={start}>
            Run sweep
          </button>
        </div>
        {err && (
          <p className="error" role="alert">
            {err}
          </p>
        )}
      </div>
      {runs.length > 0 && (
        <div className="card">
          <h3 style={{ marginTop: 0 }}>Results</h3>
          <table>
            <thead>
              <tr>
                <th>chunk tokens</th>
                <th>top-k</th>
                <th className="num">hit-rate</th>
                <th className="num">MRR</th>
                <th className="num">answer</th>
                <th className="num">faithful</th>
                <th>status</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {runs.map((r) => (
                <tr key={r.id}>
                  <td>{r.params.chunk_tokens}</td>
                  <td>{r.params.top_k}</td>
                  <td className="num">{f(r.hit_rate)}</td>
                  <td className="num">{f(r.mrr)}</td>
                  <td className="num">{f(r.avg_answer_score)}</td>
                  <td className="num">{f(r.avg_faithfulness)}</td>
                  <td>{r.status}</td>
                  <td>
                    <button type="button" onClick={() => setDetail(r)}>
                      Details
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {detail?.details && (
        <div className="card" aria-label="Per-question details">
          <h3 style={{ marginTop: 0 }}>
            Per question (chunk {detail.params.chunk_tokens}, k={detail.params.top_k})
          </h3>
          <table>
            <thead>
              <tr>
                <th>question</th>
                <th>hit</th>
                <th>retrieved</th>
                <th>answer score</th>
              </tr>
            </thead>
            <tbody>
              {detail.details.questions.map((q) => (
                <tr key={q.question}>
                  <td>{q.question}</td>
                  <td>{q.hit == null ? "–" : q.hit ? "✔" : "✘"}</td>
                  <td className="muted">{q.retrieved_files.join(", ")}</td>
                  <td>{f(q.correctness)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
