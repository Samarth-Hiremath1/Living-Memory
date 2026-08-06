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

`flight_node`, `history_node`, and `wellness_node` have no dependency on each other so LangGraph runs them concurrently. **Measured:** on a controlled 3×1s workload the fan-out gives a **3.00x** speedup, confirming the mechanism is real. On the actual pipeline it currently saves ~3ms (**1.00x**) — because only `history_node` has meaningful latency (~6.4s Claude call) while `flight_node` (~3ms, cached) and `wellness_node` (~0ms, mock) return almost instantly. There is nothing to overlap. The parallelism pays off once the other two nodes do real work; see [Measured results](#measured-results). `place_node` legitimately needs the history output before it can match a PlaceMaker, so it runs after the fan-in. The `synthesize_node` then has the full picture from all four upstream agents.

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

The **Concierge Research Agent** answers those. It's a separate LangGraph graph — a ReAct loop rather than a DAG — and it talks to a **real MCP server** over stdio.

The agent holds **no hardcoded tool list**. On each run it calls `tools/list` against `src/mcp_server/server.py`, translates the returned MCP schemas (`inputSchema`) into the Anthropic tool format (`input_schema`), and routes every execution through `tools/call`. Adding a tool to the server makes it available to the agent with no change to the agent code.

| Tool | What it does |
|---|---|
| **`get_weather`** | Live conditions for any city via `wttr.in` — arrival packing notes, golden-hour timing, activity recommendations |
| **`get_flight_status`** | IATA flight lookup with route, scheduled vs. estimated arrival, gate, and a computed jet-lag severity note based on the origin timezone |
| **`find_placemaker`** | Searches the property's **internal** roster (chefs, sommeliers, wellness directors) by keyword overlap — the only tool that queries Living Memory's own graph rather than an external API |


### The MCP server

`src/mcp_server/server.py` is a genuine Model Context Protocol server: JSON-RPC 2.0 over **stdio**, real `initialize` handshake, built on the official `mcp` Python SDK (pinned `>=1.9,<2.0` — the 2.x line reworked the low-level `Server` API).

It exposes **all three MCP primitives**:

| Primitive | Controlled by | What this server exposes |
|---|---|---|
| **Tools** | the model | `get_weather`, `get_flight_status`, `find_placemaker` |
| **Resources** | the application | `livingmemory://sand-hill/placemakers` (expert roster), `livingmemory://sand-hill/profile` (property character, amenities, calendar) |
| **Prompts** | the user | `brief_me_on_guest` — a briefing template taking `guest_name`, optional `flight_number` and `interests` |

The server contains **no business logic**. Every tool delegates to the same functions the rest of the app uses (`src/tools/*`); this module is purely the protocol layer.

Run it standalone (it will appear to hang — correct, it's waiting for JSON-RPC on stdin):

```bash
cd backend && python -m src.mcp_server.server
```

Or drive it from the client bridge:

```bash
cd backend && python -c "
from src.mcp_server.client import get_bridge
b = get_bridge()
print([t['name'] for t in b.list_tools()])
print(b.call_tool('find_placemaker', {'interests': 'Napa wine'}))
"
```

Tested by `tests/test_mcp_server.py` — 18 tests that spawn a real server subprocess and speak actual JSON-RPC. No mocks.


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

### Layer 1 — pytest (110 tests, 109 passing)

| File | Tests | Needs API key |
|---|---:|---|
| `test_mcp_agent.py` | 50 | 27 of them (25 eval cases + 2 shape tests) |
| `test_rubric_scorer.py` | 39 | no — judge is mocked |
| `test_mcp_server.py` | 18 | no — protocol layer is model-independent |
| `test_friend_filter.py` | 3 | yes |
| **Total** | **110** | **83 run without one** |

```bash
pytest tests/ -q                      # 109 passed, 1 failed in 93.9s
pytest tests/ -q -m "not integration" # 83 passed in ~5s, no API key
```

The single failure is left red deliberately — it's a real agent defect (see below), and a green suite that hides it is worth less than a red one that names it.

### Layer 2 — Rubric-based LLM-as-judge (`eval/rubric_scorer.py`)

A Claude judge scores each run on four weighted dimensions and writes a markdown report with per-dimension means, per-slice breakdowns, and worst cases first.

| Dimension | Weight | What the judge looks at |
|---|---:|---|
| `tool_selection` | 0.30 | Right tool(s) for the case's `tool_policy`? |
| `factuality` | 0.40 | Answer grounded in tool output? Penalises fabrication |
| `step_efficiency` | 0.20 | Minimum reasonable steps? Penalises redundancy |
| `loop_safety` | 0.10 | Stayed bounded (≤4 steps ideal)? Penalises loops |

Judge is Sonnet, agent is Haiku — different tiers, so it is not literally self-grading, though same-family bias remains. Weights are validated at run time (`RubricConfig.validate()`), and the report prints the **scored** count as the denominator for every mean, excluding any case whose judge call failed.

**`tool_policy` — grading outcomes, not paths.** Each case declares `required`, `optional`, or `forbidden`. This replaced a schema that hardcoded *which tool must be called*, which punished the agent for correctly declining to call an API on obviously bad input. See [Measured results](#measured-results) for what that change revealed.

```bash
python -m eval.run_eval                        # 25 cases → eval_report.md
python -m eval.run_eval --slice degraded-api   # single slice
python -m eval.run_eval --judge-model claude-haiku-4-5
```

**39 tests** cover the scorer itself with a mocked judge — JSON parsing edge cases (code fences, missing dimensions, out-of-range scores), weight validation, slice aggregation, and report ordering:

```bash
pytest tests/test_rubric_scorer.py -q   # 39 passed
```

### What is NOT validated

The judge has never been calibrated. No repeat runs to measure score variance, no human-labelled set to check agreement, no adversarial probes for verbosity bias. These scores are an unvalidated signal, not a measurement — treat them as directional.

---

## Measured results

Every number here was produced by a command in this repo. Nothing is estimated.

### Test suite — 110 tests, 109 passing

```bash
cd backend && pytest tests/ -q          # 109 passed, 1 failed in 93.9s
pytest tests/ -q -m "not integration"   # 83 passed (no API key needed)
```

| Group | Count |
|---|---:|
| Tool unit tests | 16 |
| Rubric scorer tests (mocked judge) | 39 |
| **MCP server tests** (real subprocess, real JSON-RPC) | **18** |
| Eval-suite structural tests | 7 |
| Friend filter tests | 3 |
| Integration eval cases (25) + agent shape (2) | 27 |
| **Total** | **110** |

The one failure is real and left red on purpose — see below.

### Rubric eval — 25 cases, 6 slices

```bash
cd backend && python -m eval.run_eval    # 198.9s, judge: claude-sonnet-4-5
```

**Composite: 0.828** (n=25, all 25 scored successfully)

| Slice | N | tool_selection | factuality | step_efficiency | loop_safety | Weighted |
|---|---:|---:|---:|---:|---:|---:|
| `no-tool` | 3 | 1.000 | 1.000 | 1.000 | 1.000 | **1.000** |
| `degraded-api` | 5 | 1.000 | 0.800 | 1.000 | 1.000 | **0.920** |
| `ambiguous-query` | 3 | 1.000 | 0.667 | 1.000 | 1.000 | **0.867** |
| `single-tool-external` | 6 | 1.000 | 0.667 | 1.000 | 1.000 | **0.867** |
| `multi-tool` | 4 | 0.750 | 0.750 | 0.750 | 1.000 | **0.775** |
| `single-tool-internal` | 4 | 0.500 | 0.500 | 0.500 | 1.000 | **0.550** |

### What the eval actually found

**1. Over-clarification is the dominant failure mode** (3 cases at 0.100). The agent asks the user for details instead of calling a tool it has enough information to call. Asked *"Guest is a serious food person and wants to actually meet the chef — what can we set up and with whom?"* it returned a list of clarifying questions and made zero tool calls. This is the worst kind of failure because the response reads helpful and professional while delivering nothing. It sinks `single-tool-internal` to 0.550.

**2. Silent wrong-data pass-through** (`weather_location_extraction`, 0.600). Asked for Napa Valley, `wttr.in` returned data for a place called "Fu Tei". The agent presented it as Napa Valley weather and built packing advice on top of it. Tool selection scored 1.00 — it called the right tool with the right argument — but factuality scored 0.00. **No binary assertion would ever catch this**, which is precisely the argument for a graded layer.

**3. The original "degraded-api tool-routing failure" was substantially a rubric bug.** That case previously scored 0.30 with tool_selection 0.00. The agent's behaviour is **unchanged** — it still makes 0 tool calls on a nonsense location. It now scores **1.000**, because the case was rewritten from `tool_policy: required` to `optional`. The old rubric encoded *an action* ("get_weather must be called") as ground truth and punished the agent for correctly declining to call an API on obvious garbage. Fixing the rubric made a false finding disappear and surfaced three real ones.

### Pipeline parallelism — 1.00x, and why

```bash
cd backend && python -m scripts.bench_pipeline --runs 3
```

| Measurement | Value |
|---|---:|
| Controlled 3×1s fan-out (mechanism check) | **3.00x** |
| Real pipeline — serial cost of fan-out | 6408 ms |
| Real pipeline — actual wall time | 6406 ms |
| **Real pipeline speedup** | **1.00x** |
| Full pipeline end-to-end | ~43 s |

LangGraph's fan-out genuinely runs sync nodes concurrently — a controlled test with three 1-second nodes measures 3.00x. But on the real pipeline the speedup is **zero**, because only `history_node` has latency (~6.4 s Claude call). `flight_node` returns in ~3 ms (cache/demo fallback) and `wellness_node` in ~0 ms (mock data). You cannot overlap one slow thing with two instant things.

The architecture is correct and the benefit is currently theoretical. It materialises when the other two branches do real work — a live AviationStack call and a real wellness integration.

---

## Deployment

### Docker

```bash
docker compose up --build       # backend :8000, frontend :3000
```

Both images are verified to build and run. Dependency layers are copied before source so a code edit doesn't reinstall the world — the backend installs from a generated `requirements.txt`, so pins (notably `mcp<2.0`) are identical in local dev and in the image.

| Image | Size |
|---|---:|
| `living-memory-backend:local` | 450 MB |
| `living-memory-frontend:local` | 828 MB (multi-stage: deps → builder → runner) |

### Kubernetes

```bash
kubectl apply -f k8s/
kubeconform -summary -strict k8s/*.yaml   # 4 resources, 0 invalid
```

**Liveness and readiness deliberately point at different endpoints:**

| Probe | Endpoint | Checks | On failure |
|---|---|---|---|
| `livenessProbe` | `/health/live` | Nothing external — is the process alive? | Pod restarted |
| `readinessProbe` | `/health/ready` | Seed data loaded, API key configured | Pod pulled from Service, **not** restarted |

Pointing liveness at a dependency check is an outage amplifier: one slow dependency fails liveness on every pod at once, Kubernetes restarts the whole fleet in a loop, and a recoverable degradation becomes a self-inflicted outage. A `startupProbe` suspends both until first boot completes.

### Observability

Every node in both graphs is wrapped by `@instrument`, emitting one JSON line per execution:

```json
{"ts":"2026-08-02T00:05:13.012+00:00","level":"INFO","logger":"living_memory",
 "msg":"node history_node finished in 6161.0ms (ok)","event":"node",
 "graph":"arrival_pipeline","node":"history_node","duration_ms":6161.0,"status":"ok"}
```

Wall-clock start/end are retained in a process-local registry so `scripts/bench_pipeline.py` can compute overlap directly rather than scraping logs.

### CI

`.github/workflows/ci.yml` runs on every push: backend tests (no API key needed), eval-suite shape assertions, rubric weight validation, both Docker builds, a container smoke test against `/health/live`, and offline manifest validation with `kubeconform`.


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
- Real MCP server (JSON-RPC over stdio) exposing tools, resources and prompts; ReAct agent refactored into an MCP client
- 110-test pytest suite (109 passing) + 25-case rubric eval harness across 6 failure-mode slices
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

**Kubernetes deployment** — Manifests exist and validate against the published schemas (`kubeconform -strict`, 4 resources, 0 invalid), and both Docker images are verified to build and run. But the manifests have **never been applied to a live cluster**. This is deployment configuration, not a deployment.

**MCP server scope** — It is a genuine server (stdio, JSON-RPC 2.0, real handshake, all three primitives), but deliberately narrow. Not covered: HTTP/SSE transport, authentication, resource *templates* (parameterized URIs), `resources/subscribe`, `notifications/tools/list_changed` (the client caches the catalogue after first fetch), sampling, roots, and non-text content blocks — the client flattens everything to text, so `ImageContent` or `EmbeddedResource` would be mangled. It has also never been consumed by a third-party host such as Claude Desktop, so cross-host compatibility is unproven.

**Judge calibration** — See the Eval Suite section. The rubric scores have never been checked against human labels or tested for run-to-run variance.

---

## What's not built

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
