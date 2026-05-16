"use client"

import { useEffect, useState, useRef, ReactNode, useCallback } from "react"

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"

interface Observation {
  id: string
  raw_text: string
  tags: string[]
  timestamp: string
  source: string
  sentiment?: string | null
}

interface ActionItem {
  text: string
  done: boolean
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
  room_type: string | null
}

interface InhouseGuest {
  guest: Guest | null
  stay: Stay
  recent_observations: Observation[]
  plan: Record<string, unknown> | null
}

// Full demo roster — all 5 current Sand Hill guests
const DEMO_GUESTS: InhouseGuest[] = [
  {
    guest: {
      id: "guest-samarth-hiremath",
      name: "Samarth Hiremath",
      nationality: "Indian-American",
      home_city: "San Francisco",
      consent_level: "living_memory",
    },
    stay: {
      id: "stay-samarth-sandhill-2026",
      check_in: new Date().toISOString().split("T")[0],
      room_type: "Garden Bungalow",
    },
    recent_observations: [
      {
        id: "obs-samarth-1",
        raw_text: "Samarth asked about the best hiking trails nearby — specifically looking for routes with good viewpoints over the valley. Mentioned he runs trails in Marin on weekends.",
        tags: ["hiking", "trails", "viewpoints", "marin", "active"],
        timestamp: new Date(Date.now() - 3 * 60 * 60 * 1000).toISOString(),
        source: "staff_text",
        sentiment: "positive",
      },
      {
        id: "obs-samarth-2",
        raw_text: "Guest asked if we could arrange an early morning trail run before breakfast. Also curious about photography spots at sunrise on the property.",
        tags: ["trail run", "photography", "sunrise", "morning"],
        timestamp: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(),
        source: "staff_text",
        sentiment: "positive",
      },
      {
        id: "obs-samarth-3",
        raw_text: "Samarth asked whether Madera does South Asian-inspired dishes or seasonal specials. Said he cooks Indian food at home and appreciated that Reylon sources locally.",
        tags: ["food", "indian cuisine", "madera", "culinary interest"],
        timestamp: new Date(Date.now() - 60 * 60 * 1000).toISOString(),
        source: "staff_text",
        sentiment: "positive",
      },
    ],
    plan: {
      moments_to_create: [
        "Map out a 5–6 mile trail loop with valley viewpoints — Natalie knows the best routes for early risers",
        "Identify the best sunrise photography vantage point on the property and leave a handwritten note",
        "Ask Reylon if he can suggest a farm-to-table dish with spice — note Samarth's love of bold flavors",
        "Set up early 6am breakfast option for the terrace on trail-run mornings",
      ],
    },
  },
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
      room_type: "Garden Bungalow",
    },
    recent_observations: [
      {
        id: "obs-demo-anna-1",
        raw_text: "Anna arrived looking a bit tired after the long-haul from Frankfurt. Mentioned she's looking forward to the oak grove walk and natural wine at Madera.",
        tags: ["arrival", "tired", "oak grove", "natural wine"],
        timestamp: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(),
        source: "staff_text",
        sentiment: "neutral",
      },
    ],
    plan: {
      moments_to_create: [
        "Reserve the oak grove trail for a sunset walk — Natalie Cheng can guide",
        "Ask David Park to select a natural Loire wine for room arrival",
        "Keep the check-in seamless and unhurried — she's jet-lagged from Frankfurt",
      ],
    },
  },
  {
    guest: {
      id: "guest-marcus-chen",
      name: "Marcus Chen",
      nationality: "Singaporean",
      home_city: "Singapore",
      consent_level: "living_memory",
    },
    stay: {
      id: "stay-marcus-sandhill-2026",
      check_in: new Date().toISOString().split("T")[0],
      room_type: "Poolside Cabana",
    },
    recent_observations: [
      {
        id: "obs-demo-marcus-1",
        raw_text: "Marcus asked about contemporary art on display in the lobby and whether we could arrange a private gallery viewing in Palo Alto.",
        tags: ["art", "contemporary", "gallery", "palo alto"],
        timestamp: new Date(Date.now() - 45 * 60 * 1000).toISOString(),
        source: "staff_text",
        sentiment: "positive",
      },
      {
        id: "obs-demo-marcus-2",
        raw_text: "Guest expressed interest in the property's architecture and landscape design — asked about the design firm behind the bungalows.",
        tags: ["architecture", "landscape design", "property"],
        timestamp: new Date(Date.now() - 30 * 60 * 1000).toISOString(),
        source: "staff_text",
        sentiment: "positive",
      },
    ],
    plan: {
      moments_to_create: [
        "Look into gallery contacts in Palo Alto for a private contemporary art viewing",
        "Share property design history — Marcus appreciates architecture and landscape craft",
        "Note: celebrates quietly — no fanfare unless he asks",
      ],
    },
  },
  {
    guest: {
      id: "guest-elena-vasquez",
      name: "Elena Vasquez",
      nationality: "Spanish",
      home_city: "Madrid",
      consent_level: "living_memory",
    },
    stay: {
      id: "stay-elena-sandhill-2026",
      check_in: new Date().toISOString().split("T")[0],
      room_type: "Executive Suite",
    },
    recent_observations: [
      {
        id: "obs-demo-elena-1",
        raw_text: "Elena requested a quiet corner table for all Madera dinners. She's here on a writing retreat and needs uninterrupted mornings.",
        tags: ["quiet", "writing retreat", "madera", "do not disturb"],
        timestamp: new Date(Date.now() - 3 * 60 * 60 * 1000).toISOString(),
        source: "staff_text",
        sentiment: "neutral",
      },
      {
        id: "obs-demo-elena-2",
        raw_text: "Guest asked for bookshop recommendations in Palo Alto or Menlo Park — specifically looking for a good independent store with a strong literary fiction section.",
        tags: ["bookshop", "reading", "literary fiction", "local"],
        timestamp: new Date(Date.now() - 90 * 60 * 1000).toISOString(),
        source: "staff_text",
        sentiment: "positive",
      },
    ],
    plan: {
      moments_to_create: [
        "Hold all housekeeping until after noon — writing retreat, mornings are sacred",
        "Ask Reylon Agustin to recommend a quiet tasting menu for her last evening",
        "Leave a curated set of local literary recommendations in the suite",
      ],
    },
  },
  {
    guest: {
      id: "guest-harrison-family",
      name: "The Harrison Family",
      nationality: "American",
      home_city: "New York",
      consent_level: "living_memory",
    },
    stay: {
      id: "stay-harrison-sandhill-2026",
      check_in: new Date().toISOString().split("T")[0],
      room_type: "Two-Bedroom Family Suite",
    },
    recent_observations: [
      {
        id: "obs-demo-harrison-1",
        raw_text: "Two kids (ages 8 and 11). Parents asked about family-friendly trails and the pool. One child has a nut allergy — flagged with dining team.",
        tags: ["family", "kids", "pool", "trails", "nut allergy"],
        timestamp: new Date(Date.now() - 90 * 60 * 1000).toISOString(),
        source: "staff_text",
        sentiment: "positive",
      },
      {
        id: "obs-demo-harrison-2",
        raw_text: "Both children are interested in the outdoor activities — parents asked about hiking options suitable for an 8-year-old and whether there are any ranger-led programs nearby.",
        tags: ["hiking", "kids activities", "ranger", "outdoor"],
        timestamp: new Date(Date.now() - 60 * 60 * 1000).toISOString(),
        source: "staff_text",
        sentiment: "positive",
      },
    ],
    plan: {
      moments_to_create: [
        "Nut allergy active — all F&B staff alerted, Reylon has an allergy-safe menu ready",
        "Book the family trail walk for tomorrow morning — Natalie can lead",
        "Set up a welcome basket with age-appropriate activities for the kids",
      ],
    },
  },
  {
    guest: {
      id: "guest-samarth-hiremath",
      name: "Samarth Hiremath",
      nationality: "American",
      home_city: "San Francisco",
      consent_level: "living_memory",
    },
    stay: {
      id: "stay-samarth-sandhill-2026",
      check_in: new Date().toISOString().split("T")[0],
      room_type: "Garden Bungalow",
    },
    recent_observations: [
      {
        id: "obs-samarth-1",
        raw_text: "Samarth asked about the best hiking trails nearby — specifically looking for routes with good viewpoints over the valley. Mentioned he runs trails in Marin on weekends.",
        tags: ["hiking", "trails", "viewpoints", "marin", "active"],
        timestamp: new Date(new Date().setHours(10, 0, 0, 0)).toISOString(),
        source: "staff_text",
        sentiment: "positive",
      },
      {
        id: "obs-samarth-2",
        raw_text: "Guest asked if we could arrange an early morning trail run before breakfast. Also curious about photography spots at sunrise on the property.",
        tags: ["trail run", "photography", "sunrise", "active", "morning"],
        timestamp: new Date(new Date().setHours(11, 0, 0, 0)).toISOString(),
        source: "staff_text",
        sentiment: "positive",
      },
    ],
    plan: {
      moments_to_create: [
        "Map out a 5-6 mile loop with valley viewpoints — Natalie Cheng knows the best routes",
        "Identify sunrise photography spots on the property and share with Samarth",
        "Arrange an early 6am breakfast option for morning trail run days",
      ],
    },
  },
]

const SAMARTH_DEFAULT_ACTION_ITEMS: ActionItem[] = [
  { text: "[Concierge] Map out 5–6 mile trail loop with valley viewpoints for early morning run", done: false },
  { text: "[Concierge] Identify best sunrise photography spot — leave handwritten note in bungalow", done: false },
  { text: "[F&B] Ask Reylon about bold-flavor dish for Samarth — loves spice, curious about Indian-inspired California food", done: false },
]

function SentimentDot({ sentiment }: { sentiment?: string | null }) {
  const colors: Record<string, string> = {
    positive: "bg-green-400",
    neutral: "bg-stone-300",
    negative: "bg-red-400",
    concerned: "bg-amber-400",
  }
  const color = colors[sentiment ?? "neutral"] ?? "bg-stone-300"
  return <span className={`inline-block w-2 h-2 rounded-full ${color} shrink-0 mt-1.5`} />
}

function SourceLabel({ source }: { source: string }) {
  const labels: Record<string, string> = {
    staff_voice: "Voice",
    staff_text: "Text",
    welcome_call: "Welcome Call",
    pms: "PMS",
    synthetic: "Historical",
  }
  return <span className="capitalize">{labels[source] ?? source.replace(/_/g, " ")}</span>
}

function ObservationFeed({ observations }: { observations: Observation[] }) {
  if (observations.length === 0) {
    return (
      <p className="text-xs text-stone-400 italic py-6 text-center">
        No observations yet this stay.<br />
        <span className="text-stone-300">Use the capture panel to add one.</span>
      </p>
    )
  }
  return (
    <div className="space-y-3">
      {observations.map((obs) => (
        <div key={obs.id} className="bg-white rounded-lg border border-stone-100 p-3">
          <div className="flex items-start gap-2 mb-1">
            <SentimentDot sentiment={obs.sentiment} />
            <p className="text-xs text-stone-400 flex-1">
              {new Date(obs.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
              {" · "}
              <SourceLabel source={obs.source} />
            </p>
          </div>
          <p className="text-sm text-stone-700 leading-relaxed pl-4">{obs.raw_text}</p>
          {obs.tags && obs.tags.length > 0 && (
            <div className="flex flex-wrap gap-1 mt-2 pl-4">
              {obs.tags.slice(0, 4).map((tag) => (
                <span key={tag} className="text-xs bg-stone-50 text-stone-400 px-2 py-0.5 rounded-full border border-stone-100">
                  {tag}
                </span>
              ))}
            </div>
          )}
        </div>
      ))}
    </div>
  )
}

function VoiceCapture({
  guestId,
  stayId,
  propertyId,
  onNewObservation,
}: {
  guestId: string
  stayId: string
  propertyId: string
  onNewObservation: (obs: Observation, actionItems?: string[]) => void
}) {
  const [recording, setRecording] = useState(false)
  const [transcript, setTranscript] = useState("")
  const [submitting, setSubmitting] = useState(false)
  const [textInput, setTextInput] = useState("")
  const [error, setError] = useState("")
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const recognitionRef = useRef<any>(null)

  const submitTextObservation = useCallback(async (text: string) => {
    if (!text.trim()) return
    setSubmitting(true)
    setError("")
    try {
      const res = await fetch(`${API}/observations`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          raw_text: text,
          stay_id: stayId,
          guest_id: guestId,
          property_id: propertyId,
        }),
      })
      if (!res.ok) throw new Error("API error")
      const data = await res.json()
      if (data.observation) {
        onNewObservation(data.observation, data.action_items || [])
      }
    } catch {
      setError("Could not save observation — check backend connection.")
    } finally {
      setSubmitting(false)
    }
  }, [guestId, stayId, propertyId, onNewObservation])

  function startRecording() {
    setError("")
    setTranscript("")
    // Use browser Web Speech API — real transcription, no backend needed
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const SR = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition
    if (!SR) {
      setError("Voice recognition not supported in this browser — use the text input below.")
      return
    }
    const recognition = new SR()
    recognition.continuous = false
    recognition.interimResults = false
    recognition.lang = "en-US"
    recognitionRef.current = recognition

    recognition.onresult = (event: { results: { [x: string]: { [x: string]: { transcript: string } } } }) => {
      const text = event.results[0][0].transcript
      setTranscript(text)
      setRecording(false)
      submitTextObservation(text)
    }
    recognition.onerror = () => {
      setError("Could not capture voice. Try the text input below.")
      setRecording(false)
    }
    recognition.onend = () => setRecording(false)
    recognition.start()
    setRecording(true)
  }

  function stopRecording() {
    recognitionRef.current?.stop()
    setRecording(false)
  }

  async function submitText() {
    if (!textInput.trim()) return
    await submitTextObservation(textInput.trim())
    setTextInput("")
    setTranscript("")
  }

  return (
    <div className="space-y-3">
      <button
        onMouseDown={startRecording}
        onMouseUp={stopRecording}
        onTouchStart={startRecording}
        onTouchEnd={stopRecording}
        disabled={submitting}
        className={`w-full py-4 rounded-xl text-sm font-medium transition-all select-none ${
          recording
            ? "bg-red-500 text-white shadow-lg scale-[0.98]"
            : "bg-stone-800 text-white hover:bg-stone-900"
        } disabled:opacity-40`}
      >
        {recording
          ? "● Listening — release when done"
          : submitting
          ? "Saving..."
          : "Hold to speak an observation"}
      </button>

      {transcript && (
        <p className="text-xs text-stone-500 italic bg-stone-50 rounded-lg px-3 py-2">
          Heard: &ldquo;{transcript}&rdquo;
        </p>
      )}

      {error && (
        <p className="text-xs text-red-400 bg-red-50 rounded-lg px-3 py-2">{error}</p>
      )}

      <div className="flex gap-2">
        <input
          value={textInput}
          onChange={(e) => setTextInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && submitText()}
          placeholder="Or type an observation and press Enter..."
          className="flex-1 rounded-lg border border-stone-200 px-3 py-2 text-sm focus:outline-none focus:border-stone-400"
        />
        <button
          onClick={submitText}
          disabled={submitting || !textInput.trim()}
          className="px-4 py-2 rounded-lg bg-stone-200 text-stone-700 text-sm hover:bg-stone-300 disabled:opacity-40 transition-colors"
        >
          Add
        </button>
      </div>

      <p className="text-xs text-stone-400">
        Voice uses your browser&apos;s built-in speech recognition. Observations are parsed by Claude instantly.
      </p>
    </div>
  )
}

function GuestPanel({ data }: { data: InhouseGuest }) {
  const [observations, setObservations] = useState<Observation[]>(data.recent_observations)
  const [actionItems, setActionItems] = useState<ActionItem[]>(
    data.guest?.id === "guest-samarth-hiremath" ? SAMARTH_DEFAULT_ACTION_ITEMS : []
  )
  const [newActionText, setNewActionText] = useState("")
  const moments = (data.plan?.moments_to_create as string[]) || []

  function addObservation(obs: Observation, newActionItems?: string[]) {
    if (obs) setObservations((prev) => [obs, ...prev])
    if (newActionItems && newActionItems.length > 0) {
      setActionItems((prev) => [
        ...prev,
        ...newActionItems.map((text) => ({ text, done: false })),
      ])
    }
  }

  function toggleActionItem(index: number) {
    setActionItems((prev) =>
      prev.map((item, i) => (i === index ? { ...item, done: !item.done } : item))
    )
  }

  function deleteActionItem(index: number) {
    setActionItems((prev) => prev.filter((_, i) => i !== index))
  }

  function addManualActionItem() {
    const text = newActionText.trim()
    if (!text) return
    setActionItems((prev) => [...prev, { text, done: false }])
    setNewActionText("")
  }

  return (
    <div className="grid grid-cols-5 gap-6">
      {/* Left: observation feed */}
      <div className="col-span-2 space-y-4">
        <div>
          <h3 className="text-xs uppercase tracking-widest text-stone-400">Observation Feed</h3>
          <p className="text-xs text-stone-300 mt-0.5">What staff has noticed this stay</p>
        </div>
        <ObservationFeed observations={observations} />
      </div>

      {/* Right: suggestions + action items + capture */}
      <div className="col-span-3 space-y-6">
        {moments.length > 0 && (
          <div>
            <h3 className="text-xs uppercase tracking-widest text-stone-400 mb-1">Live Suggestions</h3>
            <p className="text-xs text-stone-300 mb-3">
              AI-generated moments based on this guest&apos;s history and preferences
            </p>
            <div className="space-y-2">
              {moments.map((m, i) => (
                <div
                  key={i}
                  className="flex gap-3 bg-white rounded-lg border border-stone-100 px-4 py-3 text-sm text-stone-700"
                >
                  <span className="text-rosewood-400 shrink-0">—</span>
                  <span>{m}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Action Items */}
        <div>
          <h3 className="text-xs uppercase tracking-widest text-stone-400 mb-1">Action Items</h3>
          <p className="text-xs text-stone-300 mb-3">
            AI-generated from observations · check off when done · add or delete manually
          </p>
          {actionItems.length === 0 ? (
            <p className="text-xs text-stone-400 italic mb-3">No action items yet. They appear when observations are added — or add one below.</p>
          ) : (
            <div className="space-y-2 mb-3">
              {actionItems.map((item, i) => (
                <div
                  key={i}
                  className="flex items-start gap-3 bg-white rounded-lg border border-stone-100 px-4 py-3 group hover:border-stone-200 transition-colors"
                >
                  <input
                    type="checkbox"
                    checked={item.done}
                    onChange={() => toggleActionItem(i)}
                    className="mt-0.5 shrink-0 accent-stone-700 cursor-pointer"
                  />
                  <span
                    className={`text-sm flex-1 ${item.done ? "line-through text-stone-300" : "text-stone-700"}`}
                  >
                    {item.text}
                  </span>
                  <button
                    onClick={() => deleteActionItem(i)}
                    className="shrink-0 text-stone-200 hover:text-red-400 transition-colors opacity-0 group-hover:opacity-100 text-xs leading-none pt-0.5"
                    title="Remove"
                  >
                    ✕
                  </button>
                </div>
              ))}
            </div>
          )}
          {/* Manual add */}
          <div className="flex gap-2">
            <input
              value={newActionText}
              onChange={(e) => setNewActionText(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && addManualActionItem()}
              placeholder="Add an action item manually..."
              className="flex-1 rounded-lg border border-stone-200 bg-white px-3 py-2 text-sm text-stone-700 focus:outline-none focus:border-stone-400 placeholder:text-stone-300"
            />
            <button
              onClick={addManualActionItem}
              disabled={!newActionText.trim()}
              className="px-3 py-2 rounded-lg bg-stone-200 text-stone-600 text-sm hover:bg-stone-300 disabled:opacity-30 transition-colors"
            >
              + Add
            </button>
          </div>
        </div>

        <div>
          <h3 className="text-xs uppercase tracking-widest text-stone-400 mb-1">Capture Observation</h3>
          <p className="text-xs text-stone-300 mb-3">
            Speak or type anything you notice — mood, requests, reactions. It goes into the guest&apos;s memory.
          </p>
          <VoiceCapture
            guestId={data.guest?.id || ""}
            stayId={data.stay.id}
            propertyId="sand-hill"
            onNewObservation={addObservation}
          />
        </div>
      </div>
    </div>
  )
}

function ConsentPill({ level }: { level: string }) {
  const styles: Record<string, string> = {
    standard: "bg-stone-100 text-stone-500",
    living_memory: "bg-rosewood-50 text-rosewood-600",
  }
  const labels: Record<string, string> = {
    standard: "Standard",
    living_memory: "Living Memory",
  }
  return (
    <span className={`text-xs px-2 py-0.5 rounded-full font-sans ${styles[level] ?? "bg-stone-100 text-stone-400"}`}>
      {labels[level] ?? level}
    </span>
  )
}

// Feature 4: Simple staff auth gate
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

export default function ConciergePage() {
  const [guests, setGuests] = useState<InhouseGuest[]>([])
  const [selected, setSelected] = useState(0)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetch(`${API}/arrivals/inhouse`)
      .then((r) => r.json())
      .then((data) => setGuests(data.length > 0 ? data : DEMO_GUESTS))
      .catch(() => setGuests(DEMO_GUESTS))
      .finally(() => setLoading(false))
  }, [])

  const current = guests[selected]

  return (
    <StaffAuth>
      <div className="min-h-screen bg-stone-50 flex flex-col">
        {/* Header */}
        <header className="border-b border-stone-200 bg-white px-8 py-4">
          <div className="max-w-6xl mx-auto flex items-center justify-between">
            <div>
              <p className="text-xs font-sans uppercase tracking-widest text-stone-400 mb-0.5">
                Rosewood Sand Hill — Staff Tool
              </p>
              <h1 className="font-serif text-xl text-stone-900">Concierge Tablet</h1>
              <p className="text-xs text-stone-400 mt-0.5">
                Voice and text observation capture · AI-powered moment suggestions · Live guest memory
              </p>
            </div>
            <div className="text-right">
              <p className="text-sm font-semibold text-stone-700">{guests.length} in-house tonight</p>
              <p className="text-xs text-stone-400 mt-0.5">All observations feed the memory graph</p>
            </div>
          </div>
        </header>

        <div className="flex-1 max-w-6xl mx-auto w-full px-8 py-6 flex gap-6">
          {/* Guest sidebar */}
          <div className="w-56 shrink-0 space-y-2">
            <p className="text-xs text-stone-400 uppercase tracking-widest px-1 mb-3">In-House Guests</p>
            {loading ? (
              <p className="text-xs text-stone-400 py-4">Loading...</p>
            ) : (
              guests.map((g, i) => (
                <button
                  key={i}
                  onClick={() => setSelected(i)}
                  className={`w-full text-left rounded-lg px-4 py-3 transition-colors ${
                    selected === i
                      ? "bg-stone-800 text-white"
                      : "bg-white border border-stone-100 text-stone-700 hover:border-stone-300"
                  }`}
                >
                  <p className="font-semibold text-sm truncate">{g.guest?.name || "Guest"}</p>
                  <p className={`text-xs mt-0.5 truncate ${selected === i ? "text-stone-300" : "text-stone-400"}`}>
                    {g.stay.room_type || "—"}
                  </p>
                </button>
              ))
            )}
          </div>

          {/* Main panel */}
          <div className="flex-1">
            {current ? (
              <div>
                <div className="flex items-start justify-between mb-6">
                  <div>
                    <div className="flex items-center gap-2 mb-1">
                      <h2 className="font-serif text-2xl text-stone-900">{current.guest?.name}</h2>
                      {current.guest && <ConsentPill level={current.guest.consent_level} />}
                    </div>
                    <p className="text-sm text-stone-400">
                      {current.guest?.home_city && `${current.guest.home_city} · `}
                      {current.guest?.nationality} · {current.stay.room_type}
                    </p>
                  </div>
                  <div className="text-right text-xs text-stone-400">
                    <p>Check-in: {new Date(current.stay.check_in).toLocaleDateString("en-US", { month: "short", day: "numeric" })}</p>
                  </div>
                </div>
                {/* Bug 1 fix: key prop forces GuestPanel to remount when guest changes */}
                <GuestPanel key={current.guest?.id || current.stay.id} data={current} />
              </div>
            ) : (
              <div className="text-center py-20 text-stone-400 font-serif">Select a guest to view details.</div>
            )}
          </div>
        </div>
      </div>
    </StaffAuth>
  )
}
