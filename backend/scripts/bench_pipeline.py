"""
Benchmark the arrival pipeline's parallel fan-out.

Answers the question the README has always asserted without evidence:
"how much does running flight/history/wellness concurrently actually save?"

Method
------
Every pipeline node is wrapped by @instrument, which records wall-clock start
and end via time.perf_counter(). For the three fan-out nodes:

    serial_ms = sum(each node's duration)      what a sequential chain costs
    wall_ms   = max(end) - min(start)          what actually elapsed
    speedup   = serial_ms / wall_ms

Summing durations alone proves nothing about concurrency — you need the
timestamps to show the intervals overlap.

Usage:
    cd backend && python -m scripts.bench_pipeline [--runs 3]
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time

from src.agents.orchestrator import generate_arrival_plan
from src.graph.store import graph
from src.observability import (
    configure_logging,
    get_timings,
    reset_timings,
    summarize_parallel_section,
)

PARALLEL_NODES = ["flight_node", "history_node", "wellness_node"]


def _seed() -> None:
    """Load property/placemaker/guest fixtures the same way the API does."""
    import json as _json
    from pathlib import Path

    from src.graph.schema import PlaceMaker, Property

    data_dir = Path("../data")
    for prop_file in (data_dir / "properties").glob("*.json"):
        try:
            graph.upsert_property(Property.model_validate(_json.loads(prop_file.read_text())))
        except Exception:
            pass
    pm_file = data_dir / "placemakers" / "placemakers.json"
    if pm_file.exists():
        for pm in _json.loads(pm_file.read_text()):
            try:
                graph.upsert_placemaker(PlaceMaker.model_validate(pm))
            except Exception:
                pass
    syn = data_dir / "synthetic" / "guests.json"
    if syn.exists():
        try:
            graph.bulk_load(_json.loads(syn.read_text()))
        except Exception:
            pass


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=3)
    args = ap.parse_args()

    configure_logging()
    _seed()

    guests = graph.list_guests()
    if not guests:
        print("No guests loaded — cannot benchmark.", file=sys.stderr)
        return 1

    # Prefer a stay that has a flight number. Without one, flight_node returns
    # immediately and the fan-out has only one node doing real work — which
    # measures nothing about parallelism.
    target = None
    for g in guests:
        for s in graph.get_stays_for_guest(g.id):
            if s.flight_number:
                target = (g, s)
                break
        if target:
            break
    if target is None:  # fall back to any stay, and say so
        for g in guests:
            stays = graph.get_stays_for_guest(g.id)
            if stays:
                target = (g, stays[0])
                print("WARNING: no stay has a flight_number; flight_node will no-op.")
                break
    if target is None:
        print("No guest with a stay — cannot benchmark.", file=sys.stderr)
        return 1

    guest, stay = target
    print(f"Benchmarking pipeline for guest={guest.name} stay={stay.id}")
    print(f"Parallel nodes: {', '.join(PARALLEL_NODES)}\n")

    results = []
    for i in range(1, args.runs + 1):
        reset_timings()
        t0 = time.perf_counter()
        generate_arrival_plan(guest.id, stay.id)
        total_ms = (time.perf_counter() - t0) * 1000

        summary = summarize_parallel_section(PARALLEL_NODES, "arrival_pipeline")
        summary["total_pipeline_ms"] = round(total_ms, 2)
        results.append(summary)

        print(f"run {i}:")
        for node, ms in sorted(summary["nodes"].items(), key=lambda x: -x[1]):
            print(f"    {node:16} {ms:9.1f} ms")
        print(f"    {'serial (sum)':16} {summary['serial_ms']:9.1f} ms")
        print(f"    {'wall (actual)':16} {summary['wall_ms']:9.1f} ms")
        print(f"    {'speedup':16} {summary['speedup']:9.2f}x")
        print(f"    {'saved':16} {summary['overlap_ms']:9.1f} ms")
        print(f"    {'full pipeline':16} {summary['total_pipeline_ms']:9.1f} ms\n")

    print("=" * 58)
    print(f"MEDIAN OVER {args.runs} RUNS")
    print("=" * 58)
    med = {
        "serial_ms": statistics.median(r["serial_ms"] for r in results),
        "wall_ms": statistics.median(r["wall_ms"] for r in results),
        "speedup": statistics.median(r["speedup"] for r in results),
        "overlap_ms": statistics.median(r["overlap_ms"] for r in results),
        "total_pipeline_ms": statistics.median(r["total_pipeline_ms"] for r in results),
    }
    print(f"  parallel section, serial cost : {med['serial_ms']:.1f} ms")
    print(f"  parallel section, actual wall : {med['wall_ms']:.1f} ms")
    print(f"  SPEEDUP                       : {med['speedup']:.2f}x")
    print(f"  wall time saved               : {med['overlap_ms']:.1f} ms")
    print(f"  full pipeline end-to-end      : {med['total_pipeline_ms']:.1f} ms")
    print()
    print(json.dumps(med, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
