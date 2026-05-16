"""In-memory graph store with JSON persistence. Schema future-compatible with Neo4j."""

from __future__ import annotations
import json
from pathlib import Path
from threading import Lock
from typing import Any

from .schema import (
    GraphStore, Guest, Stay, Observation, Property, PlaceMaker, ArrivalPlan
)


class GuestGraph:
    def __init__(self, persist_path: str = "./data/graph_store.json"):
        self._path = Path(persist_path)
        self._lock = Lock()
        self._store = GraphStore()
        self._load()

    # ── persistence ──────────────────────────────────────────────────────────

    def _load(self) -> None:
        if self._path.exists():
            try:
                raw = json.loads(self._path.read_text())
                self._store = GraphStore.model_validate(raw)
            except Exception:
                self._store = GraphStore()

    def save(self) -> None:
        with self._lock:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(self._store.model_dump_json(indent=2))

    # ── guests ────────────────────────────────────────────────────────────────

    def upsert_guest(self, guest: Guest) -> Guest:
        with self._lock:
            self._store.guests[guest.id] = guest
        self.save()
        return guest

    def get_guest(self, guest_id: str) -> Guest | None:
        return self._store.guests.get(guest_id)

    def get_guest_by_email(self, email: str) -> Guest | None:
        for g in self._store.guests.values():
            if g.email and g.email.lower() == email.lower():
                return g
        return None

    def list_guests(self) -> list[Guest]:
        return list(self._store.guests.values())

    # ── stays ─────────────────────────────────────────────────────────────────

    def upsert_stay(self, stay: Stay) -> Stay:
        with self._lock:
            self._store.stays[stay.id] = stay
            guest = self._store.guests.get(stay.guest_id)
            if guest and stay.id not in guest.stays:
                guest.stays.append(stay.id)
        self.save()
        return stay

    def get_stay(self, stay_id: str) -> Stay | None:
        return self._store.stays.get(stay_id)

    def get_stays_for_guest(self, guest_id: str) -> list[Stay]:
        return [s for s in self._store.stays.values() if s.guest_id == guest_id]

    # ── observations ──────────────────────────────────────────────────────────

    def add_observation(self, obs: Observation) -> Observation:
        with self._lock:
            self._store.observations[obs.id] = obs
            stay = self._store.stays.get(obs.stay_id)
            if stay and obs.id not in stay.observations:
                stay.observations.append(obs.id)
        self.save()
        return obs

    def get_observations_for_guest(self, guest_id: str) -> list[Observation]:
        return [o for o in self._store.observations.values() if o.guest_id == guest_id]

    def get_observations_for_stay(self, stay_id: str) -> list[Observation]:
        return [o for o in self._store.observations.values() if o.stay_id == stay_id]

    # ── properties ────────────────────────────────────────────────────────────

    def upsert_property(self, prop: Property) -> Property:
        with self._lock:
            self._store.properties[prop.id] = prop
        self.save()
        return prop

    def get_property(self, property_id: str) -> Property | None:
        return self._store.properties.get(property_id)

    def list_properties(self) -> list[Property]:
        return list(self._store.properties.values())

    # ── placemakers ───────────────────────────────────────────────────────────

    def upsert_placemaker(self, pm: PlaceMaker) -> PlaceMaker:
        with self._lock:
            self._store.placemakers[pm.id] = pm
        self.save()
        return pm

    def get_placemakers_for_property(self, property_id: str) -> list[PlaceMaker]:
        return [p for p in self._store.placemakers.values() if p.property_id == property_id]

    # ── arrival plans ─────────────────────────────────────────────────────────

    def upsert_arrival_plan(self, plan: ArrivalPlan) -> ArrivalPlan:
        with self._lock:
            self._store.arrival_plans[plan.id] = plan
        self.save()
        return plan

    def get_arrival_plan_for_stay(self, stay_id: str) -> ArrivalPlan | None:
        for p in self._store.arrival_plans.values():
            if p.stay_id == stay_id:
                return p
        return None

    # ── bulk load ─────────────────────────────────────────────────────────────

    def bulk_load(self, data: dict[str, Any]) -> None:
        """Load data from a dict (e.g., seeded from JSON files)."""
        if "guests" in data:
            for g in data["guests"]:
                self._store.guests[g["id"]] = Guest.model_validate(g)
        if "stays" in data:
            for s in data["stays"]:
                self._store.stays[s["id"]] = Stay.model_validate(s)
        if "observations" in data:
            for o in data["observations"]:
                self._store.observations[o["id"]] = Observation.model_validate(o)
        if "properties" in data:
            for p in data["properties"]:
                self._store.properties[p["id"]] = Property.model_validate(p)
        if "placemakers" in data:
            for pm in data["placemakers"]:
                self._store.placemakers[pm["id"]] = PlaceMaker.model_validate(pm)
        self.save()

    @property
    def raw(self) -> GraphStore:
        return self._store


# Global singleton — import this everywhere
graph = GuestGraph()
