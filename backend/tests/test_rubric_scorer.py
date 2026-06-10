"""
Tests for the rubric-based LLM-as-judge scorer.

All tests here mock the Claude judge call — no real API access is needed.
Run with:  pytest tests/test_rubric_scorer.py -v
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from unittest.mock import MagicMock, patch

import pytest

from eval.cases import EVAL_CASES, all_slices, cases_by_slice, get_case
from eval.rubric_scorer import (
    DEFAULT_DIMENSIONS,
    DEFAULT_JUDGE_PROMPT_TEMPLATE,
    DEFAULT_RUBRIC,
    AggregateReport,
    CaseScore,
    DimensionScore,
    RubricConfig,
    RubricDimension,
    _parse_judge_response,
    _weighted_total,
    aggregate_scores,
    generate_markdown_report,
    score_case,
)


# ── Helpers ───────────────────────────────────────────────────────────────────


@dataclass
class FakeAgentResult:
    """Stand-in for MCPAgentResult in scorer-only tests."""
    final_answer: str = "The capital of France is Paris."
    tool_calls: list[dict] = field(default_factory=list)
    steps_taken: int = 0
    error: str | None = None


def _fake_claude_response(payload: dict) -> MagicMock:
    """Build a MagicMock mimicking an Anthropic Messages API response."""
    block = MagicMock()
    block.text = json.dumps(payload)
    resp = MagicMock()
    resp.content = [block]
    return resp


def _all_perfect_payload() -> dict:
    return {
        "tool_selection":  {"score": 1.0, "reasoning": "correct"},
        "factuality":      {"score": 1.0, "reasoning": "grounded"},
        "step_efficiency": {"score": 1.0, "reasoning": "minimal"},
        "loop_safety":     {"score": 1.0, "reasoning": "bounded"},
    }


# ── Rubric structure ─────────────────────────────────────────────────────────


class TestRubricConfig:
    def test_default_weights_sum_to_one(self):
        assert DEFAULT_RUBRIC.weights_sum_to_one()

    def test_default_dimensions_present(self):
        names = {d.name for d in DEFAULT_RUBRIC.dimensions}
        assert names == {"tool_selection", "factuality", "step_efficiency", "loop_safety"}

    def test_custom_dimensions_override(self):
        custom = RubricConfig(
            dimensions=(
                RubricDimension("a", "x", 0.5),
                RubricDimension("b", "y", 0.5),
            ),
        )
        assert custom.weights_sum_to_one()
        assert len(custom.dimensions) == 2

    def test_weights_not_summing_to_one_detected(self):
        bad = RubricConfig(
            dimensions=(
                RubricDimension("a", "x", 0.3),
                RubricDimension("b", "y", 0.3),
            ),
        )
        assert not bad.weights_sum_to_one()

    def test_judge_prompt_template_is_overridable(self):
        custom = RubricConfig(judge_prompt_template="just {query}")
        assert "just {query}" in custom.judge_prompt_template

    def test_default_model_falls_back_to_settings(self):
        # judge_model="" → falls back to settings.orchestrator_model
        assert DEFAULT_RUBRIC.model() != ""


# ── Cases module ─────────────────────────────────────────────────────────────


class TestCases:
    def test_every_case_has_a_slice(self):
        for c in EVAL_CASES:
            assert c.get("slice"), f"case {c['id']} missing slice"

    def test_every_case_has_required_fields(self):
        required = {"id", "slice", "query", "expected_tools", "expected_keywords"}
        for c in EVAL_CASES:
            assert required.issubset(c.keys()), f"case {c['id']} missing fields"

    def test_get_case_returns_case(self):
        c = get_case("weather_arrival_planning")
        assert c is not None
        assert c["id"] == "weather_arrival_planning"

    def test_get_case_unknown_returns_none(self):
        assert get_case("does-not-exist") is None

    def test_cases_by_slice(self):
        external = cases_by_slice("single-tool-external")
        assert len(external) >= 1
        assert all(c["slice"] == "single-tool-external" for c in external)

    def test_all_slices_dedupes(self):
        slices = all_slices()
        assert len(slices) == len(set(slices))
        assert "multi-tool" in slices
        assert "no-tool" in slices


# ── Judge response parsing ───────────────────────────────────────────────────


class TestParseJudgeResponse:
    def test_clean_json(self):
        text = json.dumps(_all_perfect_payload())
        parsed = _parse_judge_response(text, DEFAULT_DIMENSIONS)
        for d in DEFAULT_DIMENSIONS:
            assert parsed[d.name].score == 1.0

    def test_json_with_code_fences(self):
        payload = _all_perfect_payload()
        text = f"```json\n{json.dumps(payload)}\n```"
        parsed = _parse_judge_response(text, DEFAULT_DIMENSIONS)
        for d in DEFAULT_DIMENSIONS:
            assert parsed[d.name].score == 1.0

    def test_json_with_surrounding_prose(self):
        payload = _all_perfect_payload()
        text = "Here are the scores:\n\n" + json.dumps(payload) + "\n\nLet me know if you need anything else."
        parsed = _parse_judge_response(text, DEFAULT_DIMENSIONS)
        assert parsed["tool_selection"].score == 1.0

    def test_score_clamped_to_zero_one(self):
        text = json.dumps({
            "tool_selection":  {"score": 1.5, "reasoning": "over"},
            "factuality":      {"score": -0.2, "reasoning": "under"},
            "step_efficiency": {"score": 0.5, "reasoning": "ok"},
            "loop_safety":     {"score": 1.0, "reasoning": "ok"},
        })
        parsed = _parse_judge_response(text, DEFAULT_DIMENSIONS)
        assert parsed["tool_selection"].score == 1.0
        assert parsed["factuality"].score == 0.0
        assert parsed["step_efficiency"].score == 0.5

    def test_missing_dimension_defaults_to_zero(self):
        text = json.dumps({
            "tool_selection": {"score": 1.0, "reasoning": "ok"},
            # factuality intentionally missing
            "step_efficiency": {"score": 0.7, "reasoning": "ok"},
            "loop_safety": {"score": 1.0, "reasoning": "ok"},
        })
        parsed = _parse_judge_response(text, DEFAULT_DIMENSIONS)
        assert parsed["factuality"].score == 0.0
        assert "omitted" in parsed["factuality"].reasoning.lower()

    def test_unparseable_raises(self):
        with pytest.raises(ValueError):
            _parse_judge_response("not json at all", DEFAULT_DIMENSIONS)

    def test_non_numeric_score_treated_as_zero(self):
        text = json.dumps({
            "tool_selection":  {"score": "good", "reasoning": "ok"},
            "factuality":      {"score": 1.0, "reasoning": "ok"},
            "step_efficiency": {"score": 1.0, "reasoning": "ok"},
            "loop_safety":     {"score": 1.0, "reasoning": "ok"},
        })
        parsed = _parse_judge_response(text, DEFAULT_DIMENSIONS)
        assert parsed["tool_selection"].score == 0.0


# ── Weighted total ───────────────────────────────────────────────────────────


class TestWeightedTotal:
    def test_all_ones_gives_one(self):
        scores = {
            d.name: DimensionScore(score=1.0, reasoning="")
            for d in DEFAULT_DIMENSIONS
        }
        assert _weighted_total(scores, DEFAULT_DIMENSIONS) == 1.0

    def test_all_zeros_gives_zero(self):
        scores = {
            d.name: DimensionScore(score=0.0, reasoning="")
            for d in DEFAULT_DIMENSIONS
        }
        assert _weighted_total(scores, DEFAULT_DIMENSIONS) == 0.0

    def test_mixed_scores_use_weights(self):
        # tool_selection 0.30, factuality 0.40, step_eff 0.20, loop_safe 0.10
        scores = {
            "tool_selection":  DimensionScore(1.0, ""),
            "factuality":      DimensionScore(0.5, ""),
            "step_efficiency": DimensionScore(0.0, ""),
            "loop_safety":     DimensionScore(1.0, ""),
        }
        # 1.0*0.30 + 0.5*0.40 + 0.0*0.20 + 1.0*0.10 = 0.30 + 0.20 + 0 + 0.10 = 0.60
        assert _weighted_total(scores, DEFAULT_DIMENSIONS) == 0.60


# ── score_case (with mocked judge) ────────────────────────────────────────────


class TestScoreCase:
    def test_perfect_response_yields_perfect_score(self):
        result = FakeAgentResult(steps_taken=0)
        fake_response = _fake_claude_response(_all_perfect_payload())
        with patch("eval.rubric_scorer._client") as mock_client:
            mock_client.messages.create.return_value = fake_response
            case = get_case("no_tool_needed")
            cs = score_case(case, result)
        assert cs.error is None
        assert cs.weighted_total == 1.0
        assert cs.case_id == "no_tool_needed"
        assert cs.slice_tag == "no-tool"

    def test_judge_error_captured_in_score(self):
        result = FakeAgentResult()
        with patch("eval.rubric_scorer._client") as mock_client:
            mock_client.messages.create.side_effect = RuntimeError("API down")
            cs = score_case(get_case("weather_arrival_planning"), result)
        assert cs.error is not None
        assert "API down" in cs.error
        assert cs.weighted_total == 0.0  # default

    def test_malformed_json_captured_as_error(self):
        result = FakeAgentResult()
        bad = MagicMock()
        bad.text = "this is not json"
        resp = MagicMock()
        resp.content = [bad]
        with patch("eval.rubric_scorer._client") as mock_client:
            mock_client.messages.create.return_value = resp
            cs = score_case(get_case("weather_arrival_planning"), result)
        assert cs.error is not None

    def test_partial_score_reflects_weights(self):
        result = FakeAgentResult(steps_taken=2)
        payload = {
            "tool_selection":  {"score": 0.5, "reasoning": "one of two"},
            "factuality":      {"score": 1.0, "reasoning": "grounded"},
            "step_efficiency": {"score": 1.0, "reasoning": "minimal"},
            "loop_safety":     {"score": 1.0, "reasoning": "bounded"},
        }
        with patch("eval.rubric_scorer._client") as mock_client:
            mock_client.messages.create.return_value = _fake_claude_response(payload)
            cs = score_case(get_case("chained_flight_and_placemaker"), result)
        # 0.5*0.30 + 1.0*0.40 + 1.0*0.20 + 1.0*0.10 = 0.15+0.40+0.20+0.10 = 0.85
        assert cs.weighted_total == 0.85


# ── Aggregation ──────────────────────────────────────────────────────────────


def _make_case_score(case_id: str, slice_tag: str, scores: dict[str, float]) -> CaseScore:
    """Build a CaseScore manually (no LLM judge)."""
    dim_scores = {
        name: DimensionScore(score=val, reasoning="")
        for name, val in scores.items()
    }
    weighted = _weighted_total(dim_scores, DEFAULT_DIMENSIONS)
    return CaseScore(
        case_id=case_id,
        slice_tag=slice_tag,
        dimension_scores=dim_scores,
        weighted_total=weighted,
        steps_taken=1,
        final_answer="...",
        tool_calls=[],
    )


class TestAggregate:
    def _three_cases(self) -> list[CaseScore]:
        return [
            _make_case_score("a", "single-tool-external",
                             {"tool_selection": 1.0, "factuality": 1.0,
                              "step_efficiency": 1.0, "loop_safety": 1.0}),
            _make_case_score("b", "single-tool-external",
                             {"tool_selection": 0.5, "factuality": 0.5,
                              "step_efficiency": 0.5, "loop_safety": 1.0}),
            _make_case_score("c", "multi-tool",
                             {"tool_selection": 0.0, "factuality": 0.0,
                              "step_efficiency": 0.5, "loop_safety": 0.5}),
        ]

    def test_overall_mean_computed(self):
        report = aggregate_scores(self._three_cases())
        # tool_selection mean = (1.0 + 0.5 + 0.0) / 3 = 0.5
        assert report.overall_per_dimension_mean["tool_selection"] == 0.5
        # factuality mean = (1.0 + 0.5 + 0.0) / 3 = 0.5
        assert report.overall_per_dimension_mean["factuality"] == 0.5

    def test_per_slice_aggregation(self):
        report = aggregate_scores(self._three_cases())
        slices_by_tag = {s.slice_tag: s for s in report.per_slice}
        ext = slices_by_tag["single-tool-external"]
        assert ext.case_count == 2
        assert ext.per_dimension_mean["tool_selection"] == 0.75  # (1.0 + 0.5) / 2
        multi = slices_by_tag["multi-tool"]
        assert multi.case_count == 1

    def test_errored_cases_excluded_from_means(self):
        cases = self._three_cases()
        cases.append(CaseScore(
            case_id="d", slice_tag="multi-tool",
            dimension_scores={d.name: DimensionScore(0.0, "") for d in DEFAULT_DIMENSIONS},
            weighted_total=0.0, steps_taken=0, final_answer="", tool_calls=[],
            error="judge failed",
        ))
        report = aggregate_scores(cases)
        # Overall mean should be the same as before — errored case excluded
        assert report.overall_per_dimension_mean["tool_selection"] == 0.5

    def test_empty_input_yields_zero(self):
        report = aggregate_scores([])
        assert report.overall_weighted_total == 0.0
        assert report.per_slice == []

    def test_weights_recorded(self):
        report = aggregate_scores(self._three_cases())
        assert report.weights["tool_selection"] == 0.30


# ── Markdown report ──────────────────────────────────────────────────────────


class TestReport:
    def _build_report(self) -> AggregateReport:
        cases = [
            _make_case_score("good_case", "single-tool-external",
                             {"tool_selection": 1.0, "factuality": 1.0,
                              "step_efficiency": 1.0, "loop_safety": 1.0}),
            _make_case_score("bad_case", "multi-tool",
                             {"tool_selection": 0.0, "factuality": 0.2,
                              "step_efficiency": 0.5, "loop_safety": 1.0}),
        ]
        return aggregate_scores(cases)

    def test_contains_main_sections(self):
        md = generate_markdown_report(self._build_report())
        assert "# Concierge Research Agent — Rubric Eval Report" in md
        assert "## Worst-performing cases" in md
        assert "## Overall per-dimension" in md
        assert "## Per-slice breakdown" in md
        assert "## All cases" in md

    def test_worst_case_surfaced_at_top(self):
        md = generate_markdown_report(self._build_report())
        worst_idx = md.find("## Worst-performing cases")
        overall_idx = md.find("## Overall per-dimension")
        assert 0 <= worst_idx < overall_idx
        # bad_case should appear in the worst section, before the All cases table
        bad_idx = md.find("bad_case")
        good_idx = md.find("good_case")
        assert bad_idx != -1 and good_idx != -1
        # bad_case appears first because it's in the worst-performing section
        assert bad_idx < good_idx

    def test_slice_table_includes_all_slices(self):
        md = generate_markdown_report(self._build_report())
        assert "single-tool-external" in md
        assert "multi-tool" in md

    def test_handles_only_errored_cases(self):
        errored = [CaseScore(
            case_id="x", slice_tag="multi-tool",
            dimension_scores={d.name: DimensionScore(0.0, "") for d in DEFAULT_DIMENSIONS},
            weighted_total=0.0, steps_taken=0, final_answer="", tool_calls=[],
            error="failed",
        )]
        report = aggregate_scores(errored)
        md = generate_markdown_report(report)
        # Should still render without crashing
        assert "## Worst-performing cases" in md
        assert "No successfully scored cases" in md


# ── CLI runner sanity ────────────────────────────────────────────────────────


class TestRunEvalCLI:
    def test_parse_args_default(self):
        from eval.run_eval import _parse_args
        args = _parse_args([])
        assert args.output == "eval_report.md"
        assert args.slice_filter == "all"
        assert args.only == ""

    def test_parse_args_filter(self):
        from eval.run_eval import _parse_args
        args = _parse_args(["--only", "weather_arrival_planning", "-o", "x.md"])
        assert args.only == "weather_arrival_planning"
        assert args.output == "x.md"

    def test_filter_cases_only(self):
        from eval.run_eval import _filter_cases, _parse_args
        args = _parse_args(["--only", "weather_arrival_planning,flight_status_basic"])
        cases = _filter_cases(args)
        assert {c["id"] for c in cases} == {"weather_arrival_planning", "flight_status_basic"}

    def test_filter_cases_slice(self):
        from eval.run_eval import _filter_cases, _parse_args
        args = _parse_args(["--slice", "no-tool"])
        cases = _filter_cases(args)
        assert all(c["slice"] == "no-tool" for c in cases)
        assert len(cases) >= 1
