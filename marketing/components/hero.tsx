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
            Application alignment evaluations. Check the commitments your assistant makes, with evidence behind every release decision.
          </p>
          <p className="text-base sm:text-lg text-slate-400 max-w-2xl mx-auto">
            Capture answers, compare changes, review failures, and keep regressions in CI. Python SDK, CLI, and offline reports.
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
                <div className="pl-4 text-slate-500 text-xs mt-0.5">Lightweight Python core · optional model dependencies</div>
              </div>

              {/* Run */}
              <div className="pt-1">
                <div className="flex gap-2">
                  <span className="text-signal select-none">$</span>
                  <span className="text-slate-300">alignmenter init-suite --out evals/resource-task</span>
                </div>
                <div className="pl-4 text-[10px] sm:text-xs text-slate-500 mt-1">Then: alignmenter run-suite evals/resource-task/suite.yaml</div>
                <div className="pl-4 space-y-0.5 mt-1.5 text-xs">
                  <div className="text-slate-400">Offline example: 2 resource-constraint cases</div>
                  <div className="text-slate-400">Target: local Python function · Judge calls: 0</div>
                  <div className="text-slate-400 mt-1">Example checks:</div>
                  <div className="text-emerald-400">✓ Uses available resources</div>
                  <div className="text-emerald-400">✓ Every required case evaluated</div>
                  <div className="text-emerald-400">✓ HTML, JSON, Markdown, and JUnit artifacts</div>
                  <div className="text-slate-400 mt-1">
                    Inspect saved evidence: <span className="text-blue-400 underline">review/index.html</span>
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
            <div className="text-2xl font-bold text-white">Your criteria</div>
            <div className="text-xs text-slate-400 mt-0.5">Application commitments</div>
          </div>
          <div className="text-center">
            <div className="text-2xl font-bold text-white">CI gates</div>
            <div className="text-xs text-slate-400 mt-0.5">Pass, fail, inconclusive</div>
          </div>
          <div className="text-center">
            <div className="text-2xl font-bold text-white">Local-first</div>
            <div className="text-xs text-slate-400 mt-0.5">Optional cloud judges</div>
          </div>
          <div className="text-center">
            <div className="text-2xl font-bold text-white">SDK + CLI</div>
            <div className="text-xs text-slate-400 mt-0.5">Application-owned adapters</div>
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
