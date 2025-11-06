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
              <span className="text-slate-300">alignmenter init</span>
            </div>

            <div className="pl-5 text-slate-500 text-[11px] sm:text-xs">
              # optional: `alignmenter import gpt --instructions brand.txt --out alignmenter/configs/persona/brand.yaml`
            </div>

            <div className="flex items-start gap-2">
              <span className="text-signal flex-shrink-0">$</span>
              <span className="text-slate-300 break-all">
                alignmenter run --model openai-gpt:brand-voice --config configs/brand.yaml
              </span>
            </div>

            <div className="pl-3 sm:pl-4 space-y-1 text-xs sm:text-sm">
              <div className="text-slate-400">Loading dataset: 60 turns across 10 sessions</div>
              <div className="text-emerald-300">✓ Brand voice score: 0.83 (range: 0.79-0.87)</div>
              <div className="text-emerald-300">✓ Safety score: 0.95</div>
              <div className="text-emerald-300">✓ Consistency score: 0.88</div>
              <div className="text-slate-400 break-all">
                Report written to: <span className="text-blue-400">reports/2025-10-31_14-23/index.html</span>
              </div>
            </div>

            <div className="flex items-start gap-2 pt-1 sm:pt-2">
              <span className="text-signal flex-shrink-0">$</span>
              <span className="text-slate-300">
                alignmenter report --last
              </span>
            </div>

            <div className="pl-3 sm:pl-4 text-xs sm:text-sm text-slate-400">Opening report in browser...</div>

            <div className="pl-5 text-slate-500 text-[11px] sm:text-xs pt-3">
              # optionally add qualitative analysis with LLM judges
            </div>

            <div className="flex items-start gap-2">
              <span className="text-signal flex-shrink-0">$</span>
              <span className="text-slate-300 break-all">
                alignmenter calibrate validate --judge openai:gpt-4o --judge-sample 0.2
              </span>
            </div>

            <div className="pl-3 sm:pl-4 space-y-1 text-xs sm:text-sm">
              <div className="text-slate-400">Analyzing 12 sessions with LLM judge...</div>
              <div className="text-emerald-300">✓ Agreement rate: 87.5%</div>
              <div className="text-slate-400">Total cost: $0.032</div>
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
              Custom GPT ready
            </div>
            <div className="text-xs sm:text-sm text-slate-400">
              OpenAI, Anthropic, local, GPT Builder
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
