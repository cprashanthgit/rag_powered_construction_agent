# -*- coding: utf-8 -*-
"""
eval/run_eval.py — Phase 6: RAGAS Evaluation Pipeline

Runs the full 25-question golden dataset through the live RAG pipeline
and scores each answer using RAGAS metrics. Results are saved as a
markdown report in eval/results/<run-id>.md.

This script is STANDALONE — it never modifies the running API.
Run it from the project root directory:

    python eval/run_eval.py
    python eval/run_eval.py 2026-06-21-baseline
    python eval/run_eval.py 2026-06-21-mode2 --mode openai

Requirements:
    pip install ragas datasets
    OpenAI API key must be set in .env (RAGAS uses LLM-as-judge)

RAGAS Metrics:
    faithfulness        — Does the answer stick to the retrieved context?
                          1.0 = zero hallucination, 0.0 = fully hallucinated
    answer_relevancy    — Does the answer address the question asked?
                          1.0 = perfectly on-topic
    context_precision   — Are the retrieved chunks ranked well (relevant first)?
                          1.0 = most relevant chunks at the top
    context_recall      — Did the retrieved chunks contain all needed information?
                          1.0 = all ground-truth info was retrievable
    answer_correctness  — Does the answer match the ground truth?
                          1.0 = exact match in meaning
"""

import json
import sys
import os
import time
from datetime import datetime
from pathlib import Path

# ── Add project root to path so we can import pipeline ──────────────────────
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def load_golden_dataset() -> list[dict]:
    """Load the 25-question golden dataset from eval/golden_dataset.json."""
    dataset_path = Path(__file__).parent / "golden_dataset.json"
    if not dataset_path.exists():
        raise FileNotFoundError(f"Golden dataset not found: {dataset_path}")
    with open(dataset_path, encoding="utf-8") as f:
        data = json.load(f)
    print(f"[EVAL] Loaded {len(data)} questions from golden dataset.")
    return data


def run_pipeline_on_dataset(golden: list[dict]) -> list[dict]:
    """
    Run ask_question() on every question in the golden dataset.
    Returns a list of rows ready for RAGAS evaluation.
    """
    # Import here so pipeline loads after sys.path is set
    from pipeline import ask_question

    rows = []
    failed = 0

    print(f"\n[EVAL] Running RAG pipeline on {len(golden)} questions...")
    print("       This may take a few minutes depending on your LLM backend.\n")

    for i, item in enumerate(golden, start=1):
        question = item["question"]
        ground_truth = item["ground_truth"]

        print(f"  [{i:02d}/{len(golden)}] {question[:70]}...")

        try:
            t0 = time.time()
            response = ask_question(question)
            elapsed = time.time() - t0

            cache_label = " (cached)" if response.get("from_cache") else ""
            print(f"         → {elapsed:.1f}s{cache_label}")

            rows.append({
                "question":     question,
                "answer":       response["answer"],
                "contexts":     response["chunks"],      # list[str] for RAGAS
                "ground_truth": ground_truth,
            })

        except Exception as exc:
            print(f"         ✗ ERROR: {exc}")
            failed += 1
            # Still add a placeholder row so question count stays consistent
            rows.append({
                "question":     question,
                "answer":       f"[ERROR: {exc}]",
                "contexts":     [],
                "ground_truth": ground_truth,
            })

    print(f"\n[EVAL] Pipeline complete. {len(rows) - failed}/{len(rows)} succeeded.\n")
    return rows


def run_ragas(rows: list[dict]) -> tuple[object, dict]:
    """
    Run RAGAS evaluation on the collected rows.
    Returns (scores_dataframe, mean_scores_dict).

    RAGAS 0.2+ renamed the dataset columns from 0.1.x:
        question      ->  user_input
        answer        ->  response
        contexts      ->  retrieved_contexts
        ground_truth  ->  reference
    """
    try:
        # RAGAS 0.2+ API
        from ragas import evaluate, EvaluationDataset
        from ragas.metrics import (
            Faithfulness,
            AnswerRelevancy,
            ContextPrecision,
            ContextRecall,
            AnswerCorrectness,
        )
        from ragas.llms import LangchainLLMWrapper
        from ragas.embeddings import LangchainEmbeddingsWrapper
        from langchain_openai import ChatOpenAI, OpenAIEmbeddings

        print("[EVAL] Using RAGAS 0.2+ API (all 5 metrics)")

        # Explicitly wrap LLM and embeddings so RAGAS can call async methods
        # correctly. Without this, AnswerRelevancy and AnswerCorrectness fail
        # with 'embed_query' or 'aembed_text' attribute errors in RAGAS 0.2+.
        llm        = LangchainLLMWrapper(ChatOpenAI(model="gpt-3.5-turbo", temperature=0))
        embeddings = LangchainEmbeddingsWrapper(OpenAIEmbeddings())

        # Remap column names to what RAGAS 0.2+ expects
        remapped = [
            {
                "user_input":         row["question"],
                "response":           row["answer"],
                "retrieved_contexts": row["contexts"],
                "reference":          row["ground_truth"],
            }
            for row in rows
        ]

        metrics = [
            Faithfulness(llm=llm),
            AnswerRelevancy(llm=llm, embeddings=embeddings),  # semantic Q↔A similarity
            ContextPrecision(llm=llm),
            ContextRecall(llm=llm),
            AnswerCorrectness(llm=llm, embeddings=embeddings), # answer vs ground truth
        ]

        dataset = EvaluationDataset.from_list(remapped)
        result = evaluate(dataset, metrics=metrics)

    except (ImportError, AttributeError):
        # RAGAS 0.1.x API fallback — uses original column names
        from ragas import evaluate
        from ragas.metrics import (
            faithfulness,
            answer_relevancy,
            context_precision,
            context_recall,
            answer_correctness,
        )
        from datasets import Dataset

        print("[EVAL] Using RAGAS 0.1.x API")

        metrics = [
            faithfulness,
            answer_relevancy,
            context_precision,
            context_recall,
            answer_correctness,
        ]

        dataset = Dataset.from_list(rows)
        result = evaluate(dataset, metrics=metrics)

    df = result.to_pandas()
    metric_cols = [
        "faithfulness",
        "answer_relevancy",
        "context_precision",
        "context_recall",
        "answer_correctness",
    ]
    # Only average columns that exist (handles API differences between versions)
    available_cols = [c for c in metric_cols if c in df.columns]
    means = df[available_cols].mean().to_dict()

    return df, means


def save_report(df, means: dict, run_id: str, golden: list[dict]) -> Path:
    """Save a markdown evaluation report to eval/results/<run-id>.md."""
    results_dir = Path(__file__).parent / "results"
    results_dir.mkdir(exist_ok=True)

    # Score interpretation guide
    def interpret(score: float) -> str:
        if score >= 0.85:
            return "✅ Excellent"
        elif score >= 0.70:
            return "🟡 Good"
        elif score >= 0.55:
            return "🟠 Fair"
        else:
            return "🔴 Needs Work"

    # Build the 5 lowest faithfulness questions table
    # RAGAS 0.2+ uses 'user_input' as the question column in the output DataFrame
    question_col = "user_input" if "user_input" in df.columns else "question"

    if "faithfulness" in df.columns and question_col in df.columns:
        worst_rows = df.nsmallest(5, "faithfulness")[[question_col, "faithfulness"]]
        worst_rows = worst_rows.rename(columns={question_col: "question"})
        worst_md = worst_rows.to_markdown(index=False)
    else:
        worst_md = "_faithfulness metric not available_"

    def _fmt(val):
        """Format a score or return N/A if NaN/missing."""
        import math
        if val is None or (isinstance(val, float) and math.isnan(val)):
            return "N/A"
        return f"{val:.3f}"

    report = f"""# RAGAS Evaluation Report

**Run ID:** `{run_id}`
**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M')}
**Questions evaluated:** {len(golden)}
**Metrics:** Faithfulness · Answer Relevancy · Context Precision · Context Recall · Answer Correctness
**Generated:** `python eval/run_eval.py {run_id}`

---

## Aggregate Scores

| Metric | Score | Interpretation | What It Measures |
|---|---|---|---|
| Faithfulness | {_fmt(means.get('faithfulness'))} | {interpret(means.get('faithfulness', 0))} | Hallucination — are answers grounded in retrieved context? |
| Answer Relevancy | {_fmt(means.get('answer_relevancy'))} | {interpret(means.get('answer_relevancy', 0))} | Does the answer address the actual question asked? |
| Context Precision | {_fmt(means.get('context_precision'))} | {interpret(means.get('context_precision', 0))} | Were the most relevant chunks ranked first? |
| Context Recall | {_fmt(means.get('context_recall'))} | {interpret(means.get('context_recall', 0))} | Did retrieval find all information needed to answer? |
| Answer Correctness | {_fmt(means.get('answer_correctness'))} | {interpret(means.get('answer_correctness', 0))} | Does the answer match the ground truth meaning? |

> Score range: 0.0 (worst) → 1.0 (best). Threshold: 0.70+ is Good, 0.85+ is Excellent.

---

## 5 Lowest Faithfulness Questions

These are the questions where the system had the highest hallucination risk.
Review the retrieved chunks vs the generated answer for these entries.

{worst_md}

---

## All Question Scores

{df[[question_col, 'faithfulness', 'answer_relevancy', 'context_precision', 'context_recall', 'answer_correctness']].rename(columns={question_col: 'question'}).to_markdown(index=False) if all(c in df.columns for c in ['faithfulness', 'context_precision', 'context_recall']) else df.to_markdown(index=False)}

---

_Generated by eval/run_eval.py — Construction Safety RAG Assistant_
"""

    report_path = results_dir / f"{run_id}.md"
    report_path.write_text(report, encoding="utf-8")
    return report_path


def run(run_id: str | None = None) -> dict:
    """
    Main entry point. Returns the mean scores dict.
    """
    run_id = run_id or datetime.now().strftime("%Y-%m-%d-run1")

    print("=" * 65)
    print(f"  RAGAS Evaluation — {run_id}")
    print("=" * 65)

    # 1. Load dataset
    golden = load_golden_dataset()

    # 2. Run pipeline on all questions
    rows = run_pipeline_on_dataset(golden)

    # 3. Score with RAGAS
    print("[EVAL] Scoring with RAGAS (this calls the OpenAI API for judging)...")
    df, means = run_ragas(rows)

    # 4. Print summary
    print("\n" + "=" * 65)
    print("  RESULTS")
    print("=" * 65)
    for metric, score in means.items():
        import math
        if score is None or (isinstance(score, float) and math.isnan(score)):
            print(f"  {metric:<22} N/A    (metric returned no score)")
        else:
            bar = "█" * int(score * 20)
            print(f"  {metric:<22} {score:.3f}  {bar}")

    # 5. Save report
    report_path = save_report(df, means, run_id, golden)
    print(f"\n[EVAL] Full report saved: {report_path}")
    print(f"[EVAL] Run regression check: python eval/regression_check.py")

    return means


if __name__ == "__main__":
    # Usage:
    #   python eval/run_eval.py
    #   python eval/run_eval.py 2026-06-21-baseline
    run_id_arg = sys.argv[1] if len(sys.argv) > 1 else None
    scores = run(run_id_arg)
