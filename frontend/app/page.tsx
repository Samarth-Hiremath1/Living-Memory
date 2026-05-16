import Link from "next/link"

export default function Home() {
  return (
    <main className="min-h-screen flex flex-col items-center justify-center px-8">
      <div className="max-w-xl text-center space-y-8">
        <div className="space-y-2">
          <p className="text-xs font-sans uppercase tracking-widest text-stone-400">Rosewood Hotels · Sand Hill</p>
          <h1 className="text-4xl font-serif text-stone-900">Living Memory</h1>
          <p className="text-stone-500 font-serif italic text-lg">
            An invisible AI nervous system for luxury hotels.
          </p>
        </div>

        <div className="h-px bg-stone-200" />

        <div className="text-left space-y-3">
          <p className="text-xs uppercase tracking-widest text-stone-400 text-center mb-4">Staff Views</p>

          <Link
            href="/manager"
            className="group block rounded-xl border border-stone-200 bg-white p-6 hover:border-rosewood-300 hover:shadow-sm transition-all"
          >
            <div className="flex items-start justify-between">
              <div>
                <p className="text-xs font-sans uppercase tracking-widest text-stone-400 mb-1">General Manager</p>
                <h2 className="font-serif text-xl text-stone-800 group-hover:text-rosewood-600">Morning Arrivals Dashboard</h2>
                <p className="mt-1 text-sm text-stone-500">
                  AI-generated dossiers for every arriving guest — room setup, welcome amenity, PlaceMaker matches, jet lag notes. Used each morning by the GM and front-of-house team.
                </p>
              </div>
            </div>
          </Link>

          <Link
            href="/concierge"
            className="group block rounded-xl border border-stone-200 bg-white p-6 hover:border-rosewood-300 hover:shadow-sm transition-all"
          >
            <div className="flex items-start justify-between">
              <div>
                <p className="text-xs font-sans uppercase tracking-widest text-stone-400 mb-1">Concierge / Front Desk</p>
                <h2 className="font-serif text-xl text-stone-800 group-hover:text-rosewood-600">Concierge Tablet</h2>
                <p className="mt-1 text-sm text-stone-500">
                  Live view of all in-house guests. Staff speak or type observations that are instantly parsed by Claude and added to each guest&apos;s memory graph. AI suggests moments to create.
                </p>
              </div>
            </div>
          </Link>
        </div>

        <div className="h-px bg-stone-200" />

        <div className="text-left space-y-3">
          <p className="text-xs uppercase tracking-widest text-stone-400 text-center mb-4">Guest Experiences</p>

          <Link
            href="/welcome"
            className="group block rounded-xl border border-stone-200 bg-white p-6 hover:border-rosewood-300 hover:shadow-sm transition-all"
          >
            <div className="flex items-start justify-between">
              <div>
                <p className="text-xs font-sans uppercase tracking-widest text-stone-400 mb-1">Before Arrival</p>
                <h2 className="font-serif text-xl text-stone-800 group-hover:text-rosewood-600">Welcome Conversation</h2>
                <p className="mt-1 text-sm text-stone-500">
                  A warm pre-arrival voice call with the Rosewood Ambassador. Anna shares what she&apos;s hoping for — preferences are extracted by Claude and saved to her profile for staff and AI to use.
                </p>
              </div>
            </div>
          </Link>

          <Link
            href="/guest"
            className="group block rounded-xl border border-stone-200 bg-white p-6 hover:border-rosewood-300 hover:shadow-sm transition-all"
          >
            <div className="flex items-start justify-between">
              <div>
                <p className="text-xs font-sans uppercase tracking-widest text-stone-400 mb-1">During Stay</p>
                <h2 className="font-serif text-xl text-stone-800 group-hover:text-rosewood-600">In-Stay Concierge</h2>
                <p className="mt-1 text-sm text-stone-500">
                  A voice assistant powered by the PlaceMaker Engine — not generic tourism, but Rosewood&apos;s actual cultural network. Natalie Cheng, Reylon Agustin, David Park. Real people, real introductions.
                </p>
              </div>
            </div>
          </Link>
        </div>

        <p className="text-xs text-stone-300 font-sans pt-2">
          AI never faces the guest directly as AI. Every insight routes through human staff or warm, named voices.
        </p>
      </div>
    </main>
  )
}
