import Link from "next/link";

export function Hero() {
  return (
    <section className="relative min-h-screen flex items-center px-4 sm:px-6 py-8 sm:py-12 snap-start snap-always">
      <div className="max-w-6xl mx-auto w-full">
        {/* Header */}
        <div className="text-center space-y-4 mb-8">
          <h1 className="text-4xl sm:text-5xl md:text-6xl font-bold text-white leading-tight">
            <span className="text-signal">Alignmenter</span>
          </h1>
          <p className="text-lg sm:text-xl text-slate-300 max-w-3xl mx-auto">
            Automated testing for AI chatbots. Measure brand voice, safety, and consistency across model versions.
          </p>
          <p className="text-base sm:text-lg text-slate-400 max-w-2xl mx-auto">
            Test GPT-4, Claude, or local models with the same dataset. Track scores over time. Get detailed reports and optional LLM judge analysis.
          </p>
        </div>

        {/* Terminal Demo */}
        <div className="relative max-w-4xl mx-auto mb-8">
          <div className="relative rounded-lg border border-slate-800 bg-slate-950/90 p-4 shadow-2xl shadow-black/60 backdrop-blur font-mono text-sm">
            {/* Terminal Header */}
            <div className="flex items-center gap-2 mb-3 pb-2 border-b border-slate-800">
              <div className="flex gap-1.5">
                <div className="w-2.5 h-2.5 rounded-full bg-red-500/80" />
                <div className="w-2.5 h-2.5 rounded-full bg-yellow-500/80" />
                <div className="w-2.5 h-2.5 rounded-full bg-green-500/80" />
              </div>
              <div className="text-slate-500 text-xs ml-2">~/my-chatbot</div>
            </div>

            {/* Terminal Content */}
            <div className="space-y-2.5 text-xs sm:text-sm">
              {/* Install */}
              <div>
                <div className="flex gap-2">
                  <span className="text-signal select-none">$</span>
                  <span className="text-slate-300">pip install alignmenter</span>
                </div>
                <div className="pl-4 text-slate-500 text-xs mt-0.5">Successfully installed alignmenter-0.3.0</div>
              </div>

              {/* Run */}
              <div className="pt-1">
                <div className="flex gap-2">
                  <span className="text-signal select-none">$</span>
                  <span className="text-slate-300">alignmenter run --model openai-gpt:brand-voice --config configs/brand.yaml</span>
                </div>
                <div className="pl-4 space-y-0.5 mt-1.5 text-xs">
                  <div className="text-slate-400">Loading test dataset: 60 conversation turns</div>
                  <div className="text-slate-400">Running model: openai-gpt:brand-voice</div>
                  <div className="text-slate-400 mt-1">Computing metrics...</div>
                  <div className="text-emerald-400">✓ Brand Authenticity: 0.83 (strong match to reference voice)</div>
                  <div className="text-emerald-400">✓ Safety: 0.95 (2 keyword flags, 0 critical)</div>
                  <div className="text-emerald-400">✓ Stability: 0.88 (consistent tone across sessions)</div>
                  <div className="text-slate-400 mt-1">
                    Report saved: <span className="text-blue-400 underline">reports/2025-11-06_14-32/index.html</span>
                  </div>
                </div>
              </div>

              {/* Cursor */}
              <div className="flex gap-2 pt-1">
                <span className="text-signal select-none">$</span>
                <span className="text-slate-300 animate-pulse">_</span>
              </div>
            </div>

            {/* Subtle accent */}
            <div className="absolute -inset-px bg-gradient-to-r from-signal/10 to-blue-500/10 rounded-lg blur-xl -z-10 opacity-50" />
          </div>
        </div>

        {/* Quick stats */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 max-w-3xl mx-auto mb-6">
          <div className="text-center">
            <div className="text-2xl font-bold text-white">3 metrics</div>
            <div className="text-xs text-slate-400 mt-0.5">Brand, safety, stability</div>
          </div>
          <div className="text-center">
            <div className="text-2xl font-bold text-white">~10 sec</div>
            <div className="text-xs text-slate-400 mt-0.5">Demo runtime</div>
          </div>
          <div className="text-center">
            <div className="text-2xl font-bold text-white">Local-first</div>
            <div className="text-xs text-slate-400 mt-0.5">Optional cloud judges</div>
          </div>
          <div className="text-center">
            <div className="text-2xl font-bold text-white">Any model</div>
            <div className="text-xs text-slate-400 mt-0.5">OpenAI, Anthropic, local</div>
          </div>
        </div>

        {/* CTAs */}
        <div className="flex flex-col sm:flex-row gap-3 justify-center items-center">
          <Link
            href="https://docs.alignmenter.com"
            className="inline-flex items-center justify-center px-6 py-3 text-base font-medium text-black bg-signal hover:bg-signal/90 transition-colors"
          >
            Read the Docs →
          </Link>
          <Link
            href="https://github.com/justinGrosvenor/alignmenter"
            className="inline-flex items-center justify-center px-6 py-3 text-base font-medium text-slate-300 border border-slate-700 hover:border-slate-600 hover:bg-slate-900/50 transition-colors"
          >
            View on GitHub →
          </Link>
        </div>
        <div className="flex items-center justify-center gap-3 text-sm text-slate-400 mt-4">
          <span>Open source</span>
          <span>•</span>
          <span>Apache 2.0</span>
        </div>
      </div>
    </section>
  );
}
