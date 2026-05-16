#!/usr/bin/env python3
"""
Seed the graph store from synthetic JSON files.
Run from the repo root: python scripts/generate_synthetic_data.py
"""

import sys
import json
from pathlib import Path

# Add backend/src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from src.graph.store import graph
from src.graph.schema import Property, PlaceMaker

DATA_DIR = Path(__file__).parent.parent / "data"


def load_properties():
    for prop_file in (DATA_DIR / "properties").glob("*.json"):
        prop = Property.model_validate(json.loads(prop_file.read_text()))
        graph.upsert_property(prop)
        print(f"  ✓ Property: {prop.name}")


def load_placemakers():
    pm_file = DATA_DIR / "placemakers" / "placemakers.json"
    pms = json.loads(pm_file.read_text())
    for pm_data in pms:
        pm = PlaceMaker.model_validate(pm_data)
        graph.upsert_placemaker(pm)
        print(f"  ✓ PlaceMaker: {pm.name} ({pm.property_id})")


def load_guests():
    guests_file = DATA_DIR / "synthetic" / "guests.json"
    data = json.loads(guests_file.read_text())
    graph.bulk_load(data)
    guests = graph.list_guests()
    print(f"  ✓ Loaded {len(guests)} guests")
    stays = list(graph.raw.stays.values())
    print(f"  ✓ Loaded {len(stays)} stays")
    obs = list(graph.raw.observations.values())
    print(f"  ✓ Loaded {len(obs)} observations")


def main():
    print("\n🌿 Living Memory — Seeding graph store\n")

    print("Loading properties...")
    load_properties()

    print("\nLoading PlaceMakers...")
    load_placemakers()

    print("\nLoading synthetic guest data...")
    load_guests()

    print(f"\n✅ Graph store saved to: {graph._path.resolve()}\n")
    print("You can now run: cd backend && uvicorn src.api:app --reload\n")


if __name__ == "__main__":
    main()
