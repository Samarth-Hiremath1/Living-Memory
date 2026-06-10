"""
Rubric-based LLM-as-judge evaluation for the Concierge Research Agent.

Modules:
  cases          — shared EVAL_CASES list with slice tags
  rubric_scorer  — RubricConfig, score_case, aggregate_scores, generate_report
  run_eval       — CLI: execute agent on all cases, score, write markdown report
"""
