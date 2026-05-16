import type { Metadata } from "next"
import "./globals.css"

export const metadata: Metadata = {
  title: "Living Memory — Rosewood",
  description: "An invisible AI nervous system for luxury hotels.",
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="bg-stone-50 text-stone-800 antialiased">{children}</body>
    </html>
  )
}
