# Living Memory

An invisible AI nervous system for luxury hotels. AI orchestrates; humans deliver.

## Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+
- API keys: Anthropic, ElevenLabs, AviationStack

### Setup

```bash
# Clone and enter repo
git clone <repo-url> && cd living-memory

# Copy env
cp .env.example .env
# Fill in your API keys in .env

# Backend
cd backend
pip install -e ".[dev]"
uvicorn src.api:app --reload --port 8000

# Frontend (new terminal)
cd frontend
npm install
npm run dev
```

### Demo flow
```bash
# Generate synthetic data
cd backend && python ../scripts/generate_synthetic_data.py

# Run the full 90-second demo scenario
python ../scripts/run_demo_scenario.py
```

### Views
- `http://localhost:3000/welcome` — Guest welcome conversation (Anna's landing page)
- `http://localhost:3000/manager` — Morning manager dashboard
- `http://localhost:3000/concierge` — Live concierge tablet view

### API
- `http://localhost:8000/docs` — FastAPI auto-docs

## Architecture

```
Guest signal (flight, voice call, staff obs)
        ↓
LangGraph orchestrator
  ├── flight_agent    → AviationStack
  ├── history_agent   → guest graph
  ├── place_agent     → PlaceMaker inventory
  ├── wellness_agent  → mock wearable signals
  └── synthesizer     → composes arrival plan
        ↓
friend_filter (Claude) — the creepy-line filter
        ↓
Staff briefing / dossier (manager dashboard, concierge view)
        ↓
Human staff delivers the moment
```

AI never faces the guest directly. Every output is a staff output.
