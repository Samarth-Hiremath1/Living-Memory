# Living Memory

*AI for the staff. Magic for the guest.*

---

## The problem

Luxury hotels run on staff who remember the small things — the wine a guest preferred, the trail they asked about, the fact that they always want the room cool. But shifts change, turnover is high, and the best observations live in someone's head until they leave. Across a chain like Rosewood — 33 properties, 21 countries — those details effectively never travel. A guest who had a perfect stay in Hong Kong arrives in Paris to a blank slate. Living Memory is the connective tissue that lets those details move with the guest.

---

## Multi-Agent Architecture

The arrival plan pipeline is built with [LangGraph](https://github.com/langchain-ai/langgraph) — a stateful, graph-structured multi-agent framework where each agent is a node and edges define execution order and parallelism. Five specialized Claude agents each own a narrow slice of the problem.

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

`flight_node`, `history_node`, and `wellness_node` have no dependency on each other so LangGraph runs them concurrently — reducing wall time compared to a naive sequential chain. `place_node` legitimately needs the history output before it can match a PlaceMaker, so it runs after the fan-in. The `synthesize_node` then has the full picture from all four upstream agents.

**Why LangGraph over a plain function chain:**
- **Typed shared state** (`ArrivalPipelineState`) — every agent reads and writes to the same explicitly typed object; data flow is inspectable and each node is independently testable
- **Parallel fan-out / fan-in** — flight, history, and wellness run concurrently; the framework handles the join barrier
- **Conditional routing hooks** — ready to branch (e.g. richer synthesizer prompt for Living Memory guests, skip wellness node if guest hasn't opted in) without restructuring the graph

| Agent | Purpose |
|---|---|
| **Flight Agent** | Checks live arrival status via AviationStack; computes jet lag severity and translates it into a staff note |
| **History Agent** | Reads all past observations across every property; Claude Haiku extracts patterns, occasions, and standout moments |
| **Wellness Agent** | Reads opt-in wellness signals (mock wearable data); produces surface-level staff notes only, never clinical data |
| **PlaceMaker Agent** | Matches extracted guest interests to the right property expert — chef, sommelier, or wellness director |
| **Synthesizer** | Combines all agent outputs into a complete arrival plan and warm staff dossier using Claude Sonnet |
| **Friend Filter** | Rewrites every AI output through a "would a close friend say this?" test; strips clinical language before anything reaches staff |
| **Observation Parser** | Turns freeform staff voice notes into structured tags, sentiment, and action items using Claude Haiku |
| **Welcome Summarizer** | Processes the pre-arrival voice transcript or form; extracts structured preferences and merges them into the guest's profile |
| **Welcome Ambassador** | ElevenLabs conversational AI agent that conducts the pre-arrival voice call |
| **In-Stay Concierge** | Second ElevenLabs agent available during the stay; full property and PlaceMaker knowledge for live voice requests |

---

## MCP Tool-Use Agent

The arrival pipeline produces the morning dossier on a schedule. But staff also have **ad-hoc questions** throughout the day: *"Is LH456 on time?"*, *"What's the weather in Napa?"*, *"Who at the property should host a guest who loves natural wine?"*

The **Concierge Research Agent** answers those. It's a separate LangGraph graph — a ReAct loop rather than a DAG — that gives Claude three hospitality-scoped tools defined in **MCP format** (the same `name` / `description` / `input_schema` spec used in Anthropic's tool-use API and Model Context Protocol):

| Tool | What it does |
|---|---|
| **`get_weather`** | Live conditions for any city via `wttr.in` — arrival packing notes, golden-hour timing, activity recommendations |
| **`get_flight_status`** | IATA flight lookup with route, scheduled vs. estimated arrival, gate, and a computed jet-lag severity note based on the origin timezone |
| **`find_placemaker`** | Searches the property's **internal** roster (chefs, sommeliers, wellness directors) by keyword overlap — the only tool that queries Living Memory's own graph rather than an external API |

```
START
  │
  ▼
agent_node  ←─────────────────────┐
(Claude decides: answer            │
 directly or call tools)           │
  │                                │
  ├──(tool_use)──→ tool_node ──────┘   (loop until no more tool calls)
  │
  └──(end_turn)──→ END
```

Claude autonomously selects and chains tools within a single turn. The killer demo query:

> *"Guest is inbound on LH456. They mentioned they're passionate about California cuisine. Check the flight and tell me who at the property would be the right host."*

Claude calls `get_flight_status` and `find_placemaker` in parallel, then composes: *"Perfect timing. LH456 is arriving on schedule — significant jet lag incoming (9h difference). Reylon Agustin at Madera would be the perfect host for this guest..."*

Exposed at `POST /agent/query`. Tool catalogue at `GET /agent/tools`.

---

## Eval Suite

Agent behaviour is locked in by a two-layer pytest suite under `backend/tests/` and `backend/eval/`.

### Layer 1 — Unit + integration tests (`test_mcp_agent.py`)

- **16 unit tests** for the individual tools — no LLM calls, no API keys, run in ~3 seconds
- **11 integration tests** for the full ReAct loop — assert correct tool selection, expected keywords in the final answer, and that the agent stays bounded (≤6 steps)
- Eval cases span 6 failure-mode slices: `single-tool-external`, `single-tool-internal`, `multi-tool`, `no-tool`, `ambiguous-query`, `degraded-api`

```bash
pytest tests/test_mcp_agent.py -v                   # all 27 tests
pytest tests/test_mcp_agent.py -m "not integration" # unit tests only
```

### Layer 2 — Rubric-based LLM-as-judge (`eval/rubric_scorer.py`)

A Claude-based judge scores each agent run on four weighted dimensions and produces a markdown report with per-dimension means and per-slice breakdowns.

| Dimension | Weight | What the judge looks at |
|---|---:|---|
| `tool_selection` | 0.30 | Right tool(s) chosen? Penalises wrong, missing, or unnecessary calls |
| `factuality` | 0.40 | Answer grounded in tool output? Penalises fabrication |
| `step_efficiency` | 0.20 | Minimum reasonable steps taken? Penalises redundancy |
| `loop_safety` | 0.10 | Stayed bounded (≤4 steps ideal)? Penalises loops |

The rubric — dimensions, weights, judge model, and prompt template — is fully configurable via `RubricConfig`. The report surfaces worst-performing cases at the top, then breaks down scores by slice so it's easy to see which categories the agent fails on.

```bash
python -m eval.run_eval                        # all cases → eval_report.md
python -m eval.run_eval --slice degraded-api   # single slice
python -m eval.run_eval --judge-model claude-haiku-4-5
```

**39 unit tests** cover the scorer itself (mocked judge — no API needed):

```bash
pytest tests/test_rubric_scorer.py -v   # 39 tests, ~0.5s
```

**Real result from the degraded-api slice:** The judge correctly flagged the agent short-circuiting — refusing to call the tool on an obviously bad location instead of letting it return its real error. Weighted score: 0.30. Tool selection: 0.00. This is the kind of failure mode that a pass/fail assertion wouldn't distinguish.

---

## The Friend Filter

Every AI output passes through a "friend filter" before reaching staff. The principle: would a close colleague who knew this guest well say this naturally?

**Before:**
> "Guest exhibits 73% rosé preference based on last 5 dinner orders. Dietary flags: pescatarian (confidence: high). Recommend wine pairing aligned with historical ordering pattern."

**After:**
> "Samarth usually leans toward something light and outdoorsy — a natural rosé or a coastal white would land well. He doesn't eat meat, but he's not fussy about it."

The filter runs on Claude Haiku and is applied to history patterns, wellness notes, and the synthesizer's dossier output. It actively rewrites structure that sounds like a readout into language that sounds like a briefing from someone who cares.

---

## How it works

**Before arrival:** When a reservation is created, the guest receives a welcome link. They can have a short voice conversation with the Rosewood Ambassador (an ElevenLabs conversational AI), fill out an optional form, or skip it entirely. Whatever they share is stored in their profile.

**The morning briefing:** The manager dashboard triggers the multi-agent pipeline for each arriving guest. Agents run in parallel — checking the flight, reading past observations, scanning wellness signals — then combine into a "First 24 Hours" plan: room temperature, welcome amenity, 3–4 moments to create, and a PlaceMaker introduction.

**During the stay:** Staff capture observations by voice or text on the concierge tablet ("She mentioned wanting to photograph the valley at golden hour"). Claude parses the note, extracts action items, and the concierge view updates in real time — no forms, no tickets.

**Across properties:** Guests who opt into "Living Memory" carry their preferences across every Rosewood property worldwide. The Paris property's pre-arrival briefing already knows what they ordered in Hong Kong.

---

## System architecture

**Two frontends:**
- **Guest-facing:** Welcome page (voice + form), data transparency page, consent management
- **Staff-facing:** Manager dashboard (today's arrivals, plan generation, dossier view), concierge tablet (in-house guests, live observation capture)

**Data layer:** In-memory Python dict with JSON persistence at `backend/data/graph_store.json`. Schema is Neo4j-compatible for a production migration. Consent model: Standard (this stay only) or Living Memory (cross-property, persistent).

**Voice:** Two ElevenLabs agents — Welcome Ambassador (pre-arrival, opt-in) and In-Stay Concierge. Transcripts are processed by Claude Haiku to extract structured preferences before the pipeline runs.

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

### Try this first

1. Go to `localhost:3000/welcome` and have a 60-second conversation with the Ambassador (or fill out the quick form). This seeds your guest profile.
2. Open `localhost:3000/manager` (password: `sandhill2026`) and click "Generate Arrival Plan" — watch the LangGraph pipeline run live: parallel flight/history/wellness, fan-in, PlaceMaker match, and final synthesis.
3. Open `localhost:3000/concierge` and capture an observation by voice or text. Watch it appear immediately with action items extracted automatically.
4. Hit the Concierge Research Agent directly:
   ```bash
   curl -X POST localhost:8000/agent/query \
     -H "Content-Type: application/json" \
     -d '{"query": "Guest inbound on LH456 loves California cuisine — check the flight and tell me who should host them."}'
   ```

**Other views:**
- `localhost:3000/my-data` — Guest data transparency and consent management
- `localhost:8000/docs` — Full API documentation

---

## What's implemented

- Full guest/stay/observation/plan data model with JSON persistence
- LangGraph orchestration pipeline — parallel fan-out, typed shared state, fan-in
- Arrival plan generation with Claude Sonnet producing a full staff dossier
- Concierge Research Agent — ReAct loop with MCP-style tools and 27-case pytest eval suite
- Rubric-based LLM-as-judge eval layer — 4-dimension scoring, slice breakdowns, markdown report, 39 scorer tests
- Friend Filter — tone translation from clinical AI output to warm, readable language
- Staff observation capture via text and browser speech recognition (Web Speech API)
- Welcome page with ElevenLabs voice conversation + optional survey form as fallback
- Welcome transcript processing — Claude Haiku extracts structured preferences, merges into guest profile
- Manager dashboard: today's arrivals, per-guest plan generation, dossier view with cross-property memory timeline
- Concierge tablet: in-house guest list, real-time observation capture with optimistic UI updates, editable action item list
- Consent management: Standard vs. Living Memory, "Forget Me Everywhere" data deletion
- Guest data transparency page
- PMS webhook endpoint — receives a reservation, creates guest/stay, returns a welcome link
- ElevenLabs post-call webhook (requires public URL for ElevenLabs to call)
- Staff auth gate on manager dashboard
- FastAPI with auto-docs at `/docs`

---

## What's partial or stubbed

**Cross-property memory** — Past-stay timelines are hardcoded in the frontend for demo guests. The backend data model fully supports it; dynamic fetching isn't wired yet.

**Flight tracking** — AviationStack integration is wired into `flight_node`. Falls back to mock data if no API key is configured.

**ElevenLabs post-call webhook** — Backend endpoint works but requires a public URL (ngrok) for ElevenLabs to reach it. Frontend-side transcript processing is the active fallback.

**Briefing audio** — `GET /arrivals/plan/{stay_id}/audio` pipes the dossier through ElevenLabs TTS into an MP3. Not exposed in the UI yet.

**Identity resolution** — `identity.py` has fuzzy cross-property matching. No UI to trigger or review it.

**Conditional pipeline routing** — LangGraph graph uses fixed edges. Conditional branches (e.g. richer synthesizer for Living Memory guests) are architecturally ready but not wired.

---

## What's not built

- Production deployment / hosting
- Real PMS integration (fake client exists for testing)
- Staff mobile push notifications
- Automated PlaceMaker availability or booking
- Multi-property backend sync
- Any real authentication beyond the demo password

---

## Future directions

**Departure and post-stay continuity.** The system focuses on arrival and in-stay. Post-stay relationship continuity — a checkout note referencing something specific from the stay, an email timed for when the guest is likely planning their next trip — is largely unaddressed.

**Family and group memory.** The data model treats each guest as an individual. Adding family-member nodes (Anna's husband doesn't drink, their daughter loves marine biology) would let the system serve a whole trip, not just one person.

**Real wellness signal integration.** The wellness node runs on mock data. Whoop, Oura, and Apple Watch HRV are technically tractable opt-in integrations — "the system noticed your HRV is suppressed post-flight and pushed your breakfast back an hour" is the kind of moment that sticks.

**Conditional pipeline routing.** The next step is meaningful LangGraph branching — a Living Memory guest gets a richer synthesizer prompt weaving in cross-property patterns; a Standard guest gets a clean, current-stay-only plan.

**PlaceMaker availability and booking.** The system recommends but doesn't connect to actual scheduling. Closing that loop — system proposes, staff confirms, guest receives a calendar hold — is the last mile between a recommendation and a moment.

---

## Concept

The best hospitality happens when staff seem to already know you — not because they memorized a file, but because someone thoughtful passed along the right detail at the right moment. Living Memory is what makes that possible at scale. It listens to staff observations during a stay, connects them to what the guest shared before they arrived, and quietly surfaces the one or two things that matter most to the team preparing for their return. The AI does the connective tissue work; the humans do the delivery. The guest never knows a system was involved — they just feel genuinely anticipated.
