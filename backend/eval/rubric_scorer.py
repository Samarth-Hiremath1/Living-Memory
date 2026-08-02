"""
Rubric-based LLM-as-judge scoring for the Concierge Research Agent.

Pipeline:
    run_mcp_agent(query) ──▶ MCPAgentResult
                                  │
                                  ▼
                          score_case(case, result, config)
                                  │
                                  ▼ (one Claude call to the judge)
                              CaseScore
                                  │
                                  ▼
        aggregate_scores(case_scores) ──▶ AggregateReport
                                  │
                                  ▼
                       generate_markdown_report(report)

All of the rubric (dimensions, weights, judge model, judge prompt template)
is held in a RubricConfig — DEFAULT_RUBRIC is provided, but callers can
swap any field independently.
"""

from __future__ import annotations

import json
import re
import statistics
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import anthropic

from src.config import settings  # absolute — backend/ is on sys.path


# ── Rubric definitions ────────────────────────────────────────────────────────


@dataclass(frozen=True)
class RubricDimension:
    """One scoring dimension. Score is always normalised to [0, 1]."""
    name: str
    description: str
    weight: float


DEFAULT_DIMENSIONS: tuple[RubricDimension, ...] = (
    RubricDimension(
        name="tool_selection",
        description=(
            "Did the agent select the appropriate tool(s) for this query? "
            "Score 1.0 if the choices match what's needed; 0.5 for partial match "
            "(e.g. one of two expected tools called); 0.0 for wrong or missing tools. "
            "If the case has no expected tools, score 1.0 when the agent correctly "
            "answered without tools, and lower if it called a tool unnecessarily."
        ),
        weight=0.30,
    ),
    RubricDimension(
        name="factuality",
        description=(
            "Is the final answer factually grounded in the tool outputs (or the "
            "query when no tool was used)? Score 1.0 for fully grounded; 0.5 if "
            "some claims are unsupported but the gist is correct; 0.0 for fabrication "
            "or contradictions of the tool output."
        ),
        weight=0.40,
    ),
    RubricDimension(
        name="step_efficiency",
        description=(
            "Did the agent use a reasonable number of steps? Score 1.0 if it "
            "completed the task in the minimum reasonable steps (1 step per "
            "expected tool, plus 0 for the final synthesis). 0.5 if it used one "
            "extra step. 0.0 if it used many redundant or unnecessary tool calls."
        ),
        weight=0.20,
    ),
    RubricDimension(
        name="loop_safety",
        description=(
            "Did the agent stay within reasonable step bounds without obvious "
            "looping behaviour? Score 1.0 if steps_taken <= 4; 0.5 if 5-6; "
            "0.0 if it appears to have looped or hit the maximum-step cap."
        ),
        weight=0.10,
    ),
)


DEFAULT_JUDGE_PROMPT_TEMPLATE = """\
You are a strict but fair evaluator for an LLM tool-use agent. You will score
the agent's behaviour on a single eval case along multiple dimensions.

# THE CASE

Case id:         {case_id}
Slice category:  {slice_tag}
Description:     {description}
Query:           {query}
Tool policy:     {tool_policy}
Expected tools:  {expected_tools}
Acceptable tools (may be called, no penalty either way): {acceptable_tools}
Expected answer signals: {expected_keywords}

HOW TO APPLY THE TOOL POLICY when scoring `tool_selection`:
  - "required":  every tool in Expected tools must have been called. Missing one
                 is a partial or total miss.
  - "optional":  the agent is graded on the OUTCOME, not the path. Calling a
                 listed acceptable tool and not calling it are BOTH fully
                 correct. Score 1.0 unless it called something irrelevant or
                 produced a bad outcome (e.g. fabricated data).
  - "forbidden": no tool should have been called. Calling one is the penalty.

# THE AGENT'S ACTUAL BEHAVIOUR

Steps taken:     {steps_taken}
Tool calls (in order):
{tool_calls_block}

Final answer:
{final_answer}

# YOUR RUBRIC

Score the agent on each dimension below. Each score is a float in [0.0, 1.0].

{rubric_description_block}

# OUTPUT FORMAT

Return a SINGLE valid JSON object. No surrounding prose, no code fences. Schema:

{{
  "tool_selection":  {{"score": 0.0, "reasoning": "..."}},
  "factuality":      {{"score": 0.0, "reasoning": "..."}},
  "step_efficiency": {{"score": 0.0, "reasoning": "..."}},
  "loop_safety":     {{"score": 0.0, "reasoning": "..."}}
}}

Each `reasoning` field should be ONE concise sentence justifying the score.
"""


@dataclass(frozen=True)
class RubricConfig:
    """Full configuration for the rubric scorer. All fields are overridable."""
    dimensions: tuple[RubricDimension, ...] = DEFAULT_DIMENSIONS
    judge_model: str = ""  # falls back to settings.orchestrator_model
    judge_prompt_template: str = DEFAULT_JUDGE_PROMPT_TEMPLATE
    judge_max_tokens: int = 800
    judge_system: str = (
        "You evaluate LLM agents objectively. You ground every score in the "
        "evidence provided. You return only valid JSON when asked."
    )

    def model(self) -> str:
        return self.judge_model or settings.orchestrator_model

    def weights_sum_to_one(self) -> bool:
        return abs(sum(d.weight for d in self.dimensions) - 1.0) < 1e-6

    def validate(self) -> None:
        """
        Raise if the rubric is internally inconsistent.

        Called at the top of score_case and aggregate_scores. Previously this
        check existed but was never invoked, so a config whose weights summed to
        1.5 would silently produce composite scores above 1.0 and every report
        built from it would be quietly wrong.
        """
        if not self.dimensions:
            raise ValueError("RubricConfig has no dimensions")
        if not self.weights_sum_to_one():
            total = sum(d.weight for d in self.dimensions)
            raise ValueError(
                f"Rubric weights must sum to 1.0, got {total:.4f} "
                f"({{{', '.join(f'{d.name}={d.weight}' for d in self.dimensions)}}}). "
                "Composite scores would be uninterpretable."
            )
        for d in self.dimensions:
            if not 0.0 <= d.weight <= 1.0:
                raise ValueError(f"Dimension '{d.name}' weight {d.weight} outside [0,1]")
        names = [d.name for d in self.dimensions]
        if len(names) != len(set(names)):
            raise ValueError(f"Duplicate dimension names: {names}")


DEFAULT_RUBRIC = RubricConfig()


# ── Score dataclasses ────────────────────────────────────────────────────────


@dataclass
class DimensionScore:
    score: float  # always in [0, 1]
    reasoning: str


@dataclass
class CaseScore:
    case_id: str
    slice_tag: str
    dimension_scores: dict[str, DimensionScore]
    weighted_total: float
    steps_taken: int
    final_answer: str
    tool_calls: list[dict]
    error: str | None = None  # set if judge invocation or parsing failed


@dataclass
class SliceAggregate:
    slice_tag: str
    case_count: int
    per_dimension_mean: dict[str, float]
    weighted_total_mean: float


@dataclass
class AggregateReport:
    case_scores: list[CaseScore]
    overall_per_dimension_mean: dict[str, float]
    overall_weighted_total: float
    per_slice: list[SliceAggregate]
    judge_model: str
    generated_at: str
    weights: dict[str, float]
    # Honest denominator: every mean above is computed over `scored_count`
    # cases, NOT over len(case_scores). Cases whose judge call failed are
    # excluded from the arithmetic, so reporting the total as the denominator
    # would overstate the sample the numbers actually rest on.
    total_count: int = 0
    scored_count: int = 0
    errored_count: int = 0


# ── Scoring ──────────────────────────────────────────────────────────────────


_client = anthropic.Anthropic(api_key=settings.anthropic_api_key)


def _format_tool_calls(tool_calls: list[dict]) -> str:
    if not tool_calls:
        return "  (none)"
    lines = []
    for i, call in enumerate(tool_calls, 1):
        out = str(call.get("output", ""))
        if len(out) > 400:
            out = out[:397] + "..."
        lines.append(
            f"  {i}. {call.get('tool', '?')}"
            f"({json.dumps(call.get('input', {}), ensure_ascii=False)})"
            f"\n     → {out}"
        )
    return "\n".join(lines)


def _format_rubric(dimensions: tuple[RubricDimension, ...]) -> str:
    lines = []
    for d in dimensions:
        lines.append(f"## {d.name}  (weight {d.weight:.2f})")
        lines.append(d.description)
        lines.append("")
    return "\n".join(lines).rstrip()


def _build_judge_prompt(case: dict, result: Any, config: RubricConfig) -> str:
    return config.judge_prompt_template.format(
        case_id=case.get("id", "?"),
        slice_tag=case.get("slice", "unknown"),
        description=case.get("description", ""),
        query=case.get("query", ""),
        tool_policy=case.get("tool_policy", "required"),
        acceptable_tools=case.get("acceptable_tools", []),
        expected_tools=case.get("expected_tools", []),
        expected_keywords=case.get("expected_keywords", []),
        steps_taken=getattr(result, "steps_taken", 0),
        tool_calls_block=_format_tool_calls(getattr(result, "tool_calls", []) or []),
        final_answer=getattr(result, "final_answer", "") or "(empty)",
        rubric_description_block=_format_rubric(config.dimensions),
    )


# Match a JSON object even inside accidental code fences
_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


def _parse_judge_response(text: str, dimensions: tuple[RubricDimension, ...]) -> dict[str, DimensionScore]:
    """
    Parse the judge's JSON response into DimensionScore objects.
    Tolerates code fences and minor formatting noise.
    Raises ValueError if the response cannot be parsed.
    """
    cleaned = text.strip()
    if cleaned.startswith("```"):
        # Strip leading ```json or ``` and trailing ```
        cleaned = re.sub(r"^```(?:json)?\n?", "", cleaned)
        cleaned = re.sub(r"\n?```$", "", cleaned)

    # If still not parseable, try to extract the first {...} block
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        m = _JSON_RE.search(cleaned)
        if not m:
            raise ValueError(f"Could not find JSON in judge response: {text[:200]!r}")
        parsed = json.loads(m.group(0))

    if not isinstance(parsed, dict):
        raise ValueError(f"Judge response is not a JSON object: {type(parsed)}")

    scores: dict[str, DimensionScore] = {}
    for dim in dimensions:
        entry = parsed.get(dim.name)
        if entry is None:
            # Treat a missing dimension as 0.0 with a flag, rather than erroring
            scores[dim.name] = DimensionScore(
                score=0.0, reasoning=f"(judge omitted '{dim.name}')"
            )
            continue
        raw_score = entry.get("score") if isinstance(entry, dict) else entry
        try:
            score_val = float(raw_score)
        except (TypeError, ValueError):
            score_val = 0.0
        # Clamp to [0, 1] — judges occasionally drift
        score_val = max(0.0, min(1.0, score_val))
        reasoning = (
            entry.get("reasoning", "") if isinstance(entry, dict) else ""
        )
        scores[dim.name] = DimensionScore(score=score_val, reasoning=str(reasoning))
    return scores


def _weighted_total(
    dimension_scores: dict[str, DimensionScore],
    dimensions: tuple[RubricDimension, ...],
) -> float:
    total = 0.0
    for d in dimensions:
        total += dimension_scores[d.name].score * d.weight
    return round(total, 4)


def score_case(case: dict, result: Any, config: RubricConfig | None = None) -> CaseScore:
    """
    Score one (case, agent-result) pair using the LLM judge.
    Always returns a CaseScore — errors are captured in the .error field.
    """
    cfg = config or DEFAULT_RUBRIC
    cfg.validate()
    base = CaseScore(
        case_id=case.get("id", "?"),
        slice_tag=case.get("slice", "unknown"),
        dimension_scores={
            d.name: DimensionScore(score=0.0, reasoning="(not scored)")
            for d in cfg.dimensions
        },
        weighted_total=0.0,
        steps_taken=getattr(result, "steps_taken", 0),
        final_answer=getattr(result, "final_answer", "") or "",
        tool_calls=getattr(result, "tool_calls", []) or [],
    )

    try:
        prompt = _build_judge_prompt(case, result, cfg)
        resp = _client.messages.create(
            model=cfg.model(),
            max_tokens=cfg.judge_max_tokens,
            system=cfg.judge_system,
            messages=[{"role": "user", "content": prompt}],
        )
        text = resp.content[0].text if resp.content else ""
        parsed = _parse_judge_response(text, cfg.dimensions)
    except Exception as exc:
        base.error = f"Judge call failed: {exc}"
        return base

    base.dimension_scores = parsed
    base.weighted_total = _weighted_total(parsed, cfg.dimensions)
    return base


# ── Aggregation ──────────────────────────────────────────────────────────────


def aggregate_scores(
    case_scores: list[CaseScore],
    config: RubricConfig | None = None,
) -> AggregateReport:
    """Compute overall and per-slice aggregates."""
    cfg = config or DEFAULT_RUBRIC
    cfg.validate()
    dim_names = [d.name for d in cfg.dimensions]
    valid = [cs for cs in case_scores if cs.error is None]

    def _mean(values: list[float]) -> float:
        return round(statistics.fmean(values), 4) if values else 0.0

    overall_per_dim = {
        name: _mean([cs.dimension_scores[name].score for cs in valid if name in cs.dimension_scores])
        for name in dim_names
    }
    overall_weighted = _mean([cs.weighted_total for cs in valid])

    # Group by slice
    by_slice: dict[str, list[CaseScore]] = {}
    for cs in valid:
        by_slice.setdefault(cs.slice_tag, []).append(cs)

    per_slice: list[SliceAggregate] = []
    for slice_tag in sorted(by_slice.keys()):
        members = by_slice[slice_tag]
        per_dim = {
            name: _mean([cs.dimension_scores[name].score for cs in members if name in cs.dimension_scores])
            for name in dim_names
        }
        per_slice.append(
            SliceAggregate(
                slice_tag=slice_tag,
                case_count=len(members),
                per_dimension_mean=per_dim,
                weighted_total_mean=_mean([cs.weighted_total for cs in members]),
            )
        )

    return AggregateReport(
        case_scores=case_scores,
        overall_per_dimension_mean=overall_per_dim,
        overall_weighted_total=overall_weighted,
        per_slice=per_slice,
        judge_model=cfg.model(),
        generated_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        weights={d.name: d.weight for d in cfg.dimensions},
        total_count=len(case_scores),
        scored_count=len(valid),
        errored_count=len(case_scores) - len(valid),
    )


# ── Markdown report ──────────────────────────────────────────────────────────


def generate_markdown_report(
    report: AggregateReport,
    *,
    worst_n: int = 5,
) -> str:
    """
    Render the aggregate report as a markdown document.

    Layout (top to bottom):
      1. Header
      2. Worst-performing cases (surfaced at the top)
      3. Overall per-dimension scores
      4. Per-slice breakdown
      5. Full per-case table (appendix)
    """
    lines: list[str] = []

    # ── Header ───────────────────────────────────────────────────────────────
    lines.append("# Concierge Research Agent — Rubric Eval Report")
    lines.append("")
    lines.append(f"- **Generated:** {report.generated_at}")
    lines.append(f"- **Judge model:** `{report.judge_model}`")
    lines.append(f"- **Cases in suite:** {report.total_count}")
    lines.append(
        f"- **Cases successfully scored (denominator for every mean below):** "
        f"**{report.scored_count}**"
    )
    if report.errored_count:
        lines.append(
            f"- **Cases excluded — judge call failed:** {report.errored_count} "
            f"(these are NOT in any mean)"
        )
    lines.append(
        f"- **Overall weighted score:** **{report.overall_weighted_total:.3f}** "
        f"(n={report.scored_count})"
    )
    lines.append("")

    # ── Worst-performing cases (at the top) ──────────────────────────────────
    lines.append("## Worst-performing cases")
    lines.append("")
    valid = [cs for cs in report.case_scores if cs.error is None]
    worst = sorted(valid, key=lambda cs: cs.weighted_total)[:worst_n]
    if not worst:
        lines.append("_No successfully scored cases to rank._")
    else:
        for cs in worst:
            lines.append(f"### `{cs.case_id}` — weighted **{cs.weighted_total:.3f}**")
            lines.append(f"_Slice: `{cs.slice_tag}` · steps: {cs.steps_taken}_")
            lines.append("")
            for dim_name, ds in cs.dimension_scores.items():
                lines.append(f"- **{dim_name}:** {ds.score:.2f} — {ds.reasoning}")
            ans = cs.final_answer.replace("\n", " ")
            if len(ans) > 250:
                ans = ans[:247] + "..."
            lines.append("")
            lines.append(f"> {ans}")
            lines.append("")
    lines.append("")

    # ── Overall per-dimension ────────────────────────────────────────────────
    lines.append("## Overall per-dimension")
    lines.append("")
    lines.append("| Dimension | Weight | Mean score |")
    lines.append("|---|---:|---:|")
    for name, mean in report.overall_per_dimension_mean.items():
        weight = report.weights.get(name, 0.0)
        lines.append(f"| {name} | {weight:.2f} | {mean:.3f} |")
    lines.append(
        f"| **Weighted total** | **1.00** | **{report.overall_weighted_total:.3f}** |"
    )
    lines.append("")

    # ── Per-slice breakdown ──────────────────────────────────────────────────
    lines.append("## Per-slice breakdown")
    lines.append("")
    if not report.per_slice:
        lines.append("_No slices to report._")
    else:
        dim_names = list(report.overall_per_dimension_mean.keys())
        header_cells = ["Slice", "N"] + dim_names + ["Weighted"]
        lines.append("| " + " | ".join(header_cells) + " |")
        sep_cells = ["---", "---:"] + ["---:"] * len(dim_names) + ["---:"]
        lines.append("| " + " | ".join(sep_cells) + " |")
        for sa in report.per_slice:
            row = [
                f"`{sa.slice_tag}`",
                str(sa.case_count),
            ]
            row += [f"{sa.per_dimension_mean.get(n, 0.0):.3f}" for n in dim_names]
            row.append(f"**{sa.weighted_total_mean:.3f}**")
            lines.append("| " + " | ".join(row) + " |")
    lines.append("")

    # ── Full per-case appendix ───────────────────────────────────────────────
    lines.append("## All cases")
    lines.append("")
    dim_names = list(report.overall_per_dimension_mean.keys())
    header = ["Case", "Slice", "Steps"] + dim_names + ["Weighted", "Error"]
    lines.append("| " + " | ".join(header) + " |")
    sep_cells = ["---", "---", "---:"] + ["---:"] * len(dim_names) + ["---:", "---"]
    lines.append("| " + " | ".join(sep_cells) + " |")
    for cs in report.case_scores:
        row = [
            f"`{cs.case_id}`",
            f"`{cs.slice_tag}`",
            str(cs.steps_taken),
        ]
        for n in dim_names:
            if n in cs.dimension_scores:
                row.append(f"{cs.dimension_scores[n].score:.2f}")
            else:
                row.append("—")
        row.append(f"**{cs.weighted_total:.3f}**")
        row.append(cs.error or "")
        lines.append("| " + " | ".join(row) + " |")
    lines.append("")

    return "\n".join(lines)
