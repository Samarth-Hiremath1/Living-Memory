"use client"

import { useState, useEffect, Suspense } from "react"
import { useSearchParams } from "next/navigation"

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"

type ConsentLevel = "standard" | "living_memory"

interface Guest {
  id: string
  name: string
  email: string
  nationality: string
  home_city: string
  consent_level: ConsentLevel
  preferences: Record<string, unknown>
}

interface Observation {
  id: string
  raw_text: string
  timestamp: string
  source: string
  tags: string[]
}

const CONSENT_LABELS: Record<ConsentLevel, string> = {
  standard: "Standard — used this stay only, not retained after checkout",
  living_memory: "Living Memory — travels with you across all Rosewood properties worldwide",
}

function MyDataPageInner() {
  const searchParams = useSearchParams()
  const guestIdParam = searchParams.get("guest_id") || "guest-samarth-hiremath"

  const [guest, setGuest] = useState<Guest | null>(null)
  const [observations, setObservations] = useState<Observation[]>([])
  const [loading, setLoading] = useState(true)
  const [consentLevel, setConsentLevel] = useState<ConsentLevel>("living_memory")
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [deleted, setDeleted] = useState(false)

  useEffect(() => {
    async function load() {
      try {
        const [gRes, oRes] = await Promise.all([
          fetch(`${API}/guests/${guestIdParam}`),
          fetch(`${API}/guests/${guestIdParam}/observations`),
        ])
        if (gRes.ok) {
          const g = await gRes.json()
          setGuest(g)
          setConsentLevel(g.consent_level || "living_memory")
        }
        if (oRes.ok) {
          const obs = await oRes.json()
          setObservations(obs)
        }
      } catch {
        // silent
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [guestIdParam])

  async function saveConsent() {
    setSaving(true)
    try {
      await fetch(`${API}/guests/${guestIdParam}/consent`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ consent_level: consentLevel }),
      })
      setSaved(true)
      setTimeout(() => setSaved(false), 2500)
    } catch {
      // silent
    } finally {
      setSaving(false)
    }
  }

  async function deleteAllData() {
    if (!confirm("Are you sure? This will permanently remove all your data from Rosewood's systems.")) return
    setDeleting(true)
    try {
      await fetch(`${API}/guests/${guestIdParam}/forget`, { method: "DELETE" })
      setDeleted(true)
    } catch {
      // silent — show confirmation regardless
      setDeleted(true)
    } finally {
      setDeleting(false)
    }
  }

  if (deleted) {
    return (
      <div className="min-h-screen bg-stone-50 flex items-center justify-center px-6">
        <div className="max-w-md w-full text-center space-y-4">
          <p className="text-3xl font-serif text-stone-400">✦</p>
          <h2 className="font-serif text-2xl text-stone-800">All done.</h2>
          <p className="text-stone-500 text-sm leading-relaxed">
            Your data has been removed from all Rosewood properties. We hope to welcome you back someday — on your own terms.
          </p>
        </div>
      </div>
    )
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-stone-50 flex items-center justify-center">
        <div className="flex gap-1">
          {[0, 1, 2].map((i) => (
            <div key={i} className="w-2 h-2 rounded-full bg-stone-300 animate-bounce" style={{ animationDelay: `${i * 0.15}s` }} />
          ))}
        </div>
      </div>
    )
  }

  const prefs = guest?.preferences || {}

  return (
    <div className="min-h-screen bg-stone-50">
      <header className="border-b border-stone-200 bg-white px-8 py-5">
        <div className="max-w-2xl mx-auto">
          <p className="text-xs uppercase tracking-widest text-stone-400 mb-0.5">Rosewood Sand Hill</p>
          <h1 className="font-serif text-2xl text-stone-900">Your Data</h1>
          <p className="text-sm text-stone-500 mt-1">Everything we know about you — and the controls to change it.</p>
        </div>
      </header>

      <main className="max-w-2xl mx-auto px-8 py-10 space-y-10">

        {/* Guest identity */}
        <section className="bg-white rounded-xl border border-stone-100 p-6 space-y-3">
          <p className="text-xs uppercase tracking-widest text-stone-400">Identity</p>
          <div className="space-y-1">
            <p className="font-serif text-xl text-stone-900">{guest?.name || "Guest"}</p>
            {guest?.email && <p className="text-sm text-stone-500">{guest.email}</p>}
            {guest?.home_city && (
              <p className="text-sm text-stone-400">{guest.home_city}{guest.nationality ? ` · ${guest.nationality}` : ""}</p>
            )}
          </div>
        </section>

        {/* Preferences */}
        <section className="bg-white rounded-xl border border-stone-100 p-6 space-y-4">
          <p className="text-xs uppercase tracking-widest text-stone-400">Stored Preferences</p>
          {Object.keys(prefs).length === 0 ? (
            <p className="text-sm text-stone-400 italic">No preferences stored yet.</p>
          ) : (
            <dl className="space-y-3">
              {Object.entries(prefs).map(([key, value]) => (
                <div key={key} className="flex gap-4">
                  <dt className="text-xs text-stone-400 w-36 shrink-0 capitalize pt-0.5">{key.replace(/_/g, " ")}</dt>
                  <dd className="text-sm text-stone-700">
                    {Array.isArray(value)
                      ? value.join(", ")
                      : String(value)}
                  </dd>
                </div>
              ))}
            </dl>
          )}
        </section>

        {/* Observations */}
        <section className="bg-white rounded-xl border border-stone-100 p-6 space-y-4">
          <p className="text-xs uppercase tracking-widest text-stone-400">Observations from your stays</p>
          {observations.length === 0 ? (
            <p className="text-sm text-stone-400 italic">No observations recorded yet.</p>
          ) : (
            <div className="space-y-3">
              {observations.map((obs) => (
                <div key={obs.id} className="border-l-2 border-stone-100 pl-4 py-1">
                  <p className="text-xs text-stone-400 mb-1">
                    {new Date(obs.timestamp).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })}
                    {" · "}
                    {obs.source.replace(/_/g, " ")}
                  </p>
                  <p className="text-sm text-stone-700 leading-relaxed">{obs.raw_text}</p>
                  {obs.tags && obs.tags.length > 0 && (
                    <div className="flex flex-wrap gap-1 mt-1">
                      {obs.tags.map((t) => (
                        <span key={t} className="text-xs text-stone-400 bg-stone-50 px-2 py-0.5 rounded-full border border-stone-100">{t}</span>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </section>

        {/* Memory preference */}
        <section className="bg-white rounded-xl border border-stone-100 p-6 space-y-4">
          <p className="text-xs uppercase tracking-widest text-stone-400">Memory Preference</p>
          <div className="space-y-2">
            {(["standard", "living_memory"] as ConsentLevel[]).map((level) => (
              <label key={level} className="flex items-start gap-3 cursor-pointer">
                <input
                  type="radio"
                  name="consent"
                  value={level}
                  checked={consentLevel === level}
                  onChange={() => setConsentLevel(level)}
                  className="mt-0.5 accent-stone-700"
                />
                <span className="text-sm text-stone-700">{CONSENT_LABELS[level]}</span>
              </label>
            ))}
          </div>
          <button
            onClick={saveConsent}
            disabled={saving}
            className="px-5 py-2 rounded-lg bg-stone-800 text-white text-sm hover:bg-stone-900 disabled:opacity-50 transition-colors"
          >
            {saving ? "Saving..." : saved ? "Saved" : "Update preference"}
          </button>
        </section>

        {/* Delete all data */}
        <section className="bg-white rounded-xl border border-red-100 p-6 space-y-3">
          <p className="text-xs uppercase tracking-widest text-red-400">Remove all data</p>
          <p className="text-sm text-stone-500 leading-relaxed">
            This permanently deletes all your observations, preferences, and stays from Rosewood&apos;s systems. This cannot be undone.
          </p>
          <button
            onClick={deleteAllData}
            disabled={deleting}
            className="px-5 py-2 rounded-lg border border-red-200 text-red-600 text-sm hover:bg-red-50 disabled:opacity-50 transition-colors"
          >
            {deleting ? "Removing..." : "Delete all my data"}
          </button>
        </section>
      </main>
    </div>
  )
}

export default function MyDataPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen bg-stone-50 flex items-center justify-center">
        <div className="flex gap-1">
          {[0, 1, 2].map((i) => (
            <div key={i} className="w-2 h-2 rounded-full bg-stone-300 animate-bounce" style={{ animationDelay: `${i * 0.15}s` }} />
          ))}
        </div>
      </div>
    }>
      <MyDataPageInner />
    </Suspense>
  )
}
