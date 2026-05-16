import Link from "next/link"

export default function Home() {
  return (
    <main className="min-h-screen flex flex-col items-center justify-center px-8">
      <div className="max-w-lg text-center space-y-8">
        <div className="space-y-2">
          <p className="text-xs font-sans uppercase tracking-widest text-stone-400">Rosewood Hotels</p>
          <h1 className="text-4xl font-serif text-stone-900">Living Memory</h1>
          <p className="text-stone-500 font-serif italic text-lg">
            An invisible AI nervous system for luxury hotels.
          </p>
        </div>

        <div className="h-px bg-stone-200" />

        <div className="grid gap-4">
          <Link
            href="/manager"
            className="group block rounded-lg border border-stone-200 bg-white p-6 text-left hover:border-rosewood-300 hover:shadow-sm transition-all"
          >
            <p className="text-xs font-sans uppercase tracking-widest text-stone-400 mb-1">Staff View</p>
            <h2 className="font-serif text-xl text-stone-800 group-hover:text-rosewood-600">Manager Dashboard</h2>
            <p className="mt-1 text-sm text-stone-500">Today's arrivals, dossiers, and morning briefings.</p>
          </Link>

          <Link
            href="/concierge"
            className="group block rounded-lg border border-stone-200 bg-white p-6 text-left hover:border-rosewood-300 hover:shadow-sm transition-all"
          >
            <p className="text-xs font-sans uppercase tracking-widest text-stone-400 mb-1">Staff View</p>
            <h2 className="font-serif text-xl text-stone-800 group-hover:text-rosewood-600">Concierge Tablet</h2>
            <p className="mt-1 text-sm text-stone-500">Live in-house guests, observations, and voice capture.</p>
          </Link>

          <Link
            href="/welcome"
            className="group block rounded-lg border border-stone-200 bg-white p-6 text-left hover:border-rosewood-300 hover:shadow-sm transition-all"
          >
            <p className="text-xs font-sans uppercase tracking-widest text-stone-400 mb-1">Guest Experience</p>
            <h2 className="font-serif text-xl text-stone-800 group-hover:text-rosewood-600">Welcome Conversation</h2>
            <p className="mt-1 text-sm text-stone-500">Anna's pre-arrival voice conversation with the Rosewood Ambassador.</p>
          </Link>
        </div>

        <p className="text-xs text-stone-300 font-sans">
          AI never faces the guest directly. Every output routes through human staff.
        </p>
      </div>
    </main>
  )
}
