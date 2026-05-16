# Living Memory — Project Specification

## What we're building
Living Memory is an invisible AI nervous system for luxury hotels, built for the Rosewood Hospitality Hackathon. It captures ephemeral staff observations during a stay, synthesizes them with pre-arrival signals against a property's hyper-local cultural inventory, and surfaces hand-delivered moments back through human staff. The guest never sees a screen.

## The core design principle (DO NOT VIOLATE)
**AI never directly faces the guest.** Every AI output is a *staff* output (briefings, prompts, dossiers, voice notes to managers). The only exception is the consensual Welcome Voice Ambassador (a pre-arrival opt-in call). All other outputs route through human staff for delivery.

Before any insight reaches a staff member, it passes the "friend test": *Would a close friend who knew this guest well say this naturally?* This is a Claude system prompt that filters/rephrases insights.

## Target demo (90 seconds, end-to-end)
1. **Setup**: Synthetic guest "Anna Lindqvist" books Rosewood Schloss Fuschl, Austria.
2. **Welcome conversation**: Anna receives booking confirmation, clicks "Have a moment with us?", has a 60-second voice conversation with the Rosewood Ambassador. Transcript flows into her guest graph.
3. **Arrival orchestration**: Multi-agent system pulls her flight, past stays, welcome-call transcript, property inventory, cultural calendar. Produces "First 24 Hours" plan.
4. **Staff briefing**: Morning manager sees Anna's arrival dossier — warm, human-readable, friend-tested. 3-4 "moments to create today."
5. **Live observation capture**: Waiter speaks: "Anna at table 6 just asked about mountain hikes for tomorrow." Voice transcribes, Claude parses, guest graph updates, concierge view auto-refreshes.
6. **Cross-property magic**: Anna books Hôtel de Crillon three months later. Paris property's pre-arrival dossier already references her hiking interest, Tokyo connection, and wine she loved at Schloss Fuschl.

## Tech stack (locked)
- **Backend**: Python 3.11+, FastAPI, uvicorn
- **Multi-agent orchestration**: LangGraph
- **LLM**: Anthropic Claude (Sonnet 4 for orchestration, Haiku for high-volume parsing)
- **Voice**: ElevenLabs — Conversational AI, TTS, STT
- **Graph storage**: In-memory dict + JSON persistence
- **Flight data**: AviationStack free tier
- **Frontend**: Next.js 14 (App Router) + Tailwind + shadcn/ui

## Environment variables
- `ANTHROPIC_API_KEY`
- `ELEVENLABS_API_KEY`
- `AVIATIONSTACK_API_KEY`
