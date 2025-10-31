export function CLIPreview() {
  return (
    <section className="px-4 sm:px-6 py-16 sm:py-24 bg-gradient-to-b from-transparent via-slate-950/50 to-transparent min-h-screen snap-start snap-always flex items-center">
      <div className="max-w-6xl mx-auto space-y-8 sm:space-y-12 w-full">
        <div className="text-center space-y-3 sm:space-y-4 px-4">
          <div className="inline-flex items-center gap-2 px-3 sm:px-4 py-1.5 sm:py-2 rounded-full bg-signal/10 border border-signal/20 text-signal text-xs sm:text-sm font-medium">
            <span className="w-2 h-2 rounded-full bg-signal animate-pulse" />
            Simple, powerful CLI
          </div>
          <h2 className="text-2xl sm:text-3xl md:text-4xl lg:text-5xl font-bold text-white">
            From install to results in 60 seconds
          </h2>
          <p className="text-base sm:text-lg md:text-xl text-slate-300 max-w-2xl mx-auto">
            Install with one command, run your first test, and see a full report
          </p>
        </div>

        {/* CLI Demo */}
        <div className="relative rounded-xl sm:rounded-2xl border border-slate-800 bg-slate-950/90 p-4 sm:p-6 shadow-2xl shadow-black/60 backdrop-blur overflow-hidden">
          {/* Terminal Header */}
          <div className="flex items-center gap-2 mb-4 pb-3 border-b border-slate-800">
            <div className="flex gap-2">
              <div className="w-3 h-3 rounded-full bg-red-500/80" />
              <div className="w-3 h-3 rounded-full bg-yellow-500/80" />
              <div className="w-3 h-3 rounded-full bg-green-500/80" />
            </div>
            <div className="text-slate-500 text-sm font-mono ml-4">
              terminal
            </div>
          </div>

          {/* Terminal Content */}
          <div className="font-mono text-xs sm:text-sm space-y-2 sm:space-y-3 overflow-x-auto">
            <div className="flex items-start gap-2">
              <span className="text-signal flex-shrink-0">$</span>
              <span className="text-slate-300">pip install alignmenter</span>
            </div>

            <div className="flex items-start gap-2">
              <span className="text-signal flex-shrink-0">$</span>
              <span className="text-slate-300 break-all">
                alignmenter run --model openai:gpt-4o-mini --dataset datasets/demo.jsonl
              </span>
            </div>

            <div className="text-slate-500 pl-3 sm:pl-4 space-y-1">
              <div className="flex items-center gap-2">
                <svg className="w-3 h-3 sm:w-4 sm:h-4 text-signal animate-spin flex-shrink-0" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                </svg>
                <span className="text-xs sm:text-sm">Loading dataset: 60 turns across 10 sessions</span>
              </div>
              <div className="text-signal text-xs sm:text-sm">✓ Brand voice score: 0.83 (range: 0.79-0.87)</div>
              <div className="text-signal text-xs sm:text-sm">✓ Safety score: 0.95</div>
              <div className="text-signal text-xs sm:text-sm">✓ Consistency score: 0.88</div>
              <div className="text-slate-400 text-xs sm:text-sm break-all">
                Report written to: <span className="text-blue-400">reports/2025-10-31_14-23/index.html</span>
              </div>
            </div>

            <div className="flex items-start gap-2 pt-1 sm:pt-2">
              <span className="text-signal flex-shrink-0">$</span>
              <span className="text-slate-300">
                alignmenter report --last
              </span>
            </div>

            <div className="text-slate-500 pl-3 sm:pl-4 text-xs sm:text-sm">
              <span className="text-emerald-400">✓</span> Opening report in browser...
            </div>
          </div>

          {/* Decorative gradient */}
          <div className="absolute top-0 right-0 w-96 h-96 bg-signal/5 rounded-full blur-3xl -z-10" />
        </div>

        {/* Feature callouts */}
        <div className="grid grid-cols-3 gap-4 sm:gap-6 pt-6 sm:pt-8 px-4">
          <div className="text-center space-y-1 sm:space-y-2">
            <div className="text-xl sm:text-2xl md:text-3xl font-bold text-white">
              &lt; 5 min
            </div>
            <div className="text-xs sm:text-sm text-slate-400">
              Test runtime on your laptop
            </div>
          </div>

          <div className="text-center space-y-1 sm:space-y-2">
            <div className="text-xl sm:text-2xl md:text-3xl font-bold text-white">
              3 providers
            </div>
            <div className="text-xs sm:text-sm text-slate-400">
              OpenAI, Anthropic, local
            </div>
          </div>

          <div className="text-center space-y-1 sm:space-y-2">
            <div className="text-xl sm:text-2xl md:text-3xl font-bold text-white">
              100% local
            </div>
            <div className="text-xs sm:text-sm text-slate-400">
              No data upload required
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
