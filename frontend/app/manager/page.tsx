"use client"

import { useEffect, useState } from "react"

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"

interface Moment {
  text: string
}

interface Plan {
  room_temperature_f: number
  welcome_amenity: string
  moments_to_create: string[]
  placemaker_intro: string | null
  jet_lag_note: string | null
  raw_dossier: string
  flight_status: string | null
}

interface Guest {
  name: string
  nationality: string
  home_city: string
  consent_level: string
}

interface Stay {
  check_in: string
  check_out: string | null
  room_type: string | null
  flight_number: string | null
  occasions: string[]
}

interface Arrival {
  guest: Guest | null
  stay: Stay
  plan: Plan | null
}

function ConsentBadge({ level }: { level: string }) {
  const colors: Record<string, string> = {
    standard: "bg-stone-100 text-stone-500",
    remembered: "bg-blue-50 text-blue-500",
    living_memory: "bg-rosewood-50 text-rosewood-600",
  }
  const labels: Record<string, string> = {
    standard: "Standard",
    remembered: "Remembered",
    living_memory: "Living Memory",
  }
  return (
    <span className={`text-xs font-sans px-2 py-0.5 rounded-full ${colors[level] || "bg-stone-100 text-stone-400"}`}>
      {labels[level] || level}
    </span>
  )
}

function DossierView({ plan }: { plan: Plan }) {
  const [showRaw, setShowRaw] = useState(false)
  return (
    <div className="space-y-6">
      {/* Room setup */}
      <div className="flex gap-4 text-sm">
        <div className="bg-stone-50 rounded-lg px-4 py-3 flex-1">
          <p className="text-xs uppercase tracking-widest text-stone-400 mb-1">Room Temperature</p>
          <p className="font-semibold text-stone-800">{plan.room_temperature_f}°F</p>
        </div>
        {plan.welcome_amenity && (
          <div className="bg-stone-50 rounded-lg px-4 py-3 flex-1">
            <p className="text-xs uppercase tracking-widest text-stone-400 mb-1">Welcome Amenity</p>
            <p className="font-semibold text-stone-800">{plan.welcome_amenity}</p>
          </div>
        )}
      </div>

      {/* Moments to create */}
      {plan.moments_to_create.length > 0 && (
        <div>
          <p className="text-xs uppercase tracking-widest text-stone-400 mb-3">Moments to Create Today</p>
          <ul className="space-y-2">
            {plan.moments_to_create.map((m, i) => (
              <li key={i} className="flex gap-3 text-sm text-stone-700">
                <span className="text-rosewood-400 mt-0.5">—</span>
                <span>{m}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* PlaceMaker */}
      {plan.placemaker_intro && (
        <div className="border-l-2 border-rosewood-200 pl-4 py-1">
          <p className="text-xs uppercase tracking-widest text-stone-400 mb-1">PlaceMaker Introduction</p>
          <p className="text-sm text-stone-700 font-serif italic">{plan.placemaker_intro}</p>
        </div>
      )}

      {/* Jet lag note */}
      {plan.jet_lag_note && (
        <div className="bg-amber-50 rounded-lg px-4 py-3 text-sm text-amber-800">
          <span className="font-semibold">Keep in mind: </span>{plan.jet_lag_note}
        </div>
      )}

      {/* Full dossier toggle */}
      {plan.raw_dossier && (
        <div>
          <button
            onClick={() => setShowRaw(!showRaw)}
            className="text-xs text-stone-400 hover:text-stone-600 underline"
          >
            {showRaw ? "Hide" : "Show"} full dossier
          </button>
          {showRaw && (
            <div className="mt-4 dossier-prose whitespace-pre-wrap text-sm leading-relaxed bg-white border border-stone-100 rounded-lg p-6">
              {plan.raw_dossier}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function ArrivalCard({ arrival }: { arrival: Arrival }) {
  const [expanded, setExpanded] = useState(false)
  const [generating, setGenerating] = useState(false)
  const [plan, setPlan] = useState<Plan | null>(arrival.plan)
  const { guest, stay } = arrival

  async function generatePlan() {
    setGenerating(true)
    try {
      const res = await fetch(`${API}/arrivals/generate-plan`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          guest_id: guest ? "guest-anna-lindqvist" : "",
          stay_id: stay.check_in,
          welcome_transcript: null,
        }),
      })
      if (res.ok) {
        const data = await res.json()
        setPlan(data)
        setExpanded(true)
      }
    } finally {
      setGenerating(false)
    }
  }

  return (
    <div className="bg-white rounded-xl border border-stone-100 shadow-sm overflow-hidden">
      <div className="p-6">
        <div className="flex items-start justify-between mb-4">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <h2 className="font-serif text-xl text-stone-900">{guest?.name || "Unknown Guest"}</h2>
              {guest && <ConsentBadge level={guest.consent_level} />}
            </div>
            <p className="text-sm text-stone-400">
              {guest?.home_city && `${guest.home_city} · `}
              {guest?.nationality} · {stay.room_type || "Room TBD"}
            </p>
          </div>
          <div className="text-right text-sm text-stone-500">
            <p className="font-semibold text-stone-700">
              Check-in: {new Date(stay.check_in).toLocaleDateString("en-US", { month: "short", day: "numeric" })}
            </p>
            {stay.flight_number && (
              <p className="text-xs text-stone-400 mt-0.5">Flight: {stay.flight_number}</p>
            )}
            {stay.occasions.length > 0 && (
              <p className="text-xs text-rosewood-400 mt-0.5 capitalize">{stay.occasions.join(", ")}</p>
            )}
          </div>
        </div>

        {!plan ? (
          <button
            onClick={generatePlan}
            disabled={generating}
            className="w-full mt-2 py-3 px-4 rounded-lg bg-rosewood-600 text-white text-sm font-medium hover:bg-rosewood-700 disabled:opacity-50 transition-colors"
          >
            {generating ? "Generating arrival plan..." : "Generate Arrival Plan"}
          </button>
        ) : (
          <div>
            {expanded ? (
              <DossierView plan={plan} />
            ) : (
              <button
                onClick={() => setExpanded(true)}
                className="text-sm text-rosewood-600 hover:underline"
              >
                View dossier →
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

export default function ManagerPage() {
  const [arrivals, setArrivals] = useState<Arrival[]>([])
  const [loading, setLoading] = useState(true)
  const [today] = useState(new Date().toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric" }))

  // For demo: use demo arrivals if API returns empty
  const DEMO_ARRIVALS: Arrival[] = [
    {
      guest: {
        name: "Anna Lindqvist",
        nationality: "Swedish",
        home_city: "Tokyo",
        consent_level: "living_memory",
      },
      stay: {
        check_in: new Date().toISOString().split("T")[0],
        check_out: null,
        room_type: "Lake View Suite",
        flight_number: "JL43",
        occasions: [],
      },
      plan: null,
    },
  ]

  useEffect(() => {
    fetch(`${API}/arrivals/today`)
      .then((r) => r.json())
      .then((data) => {
        setArrivals(data.length > 0 ? data : DEMO_ARRIVALS)
      })
      .catch(() => setArrivals(DEMO_ARRIVALS))
      .finally(() => setLoading(false))
  }, [])

  return (
    <div className="min-h-screen bg-stone-50">
      {/* Header */}
      <header className="border-b border-stone-200 bg-white px-8 py-5">
        <div className="max-w-4xl mx-auto flex items-center justify-between">
          <div>
            <p className="text-xs font-sans uppercase tracking-widest text-stone-400 mb-0.5">Rosewood Schloss Fuschl</p>
            <h1 className="font-serif text-2xl text-stone-900">Morning Arrivals</h1>
          </div>
          <div className="text-right">
            <p className="text-sm text-stone-500">{today}</p>
            <p className="text-xs text-stone-400 mt-0.5">{arrivals.length} arriving today</p>
          </div>
        </div>
      </header>

      {/* Content */}
      <main className="max-w-4xl mx-auto px-8 py-8">
        {loading ? (
          <div className="text-center py-20 text-stone-400 font-serif">Loading today's arrivals...</div>
        ) : arrivals.length === 0 ? (
          <div className="text-center py-20 text-stone-400 font-serif">No arrivals today.</div>
        ) : (
          <div className="space-y-6">
            {arrivals.map((a, i) => (
              <ArrivalCard key={i} arrival={a} />
            ))}
          </div>
        )}

        {/* Demo: Friend filter section */}
        <div className="mt-12">
          <FriendFilterDemo />
        </div>
      </main>
    </div>
  )
}

function FriendFilterDemo() {
  const [raw, setRaw] = useState(
    "Based on 3 past stays, guest shows 87% preference for outdoor/nature activities and a 73% likelihood of requesting Grüner Veltliner based on beverage ordering patterns."
  )
  const [filtered, setFiltered] = useState("")
  const [loading, setLoading] = useState(false)

  async function runFilter() {
    setLoading(true)
    try {
      const res = await fetch(`${API}/demo/friend-filter`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ raw_insight: raw }),
      })
      const data = await res.json()
      setFiltered(data.filtered || "")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="bg-white rounded-xl border border-stone-100 p-6">
      <p className="text-xs uppercase tracking-widest text-stone-400 mb-4">Live Demo — Friend Filter</p>
      <div className="space-y-4">
        <div>
          <label className="text-xs text-stone-400 mb-1 block">Raw AI insight (clinical)</label>
          <textarea
            value={raw}
            onChange={(e) => setRaw(e.target.value)}
            rows={3}
            className="w-full rounded-lg border border-stone-200 px-3 py-2 text-sm text-stone-600 font-sans resize-none focus:outline-none focus:border-rosewood-300"
          />
        </div>
        <button
          onClick={runFilter}
          disabled={loading}
          className="py-2 px-4 rounded-lg bg-stone-800 text-white text-sm font-medium hover:bg-stone-900 disabled:opacity-50 transition-colors"
        >
          {loading ? "Running friend filter..." : "Run Friend Filter →"}
        </button>
        {filtered && (
          <div className="bg-stone-50 rounded-lg p-4">
            <label className="text-xs text-stone-400 mb-1 block">Filtered (warm, human)</label>
            <p className="text-sm text-stone-700 font-serif italic">{filtered}</p>
          </div>
        )}
      </div>
    </div>
  )
}
