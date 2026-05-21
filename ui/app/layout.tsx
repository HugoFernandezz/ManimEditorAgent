import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Manim Editor Agent",
  description: "Multi-agent pipeline para crear videos Manim",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="es" className="dark">
      <body className={`${inter.className} bg-zinc-950 text-zinc-100 min-h-screen`}>
        <header className="border-b border-zinc-800 px-6 py-4">
          <div className="max-w-6xl mx-auto flex items-center gap-3">
            <span className="text-2xl">🎬</span>
            <h1 className="text-lg font-semibold tracking-tight">Manim Editor Agent</h1>
          </div>
        </header>
        <main className="max-w-6xl mx-auto px-6 py-8">{children}</main>
      </body>
    </html>
  );
}
