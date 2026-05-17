# Living Memory

*AI for the staff. Magic for the guest.*

A luxury hotel has thousands of small moments every day where it could get something exactly right — the fireplace already lit, the wine they mentioned, a note from the chef about tomorrow's farm lunch. Most of those moments never happen because no one connected the dots in time. Living Memory is an attempt to connect those dots automatically, and route them back through human hands.

The guest never sees a screen. The AI never talks to a guest directly (except for one opt-in pre-arrival voice call). Everything the system learns surfaces as a warm, human-readable staff briefing — never a robotic list of data points, never a clinical readout. A Claude "friend filter" rewrites every AI output to sound like it came from a well-informed colleague, not a system.

---

## How it works

**Before arrival:** When a reservation is created, the guest receives a welcome link. They can have a short voice conversation with the Rosewood Ambassador (an ElevenLabs conversational AI), or fill out an optional form — or neither. Whatever they share is stored in their profile.

**The morning briefing:** The manager dashboard triggers the multi-agent pipeline for each arriving guest. Multiple AI agents run in parallel — checking the flight, reading past observations, scanning wellness signals — then combine their findings into a "First 24 Hours" plan: room temperature, welcome amenity, 3–4 moments to create, and a PlaceMaker introduction.

**During the stay:** Staff capture observations by voice or text on the concierge tablet ("She mentioned wanting to photograph the valley at golden hour"). Claude parses the note, extracts action items, and the concierge view updates in real time — no forms, no tickets.

**Across properties:** Guests who opt into "Living Memory" carry their preferences across every Rosewood property worldwide. The Paris property's pre-arrival briefing already knows what they ordered in Hong Kong.

---

## Orchestration: LangGraph multi-agent pipeline

The arrival plan pipeline is built with [LangGraph](https://github.com/langchain-ai/langgraph) — a framework for building stateful, graph-structured multi-agent workflows. Each agent is a node; edges define what runs next and what runs in parallel.

```
START
  │
  ▼
load_context          ← validates guest + stay, loads objects into shared state
  │
  ├──────────────────────────────┐─────────────────────────┐
  ▼                              ▼                         ▼
flight_node               history_node              wellness_node
(AviationStack →          (Claude Haiku reads        (opt-in wellness
 jet lag profile)          all past observations)     signals, mock)
  │                              │                         │
  └──────────────────────────────┴─────────────────────────┘
                    fan-in: place_node waits for all three
                                 │
                                 ▼
                           place_node
                    (Claude Haiku matches guest
                     interests → PlaceMaker offering)
                                 │
                                 ▼
                          synthesize_node
                    (Claude Sonnet writes the full
                     arrival plan + dossier markdown)
                                 │
                                END
```

**Why LangGraph?**

The plain sequential version ran flight → history → wellness → place → synthesize in series. `flight_node`, `history_node`, and `wellness_node` have no dependency on each other, so LangGraph runs them in parallel — reducing wall time for every plan generation. `place_node` legitimately depends on `history_node`'s output (it needs the extracted interest patterns to match a PlaceMaker), so it runs after the fan-in.

Beyond parallelism, LangGraph gives us:
- **Typed shared state** (`ArrivalPipelineState`) — every agent reads and writes to the same explicitly typed object, making data flow inspectable
- **Independent, swappable nodes** — each agent can be tested in isolation or replaced without touching the rest of the graph
- **Conditional routing hooks** — ready to add branches (e.g. skip wellness node if guest hasn't opted in; route to a richer synthesizer for Living Memory guests)
- **Built-in visualisation** — `pipeline.get_graph().draw_mermaid()` renders the exact diagram above from the live compiled graph

---

## System architecture

**Two frontends:**
- **Guest-facing:** Welcome page (voice + form), data transparency page, consent management
- **Staff-facing:** Manager dashboard (today's arrivals, plan generation, dossier view), concierge tablet (in-house guests, live observation capture)

**Data layer:** In-memory Python dict with JSON persistence at `backend/data/graph_store.json`. Schema is Neo4j-compatible for a production migration. Consent model has two levels: Standard (this stay only) and Living Memory (cross-property, persistent).

**Voice:** Two ElevenLabs agents — the Welcome Ambassador (pre-arrival, opt-in) and the In-Stay Concierge (available from the concierge tablet). Transcripts from the welcome call are processed by Claude Haiku to extract structured preferences and merge them into the guest's profile before the arrival plan runs.

---

## What's implemented

- Full guest/stay/observation/plan data model with JSON persistence
- **LangGraph orchestration pipeline** — parallel fan-out across flight, history, and wellness agents; typed state; fan-in to PlaceMaker matching and synthesis
- Arrival plan generation with Claude Sonnet producing a full staff dossier
- Friend Filter — Claude Haiku tone translation from clinical AI output to warm, readable language
- Staff observation capture via text and browser speech recognition (Web Speech API)
- Welcome page with ElevenLabs voice conversation + optional survey form as fallback
- Welcome transcript processing — Claude Haiku extracts structured preferences and merges them into the guest's profile, ready for the pipeline
- Manager dashboard: today's arrivals, per-guest plan generation, dossier view with cross-property memory timeline
- Concierge tablet: in-house guest list, real-time observation capture with optimistic UI updates, editable action item list
- Consent management: Standard vs. Living Memory, "Forget Me Everywhere" data deletion
- Guest data transparency page — guests can see exactly what the system holds
- PMS webhook endpoint — receives a new reservation, creates a guest/stay, returns a welcome link ready to send
- ElevenLabs post-call webhook — receives conversation transcripts automatically when a call ends (requires public URL)
- Staff auth gate on manager dashboard (password: `sandhill2026`)
- FastAPI with auto-docs at `/docs`

---

## What's partial or stubbed

**Cross-property memory** — The manager dashboard shows past-stay timelines, but the data is hardcoded in the frontend for the demo guests. The backend data model fully supports it; it's not yet dynamically fetched.

**Flight tracking** — The AviationStack integration is wired into `flight_node`. If a stay has a flight number and an API key is configured, it returns live status. Without a key, it falls back to a mock result.

**ElevenLabs post-call webhook** — The backend endpoint exists and works, but ElevenLabs needs a publicly accessible URL to call it. For local development, this requires ngrok or a tunnel. The frontend-side transcript processing (which doesn't need a public URL) is the active fallback.

**Briefing audio** — There is a `GET /arrivals/plan/{stay_id}/audio` endpoint that pipes the dossier through ElevenLabs TTS into an MP3. It's not exposed in the UI yet.

**Demo scripts** — `scripts/generate_synthetic_data.py` and `scripts/run_demo_scenario.py` are referenced in the original spec but were not built out during the hackathon. The synthetic data in `data/synthetic/guests.json` is pre-populated manually.

**Identity resolution** — The `identity.py` module runs fuzzy matching to find the same guest across properties. The algorithm exists; there's no UI to trigger or review it.

**SMS/email delivery** — The PMS webhook returns a welcome link, but sending it to the guest (SMS, email) is a commented TODO.

**Conditional routing** — The LangGraph graph currently uses fixed edges. The framework is ready for conditional branches (e.g. skip wellness node if no opt-in, enrich the synthesizer for Living Memory guests), but those conditions aren't wired yet.

---

## What's not built

- Production deployment / hosting
- Real PMS integration (a fake PMS client exists for testing)
- Staff mobile push notifications
- Automated PlaceMaker availability or booking
- Multi-property backend sync (all data currently lives in one instance)
- Any real authentication beyond the demo password

---

## Running locally

**Requirements:** Python 3.11+, Node.js 18+, API keys for Anthropic and ElevenLabs (AviationStack optional).

```bash
cp .env.example .env
# Fill in ANTHROPIC_API_KEY, ELEVENLABS_API_KEY, and ELEVENLABS_AGENT_ID

# Backend — must be run from the backend/ directory
cd backend
pip install -e ".[dev]"
uvicorn src.api:app --reload --port 8000

# Frontend — new terminal
cd frontend
npm install
npm run dev
```

**Views:**
- `localhost:3000/welcome` — Guest welcome experience
- `localhost:3000/manager` — Morning manager dashboard (password: `sandhill2026`)
- `localhost:3000/concierge` — Live concierge tablet
- `localhost:3000/my-data` — Guest data transparency
- `localhost:8000/docs` — API documentation

**Demo note:** The manager dashboard falls back to demo data (Samarth Hiremath, arriving today) if the backend is unreachable. Guests whose arrival plans have already been generated show "View dossier →"; guests without a plan show "Generate Arrival Plan" — clicking it runs the full LangGraph pipeline live against the real APIs.

---

## Concept

The best hospitality happens when staff seem to already know you — not because they memorized a file, but because someone thoughtful passed along the right detail at the right moment. Living Memory is what makes that possible at scale. It listens to staff observations during a stay, connects them to what the guest shared before they arrived, and quietly surfaces the one or two things that matter most to the team preparing for their return. The AI does the connective tissue work; the humans do the delivery. The guest never knows a system was involved — they just feel genuinely anticipated.
