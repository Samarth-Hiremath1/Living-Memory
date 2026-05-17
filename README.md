# Living Memory

*AI for the staff. Magic for the guest.*

A luxury hotel has thousands of small moments every day where it could get something exactly right — the fireplace already lit, the wine they mentioned, a note from the chef about tomorrow's farm lunch. Most of those moments never happen because no one connected the dots in time. Living Memory is an attempt to connect those dots automatically, and route them back through human hands.

The guest never sees a screen. The AI never talks to a guest directly (except for one opt-in pre-arrival voice call). Everything the system learns surfaces as a warm, human-readable staff briefing — never a robotic list of data points, never a clinical readout. A Claude "friend filter" rewrites every AI output to sound like it came from a well-informed colleague, not a system.

---

## How it works

**Before arrival:** When a reservation is created, the guest receives a welcome link. They can have a short voice conversation with the Rosewood Ambassador (an ElevenLabs conversational AI), or fill out an optional form — or neither. Whatever they share is stored in their profile.

**The morning briefing:** The manager dashboard runs a multi-agent pipeline for each arriving guest: it pulls flight status, reads past-stay observations, matches the guest's interests against the property's PlaceMakers and local inventory, and synthesizes everything into a "First 24 Hours" plan. The plan includes room temperature, welcome amenity, 3–4 moments to create, and a placemaker introduction.

**During the stay:** Staff capture observations by voice or text on the concierge tablet ("She mentioned wanting to photograph the valley at golden hour"). Claude parses the note, extracts action items, and the concierge view updates in real time — no forms, no tickets.

**Across properties:** Guests who opt into "Living Memory" carry their preferences across every Rosewood property worldwide. The Paris property's pre-arrival briefing already knows what they ordered in Hong Kong.

---

## Architecture

```
Guest signal (welcome call, form, staff note, flight)
        ↓
In-memory graph store (Guest → Stay → Observations → ArrivalPlan)
        ↓
Orchestrator — sequential multi-agent pipeline
  ├── flight_agent     checks flight status and estimated arrival
  ├── history_agent    reads past-stay observations and preferences
  ├── place_agent      matches guest interests to PlaceMaker offerings
  ├── wellness_agent   reads signals like jet lag, pace, occasion
  └── synthesizer      composes the full arrival plan (Claude Sonnet)
        ↓
Friend Filter (Claude Haiku) — rewrites clinical output to warm, human language
        ↓
Staff briefing / dossier (manager dashboard, concierge tablet)
        ↓
Human staff delivers the moment
```

**Two frontends:**
- **Guest-facing:** Welcome page (voice + form), data transparency page, consent management
- **Staff-facing:** Manager dashboard (today's arrivals, plan generation, dossier), concierge tablet (in-house guests, live observation capture)

**Data layer:** In-memory Python dict with JSON persistence. Schema is Neo4j-compatible for a production migration. Consent model has two levels: Standard (this stay only) and Living Memory (cross-property, persistent).

---

## What's implemented

- Full guest/stay/observation/plan data model with JSON persistence
- Multi-agent orchestration pipeline (flight → history → place → wellness → synthesizer)
- Arrival plan generation with Claude Sonnet producing a full staff dossier
- Friend Filter — tone translation from clinical AI output to warm, readable language
- Staff observation capture via text and browser speech recognition (Web Speech API)
- Welcome page with ElevenLabs voice conversation + optional survey form as fallback
- Welcome transcript processing — Claude extracts structured preferences and merges them into the guest's profile
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

**Flight tracking** — The AviationStack integration is wired in. If a stay has a flight number and an API key is configured, it returns live status. Without a key, it returns a mock.

**ElevenLabs post-call webhook** — The backend endpoint exists and works, but ElevenLabs needs a publicly accessible URL to call it. For local development, this requires ngrok or a tunnel. The frontend-side transcript processing (which doesn't need a public URL) is the active fallback.

**Briefing audio** — There is a `GET /arrivals/plan/{stay_id}/audio` endpoint that pipes the dossier through ElevenLabs TTS into an MP3. It's not exposed in the UI yet.

**Demo scripts** — `scripts/generate_synthetic_data.py` and `scripts/run_demo_scenario.py` are referenced in the original spec but were not built out during the hackathon. The synthetic data in `data/synthetic/guests.json` is pre-populated manually.

**Identity resolution** — The `identity.py` module runs fuzzy matching to find the same guest across properties. The algorithm exists; there's no UI to trigger or review it.

**SMS/email delivery** — The PMS webhook returns a welcome link, but sending it to the guest (SMS, email) is a commented TODO.

---

## What's not built

- Production deployment / hosting
- Real PMS integration (a fake PMS client exists for testing)
- Staff mobile push notifications
- Automated placemaker availability or booking
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

**Demo tip:** The manager dashboard falls back to demo data (Samarth Hiremath, arriving today) if the backend is unreachable. Guests whose arrival plans have already been generated show "View dossier →"; guests without a plan show the "Generate Arrival Plan" button — clicking it runs the full agent pipeline live.

---

## Concept

The best hospitality happens when staff seem to already know you — not because they memorized a file, but because someone thoughtful passed along the right detail at the right moment. Living Memory is what makes that possible at scale. It listens to staff observations during a stay, connects them to what the guest shared before they arrived, and quietly surfaces the one or two things that matter most to the team preparing for their return. The AI does the connective tissue work; the humans do the delivery. The guest never knows a system was involved — they just feel genuinely anticipated.
