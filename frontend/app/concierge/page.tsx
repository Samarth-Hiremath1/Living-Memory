"use client"

import { useEffect, useState, useRef } from "react"

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"

interface Observation {
  id: string
  raw_text: string
  tags: string[]
  timestamp: string
  source: string
  sentiment: string | null
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

// Demo data
const DEMO_GUESTS: InhouseGuest[] = [
  {
    guest: {
      id: "guest-anna-lindqvist",
      name: "Anna Lindqvist",
      nationality: "Swedish",
      home_city: "Tokyo",
      consent_level: "living_memory",
    },
    stay: {
      id: "stay-anna-fuschl-2024",
      check_in: new Date().toISOString().split("T")[0],
      room_type: "Lake View Suite",
    },
    recent_observations: [],
    plan: {
      moments_to_create: [
        "Ask if she'd like the 6am dock spot reserved for tomorrow's sunrise",
        "Have Josef Huber send up a Grüner Veltliner tasting note card with welcome amenity",
        "Check if Gerald Aichriedler has morning availability for a dawn hike on day 2",
      ],
    },
  },
]

function SentimentDot({ sentiment }: { sentiment: string | null }) {
  const colors: Record<string, string> = {
    positive: "bg-green-400",
    neutral: "bg-stone-300",
    negative: "bg-red-400",
    concerned: "bg-amber-400",
  }
  return (
    <span className={`inline-block w-2 h-2 rounded-full ${colors[sentiment || "neutral"]}`} />
  )
}

function ObservationFeed({ observations }: { observations: Observation[] }) {
  if (observations.length === 0) {
    return (
      <p className="text-xs text-stone-400 italic py-4 text-center">No observations yet this stay.</p>
    )
  }
  return (
    <div className="space-y-3">
      {observations.map((obs) => (
        <div key={obs.id} className="bg-white rounded-lg border border-stone-100 p-3">
          <div className="flex items-start gap-2 mb-1">
            <SentimentDot sentiment={obs.sentiment} />
            <p className="text-xs text-stone-500 flex-1">
              {new Date(obs.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
              {" · "}
              <span className="capitalize">{obs.source.replace("_", " ")}</span>
            </p>
          </div>
          <p className="text-sm text-stone-700 leading-relaxed">{obs.raw_text}</p>
          {obs.tags.length > 0 && (
            <div className="flex flex-wrap gap-1 mt-2">
              {obs.tags.slice(0, 4).map((tag) => (
                <span key={tag} className="text-xs bg-stone-50 text-stone-400 px-2 py-0.5 rounded-full">
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
  onNewObservation: (obs: Observation) => void
}) {
  const [recording, setRecording] = useState(false)
  const [transcript, setTranscript] = useState("")
  const [submitting, setSubmitting] = useState(false)
  const [textInput, setTextInput] = useState("")
  const mediaRef = useRef<MediaRecorder | null>(null)
  const chunksRef = useRef<Blob[]>([])

  async function startRecording() {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const mr = new MediaRecorder(stream)
      chunksRef.current = []
      mr.ondataavailable = (e) => chunksRef.current.push(e.data)
      mr.onstop = async () => {
        const blob = new Blob(chunksRef.current, { type: "audio/webm" })
        await submitVoice(blob)
        stream.getTracks().forEach((t) => t.stop())
      }
      mediaRef.current = mr
      mr.start()
      setRecording(true)
    } catch {
      alert("Microphone access denied. Use text input below.")
    }
  }

  function stopRecording() {
    mediaRef.current?.stop()
    setRecording(false)
  }

  async function submitVoice(blob: Blob) {
    setSubmitting(true)
    const form = new FormData()
    form.append("audio", blob, "observation.webm")
    form.append("stay_id", stayId)
    form.append("guest_id", guestId)
    form.append("property_id", propertyId)
    try {
      const res = await fetch(`${API}/observations/voice`, { method: "POST", body: form })
      const data = await res.json()
      setTranscript(data.transcript || "")
      onNewObservation(data.observation)
    } finally {
      setSubmitting(false)
    }
  }

  async function submitText() {
    if (!textInput.trim()) return
    setSubmitting(true)
    try {
      const res = await fetch(`${API}/observations`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          raw_text: textInput,
          stay_id: stayId,
          guest_id: guestId,
          property_id: propertyId,
        }),
      })
      const data = await res.json()
      onNewObservation(data.observation)
      setTextInput("")
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="space-y-3">
      {/* Voice button */}
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
        {recording ? "● Recording — release to send" : submitting ? "Processing..." : "Hold to speak an observation"}
      </button>

      {transcript && (
        <p className="text-xs text-stone-500 italic bg-stone-50 rounded-lg px-3 py-2">
          Transcribed: "{transcript}"
        </p>
      )}

      {/* Text fallback */}
      <div className="flex gap-2">
        <input
          value={textInput}
          onChange={(e) => setTextInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && submitText()}
          placeholder="Or type an observation..."
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
    </div>
  )
}

function GuestPanel({ data }: { data: InhouseGuest }) {
  const [observations, setObservations] = useState<Observation[]>(data.recent_observations)
  const moments = (data.plan?.moments_to_create as string[]) || []

  function addObservation(obs: Observation) {
    setObservations((prev) => [obs, ...prev])
  }

  return (
    <div className="grid grid-cols-5 gap-6 h-full">
      {/* Left: observation feed */}
      <div className="col-span-2 space-y-4">
        <h3 className="text-xs uppercase tracking-widest text-stone-400">Observation Feed</h3>
        <ObservationFeed observations={observations} />
      </div>

      {/* Right: suggestions + voice capture */}
      <div className="col-span-3 space-y-6">
        {moments.length > 0 && (
          <div>
            <h3 className="text-xs uppercase tracking-widest text-stone-400 mb-3">Live Suggestions</h3>
            <div className="space-y-2">
              {moments.map((m, i) => (
                <div key={i} className="flex gap-3 bg-white rounded-lg border border-stone-100 px-4 py-3 text-sm text-stone-700">
                  <span className="text-rosewood-400 shrink-0">—</span>
                  <span>{m}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        <div>
          <h3 className="text-xs uppercase tracking-widest text-stone-400 mb-3">Capture Observation</h3>
          <VoiceCapture
            guestId={data.guest?.id || ""}
            stayId={data.stay.id}
            propertyId="schloss-fuschl"
            onNewObservation={addObservation}
          />
        </div>
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
    <div className="min-h-screen bg-stone-50 flex flex-col">
      {/* Header */}
      <header className="border-b border-stone-200 bg-white px-8 py-4">
        <div className="max-w-6xl mx-auto flex items-center justify-between">
          <div>
            <p className="text-xs font-sans uppercase tracking-widest text-stone-400 mb-0.5">Concierge View</p>
            <h1 className="font-serif text-xl text-stone-900">In-House Guests</h1>
          </div>
          <p className="text-xs text-stone-400">{guests.length} in-house</p>
        </div>
      </header>

      <div className="flex-1 max-w-6xl mx-auto w-full px-8 py-6 flex gap-6">
        {/* Guest list */}
        <div className="w-56 shrink-0 space-y-2">
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
                <p className="font-semibold text-sm">{g.guest?.name || "Guest"}</p>
                <p className={`text-xs mt-0.5 ${selected === i ? "text-stone-300" : "text-stone-400"}`}>
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
              <div className="flex items-center gap-3 mb-6">
                <div>
                  <h2 className="font-serif text-2xl text-stone-900">{current.guest?.name}</h2>
                  <p className="text-sm text-stone-400">
                    {current.guest?.home_city} · {current.stay.room_type}
                  </p>
                </div>
              </div>
              <GuestPanel data={current} />
            </div>
          ) : (
            <div className="text-center py-20 text-stone-400 font-serif">Select a guest to view details.</div>
          )}
        </div>
      </div>
    </div>
  )
}
