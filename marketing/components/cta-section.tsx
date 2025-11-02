import Link from "next/link";

export function CTASection() {
  return (
    <section className="px-4 sm:px-6 py-16 sm:py-24 flex items-center flex-1">
      <div className="max-w-4xl mx-auto w-full">
        <div className="relative rounded-2xl sm:rounded-3xl border border-signal/20 bg-gradient-to-br from-signal/10 via-slate-950/90 to-slate-950/90 p-8 sm:p-12 md:p-16 shadow-2xl shadow-signal/10 backdrop-blur overflow-hidden">
          {/* Background decoration */}
          <div className="absolute inset-0 -z-10">
            <div className="absolute top-0 right-0 w-96 h-96 bg-signal/20 rounded-full blur-3xl" />
            <div className="absolute bottom-0 left-0 w-96 h-96 bg-emerald-400/20 rounded-full blur-3xl" />
          </div>

          <div className="relative text-center space-y-6 sm:space-y-8">
            <h2 className="text-2xl sm:text-3xl md:text-4xl lg:text-5xl font-bold text-white leading-tight px-4">
              Ready to test your AI?
            </h2>

            <p className="text-base sm:text-lg md:text-xl text-slate-300 max-w-2xl mx-auto px-4">
              Join developers building better AI testing tools.
              Install the free CLI and run your first test in minutes.
            </p>

            <div className="flex flex-col sm:flex-row items-center justify-center gap-3 sm:gap-4 pt-4 px-4">
              <Link
                href="https://github.com/justinGrosvenor/alignmenter"
                className="w-full sm:w-auto group relative rounded-full bg-signal px-6 sm:px-8 py-3 sm:py-4 font-semibold text-black shadow-lg shadow-signal/40 transition-all hover:shadow-signal/60 hover:scale-105"
              >
                <span className="relative z-10 flex items-center justify-center gap-2">
                  Get started
                  <svg className="w-4 h-4 sm:w-5 sm:h-5 group-hover:translate-x-1 transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7l5 5m0 0l-5 5m5-5H6" />
                  </svg>
                </span>
              </Link>

              <Link
                href="https://github.com/justinGrosvenor/alignmenter"
                className="w-full sm:w-auto rounded-full border-2 border-signal/50 px-6 sm:px-8 py-3 sm:py-4 font-semibold text-white transition-all hover:border-signal hover:bg-signal/10 text-center"
              >
                View on GitHub
              </Link>
            </div>

            {/* Stats */}
            <div className="grid grid-cols-3 gap-4 sm:gap-6 md:gap-8 pt-8 sm:pt-12 border-t border-slate-800/50">
              <div className="space-y-1">
                <div className="text-lg sm:text-xl md:text-2xl lg:text-3xl font-bold text-signal">
                  Apache 2.0
                </div>
                <div className="text-xs sm:text-sm text-slate-400">
                  Open source license
                </div>
              </div>

              <div className="space-y-1">
                <div className="text-lg sm:text-xl md:text-2xl lg:text-3xl font-bold text-signal">
                  3 metrics
                </div>
                <div className="text-xs sm:text-sm text-slate-400">
                  Voice, safety, consistency
                </div>
              </div>

              <div className="space-y-1">
                <div className="text-lg sm:text-xl md:text-2xl lg:text-3xl font-bold text-signal">
                  Custom GPTs
                </div>
                <div className="text-xs sm:text-sm text-slate-400">
                  Plug in your GPT Builder voice
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
