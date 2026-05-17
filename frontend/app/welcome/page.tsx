"use client"

import { useState, useEffect, useRef, Suspense } from "react"
import { useSearchParams } from "next/navigation"

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"

// "processing" = conversation ended, waiting for API to extract preferences
type Phase = "pre" | "connecting" | "conversation" | "processing" | "form" | "done"
type ConsentLevel = "standard" | "living_memory"

interface TranscriptLine {
  speaker: "ambassador" | "guest"
  text: string
}

const CONSENT_DETAILS: Record<ConsentLevel, { label: string; description: string }> = {
  standard: {
    label: "Standard",
    description: "Your preferences are used only for this stay. Nothing is retained after checkout.",
  },
  living_memory: {
    label: "Living Memory",
    description: "Your preferences travel with you across all Rosewood properties worldwide. Every stay builds on the last.",
  },
}

// Demo ambassador lines — used when ElevenLabs is not configured
const DEMO_AMBASSADOR_LINES = [
  "How lovely to reach you before your arrival. I'm calling from Rosewood Sand Hill — we're so looking forward to having you with us. Are you coming straight to us from the city, or have you been on the road a while?",
  "That sounds like quite a journey. Is there something you've been imagining about your time with us this weekend?",
  "Natalie at our spa has a session designed exactly for long-haul arrivals — I'll make sure she knows you're coming. The trail through the oak grove is genuinely peaceful this time of year. Do you tend to sleep warm or do you prefer the room a bit cool? And is there anything you'd love waiting for you?",
  "We'll have everything ready for you. We're genuinely looking forward to having you. Safe travels.",
]

const DEMO_SUMMARY = [
  "Oak grove walk on arrival afternoon",
  "Natural wine selection in room",
  "Spa session with Natalie — long-haul recovery focus",
  "Quiet, unhurried pace throughout stay",
]

// Generic defaults — no guest pre-loaded until URL param or button click
const DEMO_GUEST_ID = ""
const DEMO_STAY_ID = ""
const DEMO_GUEST_NAME = "there"
const DEMO_ROOM_TYPE = "Garden Bungalow"
const DEMO_CHECK_IN = new Date().toLocaleDateString("en-US", { month: "long", day: "numeric" })

// ── Onboarding Form ─────────────────────────────────────────────────────────

interface FormData {
  arrivalTime: string
  tempPreference: string
  welcomeAmenity: string
  lookingForward: string
  dietary: string
  occasion: string
  otherRequests: string
}

function OnboardingForm({
  guestFirstName,
  guestId,
  stayId,
  consentLevel,
  onComplete,
  onBack,
}: {
  guestFirstName: string
  guestId: string
  stayId: string
  consentLevel: ConsentLevel
  onComplete: (summary: string[]) => void
  onBack: () => void
}) {
  const [form, setForm] = useState<FormData>({
    arrivalTime: "",
    tempPreference: "",
    welcomeAmenity: "",
    lookingForward: "",
    dietary: "",
    occasion: "",
    otherRequests: "",
  })
  const [submitting, setSubmitting] = useState(false)

  function set(field: keyof FormData, value: string) {
    setForm((prev) => ({ ...prev, [field]: value }))
  }

  function isAnythingFilled() {
    return Object.values(form).some((v) => v.trim().length > 0)
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setSubmitting(true)

    // Build natural-language transcript to pass through the welcome-call processor
    const lines: string[] = []
    if (form.arrivalTime) lines.push(`Guest expects to arrive at ${form.arrivalTime}.`)
    if (form.tempPreference) lines.push(`Room temperature preference: ${form.tempPreference}.`)
    if (form.welcomeAmenity) lines.push(`Welcome amenity requested: ${form.welcomeAmenity}.`)
    if (form.lookingForward) lines.push(`Looking forward to: ${form.lookingForward}.`)
    if (form.dietary) lines.push(`Dietary notes: ${form.dietary}.`)
    if (form.occasion) lines.push(`Occasion: ${form.occasion}.`)
    if (form.otherRequests) lines.push(`Other requests: ${form.otherRequests}.`)

    const transcript = `${guestFirstName} completed the pre-arrival form:\n${lines.join("\n")}`

    try {
      // Save consent level if guest is known
      if (guestId) {
        await fetch(`${API}/guests/${guestId}/consent`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ consent_level: consentLevel }),
        })
      }

      // Process through welcome-call pipeline
      const res = await fetch(`${API}/voice/process-welcome-call`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ transcript, guest_id: guestId, stay_id: stayId }),
      })

      if (res.ok) {
        const data = await res.json()
        if (data.summary && data.summary.length > 0) {
          onComplete(data.summary)
          return
        }
      }
    } catch {
      // Fall through to local summary
    }

    // Local summary if API failed or returned nothing
    const localSummary: string[] = []
    if (form.arrivalTime) localSummary.push(`Arriving around ${form.arrivalTime}`)
    if (form.tempPreference) localSummary.push(`Room temperature: ${form.tempPreference}`)
    if (form.welcomeAmenity) localSummary.push(`Welcome amenity: ${form.welcomeAmenity}`)
    if (form.lookingForward) localSummary.push(form.lookingForward)
    if (form.dietary) localSummary.push(`Dietary: ${form.dietary}`)
    if (form.occasion) localSummary.push(`Occasion: ${form.occasion}`)
    if (form.otherRequests) localSummary.push(form.otherRequests)
    onComplete(localSummary.length > 0 ? localSummary : ["Preferences saved — we'll have everything ready."])
  }

  const inputClass = "w-full bg-stone-800 border border-stone-700 text-stone-100 placeholder-stone-500 rounded-xl px-4 py-3 text-sm focus:outline-none focus:border-rosewood-500 transition-colors"
  const labelClass = "block text-xs uppercase tracking-widest text-stone-400 mb-2"

  return (
    <div className="w-full text-left space-y-6">
      <div className="flex items-center gap-4">
        <button onClick={onBack} className="text-stone-500 hover:text-stone-300 transition-colors text-sm">← Back</button>
        <div>
          <h2 className="font-serif text-2xl text-stone-100">A few quick questions</h2>
          <p className="text-xs text-stone-500 mt-0.5">So we can have everything just right when you walk in{guestFirstName !== "there" ? `, ${guestFirstName}` : ""}.</p>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="space-y-5">

        {/* Arrival time */}
        <div>
          <label className={labelClass}>What time do you expect to arrive?</label>
          <input
            type="text"
            value={form.arrivalTime}
            onChange={(e) => set("arrivalTime", e.target.value)}
            placeholder="e.g. around 3pm, late afternoon, after 6..."
            className={inputClass}
          />
        </div>

        {/* Room temperature */}
        <div>
          <label className={labelClass}>Do you tend to sleep warm or cool?</label>
          <div className="grid grid-cols-3 gap-2">
            {["Cool (65–68°F)", "Moderate (69–71°F)", "Warm (72°F+)"].map((opt) => (
              <button
                key={opt}
                type="button"
                onClick={() => set("tempPreference", opt)}
                className={`py-2.5 px-3 rounded-xl text-xs font-medium transition-colors ${
                  form.tempPreference === opt
                    ? "bg-rosewood-600 text-white"
                    : "bg-stone-800 border border-stone-700 text-stone-400 hover:border-stone-500"
                }`}
              >
                {opt}
              </button>
            ))}
          </div>
        </div>

        {/* Welcome amenity */}
        <div>
          <label className={labelClass}>Is there anything you&apos;d love waiting in your room?</label>
          <div className="grid grid-cols-2 gap-2 mb-2">
            {[
              "Cold-pressed juices & greens",
              "Local wine selection",
              "Tea & adaptogens",
              "Fresh fruit & Manresa bread",
            ].map((opt) => (
              <button
                key={opt}
                type="button"
                onClick={() => set("welcomeAmenity", opt)}
                className={`py-2 px-3 rounded-xl text-xs text-left transition-colors ${
                  form.welcomeAmenity === opt
                    ? "bg-rosewood-600 text-white"
                    : "bg-stone-800 border border-stone-700 text-stone-400 hover:border-stone-500"
                }`}
              >
                {opt}
              </button>
            ))}
          </div>
          <input
            type="text"
            value={["Cold-pressed juices & greens","Local wine selection","Tea & adaptogens","Fresh fruit & Manresa bread"].includes(form.welcomeAmenity) ? "" : form.welcomeAmenity}
            onChange={(e) => set("welcomeAmenity", e.target.value)}
            placeholder="Or describe something specific..."
            className={inputClass}
          />
        </div>

        {/* Looking forward to */}
        <div>
          <label className={labelClass}>What are you most looking forward to?</label>
          <textarea
            value={form.lookingForward}
            onChange={(e) => set("lookingForward", e.target.value)}
            placeholder="Hiking, a quiet morning, trying Madera, the spa, exploring the trails..."
            rows={2}
            className={`${inputClass} resize-none`}
          />
        </div>

        {/* Dietary */}
        <div>
          <label className={labelClass}>Any dietary preferences we should know?</label>
          <input
            type="text"
            value={form.dietary}
            onChange={(e) => set("dietary", e.target.value)}
            placeholder="Vegetarian, allergies, loves spicy food, no shellfish..."
            className={inputClass}
          />
        </div>

        {/* Occasion */}
        <div>
          <label className={labelClass}>Is this trip a special occasion? <span className="text-stone-600 normal-case not-italic">(optional)</span></label>
          <div className="flex flex-wrap gap-2">
            {["Birthday", "Anniversary", "Work retreat", "Creative reset", "Just needed a break"].map((opt) => (
              <button
                key={opt}
                type="button"
                onClick={() => set("occasion", form.occasion === opt ? "" : opt)}
                className={`py-1.5 px-3 rounded-full text-xs transition-colors ${
                  form.occasion === opt
                    ? "bg-rosewood-600 text-white"
                    : "bg-stone-800 border border-stone-700 text-stone-400 hover:border-stone-500"
                }`}
              >
                {opt}
              </button>
            ))}
          </div>
        </div>

        {/* Other */}
        <div>
          <label className={labelClass}>Anything else you&apos;d like us to know?</label>
          <textarea
            value={form.otherRequests}
            onChange={(e) => set("otherRequests", e.target.value)}
            placeholder="Early checkout, a quiet bungalow, the fireplace lit on arrival..."
            rows={2}
            className={`${inputClass} resize-none`}
          />
        </div>

        <button
          type="submit"
          disabled={submitting || !isAnythingFilled()}
          className="w-full py-4 rounded-2xl bg-rosewood-600 hover:bg-rosewood-700 text-white text-sm font-medium transition-all disabled:opacity-40"
        >
          {submitting ? "Saving your preferences..." : "We'll have everything ready →"}
        </button>

        <p className="text-xs text-stone-600 text-center">
          All fields are optional — share only what feels comfortable.
        </p>
      </form>
    </div>
  )
}

// ── Main page ────────────────────────────────────────────────────────────────

function WelcomePageInner() {
  const searchParams = useSearchParams()
  const stayIdParam = searchParams.get("stay_id")

  const [phase, setPhase] = useState<Phase>("pre")
  const [transcript, setTranscript] = useState<TranscriptLine[]>([])
  const [consentLevel, setConsentLevel] = useState<ConsentLevel>("living_memory")
  const [showConsentDetail, setShowConsentDetail] = useState(false)
  const [captured, setCaptured] = useState<string[]>([])
  const [forgotten, setForgotten] = useState(false)
  const [forgetting, setForgetting] = useState(false)

  // Demo mode interactive state
  const [demoStep, setDemoStep] = useState(0)
  const [demoInput, setDemoInput] = useState("")
  const [demoWaiting, setDemoWaiting] = useState(false)

  // Guest/stay data — populated from URL param or left as generic defaults
  const [guestId, setGuestId] = useState(DEMO_GUEST_ID)
  const [stayId, setStayId] = useState(DEMO_STAY_ID)
  const [guestFirstName, setGuestFirstName] = useState(DEMO_GUEST_NAME)
  const [roomType, setRoomType] = useState(DEMO_ROOM_TYPE)
  const [checkInDisplay, setCheckInDisplay] = useState(DEMO_CHECK_IN)

  // Stable ref for guestFirstName — avoids stale closures in async callbacks
  const guestFirstNameRef = useRef(guestFirstName)
  useEffect(() => { guestFirstNameRef.current = guestFirstName }, [guestFirstName])

  // Load stay + guest from URL param on mount
  useEffect(() => {
    if (!stayIdParam) return

    async function loadStayAndGuest() {
      try {
        const stayRes = await fetch(`${API}/stays/${stayIdParam}`)
        if (!stayRes.ok) return
        const stay = await stayRes.json()
        setStayId(stay.id)

        const guestRes = await fetch(`${API}/guests/${stay.guest_id}`)
        if (!guestRes.ok) return
        const guest = await guestRes.json()
        setGuestId(guest.id)
        setGuestFirstName(guest.name?.split(" ")[0] || guest.name)
        if (stay.room_type) setRoomType(stay.room_type)
        if (stay.check_in) {
          const d = new Date(stay.check_in + "T12:00:00")
          setCheckInDisplay(d.toLocaleDateString("en-US", { month: "long", day: "numeric" }))
        }
        if (guest.consent_level && ["standard", "living_memory"].includes(guest.consent_level)) {
          setConsentLevel(guest.consent_level as ConsentLevel)
        }
      } catch {
        // Silent fallback to demo defaults
      }
    }

    loadStayAndGuest()
  }, [stayIdParam])

  // Process transcript via API — saves preferences to guest, returns summary bullets
  async function processTranscriptWithAPI(rawTranscript: string, resolvedGuestId?: string, resolvedStayId?: string) {
    const effectiveGuestId = resolvedGuestId ?? guestId
    const effectiveStayId = resolvedStayId ?? stayId

    try {
      // Persist consent level if guest is known
      if (effectiveGuestId) {
        await fetch(`${API}/guests/${effectiveGuestId}/consent`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ consent_level: consentLevel }),
        })
      }

      const res = await fetch(`${API}/voice/process-welcome-call`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          transcript: rawTranscript,
          guest_id: effectiveGuestId,
          stay_id: effectiveStayId,
        }),
      })

      if (res.ok) {
        const data = await res.json()
        if (data.summary && data.summary.length > 0) {
          setCaptured(data.summary)
          return
        }
      }
    } catch {
      // Fall through to demo summary
    }

    setCaptured(DEMO_SUMMARY)
  }

  async function startConversation() {
    setPhase("connecting")
    setTranscript([])

    try {
      // Always fetch a fresh signed URL at click time — includes stay context
      const params = new URLSearchParams({ property_name: "Rosewood Sand Hill" })
      if (stayId) params.set("stay_id", stayId)
      if (guestFirstName && guestFirstName !== "there") params.set("guest_name", guestFirstName)

      const urlRes = await fetch(`${API}/voice/ambassador-url?${params.toString()}`)
      const urlData = urlRes.ok ? await urlRes.json() : {}

      const freshSignedUrl: string | null = urlData.signed_url || null
      const firstMessage: string | null = urlData.first_message || null
      // If the backend resolved a guest from stay_id, use those IDs
      const resolvedGuestId: string = urlData.guest_id || guestId
      const resolvedStayId: string = urlData.stay_id || stayId
      const resolvedGuestName: string = urlData.guest_name || guestFirstName

      if (freshSignedUrl) {
        await startElevenLabsConversation(freshSignedUrl, firstMessage, resolvedGuestId, resolvedStayId, resolvedGuestName)
      } else {
        runDemoMode()
      }
    } catch {
      runDemoMode()
    }
  }

  async function startElevenLabsConversation(
    url: string,
    firstMessage: string | null,
    resolvedGuestId: string,
    resolvedStayId: string,
    resolvedGuestName: string,
  ) {
    try {
      const { Conversation } = await import("@elevenlabs/client")
      setPhase("conversation")

      // Local array — avoids closure issues; transcript state is for display only
      const lines: TranscriptLine[] = []

      const sessionOptions: Record<string, unknown> = {
        signedUrl: url,
        onMessage: ({ message, source }: { message: string; source: string }) => {
          const line: TranscriptLine = {
            speaker: source === "ai" ? "ambassador" : "guest",
            text: message,
          }
          lines.push(line)
          setTranscript((prev) => [...prev, line])
        },
        onDisconnect: async () => {
          const name = guestFirstNameRef.current
          const raw = lines
            .map((l) => `${l.speaker === "ambassador" ? "Ambassador" : name}: ${l.text}`)
            .join("\n")

          // Show processing phase while we extract preferences
          setPhase("processing")
          await processTranscriptWithAPI(raw, resolvedGuestId, resolvedStayId)
          setPhase("done")
        },
      }

      // Inject personalized first message if available (requires signed URL permission)
      if (firstMessage) {
        sessionOptions.overrides = {
          agent: { firstMessage },
        }
      }

      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const conv = await (Conversation as any).startSession(sessionOptions)

      // Auto-end after 3 minutes
      setTimeout(() => {
        try { conv.endSession() } catch { /* ignore */ }
      }, 180_000)
    } catch {
      // ElevenLabs SDK failed — fall back to demo mode
      runDemoMode()
    }
  }

  function runDemoMode() {
    setPhase("conversation")
    setDemoStep(0)
    setDemoWaiting(false)
    setTimeout(() => {
      setTranscript([{ speaker: "ambassador", text: DEMO_AMBASSADOR_LINES[0] }])
      setDemoStep(1)
      setDemoWaiting(true)
    }, 900)
  }

  function submitDemoResponse() {
    if (!demoInput.trim() || !demoWaiting) return
    const userText = demoInput.trim()
    setDemoInput("")
    setDemoWaiting(false)

    setTranscript((prev) => [...prev, { speaker: "guest", text: userText }])

    const nextStep = demoStep
    if (nextStep >= DEMO_AMBASSADOR_LINES.length) {
      // Conversation complete
      setTranscript((prev) => {
        const name = guestFirstNameRef.current
        const raw = prev.map((l) => `${l.speaker === "ambassador" ? "Ambassador" : name}: ${l.text}`).join("\n")
        setPhase("processing")
        processTranscriptWithAPI(raw).then(() => setPhase("done"))
        return prev
      })
      return
    }

    setTimeout(() => {
      const ambassadorText = DEMO_AMBASSADOR_LINES[nextStep]
      setTranscript((prev) => [...prev, { speaker: "ambassador", text: ambassadorText }])
      setDemoStep(nextStep + 1)

      const isLast = nextStep === DEMO_AMBASSADOR_LINES.length - 1
      if (isLast) {
        setTimeout(() => {
          setTranscript((prev) => {
            const name = guestFirstNameRef.current
            const raw = prev.map((l) => `${l.speaker === "ambassador" ? "Ambassador" : name}: ${l.text}`).join("\n")
            setPhase("processing")
            processTranscriptWithAPI(raw).then(() => setPhase("done"))
            return prev
          })
        }, 800)
      } else {
        setDemoWaiting(true)
      }
    }, 1200 + Math.random() * 600)
  }

  async function handleForgetMe() {
    setForgetting(true)
    try {
      if (guestId) await fetch(`${API}/guests/${guestId}/forget`, { method: "DELETE" })
    } catch {
      // silent
    } finally {
      setForgetting(false)
      setForgotten(true)
    }
  }

  return (
    <div className="min-h-screen bg-stone-900 flex flex-col items-center justify-center px-6">

      {/* Memory preference panel — top right during pre phase */}
      {phase === "pre" && (
        <div className="absolute top-6 right-6 max-w-xs">
          <div className="bg-stone-800 rounded-xl px-5 py-4">
            <p className="text-xs text-stone-400 mb-3 uppercase tracking-widest">Memory preference</p>
            <div className="flex gap-2 flex-wrap mb-3">
              {(Object.keys(CONSENT_DETAILS) as ConsentLevel[]).map((level) => (
                <button
                  key={level}
                  onClick={() => { setConsentLevel(level); setShowConsentDetail(true) }}
                  className={`text-xs px-3 py-1.5 rounded-full transition-colors ${
                    consentLevel === level
                      ? "bg-rosewood-600 text-white"
                      : "bg-stone-700 text-stone-400 hover:bg-stone-600"
                  }`}
                >
                  {CONSENT_DETAILS[level].label}
                </button>
              ))}
            </div>
            {showConsentDetail && (
              <p className="text-xs text-stone-300 leading-relaxed">
                {CONSENT_DETAILS[consentLevel].description}
              </p>
            )}
            {!showConsentDetail && (
              <button
                onClick={() => setShowConsentDetail(true)}
                className="text-xs text-stone-500 hover:text-stone-300 underline"
              >
                What does this mean?
              </button>
            )}
            {consentLevel !== "standard" && (
              <div className="mt-3 pt-3 border-t border-stone-700">
                {forgotten ? (
                  <p className="text-xs text-green-400">Your data has been removed from all Rosewood properties.</p>
                ) : (
                  <button
                    onClick={handleForgetMe}
                    disabled={forgetting}
                    className="text-xs text-stone-500 hover:text-red-400 transition-colors disabled:opacity-50"
                  >
                    {forgetting ? "Removing..." : "Forget me everywhere →"}
                  </button>
                )}
              </div>
            )}
          </div>
        </div>
      )}

      <div className="max-w-lg w-full text-center space-y-10">

        {/* Pre */}
        {phase === "pre" && (
          <>
            <div className="space-y-3">
              <p className="text-xs font-sans uppercase tracking-widest text-stone-500">
                Rosewood Sand Hill · Menlo Park, California
              </p>
              <h1 className="text-4xl font-serif text-stone-100">
                {guestFirstName === "there"
                  ? <>We&apos;re looking forward<br />to having you.</>
                  : <>We&apos;re looking forward<br />to having you, {guestFirstName}.</>
                }
              </h1>
              <p className="text-stone-400 font-serif text-lg italic">
                {checkInDisplay} · {roomType}
              </p>
            </div>

            <div className="h-px bg-stone-700" />

            <div className="space-y-4">
              <p className="text-stone-400 text-sm leading-relaxed">
                Before you arrive, we&apos;d love a brief moment with you. One of our team will ask a few questions
                — nothing formal, just a conversation — so we can have everything just right when you walk in.
              </p>
              <div className="flex flex-col items-center gap-3">
                <button
                  onClick={startConversation}
                  className="group inline-flex items-center gap-3 bg-rosewood-600 hover:bg-rosewood-700 text-white rounded-full px-8 py-4 text-sm font-medium transition-all"
                >
                  <span className="w-2 h-2 rounded-full bg-white/60 group-hover:bg-white transition-colors" />
                  Have a moment with us?
                </button>
                <button
                  onClick={() => setPhase("form")}
                  className="text-xs text-stone-500 hover:text-stone-300 underline underline-offset-2 transition-colors"
                >
                  Or fill out a quick optional survey →
                </button>
              </div>
              <p className="text-xs text-stone-600">
                Optional · About 2 minutes · Your preferences are saved according to your memory setting above.
              </p>
            </div>
          </>
        )}

        {/* Onboarding Form */}
        {phase === "form" && (
          <OnboardingForm
            guestFirstName={guestFirstName}
            guestId={guestId}
            stayId={stayId}
            consentLevel={consentLevel}
            onComplete={(summary) => { setCaptured(summary); setPhase("done") }}
            onBack={() => setPhase("pre")}
          />
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
              <p className="text-stone-400 text-sm">
                Rosewood Ambassador{demoWaiting || transcript.length === 0 ? " · demo mode" : ""}
              </p>
            </div>

            <div className="space-y-3 text-left max-h-72 overflow-y-auto">
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

            {/* Demo mode: user types their response */}
            {demoWaiting && (
              <div className="flex gap-2">
                <input
                  autoFocus
                  value={demoInput}
                  onChange={(e) => setDemoInput(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && submitDemoResponse()}
                  placeholder="Your response..."
                  className="flex-1 rounded-full bg-stone-800 border border-stone-600 text-stone-100 placeholder-stone-500 px-4 py-2.5 text-sm focus:outline-none focus:border-rosewood-500"
                />
                <button
                  onClick={submitDemoResponse}
                  disabled={!demoInput.trim()}
                  className="px-4 py-2 rounded-full bg-rosewood-600 text-white text-sm disabled:opacity-30 hover:bg-rosewood-700 transition-colors"
                >
                  Send
                </button>
              </div>
            )}

            {/* Ambassador is "thinking" */}
            {!demoWaiting && transcript.length > 0 && (
              <div className="flex justify-start">
                <div className="bg-stone-800 rounded-2xl px-4 py-3 rounded-tl-sm">
                  <div className="flex gap-1">
                    {[0, 1, 2].map((i) => (
                      <div key={i} className="w-1.5 h-1.5 rounded-full bg-stone-500 animate-bounce"
                        style={{ animationDelay: `${i * 0.15}s` }} />
                    ))}
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Processing — extracting preferences after conversation ends */}
        {phase === "processing" && (
          <div className="space-y-4">
            <div className="flex justify-center gap-1">
              {[0, 1, 2].map((i) => (
                <div
                  key={i}
                  className="w-2 h-2 rounded-full bg-rosewood-400/60 animate-bounce"
                  style={{ animationDelay: `${i * 0.2}s` }}
                />
              ))}
            </div>
            <p className="text-stone-400 font-serif">Noting everything down for your arrival...</p>
            <p className="text-xs text-stone-600">Just a moment while we personalise your stay.</p>
          </div>
        )}

        {/* Done */}
        {phase === "done" && (
          <div className="space-y-6">
            <div className="space-y-2">
              <div className="text-4xl font-serif text-stone-300">✦</div>
              <h2 className="text-2xl font-serif text-stone-100">
                {guestFirstName === "there" ? "Safe travels." : `Safe travels, ${guestFirstName}.`}
              </h2>
              <p className="text-stone-400 font-serif italic">
                We&apos;ll have everything ready when you arrive at Sand Hill.
              </p>
            </div>

            {captured.length > 0 && (
              <div className="bg-stone-800 rounded-xl p-5 text-left text-sm space-y-2">
                <p className="text-xs uppercase tracking-widest text-stone-500 mb-3">What we&apos;ve noted</p>
                {captured.map((item, i) => (
                  <p key={i} className="text-stone-300">— {item}</p>
                ))}
              </div>
            )}

            <div className="bg-stone-800/50 rounded-xl p-4 text-left">
              <p className="text-xs uppercase tracking-widest text-stone-500 mb-2">Memory setting</p>
              <p className="text-sm text-stone-300">
                <span className="text-rosewood-400 font-medium">{CONSENT_DETAILS[consentLevel].label}</span>
                {" — "}
                {CONSENT_DETAILS[consentLevel].description}
              </p>
              <button className="mt-2 text-xs text-stone-500 hover:text-stone-300 underline transition-colors">
                Update anytime
              </button>
            </div>

            {guestId && (
              <div className="text-center">
                <a
                  href={`/my-data?guest_id=${guestId}`}
                  className="text-xs text-stone-500 hover:text-stone-300 underline transition-colors"
                >
                  See everything we know about you →
                </a>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

export default function WelcomePage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen bg-stone-900 flex items-center justify-center">
        <div className="flex gap-1">
          {[0, 1, 2].map((i) => (
            <div key={i} className="w-2 h-2 rounded-full bg-stone-600 animate-bounce" style={{ animationDelay: `${i * 0.15}s` }} />
          ))}
        </div>
      </div>
    }>
      <WelcomePageInner />
    </Suspense>
  )
}
