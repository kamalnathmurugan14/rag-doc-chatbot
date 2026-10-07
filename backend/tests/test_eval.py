import json
import time

import pytest

from app.errors import AppError
from app.services.eval_service import keyword_score, parse_items, retrieval_metrics

QUESTIONS = [
    {
        "question": "how many vacation days do I get",
        "expected_answer": "24 days",
        "expected_files": ["hr/leave_policy.txt"],
        "expected_keywords": ["24"],
    },
    {
        "question": "how often should passwords change",
        "expected_answer": "every 90 days",
        "expected_files": ["it/security.md"],
        "expected_keywords": ["90"],
    },
    {
        "question": "what is the cancellation notice",
        "expected_answer": "60 days",
        "expected_files": ["contracts/acme.pdf"],
    },
]


def wait(client, ids, timeout=20):
    for _ in range(int(timeout / 0.1)):
        runs = [client.get(f"/eval/runs/{i}").json() for i in ids]
        if all(r["status"] != "running" for r in runs):
            return runs
        time.sleep(0.1)
    raise AssertionError("eval did not finish")


def test_metric_helpers():
    assert retrieval_metrics(["a", "b", "c"], ["c"]) == (True, pytest.approx(1 / 3))
    assert retrieval_metrics(["a"], ["z"]) == (False, 0.0)
    assert retrieval_metrics(["a", "b"], ["b", "a"]) == (True, 1.0)
    assert (
        keyword_score("The answer is 24 days", ["24", "days", "xyz"]) == pytest.approx(2 / 3)
        and keyword_score("x", []) is None
    )


def test_parse_items_validation():
    assert parse_items(['{"question": "q"}', "", '{"question": "r", "expected_files": ["a"]}'])[1][
        "expected_files"
    ] == ["a"]
    for bad in (["not json"], ['{"no_question": 1}'], [""], ["[1,2]"]):
        with pytest.raises(AppError):
            parse_items(bad)


def test_retrieval_eval_run(indexed, client):
    ids = client.post("/eval/run", json={"inline": QUESTIONS, "top_k": [3]}).json()["run_ids"]
    (run,) = wait(client, ids)
    assert run["status"] == "done" and run["hit_rate"] == 1.0 and run["mrr"] > 0.5 and run["avg_faithfulness"] is None
    qs = run["details"]["questions"]
    assert len(qs) == 3 and all(q["hit"] for q in qs) and qs[0]["retrieved_files"][0] == "hr/leave_policy.txt"
    assert client.get("/eval/runs").json()["runs"][0]["id"] == run["id"]


def test_sweep_over_chunk_size_and_top_k(indexed, client):
    ids = client.post("/eval/run", json={"inline": QUESTIONS, "chunk_tokens": [150, 600], "top_k": [1, 3]}).json()[
        "run_ids"
    ]
    runs = wait(client, ids)
    assert len(runs) == 4 and {(r["params"]["chunk_tokens"], r["params"]["top_k"]) for r in runs} == {
        (150, 1),
        (150, 3),
        (600, 1),
        (600, 3),
    }
    assert all(r["status"] == "done" and r["hit_rate"] is not None for r in runs)
    k3 = [r for r in runs if r["params"]["top_k"] == 3]
    assert all(
        r["hit_rate"]
        >= [
            x for x in runs if x["params"]["top_k"] == 1 and x["params"]["chunk_tokens"] == r["params"]["chunk_tokens"]
        ][0]["hit_rate"]
        for r in k3
    )


def test_llm_judge_and_keywords(indexed, client, llm):
    def respond(messages, params):
        u = messages[-1]["content"]
        return '{"correctness": 2, "faithfulness": 1}' if "grading an answer" in u else "Employees get 24 days [1]."

    llm.responder = respond
    ids = client.post("/eval/run", json={"inline": QUESTIONS[:1], "judge": True}).json()["run_ids"]
    (run,) = wait(client, ids)
    assert run["avg_answer_score"] == 1.0 and run["avg_faithfulness"] == 0.5
    row = run["details"]["questions"][0]
    assert (
        row["answer"].startswith("Employees get 24")
        and row["keyword_score"] == 1.0
        and run["details"]["keyword_score"] == 1.0
    )


def test_unparsable_judge_output_is_excluded(indexed, client, llm):
    llm.responder = lambda m, p: "I refuse to output JSON"
    (run,) = wait(client, client.post("/eval/run", json={"inline": QUESTIONS[:1], "judge": True}).json()["run_ids"])
    assert run["status"] == "done" and run["avg_answer_score"] is None


def test_questions_file_and_errors(indexed, client, settings):
    (settings.docs_root / "q.jsonl").write_text("\n".join(json.dumps(q) for q in QUESTIONS), encoding="utf-8")
    ids = client.post("/eval/run", json={"questions_path": "q.jsonl"}).json()["run_ids"]
    assert wait(client, ids)[0]["details"]["questions"][1]["question"].startswith("how often")
    assert client.post("/eval/run", json={"questions_path": "../../etc/passwd"}).status_code == 400
    assert client.post("/eval/run", json={"questions_path": "missing.jsonl"}).status_code == 404
    assert client.post("/eval/run", json={}).json()["error"]["code"] == "MISSING_INPUT"
    (settings.docs_root / "bad.jsonl").write_text("{oops", encoding="utf-8")
    assert client.post("/eval/run", json={"questions_path": "bad.jsonl"}).json()["error"]["code"] == "BAD_EVAL_FILE"
    assert client.get("/eval/runs/999").status_code == 404


def test_sample_questions_file_is_valid():
    from pathlib import Path

    items = parse_items(
        Path(__file__)
        .resolve()
        .parent.parent.joinpath("eval", "questions.sample.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    )
    assert len(items) >= 3 and all(i["expected_files"] for i in items)
