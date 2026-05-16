"use client"

import { useEffect, useState, ReactNode } from "react"

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"

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
  id: string
  name: string
  nationality: string
  home_city: string
  consent_level: string
}

interface Stay {
  id: string
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

// Cross-property memory — hardcoded for demo
const CROSS_PROPERTY_MEMORY: Record<string, Array<{ property: string; dates: string; note: string }>> = {
  "guest-anna-lindqvist": [
    { property: "Rosewood Hong Kong", dates: "Mar 2023", note: "Art Basel HK — quiet breakfast preference noted, natural wine interest emerged." },
    { property: "The Carlyle, New York", dates: "Sep 2023", note: "Architecture conference at MoMA — early morning runs in Central Park, room at 67°F." },
  ],
  "guest-marcus-chen": [
    { property: "Rosewood Hong Kong", dates: "May 2023", note: "Investor meetings — deep interest in contemporary art, Burgundy pairing with sommelier." },
    { property: "Hôtel de Crillon, Paris", dates: "Oct 2024", note: "10th anniversary with wife Sophie — requested spontaneous atmosphere, natural wine." },
  ],
  "guest-elena-vasquez": [
    { property: "Hôtel de Crillon, Paris", dates: "Sep 2023", note: "Annual Paris visit — bookshop recommendations, gallery dinner in Marais, quiet table always." },
    { property: "The Carlyle, New York", dates: "May 2024", note: "Frieze New York — foundation acquisitions, meeting with Madrid gallerist, corner table." },
  ],
}

function ConsentBadge({ level }: { level: string }) {
  const colors: Record<string, string> = {
    standard: "bg-stone-100 text-stone-500",
    remembered: "bg-blue-50 text-blue-500",
    living_memory: "bg-rosewood-50 text-rosewood-600",
  }
  const labels: Record<string, string> = {
    standard: "Standard",
    living_memory: "Living Memory",
  }
  return (
    <span className={`text-xs font-sans px-2 py-0.5 rounded-full ${colors[level] || "bg-stone-100 text-stone-400"}`}>
      {labels[level] || level}
    </span>
  )
}

function CrossPropertyMemory({ guestId, consentLevel }: { guestId: string; consentLevel: string }) {
  const pastStays = CROSS_PROPERTY_MEMORY[guestId]

  if (consentLevel !== "living_memory" || !pastStays || pastStays.length === 0) return null

  return (
    <div className="mt-6 pt-6 border-t border-stone-100">
      <p className="text-xs uppercase tracking-widest text-stone-400 mb-4">Memory from other properties</p>
      <div className="space-y-4">
        {pastStays.map((stay, i) => (
          <div key={i} className="flex gap-4">
            <div className="flex flex-col items-center">
              <div className="w-2 h-2 rounded-full bg-rosewood-300 mt-1 shrink-0" />
              {i < pastStays.length - 1 && <div className="w-px flex-1 bg-stone-100 mt-1" />}
            </div>
            <div className="pb-4">
              <p className="text-xs text-stone-400 mb-0.5">{stay.dates}</p>
              <p className="text-sm font-medium text-stone-700">{stay.property}</p>
              <p className="text-sm text-stone-500 mt-0.5 leading-relaxed">{stay.note}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

function DossierView({ plan, guestId, consentLevel }: { plan: Plan; guestId: string; consentLevel: string }) {
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

      {/* Feature 7: Cross-property memory */}
      <CrossPropertyMemory guestId={guestId} consentLevel={consentLevel} />
    </div>
  )
}

// Feature 5: Welcome link panel in ArrivalCard
function WelcomeLinkPanel({ stayId }: { stayId: string }) {
  const [open, setOpen] = useState(false)
  const [smsSent, setSmsSent] = useState(false)
  const welcomeUrl = `http://localhost:3000/welcome?stay_id=${stayId}`

  async function copyLink() {
    await navigator.clipboard.writeText(welcomeUrl)
  }

  function sendSms() {
    // Demo: simulated SMS send
    setSmsSent(true)
    setTimeout(() => setSmsSent(false), 3000)
  }

  return (
    <div className="mt-3">
      <button
        onClick={() => setOpen((o) => !o)}
        className="text-sm text-rosewood-600 hover:text-rosewood-700 underline transition-colors"
      >
        {open ? "Hide welcome link" : "Send Welcome Link →"}
      </button>

      {open && (
        <div className="mt-3 bg-stone-50 rounded-lg border border-stone-100 p-4 space-y-3">
          <p className="text-xs uppercase tracking-widest text-stone-400">Welcome Link</p>
          <div className="flex items-center gap-2">
            <code className="flex-1 text-xs bg-white border border-stone-200 rounded px-3 py-2 text-stone-600 truncate">
              {welcomeUrl}
            </code>
            <button
              onClick={copyLink}
              className="shrink-0 px-3 py-2 text-xs rounded bg-stone-200 text-stone-700 hover:bg-stone-300 transition-colors"
            >
              Copy
            </button>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={sendSms}
              className="px-4 py-2 text-xs rounded-lg bg-stone-800 text-white hover:bg-stone-900 transition-colors"
            >
              Send SMS
            </button>
            {smsSent && (
              <span className="text-xs text-green-600 font-medium">Link sent to +1-415-555-0192</span>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

function ArrivalCard({ arrival }: { arrival: Arrival }) {
  const [expanded, setExpanded] = useState(false)
  const [generating, setGenerating] = useState(false)
  const [plan, setPlan] = useState<Plan | null>(arrival.plan)
  const [planError, setPlanError] = useState<string | null>(null)
  const { guest, stay } = arrival

  async function generatePlan() {
    setGenerating(true)
    setPlanError(null)
    try {
      const res = await fetch(`${API}/arrivals/generate-plan`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          guest_id: guest?.id || "guest-anna-lindqvist",
          stay_id: stay.id || "stay-anna-sandhill-2026",
          welcome_transcript: null,
        }),
      })
      if (res.ok) {
        const data = await res.json()
        setPlan(data)
        setExpanded(true)
      } else {
        const err = await res.json().catch(() => ({ detail: "Unknown error" }))
        setPlanError(err.detail || `Server error ${res.status}`)
      }
    } catch (e) {
      setPlanError("Cannot reach the backend — make sure the server is running on port 8000.")
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
            {/* Feature 5: Send Welcome Link */}
            <WelcomeLinkPanel stayId={stay.id} />
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
          <div className="mt-2 space-y-2">
            <button
              onClick={generatePlan}
              disabled={generating}
              className="w-full py-3 px-4 rounded-lg bg-rosewood-600 text-white text-sm font-medium hover:bg-rosewood-700 disabled:opacity-50 transition-colors"
            >
              {generating ? "Generating arrival plan..." : "Generate Arrival Plan"}
            </button>
            {planError && (
              <p className="text-xs text-red-500 bg-red-50 rounded-lg px-3 py-2">{planError}</p>
            )}
          </div>
        ) : (
          <div className="mt-2">
            {expanded ? (
              <DossierView
                plan={plan}
                guestId={guest?.id || ""}
                consentLevel={guest?.consent_level || "standard"}
              />
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

// Feature 4: Staff auth gate
function StaffAuth({ children }: { children: ReactNode }) {
  const [authed, setAuthed] = useState(false)
  const [password, setPassword] = useState("")
  const [error, setError] = useState(false)

  useEffect(() => {
    if (sessionStorage.getItem("staff_authed") === "true") {
      setAuthed(true)
    }
  }, [])

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (password === "sandhill2026") {
      sessionStorage.setItem("staff_authed", "true")
      setAuthed(true)
      setError(false)
    } else {
      setError(true)
    }
  }

  if (authed) return <>{children}</>

  return (
    <div className="min-h-screen bg-stone-100 flex items-center justify-center px-6">
      <div className="bg-white rounded-2xl border border-stone-200 shadow-sm px-10 py-10 max-w-sm w-full text-center space-y-6">
        <div>
          <p className="text-xs uppercase tracking-widest text-stone-400 mb-1">Rosewood Sand Hill</p>
          <h1 className="font-serif text-xl text-stone-900">Staff Access</h1>
        </div>
        <form onSubmit={handleSubmit} className="space-y-4">
          <input
            type="password"
            value={password}
            onChange={(e) => { setPassword(e.target.value); setError(false) }}
            placeholder="Enter staff password"
            className="w-full rounded-lg border border-stone-200 px-4 py-3 text-sm text-stone-700 focus:outline-none focus:border-stone-400 text-center"
            autoFocus
          />
          {error && (
            <p className="text-xs text-red-500">Incorrect — please try again.</p>
          )}
          <button
            type="submit"
            className="w-full py-3 rounded-lg bg-stone-800 text-white text-sm font-medium hover:bg-stone-900 transition-colors"
          >
            Enter
          </button>
        </form>
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
        id: "guest-anna-lindqvist",
        name: "Anna Lindqvist",
        nationality: "Swedish",
        home_city: "San Francisco",
        consent_level: "living_memory",
      },
      stay: {
        id: "stay-anna-sandhill-2026",
        check_in: new Date().toISOString().split("T")[0],
        check_out: null,
        room_type: "Garden Bungalow",
        flight_number: "LH454",
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
    <StaffAuth>
      <div className="min-h-screen bg-stone-50">
        {/* Header */}
        <header className="border-b border-stone-200 bg-white px-8 py-5">
          <div className="max-w-4xl mx-auto flex items-center justify-between">
            <div>
              <p className="text-xs font-sans uppercase tracking-widest text-stone-400 mb-0.5">Rosewood Sand Hill</p>
              <h1 className="font-serif text-2xl text-stone-900">Morning Arrivals</h1>
              <p className="text-sm text-stone-500 max-w-md">The morning briefing for the front-of-house manager. View today's guests and generate AI-tailored arrival dossiers.</p>
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
            <div className="text-center py-20 text-stone-400 font-serif">Loading today&apos;s arrivals...</div>
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
    </StaffAuth>
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
