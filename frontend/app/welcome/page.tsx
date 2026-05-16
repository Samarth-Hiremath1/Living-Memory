"use client"

import { useState, useEffect } from "react"

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"

type Phase = "pre" | "connecting" | "conversation" | "done"

interface TranscriptLine {
  speaker: "ambassador" | "guest"
  text: string
}

// Demo transcript for fallback
const DEMO_TRANSCRIPT: TranscriptLine[] = [
  { speaker: "ambassador", text: "Anna, how wonderful to speak with you before your arrival. Are you flying in from Tokyo?" },
  { speaker: "guest", text: "Yes, it's a long flight — about 13 hours. I'm very much looking forward to arriving." },
  { speaker: "ambassador", text: "That sounds like quite a journey. Is there anything you've been imagining about the mountains?" },
  { speaker: "guest", text: "Just quiet, honestly. And I heard there's a lake? I'd love to see it at dawn." },
  { speaker: "ambassador", text: "Sunrise over the Fuschlsee is one of those things you remember. We'll make sure your mornings are as free as you'd like." },
  { speaker: "guest", text: "That's lovely. Oh — and I love Austrian wine. Grüner Veltliner specifically." },
  { speaker: "ambassador", text: "We'll take care of that. We're genuinely looking forward to having you, Anna. Safe travels." },
]

export default function WelcomePage() {
  const [phase, setPhase] = useState<Phase>("pre")
  const [transcript, setTranscript] = useState<TranscriptLine[]>([])
  const [signedUrl, setSignedUrl] = useState<string | null>(null)
  const [consentLevel, setConsentLevel] = useState<"standard" | "remembered" | "living_memory">("living_memory")

  useEffect(() => {
    // Pre-fetch signed URL
    fetch(`${API}/voice/ambassador-url?guest_name=Anna+Lindqvist&property_name=Rosewood+Schloss+Fuschl`)
      .then((r) => r.json())
      .then((d) => setSignedUrl(d.signed_url || null))
      .catch(() => {})
  }, [])

  async function startConversation() {
    setPhase("connecting")
    setTranscript([])

    if (signedUrl) {
      // Real ElevenLabs Conversational AI
      try {
        // Dynamic import of ElevenLabs client
        const { Conversation } = await import("@elevenlabs/client")
        setPhase("conversation")

        const conv = await Conversation.startSession({
          signedUrl,
          onMessage: ({ message, source }) => {
            setTranscript((prev) => [
              ...prev,
              {
                speaker: source === "ai" ? "ambassador" : "guest",
                text: message,
              },
            ])
          },
          onDisconnect: () => {
            setPhase("done")
          },
        })

        // Auto-end after 90 seconds
        setTimeout(() => conv.endSession(), 90000)
      } catch {
        // Fallback to demo
        runDemoMode()
      }
    } else {
      // Demo mode: replay transcript with delays
      runDemoMode()
    }
  }

  function runDemoMode() {
    setPhase("conversation")
    let i = 0
    function addLine() {
      if (i >= DEMO_TRANSCRIPT.length) {
        setTimeout(() => setPhase("done"), 1000)
        return
      }
      setTranscript((prev) => [...prev, DEMO_TRANSCRIPT[i]])
      i++
      setTimeout(addLine, 2800 + Math.random() * 1200)
    }
    setTimeout(addLine, 1200)
  }

  return (
    <div className="min-h-screen bg-stone-900 flex flex-col items-center justify-center px-6">
      {/* Consent selector (small, top) */}
      {phase === "pre" && (
        <div className="absolute top-6 right-6">
          <div className="bg-stone-800 rounded-lg px-4 py-3 text-right">
            <p className="text-xs text-stone-400 mb-2">Memory preference</p>
            <div className="flex gap-2">
              {(["standard", "remembered", "living_memory"] as const).map((level) => (
                <button
                  key={level}
                  onClick={() => setConsentLevel(level)}
                  className={`text-xs px-2 py-1 rounded-full transition-colors ${
                    consentLevel === level
                      ? "bg-rosewood-600 text-white"
                      : "bg-stone-700 text-stone-400 hover:bg-stone-600"
                  }`}
                >
                  {level === "standard" ? "Standard" : level === "remembered" ? "Remembered" : "Living Memory"}
                </button>
              ))}
            </div>
            <button className="mt-2 text-xs text-stone-500 hover:text-red-400 transition-colors">
              Forget me everywhere
            </button>
          </div>
        </div>
      )}

      <div className="max-w-lg w-full text-center space-y-10">
        {/* Pre */}
        {phase === "pre" && (
          <>
            <div className="space-y-3">
              <p className="text-xs font-sans uppercase tracking-widest text-stone-500">
                Rosewood Schloss Fuschl
              </p>
              <h1 className="text-4xl font-serif text-stone-100">
                We're looking forward<br />to having you, Anna.
              </h1>
              <p className="text-stone-400 font-serif text-lg italic">
                September 15 · Lake View Suite
              </p>
            </div>

            <div className="h-px bg-stone-700" />

            <div className="space-y-4">
              <p className="text-stone-400 text-sm leading-relaxed">
                Before you arrive, we'd love a brief moment with you. One of our team
                will ask a few questions — nothing formal, just a conversation.
              </p>
              <button
                onClick={startConversation}
                className="group inline-flex items-center gap-3 bg-rosewood-600 hover:bg-rosewood-700 text-white rounded-full px-8 py-4 text-sm font-medium transition-all"
              >
                <span className="w-2 h-2 rounded-full bg-white/60 group-hover:bg-white transition-colors" />
                Have a moment with us?
              </button>
              <p className="text-xs text-stone-600">
                This conversation is optional and takes about 60 seconds.
              </p>
            </div>
          </>
        )}

        {/* Connecting */}
        {phase === "connecting" && (
          <div className="space-y-4">
            <div className="flex justify-center gap-1">
              {[0, 1, 2].map((i) => (
                <div
                  key={i}
                  className="w-2 h-2 rounded-full bg-rosewood-400 animate-bounce"
                  style={{ animationDelay: `${i * 0.15}s` }}
                />
              ))}
            </div>
            <p className="text-stone-400 font-serif">Connecting you with our Ambassador...</p>
          </div>
        )}

        {/* Conversation */}
        {phase === "conversation" && (
          <div className="space-y-6 w-full">
            <div className="flex items-center justify-center gap-3 mb-2">
              <div className="w-2 h-2 rounded-full bg-green-400 animate-pulse" />
              <p className="text-stone-400 text-sm">Speaking with Rosewood Ambassador</p>
            </div>

            <div className="space-y-3 text-left max-h-80 overflow-y-auto">
              {transcript.map((line, i) => (
                <div
                  key={i}
                  className={`flex ${line.speaker === "guest" ? "justify-end" : "justify-start"}`}
                >
                  <div
                    className={`max-w-xs rounded-2xl px-4 py-3 text-sm leading-relaxed ${
                      line.speaker === "ambassador"
                        ? "bg-stone-800 text-stone-200 rounded-tl-sm"
                        : "bg-rosewood-600 text-white rounded-tr-sm"
                    }`}
                  >
                    {line.text}
                  </div>
                </div>
              ))}
              {transcript.length === 0 && (
                <p className="text-stone-500 text-sm text-center italic py-8">
                  The Ambassador is listening...
                </p>
              )}
            </div>
          </div>
        )}

        {/* Done */}
        {phase === "done" && (
          <div className="space-y-6">
            <div className="space-y-2">
              <div className="text-4xl font-serif text-stone-300">✦</div>
              <h2 className="text-2xl font-serif text-stone-100">Safe travels, Anna.</h2>
              <p className="text-stone-400 font-serif italic">
                We'll have everything ready when you arrive at the lake.
              </p>
            </div>

            <div className="bg-stone-800 rounded-xl p-5 text-left text-sm space-y-2">
              <p className="text-xs uppercase tracking-widest text-stone-500 mb-3">Captured</p>
              <p className="text-stone-300">— Dawn lake access on arrival morning</p>
              <p className="text-stone-300">— Grüner Veltliner selection in room</p>
              <p className="text-stone-300">— Quiet, unhurried pace throughout stay</p>
            </div>

            <p className="text-xs text-stone-600">
              Your memory preference is set to{" "}
              <span className="text-rosewood-400">
                {consentLevel === "living_memory" ? "Living Memory" : consentLevel === "remembered" ? "Remembered" : "Standard"}
              </span>.{" "}
              <button className="underline hover:text-stone-400 transition-colors">Update anytime.</button>
            </p>
          </div>
        )}
      </div>
    </div>
  )
}
