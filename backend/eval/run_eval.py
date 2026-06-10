"""
CLI runner — execute the Concierge Research Agent on every eval case,
score each case with the LLM judge, and write a markdown report.

Usage (from backend/):
    python -m eval.run_eval                          # run all cases, write to ./eval_report.md
    python -m eval.run_eval -o my_report.md
    python -m eval.run_eval --slice multi-tool       # filter by slice
    python -m eval.run_eval --only weather_arrival_planning,flight_status_basic
    python -m eval.run_eval --judge-model claude-haiku-4-5

Requires ANTHROPIC_API_KEY in the environment (both for the agent and the judge).
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from eval.cases import EVAL_CASES, all_slices
from eval.rubric_scorer import (
    DEFAULT_RUBRIC,
    RubricConfig,
    aggregate_scores,
    generate_markdown_report,
    score_case,
)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "-o", "--output",
        default="eval_report.md",
        help="Output markdown path (default: eval_report.md)",
    )
    parser.add_argument(
        "--slice",
        dest="slice_filter",
        choices=all_slices() + ["all"],
        default="all",
        help="Only run cases in this slice (default: all)",
    )
    parser.add_argument(
        "--only",
        default="",
        help="Comma-separated list of case ids to run (overrides --slice)",
    )
    parser.add_argument(
        "--judge-model",
        default="",
        help="Override the judge model (default: settings.orchestrator_model)",
    )
    parser.add_argument(
        "--worst-n",
        type=int,
        default=5,
        help="Number of worst-performing cases to surface at the top",
    )
    return parser.parse_args(argv)


def _filter_cases(args: argparse.Namespace) -> list[dict]:
    if args.only:
        wanted = {c.strip() for c in args.only.split(",") if c.strip()}
        return [c for c in EVAL_CASES if c["id"] in wanted]
    if args.slice_filter == "all":
        return list(EVAL_CASES)
    return [c for c in EVAL_CASES if c.get("slice") == args.slice_filter]


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    cases = _filter_cases(args)
    if not cases:
        print("No cases matched the filter.", file=sys.stderr)
        return 1

    # Build the rubric config (default + optional judge model override)
    config = DEFAULT_RUBRIC
    if args.judge_model:
        config = RubricConfig(
            dimensions=DEFAULT_RUBRIC.dimensions,
            judge_model=args.judge_model,
            judge_prompt_template=DEFAULT_RUBRIC.judge_prompt_template,
            judge_max_tokens=DEFAULT_RUBRIC.judge_max_tokens,
            judge_system=DEFAULT_RUBRIC.judge_system,
        )

    if not config.weights_sum_to_one():
        print(
            f"Warning: rubric weights sum to {sum(d.weight for d in config.dimensions):.3f}, not 1.0",
            file=sys.stderr,
        )

    # Import the agent lazily so --help works without API config
    from src.agents.mcp_agent import run_mcp_agent

    print(f"Running {len(cases)} case(s) through the agent + judge…")
    print(f"Judge model: {config.model()}\n")

    case_scores = []
    started = time.time()
    for i, case in enumerate(cases, 1):
        print(f"[{i}/{len(cases)}] {case['id']} ({case.get('slice', 'unknown')})", flush=True)

        # 1. Run the agent
        try:
            result = run_mcp_agent(case["query"])
        except Exception as exc:
            print(f"  agent error: {exc}", file=sys.stderr)
            continue

        # 2. Score via LLM judge
        score = score_case(case, result, config=config)
        if score.error:
            print(f"  judge error: {score.error}", file=sys.stderr)
        else:
            print(
                f"  weighted={score.weighted_total:.3f}  "
                f"tool_sel={score.dimension_scores['tool_selection'].score:.2f}  "
                f"fact={score.dimension_scores['factuality'].score:.2f}  "
                f"steps={score.dimension_scores['step_efficiency'].score:.2f}  "
                f"loop={score.dimension_scores['loop_safety'].score:.2f}"
            )
        case_scores.append(score)

    elapsed = time.time() - started

    # 3. Aggregate
    report = aggregate_scores(case_scores, config=config)

    # 4. Write markdown
    md = generate_markdown_report(report, worst_n=args.worst_n)
    out_path = Path(args.output)
    out_path.write_text(md)

    # 5. Console summary
    print()
    print(f"Done in {elapsed:.1f}s.")
    print(f"Overall weighted score: {report.overall_weighted_total:.3f}")
    print(f"Report written to: {out_path.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
