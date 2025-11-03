import Link from "next/link";
import { Callout } from "./callout";

export function Hero() {
  return (
    <section className="relative min-h-screen flex flex-col items-center justify-center px-4 sm:px-6 py-16 sm:py-24 snap-start snap-always">
      {/* Background decoration */}
      <div className="absolute inset-0 -z-10 overflow-hidden">
        <div className="absolute top-1/4 left-1/4 h-64 w-64 sm:h-96 sm:w-96 rounded-full bg-signal/10 blur-3xl animate-pulse" />
        <div className="absolute bottom-1/3 right-1/4 h-64 w-64 sm:h-96 sm:w-96 rounded-full bg-blue-500/10 blur-3xl animate-pulse" style={{ animationDelay: '1s' }} />
      </div>

      <div className="max-w-5xl w-full space-y-6 sm:space-y-8 text-center">
        <Callout />

        <h1 className="text-4xl sm:text-5xl md:text-6xl lg:text-7xl font-bold tracking-tight text-white leading-tight px-4">
          <span className="bg-gradient-to-r from-signal via-emerald-400 to-signal bg-clip-text text-transparent animate-gradient">
            Alignmenter
          </span>
          <br />
          tests your AI&rsquo;s voice and safety
        </h1>

        <p className="mx-auto max-w-2xl text-lg sm:text-xl text-slate-300 leading-relaxed px-4">
          Check if your AI sounds like your brand, stays safe, and behaves consistently.
          Bring your Custom GPT voice, hosted APIs, and local models. Get detailed reports in minutes, not days.
        </p>

        <div className="flex flex-col sm:flex-row items-center justify-center gap-3 sm:gap-4 pt-4 px-4">
          <Link
            href="https://github.com/justinGrosvenor/alignmenter"
            className="w-full sm:w-auto group relative rounded-full bg-signal px-6 sm:px-8 py-3 sm:py-4 font-semibold text-black shadow-lg shadow-signal/40 transition-all hover:shadow-signal/60 hover:scale-105 text-center"
          >
            <span className="relative z-10">Get started</span>
            <div className="absolute inset-0 rounded-full bg-gradient-to-r from-signal to-emerald-400 opacity-0 group-hover:opacity-100 transition-opacity" />
          </Link>

          <Link
            href="https://github.com/justinGrosvenor/alignmenter"
            className="w-full sm:w-auto rounded-full border-2 border-slate-700 px-6 sm:px-8 py-3 sm:py-4 font-semibold text-slate-200 transition-all hover:border-signal/70 hover:text-white hover:bg-signal/5 text-center"
          >
            View documentation
          </Link>
        </div>

        {/* Trust indicators */}
        <div className="pt-8 sm:pt-12 flex flex-wrap items-center justify-center gap-4 sm:gap-8 text-xs sm:text-sm text-slate-400 px-4">
          <div className="flex items-center gap-2">
            <svg className="w-5 h-5 text-signal" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
            </svg>
            <span>Open source</span>
          </div>
          <div className="flex items-center gap-2">
            <svg className="w-5 h-5 text-signal" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
            </svg>
            <span>Apache 2.0 licensed</span>
          </div>
          <div className="flex items-center gap-2">
            <svg className="w-5 h-5 text-signal" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
            </svg>
            <span>Privacy-first</span>
          </div>
        </div>

        {/* Scroll indicator */}
        <div className="absolute bottom-4 sm:bottom-8 left-1/2 -translate-x-1/2 flex flex-col items-center gap-2 animate-bounce">
          <span className="text-slate-500 text-xs sm:text-sm">Scroll to explore</span>
          <svg className="w-5 h-5 sm:w-6 sm:h-6 text-signal" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 14l-7 7m0 0l-7-7m7 7V3" />
          </svg>
        </div>
      </div>
    </section>
  );
}
