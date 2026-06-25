# -*- coding: utf-8 -*-
"""
eval/regression_check.py — Phase 6: Quality Regression Guard

After running run_eval.py for the first time, paste your baseline scores
into BASELINE below. Then run this script after any config or prompt change
to verify no metric has dropped more than REGRESSION_THRESHOLD (5%).

Usage:
    # Step 1: Run baseline eval and note the scores
    python eval/run_eval.py 2026-06-21-baseline

    # Step 2: Paste scores into BASELINE dict below, commit the file

    # Step 3: After future changes, run eval again and check regression
    python eval/run_eval.py 2026-07-01-after-chunking-change
    python eval/regression_check.py eval/results/2026-07-01-after-chunking-change.md
"""

import sys
import re
from pathlib import Path

# ── BASELINE SCORES ────────────────────────────────────────────────────────
# Fill these in after your first successful eval run.
# Run: python eval/run_eval.py 2026-06-21-baseline
# Then copy the printed scores here.
BASELINE: dict[str, float] = {
    "faithfulness":       0.0,   # ← update after first run
    "answer_relevancy":   0.0,   # ← update after first run
    "context_precision":  0.0,   # ← update after first run
    "context_recall":     0.0,   # ← update after first run
    "answer_correctness": 0.0,   # ← update after first run
}

# Alert if any metric drops more than this from baseline
REGRESSION_THRESHOLD = 0.05   # 5%

METRIC_DESCRIPTIONS = {
    "faithfulness":       "hallucination rate",
    "answer_relevancy":   "answer on-topic score",
    "context_precision":  "retrieval ranking quality",
    "context_recall":     "retrieval coverage",
    "answer_correctness": "factual correctness vs ground truth",
}


def parse_scores_from_report(report_path: str) -> dict[str, float]:
    """
    Parse metric scores from a saved RAGAS markdown report.
    Falls back to prompting the user to enter scores manually.
    """
    path = Path(report_path)
    if not path.exists():
        print(f"[ERROR] Report not found: {path}")
        sys.exit(1)

    content = path.read_text(encoding="utf-8")
    scores = {}

    metrics = [
        "faithfulness",
        "answer_relevancy",
        "context_precision",
        "context_recall",
        "answer_correctness",
    ]

    for metric in metrics:
        # Match lines like: | Faithfulness | 0.823 | ...
        pattern = rf"\|\s*{metric.replace('_', '[_ ]')}\s*\|\s*([0-9.]+)\s*\|"
        match = re.search(pattern, content, re.IGNORECASE)
        if match:
            scores[metric] = float(match.group(1))

    if not scores:
        print(f"[WARN] Could not parse scores from {path}.")
        print("       Please enter the scores manually:")
        for metric in metrics:
            val = input(f"  {metric}: ").strip()
            try:
                scores[metric] = float(val)
            except ValueError:
                scores[metric] = 0.0

    return scores


def check(current_scores: dict[str, float]) -> list[str]:
    """
    Compare current scores to BASELINE.
    Returns a list of alert strings (empty = no regressions).
    """
    alerts = []
    improvements = []

    for metric, baseline in BASELINE.items():
        if baseline == 0.0:
            # Baseline not set yet — skip this metric
            continue

        current = current_scores.get(metric, 0.0)
        delta = current - baseline  # positive = improvement, negative = regression

        if delta < -REGRESSION_THRESHOLD:
            alerts.append(
                f"⚠️  REGRESSION  {metric:<22} "
                f"baseline={baseline:.3f}  current={current:.3f}  "
                f"drop={abs(delta):.1%}  ({METRIC_DESCRIPTIONS.get(metric, '')})"
            )
        elif delta > 0.01:
            improvements.append(
                f"✅  IMPROVED    {metric:<22} "
                f"baseline={baseline:.3f}  current={current:.3f}  "
                f"gain=+{delta:.1%}"
            )

    return alerts, improvements


def main():
    print("=" * 65)
    print("  RAGAS Regression Check")
    print("=" * 65)

    # Check if BASELINE has been filled in
    if all(v == 0.0 for v in BASELINE.values()):
        print("\n[INFO] BASELINE scores are all 0.0 — not set yet.")
        print("       Run your first evaluation to get baseline scores:")
        print("         python eval/run_eval.py 2026-06-21-baseline")
        print("       Then fill in the BASELINE dict in this file.\n")
        sys.exit(0)

    # Get current scores from report or manual input
    if len(sys.argv) > 1:
        report_path = sys.argv[1]
        print(f"\n[INFO] Parsing scores from: {report_path}")
        current_scores = parse_scores_from_report(report_path)
    else:
        print("\n[INFO] No report path provided. Enter current scores manually:")
        print("       (Or run: python eval/regression_check.py eval/results/<run-id>.md)\n")
        current_scores = {}
        for metric in BASELINE:
            val = input(f"  {metric}: ").strip()
            try:
                current_scores[metric] = float(val)
            except ValueError:
                current_scores[metric] = 0.0

    # Print current vs baseline
    print("\n  Metric                   Baseline   Current    Delta")
    print("  " + "-" * 55)
    for metric, baseline in BASELINE.items():
        if baseline == 0.0:
            continue
        current = current_scores.get(metric, 0.0)
        delta = current - baseline
        delta_str = f"+{delta:.3f}" if delta >= 0 else f"{delta:.3f}"
        flag = "↑" if delta > 0.01 else ("↓" if delta < -REGRESSION_THRESHOLD else "~")
        print(f"  {metric:<24} {baseline:.3f}      {current:.3f}      {delta_str} {flag}")

    # Run regression check
    alerts, improvements = check(current_scores)

    print()
    if improvements:
        for msg in improvements:
            print(f"  {msg}")

    if alerts:
        print()
        for msg in alerts:
            print(f"  {msg}")
        print(f"\n  ❌ {len(alerts)} regression(s) detected. Review changes before deploying.\n")
        sys.exit(1)
    elif all(v == 0.0 for v in BASELINE.values()):
        pass
    else:
        print(f"  ✅ No regressions detected (threshold: {REGRESSION_THRESHOLD:.0%} drop).\n")


if __name__ == "__main__":
    main()
