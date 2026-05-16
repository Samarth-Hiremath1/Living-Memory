"use client"

import { useState, useEffect } from "react"

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"

type Phase = "idle" | "connecting" | "conversation" | "done"

interface TranscriptLine {
  speaker: "concierge" | "guest"
  text: string
}

// Only the concierge side — user speaks/types their own side in demo mode
const DEMO_CONCIERGE_OPENING = "Hello, this is your Rosewood Sand Hill concierge — how can I help you today?"

const PLACEMAKERS = [
  {
    name: "Natalie Cheng",
    role: "Wellness Director",
    description: "Sunrise yoga, spa treatments, sunset trail walks. Perfect for recovery or reconnecting with stillness.",
    tag: "wellness",
  },
  {
    name: "Reylon Agustin",
    role: "Executive Chef, Madera",
    description: "Farm-to-table California cuisine, kitchen table experiences, and conversations about where your food comes from.",
    tag: "dining",
  },
  {
    name: "David Park",
    role: "Napa & Sonoma Wine Curator",
    description: "Private cellar tastings, Napa day trips, and pairings for serious wine enthusiasts.",
    tag: "wine",
  },
]

export default function GuestPage() {
  const [phase, setPhase] = useState<Phase>("idle")
  const [transcript, setTranscript] = useState<TranscriptLine[]>([])
  const [signedUrl, setSignedUrl] = useState<string | null>(null)
  const [demoInput, setDemoInput] = useState("")
  const [demoWaiting, setDemoWaiting] = useState(false)
  const [demoThinking, setDemoThinking] = useState(false)

  useEffect(() => {
    fetch(`${API}/voice/concierge-url?guest_name=Samarth+Hiremath&property_name=Rosewood+Sand+Hill`)
      .then((r) => r.json())
      .then((d) => setSignedUrl(d.signed_url || null))
      .catch(() => {})
  }, [])

  async function startCall() {
    setPhase("connecting")
    setTranscript([])

    if (signedUrl) {
      try {
        const { Conversation } = await import("@elevenlabs/client")
        setPhase("conversation")

        const conv = await Conversation.startSession({
          signedUrl,
          onMessage: ({ message, source }: { message: string; source: string }) => {
            setTranscript((prev) => [
              ...prev,
              { speaker: source === "ai" ? "concierge" : "guest", text: message },
            ])
          },
          onDisconnect: () => setPhase("done"),
        })

        setTimeout(() => conv.endSession(), 300000) // 5 min max
      } catch {
        runDemoMode()
      }
    } else {
      runDemoMode()
    }
  }

  function runDemoMode() {
    setPhase("conversation")
    setDemoThinking(false)
    // Show the concierge opening line, then wait for the user
    setTimeout(() => {
      setTranscript([{ speaker: "concierge", text: DEMO_CONCIERGE_OPENING }])
      setDemoWaiting(true)
    }, 800)
  }

  async function submitDemoMessage() {
    if (!demoInput.trim() || !demoWaiting) return
    const userText = demoInput.trim()
    setDemoInput("")
    setDemoWaiting(false)
    setDemoThinking(true)

    // Add the user's real message
    setTranscript((prev) => [...prev, { speaker: "guest", text: userText }])

    // Call the concierge API to get a real response
    try {
      const res = await fetch(`${API}/demo/concierge-chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: userText }),
      })
      if (res.ok) {
        const data = await res.json()
        setTimeout(() => {
          setTranscript((prev) => [...prev, { speaker: "concierge", text: data.response }])
          setDemoThinking(false)
          setDemoWaiting(true)
        }, 400)
        return
      }
    } catch {
      // Fall through to scripted fallback
    }

    // Scripted fallback responses based on keywords
    const lower = userText.toLowerCase()
    let reply = "Of course — let me arrange that for you. Is there anything else I can help with?"
    if (lower.includes("spa") || lower.includes("natalie") || lower.includes("massage") || lower.includes("wellness")) {
      reply = "Natalie Cheng, our wellness director, has a recovery session available this afternoon — breathwork, restorative massage, and a private tea ceremony in the garden afterward. It's 90 minutes and especially good after a long journey. Shall I book it?"
    } else if (lower.includes("trail") || lower.includes("walk") || lower.includes("hike") || lower.includes("oak grove")) {
      reply = "The oak grove trail is beautiful right now — about 90 minutes at an easy pace. Natalie can guide you, or I can leave a map at your bungalow. The light at sunset is particularly good. What time were you thinking?"
    } else if (lower.includes("wine") || lower.includes("david") || lower.includes("napa") || lower.includes("sonoma")) {
      reply = "David Park, our wine curator, has a private cellar tasting available this afternoon — six wines from his personal selection, including bottles not on the Madera list. 75 minutes. Or if you'd like a full day in Napa, he can arrange that for tomorrow. Which appeals?"
    } else if (lower.includes("food") || lower.includes("dinner") || lower.includes("madera") || lower.includes("reylon") || lower.includes("restaurant")) {
      reply = "Madera is open this evening — Reylon's menu tonight is built around the Half Moon Bay harvest. I can reserve your preferred table. If you're interested in something more immersive, Reylon occasionally hosts a kitchen table experience. Shall I check his availability?"
    } else if (lower.includes("transport") || lower.includes("car") || lower.includes("uber") || lower.includes("san francisco") || lower.includes("airport") || lower.includes("sfo")) {
      reply = "I can arrange a car service for you — San Francisco is about 35 minutes, SFO about the same. Just let me know your time and I'll have it ready at the front."
    } else if (lower.includes("run") || lower.includes("bike") || lower.includes("cycling")) {
      reply = "We have bikes available at the front desk — the route along Sand Hill Road is flat and scenic. For trail running, the Sand Hill property trail is about 3 miles of packed earth, beautiful in the morning. Would you like a trail map?"
    }

    setTimeout(() => {
      setTranscript((prev) => [...prev, { speaker: "concierge", text: reply }])
      setDemoThinking(false)
      setDemoWaiting(true)
    }, 1000 + Math.random() * 600)
  }

  return (
    <div className="min-h-screen bg-stone-50">
      {/* Header */}
      <header className="border-b border-stone-200 bg-white px-8 py-5">
        <div className="max-w-2xl mx-auto flex items-center justify-between">
          <div>
            <p className="text-xs font-sans uppercase tracking-widest text-stone-400 mb-0.5">Rosewood Sand Hill</p>
            <h1 className="font-serif text-xl text-stone-900">Your Concierge</h1>
          </div>
          <p className="text-xs text-stone-400 font-serif italic">In-stay assistant</p>
        </div>
      </header>

      <main className="max-w-2xl mx-auto px-8 py-10 space-y-10 pb-20">

        {/* PlaceMaker Engine section */}
        {phase === "idle" && (
          <div className="space-y-8">
            <div className="space-y-2">
              <h2 className="font-serif text-2xl text-stone-800">Good afternoon, Samarth.</h2>
              <p className="text-stone-500 text-sm leading-relaxed">
                Our concierge knows every corner of Sand Hill and the surrounding area — and has real relationships
                with the people who make it special. Ask anything, or call us directly.
              </p>
            </div>

            {/* Voice call button */}
            <button
              onClick={startCall}
              className="group w-full flex items-center justify-between bg-stone-800 hover:bg-stone-900 text-white rounded-xl px-6 py-5 transition-all"
            >
              <div className="text-left">
                <p className="font-semibold text-sm">Speak with your concierge</p>
                <p className="text-xs text-stone-400 mt-0.5">Dining, spa, transportation, local recommendations</p>
              </div>
              <div className="w-10 h-10 rounded-full bg-white/10 flex items-center justify-center group-hover:bg-white/20 transition-colors">
                <span className="text-lg">🎙</span>
              </div>
            </button>

            {/* PlaceMaker Engine */}
            <div>
              <div className="mb-4">
                <p className="text-xs uppercase tracking-widest text-stone-400">The PlaceMaker Engine</p>
                <p className="text-xs text-stone-400 mt-1">
                  Our cultural network — not a directory, but real people with real expertise who can make your stay remarkable.
                </p>
              </div>
              <div className="space-y-3">
                {PLACEMAKERS.map((pm) => (
                  <div
                    key={pm.name}
                    className="bg-white rounded-xl border border-stone-100 px-5 py-4 flex items-start gap-4"
                  >
                    <div className="w-8 h-8 rounded-full bg-stone-100 flex items-center justify-center text-xs text-stone-500 font-semibold shrink-0 mt-0.5">
                      {pm.name.split(" ").map((n) => n[0]).join("")}
                    </div>
                    <div>
                      <p className="font-semibold text-sm text-stone-800">{pm.name}</p>
                      <p className="text-xs text-stone-400 mb-1">{pm.role}</p>
                      <p className="text-sm text-stone-600 leading-relaxed">{pm.description}</p>
                    </div>
                  </div>
                ))}
              </div>
              <p className="text-xs text-stone-400 mt-3 italic">
                Ask your concierge to connect you with any of them.
              </p>
            </div>
          </div>
        )}

        {/* Connecting */}
        {phase === "connecting" && (
          <div className="flex flex-col items-center justify-center py-20 space-y-4">
            <div className="flex gap-1">
              {[0, 1, 2].map((i) => (
                <div
                  key={i}
                  className="w-2 h-2 rounded-full bg-stone-400 animate-bounce"
                  style={{ animationDelay: `${i * 0.15}s` }}
                />
              ))}
            </div>
            <p className="text-stone-500 font-serif">Connecting to your concierge...</p>
          </div>
        )}

        {/* Active conversation */}
        {phase === "conversation" && (
          <div className="space-y-4">
            <div className="flex items-center gap-3">
              <div className="w-2 h-2 rounded-full bg-green-400 animate-pulse" />
              <p className="text-stone-500 text-sm">
                {signedUrl ? "Connected — Rosewood Sand Hill Concierge" : "Rosewood Sand Hill Concierge · demo mode"}
              </p>
            </div>

            <div className="space-y-3 max-h-80 overflow-y-auto">
              {transcript.map((line, i) => (
                <div key={i} className={`flex ${line.speaker === "guest" ? "justify-end" : "justify-start"}`}>
                  <div
                    className={`max-w-sm rounded-2xl px-4 py-3 text-sm leading-relaxed ${
                      line.speaker === "concierge"
                        ? "bg-white border border-stone-100 text-stone-700 rounded-tl-sm"
                        : "bg-stone-800 text-white rounded-tr-sm"
                    }`}
                  >
                    {line.text}
                  </div>
                </div>
              ))}

              {/* Concierge thinking indicator */}
              {demoThinking && (
                <div className="flex justify-start">
                  <div className="bg-white border border-stone-100 rounded-2xl px-4 py-3 rounded-tl-sm">
                    <div className="flex gap-1">
                      {[0, 1, 2].map((i) => (
                        <div key={i} className="w-1.5 h-1.5 rounded-full bg-stone-300 animate-bounce"
                          style={{ animationDelay: `${i * 0.15}s` }} />
                      ))}
                    </div>
                  </div>
                </div>
              )}

              {transcript.length === 0 && (
                <p className="text-stone-400 text-sm text-center italic py-8">Your concierge is ready...</p>
              )}
            </div>

            {/* User input — demo mode */}
            {!signedUrl && demoWaiting && (
              <div className="flex gap-2 pt-2">
                <input
                  autoFocus
                  value={demoInput}
                  onChange={(e) => setDemoInput(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && submitDemoMessage()}
                  placeholder="Ask anything — spa, dining, trails, wine..."
                  className="flex-1 rounded-xl border border-stone-200 bg-white px-4 py-3 text-sm focus:outline-none focus:border-stone-400"
                />
                <button
                  onClick={submitDemoMessage}
                  disabled={!demoInput.trim()}
                  className="px-4 py-3 rounded-xl bg-stone-800 text-white text-sm disabled:opacity-30 hover:bg-stone-900 transition-colors"
                >
                  Send
                </button>
              </div>
            )}

            <button
              onClick={() => setPhase("done")}
              className="text-xs text-stone-400 hover:text-stone-600 underline transition-colors"
            >
              End conversation
            </button>
          </div>
        )}

        {/* Done */}
        {phase === "done" && (
          <div className="space-y-6 text-center">
            <div className="space-y-2">
              <p className="text-3xl font-serif text-stone-700">✦</p>
              <h2 className="font-serif text-xl text-stone-800">All arranged.</h2>
              <p className="text-stone-500 font-serif italic text-sm">
                Is there anything else we can do? We&apos;re always here.
              </p>
            </div>
            <button
              onClick={() => { setPhase("idle"); setTranscript([]) }}
              className="text-sm text-stone-500 hover:text-stone-700 underline transition-colors"
            >
              Back to concierge
            </button>
          </div>
        )}
        </main>

      {/* Footer: data transparency link */}
      <footer className="border-t border-stone-100 bg-white px-8 py-4">
        <div className="max-w-2xl mx-auto text-center">
          <a
            href="/my-data?guest_id=guest-samarth-hiremath"
            className="text-xs text-stone-400 hover:text-stone-600 underline transition-colors"
          >
            See everything we know about you →
          </a>
        </div>
      </footer>
    </div>
  )
}
