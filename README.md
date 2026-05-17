# Living Memory

*AI for the staff. Magic for the guest.*

---

## The problem

Luxury hotels run on staff who remember the small things — the wine a guest preferred, the trail they asked about, the fact that they always want the room cool. But shifts change, turnover is high, and the best observations live in someone's head until they leave. Across a chain like Rosewood — 33 properties, 21 countries — those details effectively never travel. A guest who had a perfect stay in Hong Kong arrives in Paris to a blank slate. Living Memory is the connective tissue that lets those details move with the guest.

---

## How it works

**Before arrival:** When a reservation is created, the guest receives a welcome link. They can have a short voice conversation with the Rosewood Ambassador (an ElevenLabs conversational AI), fill out an optional form, or skip it entirely. Whatever they share is stored in their profile.

**The morning briefing:** The manager dashboard triggers the multi-agent pipeline for each arriving guest. Multiple AI agents run in parallel — checking the flight, reading past observations, scanning wellness signals — then combine their findings into a "First 24 Hours" plan: room temperature, welcome amenity, 3–4 moments to create, and a PlaceMaker introduction.

**During the stay:** Staff capture observations by voice or text on the concierge tablet ("She mentioned wanting to photograph the valley at golden hour"). Claude parses the note, extracts action items, and the concierge view updates in real time — no forms, no tickets.

**Across properties:** Guests who opt into "Living Memory" carry their preferences across every Rosewood property worldwide. The Paris property's pre-arrival briefing already knows what they ordered in Hong Kong.

---

## The agents

The system is made up of several purpose-built agents, each responsible for a narrow slice of the problem:

| Agent | Purpose |
|---|---|
| **Welcome Summarizer** | Processes the pre-arrival voice transcript or form; extracts structured preferences (arrival time, room temperature, dietary, occasion) and merges them into the guest's profile |
| **Flight Agent** | Checks live arrival status via AviationStack; computes jet lag severity and translates it into a staff note ("long-haul fatigue is real — keep check-in seamless") |
| **History Agent** | Reads all past observations across every property stay; uses Claude Haiku to extract patterns, occasions, sensitivities, and standout moments |
| **Wellness Agent** | Reads opt-in wellness signals (mock wearable data in this demo); produces surface-level staff notes only, never clinical data |
| **PlaceMaker Agent** | Matches the guest's extracted interests to the right property expert — chef, sommelier, or wellness director — and suggests the most relevant offering |
| **Synthesizer** | Combines all agent outputs into a complete arrival plan and staff dossier using Claude Sonnet; the final document includes room setup, moments to create, and a warm narrative |
| **Friend Filter** | Rewrites every AI output through a "would a close friend say this?" test before it reaches staff; strips clinical language and recalibrates tone |
| **Observation Parser** | Turns freeform staff voice notes into structured tags, sentiment, and action items using Claude Haiku |
| **Welcome Ambassador** | ElevenLabs conversational AI agent that conducts the pre-arrival voice call; asks about arrival mood, pace, room setup, and anything the guest is looking forward to |
| **In-Stay Concierge** | Second ElevenLabs agent available during the stay; has full knowledge of the property, PlaceMakers, and local area for live voice requests |

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

`flight_node`, `history_node`, and `wellness_node` have no dependency on each other, so LangGraph runs them concurrently. `place_node` legitimately needs the history output before it can match a PlaceMaker, so it runs after the fan-in. The `synthesize_node` then has the full picture from all four upstream agents.

Beyond parallelism, LangGraph gives us typed shared state (`ArrivalPipelineState`) that makes data flow explicit and inspectable, independently testable nodes, and conditional routing hooks that are ready to add — for example, routing to a richer synthesizer prompt for Living Memory guests, or skipping the wellness node if the guest hasn't opted in.

---

## The Friend Filter

Every AI output in the system passes through a "friend filter" before reaching staff. The principle: would a close colleague who knew this guest well say this naturally?

**Before:**
> "Guest exhibits 73% rosé preference based on last 5 dinner orders. Dietary flags: pescatarian (confidence: high). Recommend wine pairing aligned with historical ordering pattern."

**After:**
> "Samarth usually leans toward something light and outdoorsy — a natural rosé or a coastal white would land well. He doesn't eat meat, but he's not fussy about it."

The filter runs on Claude Haiku and is applied to history patterns, wellness notes, and the synthesizer's dossier output. It's not a cosmetic pass — it actively rewrites structure that sounds like a readout into language that sounds like a briefing from someone who cares.

---

## System architecture

**Two frontends:**
- **Guest-facing:** Welcome page (voice + form), data transparency page, consent management
- **Staff-facing:** Manager dashboard (today's arrivals, plan generation, dossier view), concierge tablet (in-house guests, live observation capture)

**Data layer:** In-memory Python dict with JSON persistence at `backend/data/graph_store.json`. Schema is Neo4j-compatible for a production migration. Consent model has two levels: Standard (this stay only) and Living Memory (cross-property, persistent).

**Voice:** Two ElevenLabs agents — the Welcome Ambassador (pre-arrival, opt-in) and the In-Stay Concierge (available from the concierge tablet). Transcripts from the welcome call are processed by Claude Haiku to extract structured preferences and merge them into the guest's profile before the arrival plan runs.

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
2. Open `localhost:3000/manager` (password: `sandhill2026`) and click "Generate Arrival Plan" — watch the LangGraph pipeline run live: flight check, history read, wellness scan, PlaceMaker match, and final synthesis.
3. Open `localhost:3000/concierge` and capture an observation by voice or text. Watch it appear in the feed immediately, with action items extracted automatically.

**Other views:**
- `localhost:3000/my-data` — Guest data transparency and consent management
- `localhost:8000/docs` — Full API documentation

---

## What's implemented

- Full guest/stay/observation/plan data model with JSON persistence
- LangGraph orchestration pipeline — parallel fan-out across flight, history, and wellness agents; typed shared state; fan-in to PlaceMaker matching and synthesis
- Arrival plan generation with Claude Sonnet producing a full staff dossier
- Friend Filter — tone translation from clinical AI output to warm, readable language
- Staff observation capture via text and browser speech recognition (Web Speech API)
- Welcome page with ElevenLabs voice conversation + optional survey form as fallback
- Welcome transcript processing — Claude Haiku extracts structured preferences and merges them into the guest's profile, ready for the pipeline
- Manager dashboard: today's arrivals, per-guest plan generation, dossier view with cross-property memory timeline
- Concierge tablet: in-house guest list, real-time observation capture with optimistic UI updates, editable action item list
- Consent management: Standard vs. Living Memory, "Forget Me Everywhere" data deletion
- Guest data transparency page — guests can see exactly what the system holds
- PMS webhook endpoint — receives a new reservation, creates a guest/stay, returns a welcome link ready to send
- ElevenLabs post-call webhook — receives conversation transcripts automatically when a call ends (requires public URL)
- Staff auth gate on manager dashboard
- FastAPI with auto-docs at `/docs`

---

## What's partial or stubbed

**Cross-property memory** — The manager dashboard shows past-stay timelines, but the data is hardcoded in the frontend for the demo guests. The backend data model fully supports it; it's not yet dynamically fetched.

**Flight tracking** — The AviationStack integration is wired into `flight_node`. If a stay has a flight number and an API key is configured, it returns live status. Without a key, it falls back to a mock result.

**ElevenLabs post-call webhook** — The backend endpoint exists and works, but ElevenLabs needs a publicly accessible URL to call it. For local development, this requires ngrok or a tunnel. The frontend-side transcript processing (which doesn't need a public URL) is the active fallback.

**Briefing audio** — There is a `GET /arrivals/plan/{stay_id}/audio` endpoint that pipes the dossier through ElevenLabs TTS into an MP3. It's not exposed in the UI yet.

**Identity resolution** — The `identity.py` module runs fuzzy matching to find the same guest across properties. The algorithm exists; there's no UI to trigger or review it.

**Conditional routing** — The LangGraph graph currently uses fixed edges. The framework is ready for conditional branches (e.g. skip wellness node if no opt-in, enrich the synthesizer for Living Memory guests), but those conditions aren't wired yet.

## What's not built

- Production deployment / hosting
- Real PMS integration (a fake PMS client exists for testing)
- Staff mobile push notifications
- Automated PlaceMaker availability or booking
- Multi-property backend sync (all data currently lives in one instance)
- Any real authentication beyond the demo password

---

## Future directions

**Departure and post-stay continuity.** The current system focuses on arrival and in-stay. Post-stay relationship continuity — a checkout note referencing something specific from the stay, an email timed for when the guest is likely planning their next trip, a cross-property suggestion tied to a life event they mentioned — is the third problem space from the brief and is largely unaddressed.

**Family and group memory.** The data model currently treats each guest as an individual. Couples and families are the bulk of luxury travel — adding family-member nodes tied to a primary profile (Anna's husband doesn't drink, their daughter loves marine biology) would let the system serve a whole trip, not just one person.

**Real wellness signal integration.** The wellness node currently runs on mock data. Whoop, Oura, and Apple Watch HRV are technically tractable opt-in integrations that would make this node genuinely useful — "the system noticed your HRV is suppressed post-flight and suggested a lighter first evening" is the kind of moment that sticks with a judge or a guest.

**Conditional pipeline routing.** The LangGraph graph currently has fixed edges. The next step is meaningful branching — a Living Memory guest gets a richer synthesizer prompt that weaves in cross-property patterns; a Standard guest gets a clean, current-stay-only plan. The framework supports this; the conditions just need to be wired.

**PlaceMaker availability and booking.** Right now the system recommends a PlaceMaker and suggests an offering, but there's no connection to actual scheduling. Closing that loop — the system proposes, staff confirms, guest receives a calendar hold — is the last mile between a recommendation and a moment.

---

## Concept

The best hospitality happens when staff seem to already know you — not because they memorized a file, but because someone thoughtful passed along the right detail at the right moment. Living Memory is what makes that possible at scale. It listens to staff observations during a stay, connects them to what the guest shared before they arrived, and quietly surfaces the one or two things that matter most to the team preparing for their return. The AI does the connective tissue work; the humans do the delivery. The guest never knows a system was involved — they just feel genuinely anticipated.
